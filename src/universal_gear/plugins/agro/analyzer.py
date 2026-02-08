"""Agro analyzer — generates market hypotheses specific to agricultural commodities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

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
from universal_gear.plugins.agro.config import AgroConfig

SEASONAL_DEVIATION_THRESHOLD = 1.5
SPREAD_THRESHOLD_PCT = 5.0
MIN_STATES_FOR_ANALYSIS = 3
HYPOTHESIS_VALIDITY_DAYS = 30


@register_analyzer("agro")
class AgroAnalyzer(BaseAnalyzer[AgroConfig]):
    """Detects agro-specific anomalies: seasonal price deviations and spread signals."""

    async def analyze(self, compression: CompressionResult) -> HypothesisResult:
        hypotheses: list[Hypothesis] = []

        if len(compression.states) >= MIN_STATES_FOR_ANALYSIS:
            hypotheses.extend(self._check_seasonal_price(compression.states))
            hypotheses.extend(self._check_price_trend(compression.states))

        if not hypotheses:
            hypotheses.append(self._null_hypothesis(compression.states))

        return HypothesisResult(
            hypotheses=hypotheses,
            states_analyzed=len(compression.states),
        )

    def _null_hypothesis(self, states: list[MarketState]) -> Hypothesis:
        """Generate a null hypothesis when no anomalies are detected."""
        now = datetime.now(UTC)
        source_ids = [s.state_id for s in states[-3:]] if states else []
        prices = _extract_signal(states, "price")
        summary = f"{prices[-1]:.2f}" if prices else "N/A"

        return Hypothesis(
            statement=(
                f"{self.config.commodity.title()} price within normal range ({summary})"
            ),
            rationale=(
                f"No seasonal deviations or persistent trends detected "
                f"across {len(states)} weekly states. "
                f"Market conditions are within historical parameters."
            ),
            status=HypothesisStatus.PENDING,
            confidence=0.8,
            valid_until=now + timedelta(days=14),
            validation_criteria=[
                ValidationCriterion(
                    metric="price_deviation_std",
                    operator="between",
                    threshold=(-SEASONAL_DEVIATION_THRESHOLD, SEASONAL_DEVIATION_THRESHOLD),
                    description="Price remains within seasonal norms",
                ),
            ],
            falsification_criteria=[
                ValidationCriterion(
                    metric="price_deviation_std",
                    operator="gt",
                    threshold=SEASONAL_DEVIATION_THRESHOLD,
                    description="Price breaks out of seasonal range",
                ),
            ],
            competing_hypotheses=["delayed_reaction", "new_equilibrium"],
            source_states=source_ids,
        )

    def _check_seasonal_price(self, states: list[MarketState]) -> list[Hypothesis]:
        prices = _extract_signal(states, "price")
        if len(prices) < MIN_STATES_FOR_ANALYSIS:
            return []

        arr = np.array(prices)
        mean = float(np.mean(arr[:-1]))
        std = float(np.std(arr[:-1]))
        if std == 0:
            return []

        current = arr[-1]
        deviation = (current - mean) / std

        if abs(deviation) < SEASONAL_DEVIATION_THRESHOLD:
            return []

        direction = "above" if deviation > 0 else "below"
        now = datetime.now(UTC)
        source_ids = [s.state_id for s in states]

        return [
            Hypothesis(
                statement=(
                    f"{self.config.commodity.title()} price {abs(deviation):.1f} std devs "
                    f"{direction} seasonal mean"
                ),
                rationale=(
                    f"Current price {current:.2f} vs mean {mean:.2f} (std {std:.2f}). "
                    f"This may indicate a supply/demand imbalance for {self.config.commodity}."
                ),
                status=HypothesisStatus.PENDING,
                confidence=min(abs(deviation) / (SEASONAL_DEVIATION_THRESHOLD * 2), 1.0),
                valid_until=now + timedelta(days=HYPOTHESIS_VALIDITY_DAYS),
                validation_criteria=[
                    ValidationCriterion(
                        metric="price_deviation_std",
                        operator="gt" if deviation > 0 else "lt",
                        threshold=SEASONAL_DEVIATION_THRESHOLD,
                        description=(
                            f"Price deviation persists beyond"
                            f" {SEASONAL_DEVIATION_THRESHOLD} std devs"
                        ),
                    ),
                ],
                falsification_criteria=[
                    ValidationCriterion(
                        metric="price_deviation_std",
                        operator="between",
                        threshold=(-1.0, 1.0),
                        description="Price returns within 1 std dev of seasonal mean",
                    ),
                ],
                competing_hypotheses=[
                    "harvest_break",
                    "exchange_rate_shock",
                    "data_collection_error",
                ],
                source_states=source_ids,
            )
        ]

    def _check_price_trend(self, states: list[MarketState]) -> list[Hypothesis]:
        prices = _extract_signal(states, "price")
        if len(prices) < MIN_STATES_FOR_ANALYSIS:
            return []

        recent = prices[-3:]
        is_rising = all(recent[i] > recent[i - 1] for i in range(1, len(recent)))
        is_falling = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))

        if not is_rising and not is_falling:
            return []

        direction = "rising" if is_rising else "falling"
        pct_change = (recent[-1] - recent[0]) / recent[0] * 100 if recent[0] else 0
        now = datetime.now(UTC)
        source_ids = [s.state_id for s in states[-3:]]

        return [
            Hypothesis(
                statement=(
                    f"{self.config.commodity.title()} price {direction} "
                    f"({pct_change:+.1f}% over 3 periods)"
                ),
                rationale=(
                    f"Consistent {direction} trend detected: "
                    f"{recent[0]:.2f} -> {recent[-1]:.2f} ({pct_change:+.1f}%)."
                ),
                status=HypothesisStatus.PENDING,
                confidence=min(abs(pct_change) / 10, 1.0),
                valid_until=now + timedelta(days=14),
                validation_criteria=[
                    ValidationCriterion(
                        metric="price_trend_direction",
                        operator="gt" if is_rising else "lt",
                        threshold=0.0,
                        description=f"Price continues {direction}",
                    ),
                ],
                falsification_criteria=[
                    ValidationCriterion(
                        metric="price_trend_reversal",
                        operator="lt" if is_rising else "gt",
                        threshold=0.0,
                        description=f"Price reverses {direction} trend",
                    ),
                ],
                competing_hypotheses=["seasonal_pattern", "one_off_event"],
                source_states=source_ids,
            )
        ]


def _extract_signal(states: list[MarketState], signal_name: str) -> list[float]:
    values: list[float] = []
    for state in states:
        for signal in state.signals:
            if signal.name == signal_name:
                values.append(signal.value)
                break
    return values
