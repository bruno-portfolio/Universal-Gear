"""Finance action -- hedge recommendations, exposure alerts, cost impact warnings."""

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
from universal_gear.plugins.finance.config import FinanceConfig

EXCHANGE_ALERT_THRESHOLD_PCT = 5.0
EXPIRY_DAYS = 14
MIN_PROBABILITY = 0.3
RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@register_action("finance")
class FinanceActionEmitter(BaseDecider[FinanceConfig]):
    """Emits hedge recommendations, exposure alerts, and cost impact warnings."""

    async def decide(self, simulation: SimulationResult) -> DecisionResult:
        decisions: list[DecisionObject] = []

        upside = self._filter_usd_strengthens(simulation)
        downside = self._filter_usd_weakens(simulation)

        for scenario in upside:
            decisions.append(self._build_hedge_recommendation(scenario, simulation.baseline))

        for scenario in downside:
            decisions.append(self._build_exposure_alert(scenario, simulation.baseline))

        cost_warnings = self._build_cost_warnings(simulation)
        decisions.extend(cost_warnings)

        if not decisions:
            decisions.append(self._build_hold_recommendation(simulation))

        decisions = self._rank_decisions(decisions)
        return DecisionResult(decisions=decisions)

    def _filter_usd_strengthens(self, simulation: SimulationResult) -> list[Scenario]:
        """Scenarios where USD strengthens significantly vs baseline."""
        baseline_rate = self._baseline_exchange(simulation.baseline)
        return [
            s
            for s in simulation.scenarios
            if (
                s.name != "baseline (status quo)"
                and s.probability >= MIN_PROBABILITY
                and self._scenario_exchange(s)
                > baseline_rate * (1 + EXCHANGE_ALERT_THRESHOLD_PCT / 100)
            )
        ]

    def _filter_usd_weakens(self, simulation: SimulationResult) -> list[Scenario]:
        """Scenarios where USD weakens significantly vs baseline."""
        baseline_rate = self._baseline_exchange(simulation.baseline)
        return [
            s
            for s in simulation.scenarios
            if (
                s.name != "baseline (status quo)"
                and s.probability >= MIN_PROBABILITY
                and RISK_RANK.get(s.risk_level, 0) >= RISK_RANK[RiskLevel.MEDIUM]
                and self._scenario_exchange(s)
                < baseline_rate * (1 - EXCHANGE_ALERT_THRESHOLD_PCT / 100)
            )
        ]

    def _build_hedge_recommendation(
        self, scenario: Scenario, baseline: Scenario | None
    ) -> DecisionObject:
        rate = self._scenario_exchange(scenario)
        base = self._baseline_exchange(baseline)
        spread = (rate - base) / base * 100 if base else 0.0

        return DecisionObject(
            decision_type=DecisionType.RECOMMENDATION,
            title=f"Hedge recommendation: {scenario.name}",
            recommendation=(
                f"USD/BRL projected at {rate:.4f} "
                f"({spread:+.1f}% vs baseline). "
                f"Consider FX hedging to protect BRL-denominated costs "
                f"against USD appreciation."
            ),
            conditions=[
                Condition(
                    description=(f"Exchange rate deviation > {EXCHANGE_ALERT_THRESHOLD_PCT}%"),
                    metric="exchange_rate_deviation_pct",
                    operator="gt",
                    threshold=EXCHANGE_ALERT_THRESHOLD_PCT,
                    window=f"{EXPIRY_DAYS} days",
                ),
            ],
            drivers=self._build_drivers(scenario),
            confidence=scenario.probability,
            risk_level=scenario.risk_level,
            cost_of_error=CostOfError(
                false_positive=("Unnecessary hedging cost (option premium or forward spread)"),
                false_negative=(f"Unhedged FX exposure loses ~{abs(spread):.1f}%"),
                estimated_magnitude=f"{abs(spread):.1f}% of FX exposure",
            ),
            expires_at=datetime.now(UTC) + timedelta(days=EXPIRY_DAYS),
            source_scenarios=[scenario.scenario_id],
        )

    def _build_exposure_alert(
        self, scenario: Scenario, baseline: Scenario | None
    ) -> DecisionObject:
        rate = self._scenario_exchange(scenario)
        base = self._baseline_exchange(baseline)
        spread = (rate - base) / base * 100 if base else 0.0

        return DecisionObject(
            decision_type=DecisionType.ALERT,
            title=f"Exposure alert: {scenario.name}",
            recommendation=(
                f"USD/BRL may drop to {rate:.4f} "
                f"({spread:+.1f}% vs baseline). "
                f"Review USD-denominated receivables and export pricing."
            ),
            conditions=[
                Condition(
                    description=(f"Exchange rate drop > {EXCHANGE_ALERT_THRESHOLD_PCT}%"),
                    metric="exchange_rate_deviation_pct",
                    operator="lt",
                    threshold=-EXCHANGE_ALERT_THRESHOLD_PCT,
                    window=f"{EXPIRY_DAYS} days",
                ),
            ],
            drivers=self._build_drivers(scenario),
            confidence=scenario.probability,
            risk_level=scenario.risk_level,
            cost_of_error=CostOfError(
                false_positive="Premature adjustment to export pricing",
                false_negative=(f"Revenue shortfall of ~{abs(spread):.1f}% on USD flows"),
                estimated_magnitude=f"{abs(spread):.1f}% of USD receivables",
            ),
            expires_at=datetime.now(UTC) + timedelta(days=EXPIRY_DAYS),
            source_scenarios=[scenario.scenario_id],
        )

    def _build_cost_warnings(self, simulation: SimulationResult) -> list[DecisionObject]:
        """Emit cost impact warnings for high-risk scenarios."""
        warnings: list[DecisionObject] = []
        for scenario in simulation.scenarios:
            if (
                scenario.name == "baseline (status quo)"
                or RISK_RANK.get(scenario.risk_level, 0) < RISK_RANK[RiskLevel.HIGH]
            ):
                continue

            cost_index = scenario.projected_outcome.get("cost_index", 1.0)
            impact_pct = (cost_index - 1.0) * 100

            if abs(impact_pct) < EXCHANGE_ALERT_THRESHOLD_PCT:
                continue

            warnings.append(
                DecisionObject(
                    decision_type=DecisionType.TRIGGER,
                    title=f"Cost impact warning: {scenario.name}",
                    recommendation=(
                        f"Composite cost index at {cost_index:.4f} "
                        f"({impact_pct:+.1f}% vs baseline). "
                        f"Review import budgets and supplier contracts."
                    ),
                    conditions=[
                        Condition(
                            description="Cost index deviation exceeds threshold",
                            metric="cost_index_deviation_pct",
                            operator="gt" if impact_pct > 0 else "lt",
                            threshold=EXCHANGE_ALERT_THRESHOLD_PCT,
                            window=f"{EXPIRY_DAYS} days",
                        ),
                    ],
                    drivers=self._build_drivers(scenario),
                    confidence=scenario.probability,
                    risk_level=scenario.risk_level,
                    cost_of_error=CostOfError(
                        false_positive="Budget revision unnecessary",
                        false_negative=(f"Budget overrun of ~{abs(impact_pct):.1f}%"),
                        estimated_magnitude=(f"{abs(impact_pct):.1f}% of import costs"),
                    ),
                    expires_at=(datetime.now(UTC) + timedelta(days=EXPIRY_DAYS)),
                    source_scenarios=[scenario.scenario_id],
                )
            )

        return warnings

    def _build_hold_recommendation(self, simulation: SimulationResult) -> DecisionObject:
        return DecisionObject(
            decision_type=DecisionType.REPORT,
            title="No actionable macro signal",
            recommendation=(
                "Current macro scenarios do not exceed alert thresholds. "
                "Continue monitoring USD/BRL and SELIC. "
                "No immediate hedging or repricing action required."
            ),
            drivers=[
                DecisionDriver(
                    name="threshold_filter",
                    weight=1.0,
                    description=(
                        f"exchange threshold {EXCHANGE_ALERT_THRESHOLD_PCT}% not breached"
                    ),
                ),
            ],
            confidence=0.8,
            risk_level=RiskLevel.LOW,
            cost_of_error=CostOfError(
                false_positive="Report generated unnecessarily",
                false_negative="Missed subtle macro signal",
            ),
            source_scenarios=[s.scenario_id for s in simulation.scenarios],
        )

    def _rank_decisions(
        self, decisions: list[DecisionObject]
    ) -> list[DecisionObject]:
        """Assign priority scores and return sorted by priority desc."""
        ranked = [
            d.model_copy(update={"priority": self._compute_priority(d)})
            for d in decisions
        ]
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

    def _scenario_exchange(self, scenario: Scenario) -> float:
        return scenario.projected_outcome.get("exchange_rate", 0.0)

    def _baseline_exchange(self, baseline: Scenario | None) -> float:
        if baseline is None:
            return 0.0
        return self._scenario_exchange(baseline)
