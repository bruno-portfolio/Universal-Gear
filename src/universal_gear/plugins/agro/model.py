"""Agro model — exchange rate x harvest conditional scenarios."""

from __future__ import annotations

import itertools
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
from universal_gear.plugins.agro.config import AgroConfig

if TYPE_CHECKING:
    from uuid import UUID

RISK_CRITICAL_DEVIATION = 0.5
RISK_HIGH_DEVIATION = 0.3
RISK_MEDIUM_DEVIATION = 0.15
DEFAULT_VOLATILITY = 0.12
HARVEST_NEUTRAL = 1.0


class AgroModelConfig(BaseModel):
    """Configuration for agro scenario generation."""

    exchange_rates: list[float] = Field(
        default_factory=lambda: [5.0, 5.5, 6.0]
    )
    harvest_multipliers: list[float] = Field(
        default_factory=lambda: [0.85, 1.0, 1.15]
    )
    export_premium_pct: list[float] = Field(
        default_factory=lambda: [0.0, 3.0, 6.0]
    )
    base_price_brl: float = 130.0
    volatility: float = DEFAULT_VOLATILITY


@register_model("agro")
class AgroScenarioEngine(BaseSimulator[AgroModelConfig]):
    """Generates agro scenarios from exchange rate x harvest combinations."""

    def __init__(self, config: AgroModelConfig | AgroConfig) -> None:
        if isinstance(config, AgroConfig):
            config = AgroModelConfig()
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
        """Override base price with observed data from the analyzer."""
        if "price" in context:
            self.config = self.config.model_copy(
                update={"base_price_brl": context["price"]},
            )

    def _build_scenarios(self, source_ids: list[UUID]) -> list[Scenario]:
        combos = list(itertools.product(
            self.config.exchange_rates,
            self.config.harvest_multipliers,
            self.config.export_premium_pct,
        ))

        scenarios: list[Scenario] = []
        for exchange, harvest, premium in combos:
            price = self._project_price(exchange, harvest, premium)
            vol = self.config.volatility

            label = self._label(exchange, harvest)

            scenarios.append(
                Scenario(
                    name=f"{label} + premium {premium:.0f}%",
                    description=(
                        f"Exchange {exchange:.2f} BRL/USD, "
                        f"harvest {harvest:.0%} of normal, "
                        f"export premium {premium:.1f}%"
                    ),
                    assumptions=[
                        Assumption(
                            variable="exchange_rate",
                            assumed_value=exchange,
                            justification="BRL/USD scenario assumption",
                        ),
                        Assumption(
                            variable="harvest_multiplier",
                            assumed_value=harvest,
                            justification="Harvest yield relative to normal",
                        ),
                        Assumption(
                            variable="export_premium_pct",
                            assumed_value=premium,
                            justification="Export premium percentage",
                        ),
                    ],
                    projected_outcome={
                        "price_brl": round(price, 2),
                        "margin_pct": round(
                            (price - self.config.base_price_brl)
                            / self.config.base_price_brl
                            * 100,
                            2,
                        ),
                    },
                    confidence_interval=(
                        round(price * (1 - vol), 2),
                        round(price * (1 + vol), 2),
                    ),
                    probability=self._estimate_probability(exchange, harvest),
                    probability_method="inverse_distance_to_baseline",
                    risk_level=self._assess_risk(price),
                    sensitivity={
                        "exchange_rate": 0.5,
                        "harvest_multiplier": 0.35,
                        "export_premium_pct": 0.15,
                    },
                    source_hypotheses=source_ids,
                )
            )

        return scenarios

    def _build_baseline(self, source_ids: list[UUID]) -> Scenario:
        mid_exchange = float(np.median(self.config.exchange_rates))
        mid_harvest = 1.0
        mid_premium = float(np.median(self.config.export_premium_pct))
        price = self._project_price(mid_exchange, mid_harvest, mid_premium)
        vol = self.config.volatility

        return Scenario(
            name="baseline (status quo)",
            description=(
                f"Median scenario: exchange {mid_exchange:.2f}, "
                f"normal harvest, premium {mid_premium:.1f}%"
            ),
            assumptions=[
                Assumption(
                    variable="exchange_rate",
                    assumed_value=mid_exchange,
                    justification="Median exchange rate",
                ),
                Assumption(
                    variable="harvest_multiplier",
                    assumed_value=mid_harvest,
                    justification="Normal harvest",
                ),
                Assumption(
                    variable="export_premium_pct",
                    assumed_value=mid_premium,
                    justification="Median export premium",
                ),
            ],
            projected_outcome={
                "price_brl": round(price, 2),
                "margin_pct": round(
                    (price - self.config.base_price_brl) / self.config.base_price_brl * 100, 2
                ),
            },
            confidence_interval=(
                round(price * (1 - vol), 2),
                round(price * (1 + vol), 2),
            ),
            probability=0.5,
            probability_method="fixed_baseline",
            risk_level=RiskLevel.MEDIUM,
            sensitivity={
                "exchange_rate": 0.5,
                "harvest_multiplier": 0.35,
                "export_premium_pct": 0.15,
            },
            source_hypotheses=source_ids,
        )

    def _project_price(
        self, exchange: float, harvest: float, premium: float
    ) -> float:
        base = self.config.base_price_brl
        exchange_effect = (exchange - 5.5) / 5.5 * 0.5
        harvest_effect = (1 - harvest) * 0.4
        premium_effect = premium / 100
        return base * (1 + exchange_effect + harvest_effect + premium_effect)

    def _estimate_probability(self, exchange: float, harvest: float) -> float:
        exchange_dist = abs(exchange - float(np.median(self.config.exchange_rates)))
        exchange_spread = max(self.config.exchange_rates) - min(self.config.exchange_rates)
        harvest_dist = abs(harvest - 1.0)

        norm_ex = exchange_dist / exchange_spread if exchange_spread else 0.0
        norm_hv = harvest_dist / 0.3

        avg = (norm_ex + norm_hv) / 2
        return round(max(0.05, 1.0 - avg), 2)

    def _assess_risk(self, price: float) -> RiskLevel:
        deviation = abs(price - self.config.base_price_brl) / self.config.base_price_brl
        if deviation > RISK_CRITICAL_DEVIATION:
            return RiskLevel.CRITICAL
        if deviation > RISK_HIGH_DEVIATION:
            return RiskLevel.HIGH
        if deviation > RISK_MEDIUM_DEVIATION:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _label(self, exchange: float, harvest: float) -> str:
        ex_label = (
            "high FX"
            if exchange > np.median(self.config.exchange_rates)
            else "low FX" if exchange < np.median(self.config.exchange_rates) else "mid FX"
        )
        hv_label = (
            "strong harvest"
            if harvest > HARVEST_NEUTRAL
            else "weak harvest" if harvest < HARVEST_NEUTRAL else "normal harvest"
        )
        return f"{ex_label} x {hv_label}"
