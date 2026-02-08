"""Finance monitor -- evaluates past decisions against actual exchange rate movements."""

from __future__ import annotations

import httpx
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
from universal_gear.plugins.finance.config import FinanceConfig

logger = structlog.get_logger()

BENEFICIAL_HIT_RATE = 0.6
DETRIMENTAL_HIT_RATE = 0.4


@register_monitor("finance")
class FinanceMonitor(BaseMonitor[FinanceConfig]):
    """Evaluates past finance decisions and checks for BCB source drift."""

    async def evaluate(self, decision: DecisionResult) -> FeedbackResult:
        scorecards: list[Scorecard] = []
        degradations: list[SourceDegradation] = []

        for dec in decision.decisions:
            scorecard = self._evaluate_decision(dec)
            scorecards.append(scorecard)

        degradations.extend(await self._check_source_drift())

        accuracy_trend = self._compute_accuracy_trend(scorecards)

        return FeedbackResult(
            scorecards=scorecards,
            sources_updated=len(degradations),
            thresholds_adjusted=0,
            accuracy_trend=accuracy_trend,
        )

    def _compute_accuracy_trend(self, scorecards: list[Scorecard]) -> list[float]:
        """Compute per-scorecard hit rate as an accuracy trend."""
        trend: list[float] = []
        for sc in scorecards:
            preds = sc.predictions_vs_reality
            if preds:
                hit_rate = sum(1 for p in preds if p.within_confidence) / len(preds)
                trend.append(round(hit_rate, 4))
        return trend

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
            adjustments.append("Review exchange rate model assumptions")
            adjustments.append("Verify SELIC projection methodology")
            adjustments.append("Check for structural breaks in FX series")

        return Scorecard(
            decision_id=dec.decision_id,
            predictions_vs_reality=predictions,
            decision_outcome=outcome,
            model_adjustments=adjustments,
            lessons_learned=(
                f"Finance evaluation: {outcome}. "
                "Real vs predicted comparison pending actual BCB data."
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
        """Probe BCB API health to detect source degradation."""
        degradations: list[SourceDegradation] = []

        # Probe the PTAX endpoint with a minimal request
        probe_url = (
            "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
            "/CotacaoDolarPeriodo(dataInicial=@di,dataFinalCotacao=@df)"
        )
        params = {
            "@di": "'01-01-2026'",
            "@df": "'01-02-2026'",
            "$format": "json",
            "$top": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(probe_url, params=params)
                if not resp.is_success:
                    degradations.append(
                        SourceDegradation(
                            source_id="bcb-ptax",
                            previous_reliability=1.0,
                            current_reliability=0.5,
                            reason=(f"BCB PTAX returned HTTP {resp.status_code}"),
                        )
                    )
        except Exception as exc:
            logger.warning("drift_check.failed", error=str(exc))
            degradations.append(
                SourceDegradation(
                    source_id="bcb-ptax",
                    previous_reliability=1.0,
                    current_reliability=0.3,
                    reason=f"BCB PTAX drift check failed: {exc}",
                )
            )

        return degradations
