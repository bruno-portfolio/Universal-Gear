"""Agro action — commercialisation window alerts and conditional price-fix recommendations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from universal_gear.core.contracts import (
    Condition,
    CostOfError,
    DecisionDriver,
    DecisionObject,
    DecisionResult,
    DecisionType,
    RiskLevel,
    Scenario,
    SimulationResult,
)
from universal_gear.core.interfaces import BaseDecider
from universal_gear.core.registry import register_action
from universal_gear.plugins.agro.config import AgroConfig

MARGIN_ALERT_THRESHOLD_PCT = 5.0
EXPIRY_DAYS = 14
MIN_PROBABILITY = 0.3
RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@register_action("agro")
class AgroActionEmitter(BaseDecider[AgroConfig]):
    """Emits commercialisation alerts based on agro scenario analysis."""

    async def decide(self, simulation: SimulationResult) -> DecisionResult:
        decisions: list[DecisionObject] = []

        upside_scenarios = self._filter_upside(simulation)
        downside_scenarios = self._filter_downside(simulation)

        for scenario in upside_scenarios:
            decisions.append(self._build_opportunity_alert(scenario, simulation.baseline))

        for scenario in downside_scenarios:
            decisions.append(self._build_risk_alert(scenario, simulation.baseline))

        if not decisions:
            decisions.append(self._build_hold_recommendation(simulation))

        decisions = self._rank_decisions(decisions)
        return DecisionResult(decisions=decisions)

    def _filter_upside(self, simulation: SimulationResult) -> list[Scenario]:
        baseline_price = self._baseline_price(simulation.baseline)
        return [
            s
            for s in simulation.scenarios
            if (
                s.name != "baseline (status quo)"
                and s.probability >= MIN_PROBABILITY
                and self._scenario_price(s)
                > baseline_price * (1 + MARGIN_ALERT_THRESHOLD_PCT / 100)
            )
        ]

    def _filter_downside(self, simulation: SimulationResult) -> list[Scenario]:
        baseline_price = self._baseline_price(simulation.baseline)
        return [
            s
            for s in simulation.scenarios
            if (
                s.name != "baseline (status quo)"
                and s.probability >= MIN_PROBABILITY
                and RISK_RANK.get(s.risk_level, 0) >= RISK_RANK[RiskLevel.MEDIUM]
                and self._scenario_price(s)
                < baseline_price * (1 - MARGIN_ALERT_THRESHOLD_PCT / 100)
            )
        ]

    def _build_opportunity_alert(
        self, scenario: Scenario, baseline: Scenario | None
    ) -> DecisionObject:
        price = self._scenario_price(scenario)
        base = self._baseline_price(baseline)
        spread = (price - base) / base * 100 if base else 0.0

        return DecisionObject(
            decision_type=DecisionType.RECOMMENDATION,
            title=f"Commercialisation opportunity: {scenario.name}",
            recommendation=(
                f"Scenario projects price at {price:.2f} BRL "
                f"({spread:+.1f}% vs baseline). "
                f"Consider forward selling or price fixation for {self.config.commodity}."
            ),
            conditions=[
                Condition(
                    description=f"Spread vs baseline > {MARGIN_ALERT_THRESHOLD_PCT}%",
                    metric="spread_vs_baseline_pct",
                    operator="gt",
                    threshold=MARGIN_ALERT_THRESHOLD_PCT,
                    window=f"{EXPIRY_DAYS} days",
                ),
            ],
            drivers=self._build_drivers(scenario),
            confidence=scenario.probability,
            risk_level=scenario.risk_level,
            cost_of_error=CostOfError(
                false_positive="Premature price fixation locks in suboptimal price",
                false_negative=f"Missed {spread:.1f}% upside opportunity",
                estimated_magnitude=f"{abs(spread):.1f}% of contract value",
            ),
            expires_at=datetime.now(UTC) + timedelta(days=EXPIRY_DAYS),
            source_scenarios=[scenario.scenario_id],
        )

    def _build_risk_alert(self, scenario: Scenario, baseline: Scenario | None) -> DecisionObject:
        price = self._scenario_price(scenario)
        base = self._baseline_price(baseline)
        spread = (price - base) / base * 100 if base else 0.0

        return DecisionObject(
            decision_type=DecisionType.ALERT,
            title=f"Downside risk: {scenario.name}",
            recommendation=(
                f"Scenario projects price drop to {price:.2f} BRL "
                f"({spread:+.1f}% vs baseline). "
                f"Consider hedging exposure to {self.config.commodity}."
            ),
            conditions=[
                Condition(
                    description=f"Price drop > {MARGIN_ALERT_THRESHOLD_PCT}%",
                    metric="spread_vs_baseline_pct",
                    operator="lt",
                    threshold=-MARGIN_ALERT_THRESHOLD_PCT,
                    window=f"{EXPIRY_DAYS} days",
                ),
            ],
            drivers=self._build_drivers(scenario),
            confidence=scenario.probability,
            risk_level=scenario.risk_level,
            cost_of_error=CostOfError(
                false_positive="Unnecessary hedging cost",
                false_negative=f"Unhedged loss of ~{abs(spread):.1f}%",
                estimated_magnitude=f"{abs(spread):.1f}% of exposure",
            ),
            expires_at=datetime.now(UTC) + timedelta(days=EXPIRY_DAYS),
            source_scenarios=[scenario.scenario_id],
        )

    def _build_hold_recommendation(self, simulation: SimulationResult) -> DecisionObject:
        return DecisionObject(
            decision_type=DecisionType.REPORT,
            title=f"No actionable signal for {self.config.commodity}",
            recommendation=(
                "Current scenarios do not exceed alert thresholds. "
                "Continue monitoring. No immediate action required."
            ),
            drivers=[
                DecisionDriver(
                    name="threshold_filter",
                    weight=1.0,
                    description=f"margin threshold {MARGIN_ALERT_THRESHOLD_PCT}% not breached",
                ),
            ],
            confidence=0.8,
            risk_level=RiskLevel.LOW,
            cost_of_error=CostOfError(
                false_positive="Report generated unnecessarily",
                false_negative="Missed subtle market signal",
            ),
            source_scenarios=[s.scenario_id for s in simulation.scenarios],
        )

    def _rank_decisions(self, decisions: list[DecisionObject]) -> list[DecisionObject]:
        """Assign priority scores and return sorted by priority desc."""
        ranked = [d.model_copy(update={"priority": self._compute_priority(d)}) for d in decisions]
        return sorted(ranked, key=lambda d: d.priority, reverse=True)

    def _compute_priority(self, decision: DecisionObject) -> int:
        risk = RISK_RANK.get(decision.risk_level, 0)
        return int(risk * decision.confidence * 10)

    def _build_drivers(self, scenario: Scenario) -> list[DecisionDriver]:
        return [
            DecisionDriver(
                name=a.variable,
                weight=scenario.sensitivity.get(a.variable, 0.3),
                description=f"{a.variable} = {a.assumed_value}",
            )
            for a in scenario.assumptions
        ]

    def _scenario_price(self, scenario: Scenario) -> float:
        return scenario.projected_outcome.get(
            "price_brl", scenario.projected_outcome.get("price", 0.0)
        )

    def _baseline_price(self, baseline: Scenario | None) -> float:
        if baseline is None:
            return 0.0
        return self._scenario_price(baseline)
