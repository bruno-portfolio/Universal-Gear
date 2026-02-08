"""Finance analyzer -- generates macroeconomic hypotheses from Brazilian market data."""

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
from universal_gear.plugins.finance.config import FinanceConfig

ZSCORE_ANOMALY_THRESHOLD = 2.0
VOLATILITY_SPIKE_THRESHOLD = 1.5
MIN_STATES_FOR_ANALYSIS = 3
HYPOTHESIS_VALIDITY_DAYS = 30
TREND_PERIODS = 3


@register_analyzer("finance")
class FinanceAnalyzer(BaseAnalyzer[FinanceConfig]):
    """Detects exchange rate anomalies, trends, and volatility spikes."""

    async def analyze(self, compression: CompressionResult) -> HypothesisResult:
        hypotheses: list[Hypothesis] = []

        if len(compression.states) >= MIN_STATES_FOR_ANALYSIS:
            hypotheses.extend(self._check_exchange_anomaly(compression.states))
            hypotheses.extend(self._check_trend(compression.states))
            hypotheses.extend(self._check_volatility_spike(compression.states))

        if not hypotheses:
            hypotheses.append(self._null_hypothesis(compression.states))

        return HypothesisResult(
            hypotheses=hypotheses,
            states_analyzed=len(compression.states),
        )

    def _null_hypothesis(self, states: list[MarketState]) -> Hypothesis:
        """Generate a null hypothesis when no anomalies are detected."""
        now = datetime.now(UTC)
        source_ids = [s.state_id for s in states[-TREND_PERIODS:]] if states else []
        rates = _extract_signal(states, "exchange_rate")
        summary = f"{rates[-1]:.4f}" if rates else "N/A"

        return Hypothesis(
            statement=f"USD/BRL within normal range ({summary})",
            rationale=(
                f"No anomalies, trends, or volatility spikes detected "
                f"across {len(states)} weekly states. "
                f"Market conditions are within historical parameters."
            ),
            status=HypothesisStatus.PENDING,
            confidence=0.8,
            valid_until=now + timedelta(days=14),
            validation_criteria=[
                ValidationCriterion(
                    metric="exchange_rate_zscore",
                    operator="between",
                    threshold=(-ZSCORE_ANOMALY_THRESHOLD, ZSCORE_ANOMALY_THRESHOLD),
                    description="Exchange rate remains within normal range",
                ),
            ],
            falsification_criteria=[
                ValidationCriterion(
                    metric="exchange_rate_zscore",
                    operator="gt",
                    threshold=ZSCORE_ANOMALY_THRESHOLD,
                    description="Exchange rate breaks out of normal range",
                ),
            ],
            competing_hypotheses=["calm_before_storm", "structural_stability"],
            source_states=source_ids,
        )

    def _check_exchange_anomaly(self, states: list[MarketState]) -> list[Hypothesis]:
        """Detect z-score anomalies in exchange rate signals."""
        prices = _extract_signal(states, "exchange_rate")
        if len(prices) < MIN_STATES_FOR_ANALYSIS:
            return []

        arr = np.array(prices)
        mean = float(np.mean(arr[:-1]))
        std = float(np.std(arr[:-1]))
        if std == 0:
            return []

        current = arr[-1]
        zscore = (current - mean) / std

        if abs(zscore) < ZSCORE_ANOMALY_THRESHOLD:
            return []

        direction = "above" if zscore > 0 else "below"
        now = datetime.now(UTC)
        source_ids = [s.state_id for s in states]

        return [
            Hypothesis(
                statement=(f"USD/BRL rate {abs(zscore):.1f} std devs {direction} recent mean"),
                rationale=(
                    f"Current rate {current:.4f} vs mean {mean:.4f} "
                    f"(std {std:.4f}). This may indicate a macro shift "
                    f"in the BRL exchange rate."
                ),
                status=HypothesisStatus.PENDING,
                confidence=min(abs(zscore) / (ZSCORE_ANOMALY_THRESHOLD * 2), 1.0),
                valid_until=now + timedelta(days=HYPOTHESIS_VALIDITY_DAYS),
                validation_criteria=[
                    ValidationCriterion(
                        metric="exchange_rate_zscore",
                        operator="gt" if zscore > 0 else "lt",
                        threshold=ZSCORE_ANOMALY_THRESHOLD,
                        description=(
                            f"Exchange rate deviation persists beyond "
                            f"{ZSCORE_ANOMALY_THRESHOLD} std devs"
                        ),
                    ),
                ],
                falsification_criteria=[
                    ValidationCriterion(
                        metric="exchange_rate_zscore",
                        operator="between",
                        threshold=(-1.0, 1.0),
                        description=("Exchange rate returns within 1 std dev of mean"),
                    ),
                ],
                competing_hypotheses=[
                    "monetary_policy_shift",
                    "external_shock",
                    "seasonal_fx_flow",
                ],
                source_states=source_ids,
            )
        ]

    def _check_trend(self, states: list[MarketState]) -> list[Hypothesis]:
        """Detect 3-period rising/falling trends in any signal."""
        hypotheses: list[Hypothesis] = []

        for signal_name in ("exchange_rate", "selic_rate", "ipca_rate"):
            values = _extract_signal(states, signal_name)
            if len(values) < TREND_PERIODS:
                continue

            recent = values[-TREND_PERIODS:]
            is_rising = all(recent[i] > recent[i - 1] for i in range(1, len(recent)))
            is_falling = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))

            if not is_rising and not is_falling:
                continue

            direction = "rising" if is_rising else "falling"
            pct_change = (recent[-1] - recent[0]) / recent[0] * 100 if recent[0] else 0
            now = datetime.now(UTC)
            source_ids = [s.state_id for s in states[-TREND_PERIODS:]]

            label = signal_name.replace("_", " ").title()
            hypotheses.append(
                Hypothesis(
                    statement=(
                        f"{label} {direction} ({pct_change:+.1f}% over {TREND_PERIODS} periods)"
                    ),
                    rationale=(
                        f"Consistent {direction} trend: "
                        f"{recent[0]:.4f} -> {recent[-1]:.4f} "
                        f"({pct_change:+.1f}%)."
                    ),
                    status=HypothesisStatus.PENDING,
                    confidence=min(abs(pct_change) / 10, 1.0),
                    valid_until=now + timedelta(days=14),
                    validation_criteria=[
                        ValidationCriterion(
                            metric=f"{signal_name}_trend",
                            operator="gt" if is_rising else "lt",
                            threshold=0.0,
                            description=f"{label} continues {direction}",
                        ),
                    ],
                    falsification_criteria=[
                        ValidationCriterion(
                            metric=f"{signal_name}_trend_reversal",
                            operator="lt" if is_rising else "gt",
                            threshold=0.0,
                            description=(f"{label} reverses {direction} trend"),
                        ),
                    ],
                    competing_hypotheses=[
                        "mean_reversion",
                        "regime_change",
                    ],
                    source_states=source_ids,
                )
            )

        return hypotheses

    def _check_volatility_spike(self, states: list[MarketState]) -> list[Hypothesis]:
        """Detect volatility spikes using rolling standard deviation."""
        prices = _extract_signal(states, "exchange_rate")
        if len(prices) < MIN_STATES_FOR_ANALYSIS + 1:
            return []

        arr = np.array(prices)
        returns = np.diff(arr) / arr[:-1]
        if len(returns) < MIN_STATES_FOR_ANALYSIS:
            return []

        historical_vol = float(np.std(returns[:-1]))
        if historical_vol == 0:
            return []

        current_return = abs(returns[-1])
        vol_ratio = current_return / historical_vol

        if vol_ratio < VOLATILITY_SPIKE_THRESHOLD:
            return []

        now = datetime.now(UTC)
        source_ids = [s.state_id for s in states]

        return [
            Hypothesis(
                statement=(f"USD/BRL volatility spike detected ({vol_ratio:.1f}x historical)"),
                rationale=(
                    f"Latest period return {current_return:.4f} vs "
                    f"historical vol {historical_vol:.4f}. "
                    f"Elevated volatility may persist."
                ),
                status=HypothesisStatus.PENDING,
                confidence=min(vol_ratio / 3.0, 1.0),
                valid_until=now + timedelta(days=14),
                validation_criteria=[
                    ValidationCriterion(
                        metric="volatility_ratio",
                        operator="gt",
                        threshold=VOLATILITY_SPIKE_THRESHOLD,
                        description=("Volatility remains elevated vs historical"),
                    ),
                ],
                falsification_criteria=[
                    ValidationCriterion(
                        metric="volatility_ratio",
                        operator="lt",
                        threshold=1.0,
                        description=("Volatility returns to historical levels"),
                    ),
                ],
                competing_hypotheses=[
                    "event_driven_spike",
                    "liquidity_squeeze",
                    "data_anomaly",
                ],
                source_states=source_ids,
            )
        ]


def _extract_signal(states: list[MarketState], signal_name: str) -> list[float]:
    """Extract values for a named signal across MarketStates."""
    values: list[float] = []
    for state in states:
        for signal in state.signals:
            if signal.name == signal_name:
                values.append(signal.value)
                break
    return values
