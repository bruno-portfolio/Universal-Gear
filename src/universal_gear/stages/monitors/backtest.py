"""Backtest monitor — compares past decisions against simulated or real outcomes."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from universal_gear.core.contracts import (
    DecisionObject,
    DecisionResult,
    FeedbackResult,
    PredictionVsReality,
    Scorecard,
)
from universal_gear.core.interfaces import BaseMonitor
from universal_gear.core.registry import register_monitor

DEFAULT_SIMULATED_NOISE = 0.05
BENEFICIAL_THRESHOLD = 0.02
DETRIMENTAL_THRESHOLD = -0.02


class BacktestConfig(BaseModel):
    """Configuration for the backtest monitor."""

    seed: int = 42
    simulated_noise: float = DEFAULT_SIMULATED_NOISE
    use_simulated_actuals: bool = True


@register_monitor("backtest")
class BacktestMonitor(BaseMonitor[BacktestConfig]):
    """Evaluates decisions by comparing predictions to (simulated) actuals."""

    async def evaluate(self, decision: DecisionResult) -> FeedbackResult:
        rng = np.random.default_rng(self.config.seed)
        scorecards: list[Scorecard] = []

        for dec in decision.decisions:
            scorecard = self._evaluate_decision(dec, rng)
            scorecards.append(scorecard)

        return FeedbackResult(
            scorecards=scorecards,
            sources_updated=0,
            thresholds_adjusted=0,
        )

    def _evaluate_decision(self, dec: DecisionObject, rng: np.random.Generator) -> Scorecard:
        predictions: list[PredictionVsReality] = []

        for condition in dec.conditions:
            predicted = condition.threshold
            noise = rng.normal(0, self.config.simulated_noise)
            actual = predicted * (1 + noise)
            error_pct = abs(actual - predicted) / abs(predicted) * 100 if predicted else 0.0

            within_ci = error_pct < (self.config.simulated_noise * 100 * 2)

            predictions.append(
                PredictionVsReality(
                    metric=condition.metric,
                    predicted=round(predicted, 4),
                    actual=round(actual, 4),
                    error_pct=round(error_pct, 2),
                    within_confidence=within_ci,
                )
            )

        if not predictions:
            predictions.append(
                PredictionVsReality(
                    metric="overall_confidence",
                    predicted=dec.confidence,
                    actual=dec.confidence * (1 + rng.normal(0, self.config.simulated_noise)),
                    error_pct=round(self.config.simulated_noise * 100, 2),
                    within_confidence=True,
                )
            )

        outcome = self._assess_outcome(predictions)

        adjustments: list[str] = []
        if outcome == "detrimental":
            adjustments.append("Consider tightening risk thresholds")
            adjustments.append("Review sensitivity weights for key variables")

        return Scorecard(
            decision_id=dec.decision_id,
            predictions_vs_reality=predictions,
            decision_outcome=outcome,
            model_adjustments=adjustments,
        )

    def _assess_outcome(self, predictions: list[PredictionVsReality]) -> str:
        if not predictions:
            return "neutral"

        within_count = sum(1 for p in predictions if p.within_confidence)
        hit_rate = within_count / len(predictions)

        if hit_rate > (1 + BENEFICIAL_THRESHOLD) / 2:
            return "beneficial"
        if hit_rate < (1 + DETRIMENTAL_THRESHOLD) / 2:
            return "detrimental"
        return "neutral"
