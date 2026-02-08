"""Pipeline orchestrator — runs the six stages in sequence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from universal_gear.core.exceptions import PipelineError, StageTransitionError
from universal_gear.core.metrics import PipelineMetrics, StageMetrics

if TYPE_CHECKING:
    from universal_gear.core.contracts import (
        CollectionResult,
        CompressionResult,
        DecisionResult,
        FeedbackResult,
        HypothesisResult,
        SimulationResult,
    )
    from universal_gear.core.interfaces import (
        BaseAnalyzer,
        BaseCollector,
        BaseDecider,
        BaseMonitor,
        BaseProcessor,
        BaseSimulator,
    )

logger = structlog.get_logger()

MIN_RELIABILITY_SCORE = 0.1


@dataclass
class PipelineResult:
    """Aggregated result of a full pipeline execution."""

    collection: CollectionResult | None = None
    compression: CompressionResult | None = None
    hypothesis: HypothesisResult | None = None
    simulation: SimulationResult | None = None
    decision: DecisionResult | None = None
    feedback: FeedbackResult | None = None
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
    success: bool = False
    error: str | None = None


class Pipeline:
    """Orchestrates the six stages of the Universal Gear framework."""

    def __init__(
        self,
        collector: BaseCollector[Any],
        processor: BaseProcessor[Any],
        analyzer: BaseAnalyzer[Any],
        model: BaseSimulator[Any],
        action: BaseDecider[Any],
        monitor: BaseMonitor[Any],
        *,
        fail_fast: bool = True,
        validate_transitions: bool = True,
    ) -> None:
        self.collector = collector
        self.processor = processor
        self.analyzer = analyzer
        self.model = model
        self.action = action
        self.monitor = monitor
        self.fail_fast = fail_fast
        self.validate_transitions = validate_transitions
        self._log = logger.bind(pipeline="universal-gear")

    async def run(self) -> PipelineResult:
        """Execute all six stages sequentially."""
        result = PipelineResult()
        pipeline_start = datetime.now(UTC)

        stages: list[tuple[str, Any]] = [
            ("observation", self._run_collection),
            ("compression", self._run_compression),
            ("hypothesis", self._run_hypothesis),
            ("simulation", self._run_simulation),
            ("decision", self._run_decision),
            ("feedback", self._run_feedback),
        ]

        for stage_name, stage_fn in stages:
            stage_start = datetime.now(UTC)
            try:
                self._log.info("stage.started", stage=stage_name)
                await stage_fn(result)
                elapsed = (datetime.now(UTC) - stage_start).total_seconds()
                result.metrics.add(
                    StageMetrics(stage=stage_name, duration_seconds=elapsed, success=True)
                )
                self._log.info("stage.completed", stage=stage_name, duration=elapsed)

            except Exception as exc:
                elapsed = (datetime.now(UTC) - stage_start).total_seconds()
                result.metrics.add(
                    StageMetrics(
                        stage=stage_name,
                        duration_seconds=elapsed,
                        success=False,
                        error=str(exc),
                    )
                )
                self._log.error("stage.failed", stage=stage_name, error=str(exc))

                if self.fail_fast:
                    result.error = f"Pipeline failed at '{stage_name}': {exc}"
                    return result

        result.success = True
        total = (datetime.now(UTC) - pipeline_start).total_seconds()
        self._log.info("pipeline.completed", duration=total, success=True)
        return result

    async def _run_collection(self, result: PipelineResult) -> None:
        result.collection = await self.collector.collect()
        self._validate_transition("observation", result.collection)

    async def _run_compression(self, result: PipelineResult) -> None:
        if not result.collection:
            raise PipelineError("No CollectionResult available for compression")
        result.compression = await self.processor.process(result.collection)
        self._validate_transition("compression", result.compression)

    async def _run_hypothesis(self, result: PipelineResult) -> None:
        if not result.compression:
            raise PipelineError("No CompressionResult available for hypothesis")
        result.hypothesis = await self.analyzer.analyze(result.compression)
        self._validate_transition("hypothesis", result.hypothesis)

    async def _run_simulation(self, result: PipelineResult) -> None:
        if not result.hypothesis:
            raise PipelineError("No HypothesisResult available for simulation")
        result.simulation = await self.model.simulate(result.hypothesis)
        self._validate_transition("simulation", result.simulation)

    async def _run_decision(self, result: PipelineResult) -> None:
        if not result.simulation:
            raise PipelineError("No SimulationResult available for decision")
        result.decision = await self.action.decide(result.simulation)
        self._validate_transition("decision", result.decision)

    async def _run_feedback(self, result: PipelineResult) -> None:
        if not result.decision:
            raise PipelineError("No DecisionResult available for feedback")
        result.feedback = await self.monitor.evaluate(result.decision)

    def _validate_transition(self, stage: str, output: Any) -> None:
        if not self.validate_transitions:
            return

        match stage:
            case "observation":
                if output.quality_report.reliability_score < MIN_RELIABILITY_SCORE:
                    raise StageTransitionError("Reliability score too low to proceed")
            case "compression":
                if not output.states:
                    raise StageTransitionError("No MarketState produced")
            case "hypothesis":
                if not output.hypotheses:
                    raise StageTransitionError("No hypotheses generated")
            case "simulation":
                pass
            case "decision":
                if not output.decisions:
                    raise StageTransitionError("No decisions generated")
