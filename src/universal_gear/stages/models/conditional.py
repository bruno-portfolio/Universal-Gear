"""Conditional scenario engine — cartesian product of assumptions with linear projection."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

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

DEFAULT_HISTORICAL_VOLATILITY = 0.15
RISK_HIGH_THRESHOLD = 0.7
RISK_MEDIUM_THRESHOLD = 0.4
RISK_LOW_THRESHOLD = 0.15


class ConditionalModelConfig(BaseModel):
    """Configuration for the conditional scenario engine."""

    variables: dict[str, list[float]] = Field(
        default_factory=lambda: {
            "exchange_rate": [4.8, 5.2, 5.6],
            "demand_index": [0.8, 1.0, 1.2],
        }
    )
    base_price: float = 100.0
    sensitivity_weights: dict[str, float] = Field(
        default_factory=lambda: {"exchange_rate": 0.6, "demand_index": 0.4}
    )
    historical_volatility: float = DEFAULT_HISTORICAL_VOLATILITY


@register_model("conditional")
class ConditionalScenarioEngine(BaseSimulator[ConditionalModelConfig]):
    """Produces scenarios from cartesian product of variable assumptions."""

    async def simulate(self, hypotheses: HypothesisResult) -> SimulationResult:
        source_ids = [h.hypothesis_id for h in hypotheses.hypotheses]
        scenarios = self._build_scenarios(source_ids)
        baseline = self._build_baseline(source_ids)

        all_scenarios = [baseline, *scenarios]

        return SimulationResult(scenarios=all_scenarios, baseline=baseline)

    def _build_scenarios(self, source_ids: list[UUID]) -> list[Scenario]:
        variables = self.config.variables
        var_names = sorted(variables.keys())
        var_values = [variables[name] for name in var_names]

        scenarios: list[Scenario] = []
        combinations = list(itertools.product(*var_values))

        for combo in combinations:
            assumptions = [
                Assumption(
                    variable=name,
                    assumed_value=value,
                    justification=f"Scenario assumption for {name}",
                )
                for name, value in zip(var_names, combo, strict=True)
            ]

            projected_price = self._project_price(dict(zip(var_names, combo, strict=True)))
            vol = self.config.historical_volatility
            ci_lower = projected_price * (1 - vol)
            ci_upper = projected_price * (1 + vol)

            probability = self._estimate_probability(dict(zip(var_names, combo, strict=True)))
            risk = self._assess_risk(projected_price)

            name_parts = [f"{n}={v}" for n, v in zip(var_names, combo, strict=True)]
            scenario_name = " x ".join(name_parts)

            scenarios.append(
                Scenario(
                    name=scenario_name,
                    description=f"Conditional scenario with {scenario_name}",
                    assumptions=assumptions,
                    projected_outcome={"price": round(projected_price, 2)},
                    confidence_interval=(round(ci_lower, 2), round(ci_upper, 2)),
                    probability=probability,
                    risk_level=risk,
                    sensitivity=dict(self.config.sensitivity_weights),
                    source_hypotheses=source_ids,
                )
            )

        return scenarios

    def _build_baseline(self, source_ids: list[UUID]) -> Scenario:
        mid_values: dict[str, float] = {}
        for name, values in self.config.variables.items():
            mid_values[name] = float(np.median(values))

        projected_price = self._project_price(mid_values)
        vol = self.config.historical_volatility

        return Scenario(
            name="baseline (status quo)",
            description="Baseline scenario — median assumptions, no action taken",
            assumptions=[
                Assumption(
                    variable=name,
                    assumed_value=value,
                    justification=f"Median historical value for {name}",
                )
                for name, value in mid_values.items()
            ],
            projected_outcome={"price": round(projected_price, 2)},
            confidence_interval=(
                round(projected_price * (1 - vol), 2),
                round(projected_price * (1 + vol), 2),
            ),
            probability=0.5,
            risk_level=RiskLevel.MEDIUM,
            sensitivity=dict(self.config.sensitivity_weights),
            source_hypotheses=source_ids,
        )

    def _project_price(self, variable_values: dict[str, float]) -> float:
        price = self.config.base_price
        for name, value in variable_values.items():
            weight = self.config.sensitivity_weights.get(name, 0.0)
            price += weight * (value - 1.0) * self.config.base_price
        return price

    def _estimate_probability(self, variable_values: dict[str, float]) -> float:
        """Rough heuristic: values closer to median get higher probability."""
        distances: list[float] = []
        for name, value in variable_values.items():
            all_values = self.config.variables.get(name, [value])
            median = float(np.median(all_values))
            spread = max(all_values) - min(all_values) if len(all_values) > 1 else 1.0
            distances.append(abs(value - median) / spread if spread else 0.0)

        avg_distance = float(np.mean(distances)) if distances else 0.0
        return round(max(0.1, 1.0 - avg_distance), 2)

    def _assess_risk(self, projected_price: float) -> RiskLevel:
        deviation = abs(projected_price - self.config.base_price) / self.config.base_price
        if deviation > RISK_HIGH_THRESHOLD:
            return RiskLevel.CRITICAL
        if deviation > RISK_MEDIUM_THRESHOLD:
            return RiskLevel.HIGH
        if deviation > RISK_LOW_THRESHOLD:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
