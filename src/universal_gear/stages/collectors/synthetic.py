"""Synthetic data collector for the toy pipeline — 100% offline, deterministic."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from universal_gear.core.contracts import (
    CollectionResult,
    DataQualityReport,
    QualityFlag,
    RawEvent,
    SourceMeta,
    SourceReliability,
    SourceType,
)
from universal_gear.core.interfaces import BaseCollector
from universal_gear.core.registry import register_collector

SEASONAL_CYCLE_DAYS = 365
DAILY_NOISE_SCALE = 0.05
OUTLIER_SIGMA = 3.0
OUTLIER_TRIGGER_PROBABILITY = 0.3


class SyntheticCollectorConfig(BaseModel):
    """Configuration for the synthetic data generator."""

    n_records: int = 90
    signals: list[str] = Field(default_factory=lambda: ["price", "demand"])
    failure_rate: float = Field(ge=0.0, le=1.0, default=0.1)
    schema_change_at: int | None = None
    anomaly_start: int | None = 75
    anomaly_magnitude: float = 0.25
    seed: int = 42
    base_price: float = 100.0
    base_demand: float = 500.0


@register_collector("synthetic")
class SyntheticCollector(BaseCollector[SyntheticCollectorConfig]):
    """Generates deterministic synthetic time-series with injected failures."""

    def _make_source(self) -> SourceMeta:
        return SourceMeta(
            source_id="synthetic-toy",
            source_type=SourceType.SYNTHETIC,
            expected_schema_version="1.0",
            reliability=SourceReliability.HIGH,
        )

    async def collect(self) -> CollectionResult:
        rng = np.random.default_rng(self.config.seed)
        source = self._make_source()
        start = datetime(2024, 1, 1, tzinfo=UTC)

        events: list[RawEvent] = []
        flags: list[QualityFlag] = []
        valid_count = 0
        schema_changed = False

        failure_mask = rng.random(self.config.n_records) < self.config.failure_rate

        for day in range(self.config.n_records):
            ts = start + timedelta(days=day)
            is_failure = bool(failure_mask[day])

            data = self._generate_day(rng, day, is_failure)

            if (
                self.config.schema_change_at is not None
                and day >= self.config.schema_change_at
                and not schema_changed
            ):
                schema_changed = True
                data = self._apply_schema_change(data)
                flags.append(
                    QualityFlag(
                        field_name="price",
                        issue="schema_changed",
                        severity="critical",
                        details=f"Schema changed at day {day}: 'price' renamed to 'price_usd'",
                    )
                )

            if is_failure:
                data, day_flags = self._inject_failure(rng, data, day)
                flags.extend(day_flags)
            else:
                valid_count += 1

            events.append(
                RawEvent(
                    source=source,
                    timestamp=ts,
                    data=data,
                    schema_version="1.0" if not schema_changed else "2.0",
                )
            )

        quality_report = DataQualityReport(
            source=source,
            total_records=self.config.n_records,
            valid_records=valid_count,
            flags=flags,
            schema_match=not schema_changed,
            reliability_score=valid_count / self.config.n_records if self.config.n_records else 0.0,
        )

        return CollectionResult(events=events, quality_report=quality_report)

    def _generate_day(self, rng: np.random.Generator, day: int, is_outlier: bool) -> dict[str, Any]:
        seasonal = math.sin(2 * math.pi * day / SEASONAL_CYCLE_DAYS)
        noise_price = rng.normal(0, DAILY_NOISE_SCALE)
        noise_demand = rng.normal(0, DAILY_NOISE_SCALE)

        price = self.config.base_price * (1 + 0.1 * seasonal + noise_price)
        demand = self.config.base_demand * (1 - 0.08 * seasonal + noise_demand)

        if is_outlier and rng.random() < OUTLIER_TRIGGER_PROBABILITY:
            price *= 1 + OUTLIER_SIGMA * DAILY_NOISE_SCALE * rng.choice([-1, 1])

        if self.config.anomaly_start is not None and day >= self.config.anomaly_start:
            price *= 1 + self.config.anomaly_magnitude

        data: dict[str, Any] = {}
        if "price" in self.config.signals:
            data["price"] = round(price, 2)
        if "demand" in self.config.signals:
            data["demand"] = round(demand, 2)
        return data

    def _apply_schema_change(self, data: dict[str, Any]) -> dict[str, Any]:
        if "price" in data:
            data["price_usd"] = data.pop("price")
        return data

    def _inject_failure(
        self, rng: np.random.Generator, data: dict[str, Any], day: int
    ) -> tuple[dict[str, Any], list[QualityFlag]]:
        flags: list[QualityFlag] = []
        failure_type = rng.choice(["missing", "null", "type_mismatch"])

        match failure_type:
            case "missing":
                key = rng.choice(list(data.keys())) if data else "price"
                data.pop(str(key), None)
                flags.append(
                    QualityFlag(
                        field_name=str(key),
                        issue="missing",
                        severity="warning",
                        details=f"Field missing at day {day}",
                    )
                )
            case "null":
                key = rng.choice(list(data.keys())) if data else "price"
                data[str(key)] = None
                flags.append(
                    QualityFlag(
                        field_name=str(key),
                        issue="null_value",
                        severity="warning",
                        details=f"Null injected at day {day}",
                    )
                )
            case "type_mismatch":
                key = rng.choice(list(data.keys())) if data else "price"
                data[str(key)] = "INVALID"
                flags.append(
                    QualityFlag(
                        field_name=str(key),
                        issue="type_mismatch",
                        severity="error",
                        details=f"Type mismatch at day {day}: expected float, got str",
                    )
                )

        return data, flags
