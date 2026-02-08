"""Z-score rolling-window anomaly detector."""

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

DEFAULT_WINDOW_SIZE = 10
DEFAULT_ZSCORE_THRESHOLD = 2.0
HYPOTHESIS_VALIDITY_DAYS = 14
MIN_WINDOW_FILL = 3


class ZScoreAnalyzerConfig(BaseModel):
    """Configuration for rolling z-score detection."""

    window_size: int = DEFAULT_WINDOW_SIZE
    threshold: float = DEFAULT_ZSCORE_THRESHOLD
    signals_to_watch: list[str] = Field(default_factory=lambda: ["price"])
    validity_days: int = HYPOTHESIS_VALIDITY_DAYS


@register_analyzer("zscore")
class ZScoreDetector(BaseAnalyzer[ZScoreAnalyzerConfig]):
    """Flags statistical outliers using a rolling z-score window."""

    async def analyze(self, compression: CompressionResult) -> HypothesisResult:
        hypotheses: list[Hypothesis] = []

        for signal_name in self.config.signals_to_watch:
            signal_hyps = self._analyze_signal(compression.states, signal_name)
            hypotheses.extend(signal_hyps)

        return HypothesisResult(
            hypotheses=hypotheses,
            states_analyzed=len(compression.states),
        )

    def _analyze_signal(self, states: list[MarketState], signal_name: str) -> list[Hypothesis]:
        values = self._extract_signal(states, signal_name)
        if len(values) < MIN_WINDOW_FILL:
            return []

        window = values[-self.config.window_size :]
        arr = np.array(window)
        mean = float(np.mean(arr[:-1]))
        std = float(np.std(arr[:-1]))

        if std == 0:
            return []

        current = arr[-1]
        zscore = (current - mean) / std

        if abs(zscore) < self.config.threshold:
            return []

        direction = "above" if zscore > 0 else "below"
        source_ids = [s.state_id for s in states[-self.config.window_size :]]
        now = datetime.now(UTC)

        return [
            Hypothesis(
                statement=(
                    f"Statistical outlier: '{signal_name}' z-score {zscore:.2f} "
                    f"({direction} rolling mean)"
                ),
                rationale=(
                    f"Rolling window of {len(window)} periods: "
                    f"mean={mean:.2f}, std={std:.2f}, current={current:.2f}, "
                    f"z-score={zscore:.2f}."
                ),
                status=HypothesisStatus.PENDING,
                confidence=min(abs(zscore) / (self.config.threshold * 2), 1.0),
                valid_until=now + timedelta(days=self.config.validity_days),
                validation_criteria=[
                    ValidationCriterion(
                        metric=f"{signal_name}_zscore",
                        operator="gt" if zscore > 0 else "lt",
                        threshold=self.config.threshold if zscore > 0 else -self.config.threshold,
                        description=f"Z-score remains {direction} threshold",
                    ),
                ],
                falsification_criteria=[
                    ValidationCriterion(
                        metric=f"{signal_name}_zscore",
                        operator="between",
                        threshold=(-1.0, 1.0),
                        description="Z-score returns to normal range (-1, 1)",
                    ),
                ],
                competing_hypotheses=["seasonal_shift", "measurement_error"],
                source_states=source_ids,
            )
        ]

    def _extract_signal(self, states: list[MarketState], signal_name: str) -> list[float]:
        values: list[float] = []
        for state in states:
            for signal in state.signals:
                if signal.name == signal_name:
                    values.append(signal.value)
                    break
        return values
