"""Integration tests — toy pipeline end-to-end and agro pipeline with mock data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from universal_gear.core.contracts import (
    CollectionResult,
    DataQualityReport,
    RawEvent,
    SourceMeta,
    SourceReliability,
    SourceType,
)
from universal_gear.core.pipeline import Pipeline
from universal_gear.plugins.agro.action import AgroActionEmitter
from universal_gear.plugins.agro.analyzer import AgroAnalyzer
from universal_gear.plugins.agro.config import AgroConfig
from universal_gear.plugins.agro.model import AgroModelConfig, AgroScenarioEngine
from universal_gear.plugins.agro.monitor import AgroMonitor
from universal_gear.plugins.agro.processor import AgroProcessor
from universal_gear.stages.actions.alert import AlertConfig, ConditionalAlertEmitter
from universal_gear.stages.analyzers.seasonal import (
    SeasonalAnalyzerConfig,
    SeasonalAnomalyDetector,
)
from universal_gear.stages.collectors.synthetic import (
    SyntheticCollector,
    SyntheticCollectorConfig,
)
from universal_gear.stages.models.conditional import (
    ConditionalModelConfig,
    ConditionalScenarioEngine,
)
from universal_gear.stages.monitors.backtest import BacktestConfig, BacktestMonitor
from universal_gear.stages.processors.aggregator import (
    AggregatorConfig,
    AggregatorProcessor,
)


def _build_toy_pipeline() -> Pipeline:
    """Build a full toy pipeline using default SyntheticCollectorConfig."""
    return Pipeline(
        collector=SyntheticCollector(SyntheticCollectorConfig()),
        processor=AggregatorProcessor(AggregatorConfig()),
        analyzer=SeasonalAnomalyDetector(SeasonalAnalyzerConfig()),
        model=ConditionalScenarioEngine(ConditionalModelConfig()),
        action=ConditionalAlertEmitter(AlertConfig()),
        monitor=BacktestMonitor(BacktestConfig()),
    )


def _build_agro_collection(
    n_records: int = 20,
    *,
    base_price: float = 130.0,
    price_spike_at: int | None = None,
    spike_magnitude: float = 1.5,
) -> CollectionResult:
    """Build a mock CollectionResult that mimics CEPEA data for agro tests."""
    source = SourceMeta(
        source_id="cepea-soja",
        source_type=SourceType.API,
        url_or_path="https://cepea.esalq.usp.br",
        reliability=SourceReliability.HIGH,
    )

    events: list[RawEvent] = []
    base_date = datetime(2024, 1, 1, tzinfo=UTC)

    for i in range(n_records):
        price = base_price + i * 0.5
        if price_spike_at is not None and i >= price_spike_at:
            price *= spike_magnitude

        events.append(
            RawEvent(
                source=source,
                timestamp=base_date + timedelta(days=i),
                data={"valor": round(price, 2), "data": "2024-01-15"},
                schema_version="cepea-v1",
            )
        )

    quality_report = DataQualityReport(
        source=source,
        total_records=n_records,
        valid_records=n_records,
        reliability_score=1.0,
    )

    return CollectionResult(events=events, quality_report=quality_report)


@pytest.mark.offline
@pytest.mark.asyncio
async def test_toy_pipeline_end_to_end():
    """Full toy pipeline runs successfully with all stages populated."""
    pipeline = _build_toy_pipeline()
    result = await pipeline.run()

    assert result.success is True, f"Pipeline failed: {result.error}"
    assert result.collection is not None
    assert result.compression is not None
    assert result.hypothesis is not None
    assert result.simulation is not None
    assert result.decision is not None
    assert result.feedback is not None


@pytest.mark.offline
@pytest.mark.asyncio
async def test_toy_pipeline_produces_90_events():
    """Collection stage produces exactly 90 events (default n_records)."""
    pipeline = _build_toy_pipeline()
    result = await pipeline.run()

    assert result.success is True, f"Pipeline failed: {result.error}"
    assert result.collection is not None
    assert len(result.collection.events) == 90


@pytest.mark.offline
@pytest.mark.asyncio
async def test_toy_pipeline_produces_hypotheses():
    """Pipeline generates at least 1 hypothesis from synthetic data."""
    pipeline = _build_toy_pipeline()
    result = await pipeline.run()

    assert result.success is True, f"Pipeline failed: {result.error}"
    assert result.hypothesis is not None
    assert len(result.hypothesis.hypotheses) >= 1


@pytest.mark.offline
@pytest.mark.asyncio
async def test_toy_pipeline_produces_decisions():
    """Pipeline generates at least 1 decision from the simulation output."""
    pipeline = _build_toy_pipeline()
    result = await pipeline.run()

    assert result.success is True, f"Pipeline failed: {result.error}"
    assert result.decision is not None
    assert len(result.decision.decisions) >= 1


@pytest.mark.offline
@pytest.mark.asyncio
async def test_toy_pipeline_deterministic():
    """Running the pipeline twice with the same seed produces identical counts."""
    pipeline_a = _build_toy_pipeline()
    pipeline_b = _build_toy_pipeline()

    result_a = await pipeline_a.run()
    result_b = await pipeline_b.run()

    assert result_a.success is True
    assert result_b.success is True

    assert result_a.collection is not None
    assert result_b.collection is not None
    assert len(result_a.collection.events) == len(result_b.collection.events)

    assert result_a.compression is not None
    assert result_b.compression is not None
    assert len(result_a.compression.states) == len(result_b.compression.states)

    assert result_a.hypothesis is not None
    assert result_b.hypothesis is not None
    assert len(result_a.hypothesis.hypotheses) == len(result_b.hypothesis.hypotheses)


@pytest.mark.offline
@pytest.mark.asyncio
async def test_agro_processor_produces_states():
    """AgroProcessor converts a mock CollectionResult into MarketStates."""
    collection = _build_agro_collection(n_records=30)
    config = AgroConfig()
    processor = AgroProcessor(config)

    compression = await processor.process(collection)

    assert len(compression.states) > 0
    assert compression.records_consumed == 30

    for state in compression.states:
        assert state.domain == "agro"
        price_signals = [s for s in state.signals if s.name == "price"]
        assert len(price_signals) == 1


@pytest.mark.offline
@pytest.mark.asyncio
async def test_agro_analyzer_detects_seasonal_deviation():
    """AgroAnalyzer detects deviation when prices spike in later records."""
    collection = _build_agro_collection(
        n_records=60, base_price=130.0, price_spike_at=50, spike_magnitude=1.5
    )
    config = AgroConfig()
    processor = AgroProcessor(config)
    analyzer = AgroAnalyzer(config)

    compression = await processor.process(collection)
    hypothesis_result = await analyzer.analyze(compression)

    assert len(hypothesis_result.hypotheses) >= 1

    statements = [h.statement.lower() for h in hypothesis_result.hypotheses]
    has_price_hypothesis = any("price" in s or "soja" in s for s in statements)
    assert has_price_hypothesis, f"Expected price-related hypothesis, got: {statements}"


@pytest.mark.offline
@pytest.mark.asyncio
async def test_agro_model_produces_scenarios():
    """AgroScenarioEngine produces scenarios from hypotheses."""
    collection = _build_agro_collection(
        n_records=60, base_price=130.0, price_spike_at=50, spike_magnitude=1.5
    )
    config = AgroConfig()
    processor = AgroProcessor(config)
    analyzer = AgroAnalyzer(config)
    model = AgroScenarioEngine(AgroModelConfig())

    compression = await processor.process(collection)
    hypothesis_result = await analyzer.analyze(compression)
    simulation_result = await model.simulate(hypothesis_result)

    assert len(simulation_result.scenarios) >= 2
    assert simulation_result.baseline is not None

    for scenario in simulation_result.scenarios:
        assert "price_brl" in scenario.projected_outcome


@pytest.mark.offline
@pytest.mark.asyncio
async def test_agro_action_produces_decisions():
    """AgroActionEmitter produces decisions from agro scenarios."""
    collection = _build_agro_collection(
        n_records=60, base_price=130.0, price_spike_at=50, spike_magnitude=1.5
    )
    config = AgroConfig()
    processor = AgroProcessor(config)
    analyzer = AgroAnalyzer(config)
    model = AgroScenarioEngine(AgroModelConfig())
    action = AgroActionEmitter(config)

    compression = await processor.process(collection)
    hypothesis_result = await analyzer.analyze(compression)
    simulation_result = await model.simulate(hypothesis_result)
    decision_result = await action.decide(simulation_result)

    assert len(decision_result.decisions) >= 1

    for decision in decision_result.decisions:
        assert decision.title
        assert decision.recommendation


@pytest.mark.offline
@pytest.mark.asyncio
async def test_agro_monitor_produces_scorecards():
    """AgroMonitor produces scorecards from agro decisions."""
    collection = _build_agro_collection(
        n_records=60, base_price=130.0, price_spike_at=50, spike_magnitude=1.5
    )
    config = AgroConfig()
    processor = AgroProcessor(config)
    analyzer = AgroAnalyzer(config)
    model = AgroScenarioEngine(AgroModelConfig())
    action = AgroActionEmitter(config)
    monitor = AgroMonitor(config)

    compression = await processor.process(collection)
    hypothesis_result = await analyzer.analyze(compression)
    simulation_result = await model.simulate(hypothesis_result)
    decision_result = await action.decide(simulation_result)
    feedback_result = await monitor.evaluate(decision_result)

    assert len(feedback_result.scorecards) >= 1
    assert len(feedback_result.scorecards) == len(decision_result.decisions)

    for scorecard in feedback_result.scorecards:
        assert scorecard.decision_outcome in ("beneficial", "neutral", "detrimental")
        assert len(scorecard.predictions_vs_reality) >= 1
