"""Temporal aggregation — daily events to weekly/monthly MarketStates."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

import numpy as np
from pydantic import BaseModel, Field

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
from universal_gear.stages.processors.normalizer import Normalizer, NormalizerConfig

DAYS_PER_WEEK = 7
DAYS_PER_MONTH = 30


class AggregatorConfig(BaseModel):
    """Configuration for the temporal aggregator."""

    granularity: Granularity = Granularity.WEEKLY
    strategies: dict[str, str] = Field(default_factory=lambda: {"price": "mean", "demand": "sum"})
    domain: str = "generic"
    default_unit: str = "unit"
    normalizer: NormalizerConfig = Field(default_factory=NormalizerConfig)


@register_processor("aggregator")
class AggregatorProcessor(BaseProcessor[AggregatorConfig]):
    """Normalises and aggregates raw events into MarketStates."""

    async def process(self, collection: CollectionResult) -> CompressionResult:
        normalizer = Normalizer(self.config.normalizer)
        normalised_data, norm_log = normalizer.normalise_events(collection.events)

        buckets = self._bucket_events(collection.events, normalised_data)
        states = self._aggregate_buckets(buckets, collection.events)

        return CompressionResult(
            states=states,
            records_consumed=len(collection.events),
            records_produced=len(states),
            normalization_log=norm_log,
        )

    def _bucket_events(
        self,
        events: list[RawEvent],
        normalised: list[dict[str, Any]],
    ) -> dict[datetime, list[tuple[RawEvent, dict[str, Any]]]]:
        buckets: dict[datetime, list[tuple[RawEvent, dict[str, Any]]]] = defaultdict(list)

        for event, norm_data in zip(events, normalised, strict=True):
            bucket_key = self._bucket_key(event.timestamp)
            buckets[bucket_key].append((event, norm_data))

        return dict(sorted(buckets.items()))

    def _bucket_key(self, ts: datetime) -> datetime:
        match self.config.granularity:
            case Granularity.WEEKLY:
                monday = ts - timedelta(days=ts.weekday())
                return monday.replace(hour=0, minute=0, second=0, microsecond=0)
            case Granularity.MONTHLY:
                return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            case Granularity.DAILY:
                return ts.replace(hour=0, minute=0, second=0, microsecond=0)
            case Granularity.QUARTERLY:
                quarter_month = ((ts.month - 1) // 3) * 3 + 1
                return ts.replace(
                    month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0
                )

    def _aggregate_buckets(
        self,
        buckets: dict[datetime, list[tuple[RawEvent, dict[str, Any]]]],
        _all_events: list[RawEvent],
    ) -> list[MarketState]:
        states: list[MarketState] = []

        for bucket_start, items in buckets.items():
            period_end = self._period_end(bucket_start)
            lineage: list[UUID] = [ev.event_id for ev, _ in items]

            signal_values: dict[str, list[float]] = defaultdict(list)
            for _, norm_data in items:
                for key, value in norm_data.items():
                    if isinstance(value, int | float):
                        signal_values[key].append(float(value))

            signals = self._compute_signals(signal_values)
            if not signals:
                continue

            reliability = min(
                (ev.source.reliability.value != "degraded") * 1.0
                for ev, _ in items
            )
            reliability = max(reliability, 0.0)

            states.append(
                MarketState(
                    domain=self.config.domain,
                    period_start=bucket_start,
                    period_end=period_end,
                    granularity=self.config.granularity,
                    signals=signals,
                    lineage=lineage,
                    source_reliability=reliability,
                )
            )

        return states

    def _period_end(self, start: datetime) -> datetime:
        match self.config.granularity:
            case Granularity.DAILY:
                return start + timedelta(days=1)
            case Granularity.WEEKLY:
                return start + timedelta(days=DAYS_PER_WEEK)
            case Granularity.MONTHLY:
                return start + timedelta(days=DAYS_PER_MONTH)
            case Granularity.QUARTERLY:
                return start + timedelta(days=DAYS_PER_MONTH * 3)

    def _compute_signals(
        self, signal_values: dict[str, list[float]]
    ) -> list[SignalValue]:
        signals: list[SignalValue] = []

        for name, values in signal_values.items():
            strategy = self.config.strategies.get(name, "mean")
            arr = np.array(values)

            match strategy:
                case "mean":
                    agg_value = float(np.mean(arr))
                case "median":
                    agg_value = float(np.median(arr))
                case "sum":
                    agg_value = float(np.sum(arr))
                case "last":
                    agg_value = float(arr[-1])
                case _:
                    agg_value = float(np.mean(arr))

            confidence = 1.0 if len(values) > 1 else 0.5

            signals.append(
                SignalValue(
                    name=name,
                    value=round(agg_value, 4),
                    unit=self.config.default_unit,
                    confidence=confidence,
                )
            )

        return signals
