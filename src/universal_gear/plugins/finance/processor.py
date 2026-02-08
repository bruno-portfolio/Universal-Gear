"""Finance processor -- aggregates daily BCB rates into weekly MarketStates."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

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
from universal_gear.plugins.finance.config import INDICATOR_UNITS, FinanceConfig

if TYPE_CHECKING:
    from uuid import UUID

DAYS_PER_WEEK = 7


@register_processor("finance")
class FinanceProcessor(BaseProcessor[FinanceConfig]):
    """Normalises and aggregates daily BCB data into weekly MarketStates."""

    async def process(self, collection: CollectionResult) -> CompressionResult:
        by_indicator = self._split_by_indicator(collection.events)
        states: list[MarketState] = []

        for indicator, events in by_indicator.items():
            buckets = self._bucket_weekly(events)
            ind_states = self._aggregate(indicator, buckets)
            states.extend(ind_states)

        states.sort(key=lambda s: s.period_start)

        norm_log = [f"aggregated {len(collection.events)} events into {len(states)} weekly states"]

        return CompressionResult(
            states=states,
            records_consumed=len(collection.events),
            records_produced=len(states),
            normalization_log=norm_log,
            aggregation_methods={
                "exchange_rate": "mean",
                "selic_rate": "mean",
                "ipca_rate": "mean",
            },
        )

    def _split_by_indicator(self, events: list[RawEvent]) -> dict[str, list[RawEvent]]:
        grouped: dict[str, list[RawEvent]] = defaultdict(list)
        for event in events:
            indicator = event.data.get("indicator", "unknown")
            grouped[indicator].append(event)
        return dict(grouped)

    def _bucket_weekly(self, events: list[RawEvent]) -> dict[datetime, list[RawEvent]]:
        buckets: dict[datetime, list[RawEvent]] = defaultdict(list)
        for event in events:
            monday = event.timestamp - timedelta(days=event.timestamp.weekday())
            key = monday.replace(hour=0, minute=0, second=0, microsecond=0)
            buckets[key].append(event)
        return dict(sorted(buckets.items()))

    def _aggregate(
        self,
        indicator: str,
        buckets: dict[datetime, list[RawEvent]],
    ) -> list[MarketState]:
        states: list[MarketState] = []
        unit = INDICATOR_UNITS.get(indicator, "unit")

        for week_start, events in buckets.items():
            week_end = week_start + timedelta(days=DAYS_PER_WEEK)
            lineage: list[UUID] = [ev.event_id for ev in events]

            signals = self._build_signals(indicator, events, unit)
            if not signals:
                continue

            reliability = min(
                1.0 if ev.source.reliability.value != "degraded" else 0.3 for ev in events
            )

            states.append(
                MarketState(
                    domain="finance",
                    period_start=week_start,
                    period_end=week_end,
                    granularity=Granularity.WEEKLY,
                    signals=signals,
                    lineage=lineage,
                    source_reliability=reliability,
                )
            )

        return states

    def _build_signals(
        self,
        indicator: str,
        events: list[RawEvent],
        unit: str,
    ) -> list[SignalValue]:
        if indicator == "usd_brl":
            return self._build_exchange_signals(events, unit)
        return self._build_rate_signals(indicator, events, unit)

    def _build_exchange_signals(self, events: list[RawEvent], unit: str) -> list[SignalValue]:
        sell_rates = _extract_numeric(events, "cotacao_venda")
        if not sell_rates:
            return []

        return [
            SignalValue(
                name="exchange_rate",
                value=round(float(np.mean(sell_rates)), 4),
                unit=unit,
                original_unit="BRL/USD",
                confidence=min(1.0, len(sell_rates) / DAYS_PER_WEEK),
            ),
        ]

    def _build_rate_signals(
        self, indicator: str, events: list[RawEvent], unit: str
    ) -> list[SignalValue]:
        values = _extract_numeric(events, "valor")
        if not values:
            return []

        signal_name = f"{indicator}_rate"
        return [
            SignalValue(
                name=signal_name,
                value=round(float(np.mean(values)), 4),
                unit=unit,
                confidence=min(1.0, len(values) / DAYS_PER_WEEK),
            ),
        ]


def _extract_numeric(events: list[RawEvent], field: str) -> list[float]:
    """Extract numeric values for a given field from raw events."""
    values: list[float] = []
    for event in events:
        val = event.data.get(field)
        if val is not None and isinstance(val, int | float):
            values.append(float(val))
    return values
