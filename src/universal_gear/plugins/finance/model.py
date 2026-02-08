"""Finance model -- conditional scenario generation for Brazilian macro indicators."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field

from universal_gear.core.contracts import (
    Assumption,
    HypothesisResult,
    RiskLevel,
    Scenario,
    SimulationResult,
)
from universal_gear.core.interfaces import BaseSimulator
from universal_gear.core.registry import register_model
from universal_gear.plugins.finance.config import FinanceConfig

if TYPE_CHECKING:
    from uuid import UUID

RISK_CRITICAL_PCT = 15.0
RISK_HIGH_PCT = 10.0
RISK_MEDIUM_PCT = 5.0
DEFAULT_VOLATILITY = 0.08


class FinanceModelConfig(BaseModel):
    """Configuration for finance scenario generation."""

    exchange_scenarios: list[float] = Field(
        default_factory=lambda: [5.0, 5.5, 6.0, 6.5],
    )
    selic_scenarios: list[float] = Field(
        default_factory=lambda: [12.25, 13.25, 14.25],
    )
    baseline_exchange: float = 5.75
    baseline_selic: float = 13.25
    volatility: float = DEFAULT_VOLATILITY


@register_model("finance")
class FinanceScenarioEngine(BaseSimulator[FinanceModelConfig]):
    """Generates macro scenarios from exchange rate x interest rate combinations."""

    def __init__(self, config: FinanceModelConfig | FinanceConfig) -> None:
        if isinstance(config, FinanceConfig):
            config = FinanceModelConfig()
        super().__init__(config)

    async def simulate(self, hypotheses: HypothesisResult) -> SimulationResult:
        self._apply_context(hypotheses.context)
        source_ids = [h.hypothesis_id for h in hypotheses.hypotheses]
        scenarios = self._build_scenarios(source_ids)
        baseline = self._build_baseline(source_ids)

        return SimulationResult(
            scenarios=[baseline, *scenarios],
            baseline=baseline,
        )

    def _apply_context(self, context: dict[str, float]) -> None:
        """Override baseline values with observed data from the analyzer."""
        updates: dict[str, float] = {}
        if "exchange_rate" in context:
            updates["baseline_exchange"] = context["exchange_rate"]
        if "selic_rate" in context:
            updates["baseline_selic"] = context["selic_rate"]
        if updates:
            self.config = self.config.model_copy(update=updates)

    def _build_scenarios(self, source_ids: list[UUID]) -> list[Scenario]:
        scenarios: list[Scenario] = []

        for exchange in self.config.exchange_scenarios:
            for selic in self.config.selic_scenarios:
                label = self._label(exchange, selic)
                cost_index = self._cost_index(exchange, selic)
                vol = self.config.volatility

                scenarios.append(
                    Scenario(
                        name=label,
                        description=(f"USD/BRL at {exchange:.2f}, SELIC at {selic:.2f}% p.a."),
                        assumptions=[
                            Assumption(
                                variable="exchange_rate",
                                assumed_value=exchange,
                                justification="USD/BRL scenario assumption",
                            ),
                            Assumption(
                                variable="selic_rate",
                                assumed_value=selic,
                                justification="SELIC target rate assumption",
                            ),
                        ],
                        projected_outcome={
                            "exchange_rate": round(exchange, 4),
                            "selic_rate": round(selic, 2),
                            "cost_index": round(cost_index, 4),
                        },
                        confidence_interval=(
                            round(exchange * (1 - vol), 4),
                            round(exchange * (1 + vol), 4),
                        ),
                        probability=self._estimate_probability(exchange, selic),
                        probability_method="inverse_distance_to_baseline",
                        risk_level=self._assess_risk(exchange),
                        sensitivity={
                            "exchange_rate": 0.6,
                            "selic_rate": 0.4,
                        },
                        source_hypotheses=source_ids,
                    )
                )

        return scenarios

    def _build_baseline(self, source_ids: list[UUID]) -> Scenario:
        exchange = self.config.baseline_exchange
        selic = self.config.baseline_selic
        cost_index = self._cost_index(exchange, selic)
        vol = self.config.volatility

        return Scenario(
            name="baseline (status quo)",
            description=(f"Current levels: USD/BRL {exchange:.2f}, SELIC {selic:.2f}% p.a."),
            assumptions=[
                Assumption(
                    variable="exchange_rate",
                    assumed_value=exchange,
                    justification="Current exchange rate level",
                ),
                Assumption(
                    variable="selic_rate",
                    assumed_value=selic,
                    justification="Current SELIC target rate",
                ),
            ],
            projected_outcome={
                "exchange_rate": round(exchange, 4),
                "selic_rate": round(selic, 2),
                "cost_index": round(cost_index, 4),
            },
            confidence_interval=(
                round(exchange * (1 - vol), 4),
                round(exchange * (1 + vol), 4),
            ),
            probability=0.5,
            probability_method="fixed_baseline",
            risk_level=RiskLevel.MEDIUM,
            sensitivity={
                "exchange_rate": 0.6,
                "selic_rate": 0.4,
            },
            source_hypotheses=source_ids,
        )

    def _cost_index(self, exchange: float, selic: float) -> float:
        """Composite cost index: weighted combination of FX and rate impact."""
        base_ex = self.config.baseline_exchange
        base_selic = self.config.baseline_selic

        fx_impact = (exchange - base_ex) / base_ex if base_ex else 0.0
        rate_impact = (selic - base_selic) / base_selic if base_selic else 0.0

        return 1.0 + fx_impact * 0.6 + rate_impact * 0.4

    def _estimate_probability(self, exchange: float, selic: float) -> float:
        """Estimate probability inversely proportional to distance from baseline."""
        ex_dist = abs(exchange - self.config.baseline_exchange)
        ex_spread = max(self.config.exchange_scenarios) - min(self.config.exchange_scenarios)

        selic_dist = abs(selic - self.config.baseline_selic)
        selic_spread = max(self.config.selic_scenarios) - min(self.config.selic_scenarios)

        norm_ex = ex_dist / ex_spread if ex_spread else 0.0
        norm_selic = selic_dist / selic_spread if selic_spread else 0.0

        avg = (norm_ex + norm_selic) / 2
        return round(max(0.05, 1.0 - avg), 2)

    def _assess_risk(self, exchange: float) -> RiskLevel:
        """Assess risk based on deviation from baseline exchange rate."""
        baseline = self.config.baseline_exchange
        deviation_pct = abs(exchange - baseline) / baseline * 100 if baseline else 0.0
        if deviation_pct > RISK_CRITICAL_PCT:
            return RiskLevel.CRITICAL
        if deviation_pct > RISK_HIGH_PCT:
            return RiskLevel.HIGH
        if deviation_pct > RISK_MEDIUM_PCT:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _label(self, exchange: float, selic: float) -> str:
        med_ex = float(np.median(self.config.exchange_scenarios))
        med_selic = float(np.median(self.config.selic_scenarios))

        if exchange > med_ex:
            ex_label = "USD strengthens"
        elif exchange < med_ex:
            ex_label = "USD weakens"
        else:
            ex_label = "USD stable"

        if selic > med_selic:
            selic_label = "tight policy"
        elif selic < med_selic:
            selic_label = "loose policy"
        else:
            selic_label = "neutral policy"

        return f"{ex_label} x {selic_label}"
