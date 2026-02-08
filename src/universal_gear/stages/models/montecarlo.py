"""Monte Carlo simulation — sampling-based scenario generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from uuid import UUID
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

DEFAULT_N_ITERATIONS = 10_000
DEFAULT_PERCENTILE_LOW = 0.05
DEFAULT_PERCENTILE_HIGH = 0.95
RISK_CRITICAL_THRESHOLD = 0.5
RISK_HIGH_THRESHOLD = 0.3
RISK_MEDIUM_THRESHOLD = 0.15


class DistributionSpec(BaseModel):
    """Specification for a random variable's distribution."""

    dist_type: str = "normal"
    mean: float = 0.0
    std: float = 1.0
    low: float | None = None
    high: float | None = None


class MonteCarloModelConfig(BaseModel):
    """Configuration for Monte Carlo simulation."""

    n_iterations: int = DEFAULT_N_ITERATIONS
    distributions: dict[str, DistributionSpec] = Field(default_factory=dict)
    seed: int = 42
    percentiles: tuple[float, float] = (DEFAULT_PERCENTILE_LOW, DEFAULT_PERCENTILE_HIGH)
    base_price: float = 100.0
    sensitivity_weights: dict[str, float] = Field(default_factory=dict)


@register_model("montecarlo")
class MonteCarloSimulator(BaseSimulator[MonteCarloModelConfig]):
    """Generates scenarios by sampling from configured distributions."""

    async def simulate(self, hypotheses: HypothesisResult) -> SimulationResult:
        rng = np.random.default_rng(self.config.seed)
        source_ids = [h.hypothesis_id for h in hypotheses.hypotheses]

        samples = self._draw_samples(rng)
        prices = self._compute_prices(samples)

        p_low, p_high = self.config.percentiles
        low_price = float(np.percentile(prices, p_low * 100))
        med_price = float(np.percentile(prices, 50))
        high_price = float(np.percentile(prices, p_high * 100))

        pessimistic = self._make_scenario(
            "pessimistic",
            low_price,
            samples,
            p_low,
            source_ids,
            description=f"Monte Carlo p{int(p_low * 100)} outcome",
        )
        baseline = self._make_scenario(
            "baseline (p50)",
            med_price,
            samples,
            0.5,
            source_ids,
            description="Monte Carlo median outcome",
        )
        optimistic = self._make_scenario(
            "optimistic",
            high_price,
            samples,
            p_high,
            source_ids,
            description=f"Monte Carlo p{int(p_high * 100)} outcome",
        )

        return SimulationResult(
            scenarios=[pessimistic, baseline, optimistic],
            baseline=baseline,
        )

    def _draw_samples(self, rng: np.random.Generator) -> dict[str, np.ndarray]:
        samples: dict[str, np.ndarray] = {}
        for name, spec in self.config.distributions.items():
            match spec.dist_type:
                case "normal":
                    samples[name] = rng.normal(spec.mean, spec.std, self.config.n_iterations)
                case "uniform":
                    low = spec.low if spec.low is not None else spec.mean - spec.std
                    high = spec.high if spec.high is not None else spec.mean + spec.std
                    samples[name] = rng.uniform(low, high, self.config.n_iterations)
                case _:
                    samples[name] = rng.normal(spec.mean, spec.std, self.config.n_iterations)
        return samples

    def _compute_prices(self, samples: dict[str, np.ndarray]) -> np.ndarray:
        prices = np.full(self.config.n_iterations, self.config.base_price)
        for name, values in samples.items():
            weight = self.config.sensitivity_weights.get(name, 0.0)
            prices = prices + weight * (values - 1.0) * self.config.base_price
        return prices

    def _make_scenario(
        self,
        name: str,
        price: float,
        samples: dict[str, np.ndarray],
        probability: float,
        source_ids: list[UUID],
        *,
        description: str,
    ) -> Scenario:
        assumptions = [
            Assumption(
                variable=var_name,
                assumed_value=round(float(np.mean(vals)), 4),
                justification=f"Monte Carlo mean of {self.config.n_iterations} samples",
            )
            for var_name, vals in samples.items()
        ]

        ci_low = round(price * 0.85, 2)
        ci_high = round(price * 1.15, 2)

        deviation = abs(price - self.config.base_price) / self.config.base_price
        risk = self._assess_risk(deviation)

        return Scenario(
            name=name,
            description=description,
            assumptions=assumptions,
            projected_outcome={"price": round(price, 2)},
            confidence_interval=(ci_low, ci_high),
            probability=round(probability, 2),
            risk_level=risk,
            sensitivity=dict(self.config.sensitivity_weights),
            source_hypotheses=source_ids,
        )

    def _assess_risk(self, deviation: float) -> RiskLevel:
        if deviation > RISK_CRITICAL_THRESHOLD:
            return RiskLevel.CRITICAL
        if deviation > RISK_HIGH_THRESHOLD:
            return RiskLevel.HIGH
        if deviation > RISK_MEDIUM_THRESHOLD:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
