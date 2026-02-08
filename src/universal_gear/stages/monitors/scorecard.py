"""Scorecard formatter -- aggregated metrics from feedback scorecards."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from universal_gear.core.contracts import FeedbackResult, Scorecard

PERFECT_HIT_RATE = 1.0


def hit_rate(scorecard: Scorecard) -> float:
    """Fraction of predictions within confidence interval."""
    preds = scorecard.predictions_vs_reality
    if not preds:
        return 0.0
    return sum(1 for p in preds if p.within_confidence) / len(preds)


def mean_absolute_error(scorecard: Scorecard) -> float:
    """Mean absolute error percentage across predictions."""
    preds = scorecard.predictions_vs_reality
    if not preds:
        return 0.0
    return sum(abs(p.error_pct) for p in preds) / len(preds)


def bias(scorecard: Scorecard) -> float:
    """Mean signed error -- positive means over-prediction."""
    preds = scorecard.predictions_vs_reality
    if not preds:
        return 0.0
    return sum(p.error_pct for p in preds) / len(preds)


def summary(feedback: FeedbackResult) -> dict[str, float]:
    """Aggregate metrics across all scorecards in a FeedbackResult."""
    if not feedback.scorecards:
        return {"hit_rate": 0.0, "mae": 0.0, "bias": 0.0}

    rates = [hit_rate(s) for s in feedback.scorecards]
    maes = [mean_absolute_error(s) for s in feedback.scorecards]
    biases = [bias(s) for s in feedback.scorecards]

    n = len(feedback.scorecards)
    return {
        "hit_rate": sum(rates) / n,
        "mae": sum(maes) / n,
        "bias": sum(biases) / n,
    }
