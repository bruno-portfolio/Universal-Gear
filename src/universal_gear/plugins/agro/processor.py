"""Agro processor — normalises agro units and aggregates by crop-week."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np

from universal_gear.core.contracts import (
    CollectionResult,
    CompressionResult,
    Granularity,
    MarketState,
    RawEvent,
    SignalValue,
)
from universal_gear.core.interfaces import BaseProcessor
from universal_gear.core.registry import register_processor
from universal_gear.plugins.agro.config import (
    COMMODITY_CANONICAL_UNIT,
    SACA_60KG_TO_TON,
    AgroConfig,
)

if TYPE_CHECKING:
    from uuid import UUID

DAYS_PER_WEEK = 7
SACA_50KG_TO_TON = 1000 / 50


@register_processor("agro")
class AgroProcessor(BaseProcessor[AgroConfig]):
    """Normalises agro-specific units and aggregates to weekly MarketStates."""

    async def process(self, collection: CollectionResult) -> CompressionResult:
        normalised = [self._normalise_event(e) for e in collection.events]
        buckets = self._bucket_weekly(collection.events, normalised)
        states = self._aggregate(buckets)

        norm_log = [f"normalised {len(collection.events)} events to {len(states)} weekly states"]

        return CompressionResult(
            states=states,
            records_consumed=len(collection.events),
            records_produced=len(states),
            normalization_log=norm_log,
            aggregation_methods={"price": "mean", "production": "mean"},
        )

    def _normalise_event(self, event: RawEvent) -> dict[str, Any]:
        data = dict(event.data)
        valor = data.get("valor")
        unidade = data.get("unidade", "")

        if valor is not None and isinstance(valor, int | float):
            valor, unidade = self._convert_unit(float(valor), str(unidade))
            data["valor"] = valor
            data["unidade"] = unidade

        return data

    def _convert_unit(self, valor: float, unidade: str) -> tuple[float, str]:
        canonical = COMMODITY_CANONICAL_UNIT.get(self.config.commodity, unidade)

        if "sc60kg" in unidade and "ton" in canonical:
            return valor * SACA_60KG_TO_TON, canonical
        if "sc50kg" in unidade and "ton" in canonical:
            return valor * SACA_50KG_TO_TON, canonical

        return valor, unidade

    def _bucket_weekly(
        self,
        events: list[RawEvent],
        normalised: list[dict[str, Any]],
    ) -> dict[datetime, list[tuple[RawEvent, dict[str, Any]]]]:
        buckets: dict[datetime, list[tuple[RawEvent, dict[str, Any]]]] = defaultdict(list)

        for event, norm in zip(events, normalised, strict=True):
            monday = event.timestamp - timedelta(days=event.timestamp.weekday())
            key = monday.replace(hour=0, minute=0, second=0, microsecond=0)
            buckets[key].append((event, norm))

        return dict(sorted(buckets.items()))

    def _aggregate(
        self,
        buckets: dict[datetime, list[tuple[RawEvent, dict[str, Any]]]],
    ) -> list[MarketState]:
        states: list[MarketState] = []
        canonical_unit = COMMODITY_CANONICAL_UNIT.get(self.config.commodity, "BRL/unit")

        for week_start, items in buckets.items():
            week_end = week_start + timedelta(days=DAYS_PER_WEEK)
            lineage: list[UUID] = [ev.event_id for ev, _ in items]

            prices = [
                float(n["valor"])
                for _, n in items
                if n.get("valor") is not None and isinstance(n["valor"], int | float)
            ]

            if not prices:
                continue

            signals = [
                SignalValue(
                    name="price",
                    value=round(float(np.mean(prices)), 2),
                    unit=canonical_unit,
                    original_unit=str(items[0][1].get("unidade", "")),
                    confidence=min(1.0, len(prices) / DAYS_PER_WEEK),
                ),
            ]

            production_values = [
                float(n["producao"])
                for _, n in items
                if n.get("producao") is not None and isinstance(n.get("producao"), int | float)
            ]
            if production_values:
                signals.append(
                    SignalValue(
                        name="production",
                        value=round(float(np.mean(production_values)), 2),
                        unit="mil_ton",
                        confidence=0.8,
                    )
                )

            reliability = min(
                1.0 if ev.source.reliability.value != "degraded" else 0.3
                for ev, _ in items
            )

            states.append(
                MarketState(
                    domain="agro",
                    period_start=week_start,
                    period_end=week_end,
                    granularity=Granularity.WEEKLY,
                    signals=signals,
                    lineage=lineage,
                    source_reliability=reliability,
                )
            )

        return states
