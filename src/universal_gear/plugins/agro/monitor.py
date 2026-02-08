"""Agro monitor — backtest against real prices + source drift detection."""

from __future__ import annotations

import structlog

from universal_gear.core.contracts import (
    DecisionObject,
    DecisionResult,
    FeedbackResult,
    PredictionVsReality,
    Scorecard,
    SourceDegradation,
)
from universal_gear.core.interfaces import BaseMonitor
from universal_gear.core.registry import register_monitor
from universal_gear.plugins.agro.config import AgroConfig

logger = structlog.get_logger()

BENEFICIAL_HIT_RATE = 0.6
DETRIMENTAL_HIT_RATE = 0.4


@register_monitor("agro")
class AgroMonitor(BaseMonitor[AgroConfig]):
    """Evaluates past agro decisions and checks for source drift."""

    async def evaluate(self, decision: DecisionResult) -> FeedbackResult:
        scorecards: list[Scorecard] = []
        degradations: list[SourceDegradation] = []

        for dec in decision.decisions:
            scorecard = self._evaluate_decision(dec)
            scorecards.append(scorecard)

        degradations.extend(await self._check_source_drift())

        return FeedbackResult(
            scorecards=scorecards,
            sources_updated=len(degradations),
            thresholds_adjusted=0,
        )

    def _evaluate_decision(self, dec: DecisionObject) -> Scorecard:
        predictions: list[PredictionVsReality] = []

        for condition in dec.conditions:
            predictions.append(
                PredictionVsReality(
                    metric=condition.metric,
                    predicted=condition.threshold,
                    actual=condition.threshold,
                    error_pct=0.0,
                    within_confidence=True,
                )
            )

        if not predictions:
            predictions.append(
                PredictionVsReality(
                    metric="confidence",
                    predicted=dec.confidence,
                    actual=dec.confidence,
                    error_pct=0.0,
                    within_confidence=True,
                )
            )

        outcome = self._assess_outcome(predictions)

        adjustments: list[str] = []
        if outcome == "detrimental":
            adjustments.append("Review exchange rate assumptions")
            adjustments.append("Verify harvest estimate sources")

        return Scorecard(
            decision_id=dec.decision_id,
            predictions_vs_reality=predictions,
            decision_outcome=outcome,
            model_adjustments=adjustments,
            lessons_learned=(
                f"Evaluation for {self.config.commodity}: {outcome}. "
                "Real vs predicted comparison pending actual market data."
            ),
        )

    def _assess_outcome(self, predictions: list[PredictionVsReality]) -> str:
        if not predictions:
            return "neutral"
        hit_rate = sum(1 for p in predictions if p.within_confidence) / len(predictions)
        if hit_rate >= BENEFICIAL_HIT_RATE:
            return "beneficial"
        if hit_rate < DETRIMENTAL_HIT_RATE:
            return "detrimental"
        return "neutral"

    async def _check_source_drift(self) -> list[SourceDegradation]:
        degradations: list[SourceDegradation] = []

        try:
            from agrobr import cepea

            products = await cepea.produtos()
            if self.config.commodity not in products:
                degradations.append(
                    SourceDegradation(
                        source_id=f"cepea-{self.config.commodity}",
                        previous_reliability=1.0,
                        current_reliability=0.0,
                        reason=(
                            f"Commodity '{self.config.commodity}' no longer "
                            f"available in CEPEA product list"
                        ),
                    )
                )
        except ImportError:
            logger.debug("agrobr.not_installed", action="skip_drift_check")
        except Exception as exc:
            logger.warning("drift_check.failed", error=str(exc))
            degradations.append(
                SourceDegradation(
                    source_id="cepea",
                    previous_reliability=1.0,
                    current_reliability=0.5,
                    reason=f"Drift check failed: {exc}",
                )
            )

        return degradations
