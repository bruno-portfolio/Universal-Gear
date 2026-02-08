"""Conditional alert emitter — filters scenarios and produces structured decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

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

DEFAULT_MIN_PROBABILITY = 0.3
DEFAULT_EXPIRY_DAYS = 7


class AlertConfig(BaseModel):
    """Configuration for the conditional alert emitter."""

    min_probability: float = Field(ge=0.0, le=1.0, default=DEFAULT_MIN_PROBABILITY)
    min_risk_level: RiskLevel = RiskLevel.MEDIUM
    expiry_days: int = DEFAULT_EXPIRY_DAYS
    decision_type: DecisionType = DecisionType.ALERT

RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@register_action("conditional_alert")
class ConditionalAlertEmitter(BaseDecider[AlertConfig]):
    """Evaluates scenarios and emits decision objects when thresholds are met."""

    async def decide(self, simulation: SimulationResult) -> DecisionResult:
        qualifying = self._filter_scenarios(simulation.scenarios)
        decisions = [self._build_decision(s, simulation.baseline) for s in qualifying]

        if not decisions:
            decisions = [self._build_no_action_decision(simulation)]

        return DecisionResult(decisions=decisions)

    def _filter_scenarios(self, scenarios: list[Scenario]) -> list[Scenario]:
        min_rank = RISK_RANK.get(self.config.min_risk_level, 0)
        return [
            s
            for s in scenarios
            if (
                s.probability >= self.config.min_probability
                and RISK_RANK.get(s.risk_level, 0) >= min_rank
                and s.name != "baseline (status quo)"
            )
        ]

    def _build_decision(
        self, scenario: Scenario, baseline: Scenario | None
    ) -> DecisionObject:
        price = scenario.projected_outcome.get("price", 0.0)
        baseline_price = (
            baseline.projected_outcome.get("price", price) if baseline else price
        )
        spread_pct = ((price - baseline_price) / baseline_price * 100) if baseline_price else 0.0

        drivers = [
            DecisionDriver(
                name=a.variable,
                weight=scenario.sensitivity.get(a.variable, 0.5),
                description=f"Assumed {a.variable} = {a.assumed_value}",
            )
            for a in scenario.assumptions
        ]

        conditions = [
            Condition(
                description=f"Spread vs baseline exceeds {abs(spread_pct):.1f}%",
                metric="spread_pct",
                operator="gt" if spread_pct > 0 else "lt",
                threshold=round(spread_pct, 2),
                window=f"{self.config.expiry_days} days",
            )
        ]

        direction = "upside" if spread_pct > 0 else "downside"

        return DecisionObject(
            decision_type=self.config.decision_type,
            title=f"{direction.title()} alert: {scenario.name}",
            recommendation=(
                f"Scenario '{scenario.name}' projects {direction} of {abs(spread_pct):.1f}% "
                f"vs baseline (price={price:.2f} vs {baseline_price:.2f}). "
                f"Risk level: {scenario.risk_level.value}."
            ),
            conditions=conditions,
            drivers=drivers,
            confidence=scenario.probability,
            risk_level=scenario.risk_level,
            cost_of_error=CostOfError(
                false_positive=f"Unnecessary action based on {scenario.name}",
                false_negative=f"Missed {direction} opportunity of ~{abs(spread_pct):.1f}%",
            ),
            expires_at=datetime.now(UTC) + timedelta(days=self.config.expiry_days),
            source_scenarios=[scenario.scenario_id],
        )

    def _build_no_action_decision(self, simulation: SimulationResult) -> DecisionObject:
        return DecisionObject(
            decision_type=DecisionType.REPORT,
            title="No actionable scenarios detected",
            recommendation=(
                "All scenarios are below the configured risk/probability thresholds. "
                "No action required at this time."
            ),
            drivers=[
                DecisionDriver(
                    name="threshold_filter",
                    weight=1.0,
                    description=(
                        f"min_probability={self.config.min_probability}, "
                        f"min_risk={self.config.min_risk_level.value}"
                    ),
                )
            ],
            confidence=0.9,
            risk_level=RiskLevel.LOW,
            cost_of_error=CostOfError(
                false_positive="Report generated unnecessarily",
                false_negative="Missed subtle risk signal",
            ),
            source_scenarios=[s.scenario_id for s in simulation.scenarios],
        )
