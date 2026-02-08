"""Seasonal anomaly detector — compares current values against historical seasonal baseline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
from pydantic import BaseModel, Field

from universal_gear.core.contracts import (
    CompressionResult,
    Hypothesis,
    HypothesisResult,
    HypothesisStatus,
    MarketState,
    ValidationCriterion,
)
from universal_gear.core.interfaces import BaseAnalyzer
from universal_gear.core.registry import register_analyzer

DEFAULT_CYCLE_PERIODS = 12
DEFAULT_DEVIATION_THRESHOLD = 2.0
HYPOTHESIS_VALIDITY_DAYS = 30
MIN_PERIODS_FOR_BASELINE = 4


class SeasonalAnalyzerConfig(BaseModel):
    """Configuration for seasonal anomaly detection."""

    cycle_periods: int = DEFAULT_CYCLE_PERIODS
    deviation_threshold: float = DEFAULT_DEVIATION_THRESHOLD
    signals_to_watch: list[str] = Field(default_factory=lambda: ["price"])
    validity_days: int = HYPOTHESIS_VALIDITY_DAYS


@register_analyzer("seasonal")
class SeasonalAnomalyDetector(BaseAnalyzer[SeasonalAnalyzerConfig]):
    """Detects deviations from historical seasonal patterns."""

    async def analyze(self, compression: CompressionResult) -> HypothesisResult:
        hypotheses: list[Hypothesis] = []

        for signal_name in self.config.signals_to_watch:
            signal_hypotheses = self._analyze_signal(compression.states, signal_name)
            hypotheses.extend(signal_hypotheses)

        return HypothesisResult(
            hypotheses=hypotheses,
            states_analyzed=len(compression.states),
        )

    def _analyze_signal(
        self, states: list[MarketState], signal_name: str
    ) -> list[Hypothesis]:
        values = self._extract_signal(states, signal_name)
        if len(values) < MIN_PERIODS_FOR_BASELINE:
            return []

        arr = np.array(values)
        mean = float(np.mean(arr[:-1]))
        std = float(np.std(arr[:-1]))

        if std == 0:
            return []

        current = arr[-1]
        deviation = abs(current - mean) / std

        if deviation < self.config.deviation_threshold:
            return []

        direction = "above" if current > mean else "below"
        source_ids = [s.state_id for s in states]
        now = datetime.now(UTC)

        return [
            Hypothesis(
                statement=(
                    f"Signal '{signal_name}' is {deviation:.1f} std devs "
                    f"{direction} seasonal mean"
                ),
                rationale=(
                    f"Current value {current:.2f} vs seasonal mean {mean:.2f} "
                    f"(std {std:.2f}). Deviation of {deviation:.1f} standard deviations "
                    f"exceeds threshold {self.config.deviation_threshold}."
                ),
                status=HypothesisStatus.PENDING,
                confidence=min(deviation / (self.config.deviation_threshold * 2), 1.0),
                valid_until=now + timedelta(days=self.config.validity_days),
                validation_criteria=[
                    ValidationCriterion(
                        metric=f"{signal_name}_deviation_pct",
                        operator="gt",
                        threshold=self.config.deviation_threshold,
                        description=(
                            f"Deviation persists above "
                            f"{self.config.deviation_threshold} std devs"
                        ),
                    ),
                ],
                falsification_criteria=[
                    ValidationCriterion(
                        metric=f"{signal_name}_deviation_pct",
                        operator="lt",
                        threshold=1.0,
                        description=f"Signal '{signal_name}' returns within 1 std dev of mean",
                    ),
                ],
                competing_hypotheses=["data_collection_error", "one_off_event"],
                source_states=source_ids,
            )
        ]

    def _extract_signal(
        self, states: list[MarketState], signal_name: str
    ) -> list[float]:
        values: list[float] = []
        for state in states:
            for signal in state.signals:
                if signal.name == signal_name:
                    values.append(signal.value)
                    break
        return values
