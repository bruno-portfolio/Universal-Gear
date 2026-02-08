"""Unit tests for all built-in stage implementations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from universal_gear.core.contracts import (
    CompressionResult,
    DecisionResult,
    DecisionType,
    Granularity,
    MarketState,
    RiskLevel,
    SignalValue,
    SimulationResult,
)
from universal_gear.stages.actions.alert import AlertConfig, ConditionalAlertEmitter
from universal_gear.stages.analyzers.seasonal import (
    MIN_PERIODS_FOR_BASELINE,
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
from universal_gear.stages.processors.aggregator import AggregatorConfig, AggregatorProcessor


def _make_market_states(
    n: int,
    *,
    price_values: list[float] | None = None,
    domain: str = "test",
) -> list[MarketState]:
    """Build *n* weekly MarketStates with configurable price signals."""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    if price_values is None:
        price_values = [100.0 + i for i in range(n)]
    states: list[MarketState] = []
    for i in range(n):
        states.append(
            MarketState(
                domain=domain,
                period_start=base + timedelta(weeks=i),
                period_end=base + timedelta(weeks=i + 1),
                granularity=Granularity.WEEKLY,
                signals=[SignalValue(name="price", value=price_values[i], unit="BRL")],
                lineage=[uuid4()],
                source_reliability=0.9,
            )
        )
    return states


def _compression_from_states(states: list[MarketState]) -> CompressionResult:
    return CompressionResult(
        states=states,
        records_consumed=len(states) * 7,
        records_produced=len(states),
    )


async def _run_pipeline_up_to_simulation() -> SimulationResult:
    """Run collector -> processor -> analyzer -> simulator inline."""
    collector = SyntheticCollector(
        SyntheticCollectorConfig(n_records=90, seed=42, anomaly_start=75, anomaly_magnitude=0.25)
    )
    collection = await collector.collect()

    processor = AggregatorProcessor(AggregatorConfig(domain="test"))
    compression = await processor.process(collection)

    analyzer = SeasonalAnomalyDetector(SeasonalAnalyzerConfig())
    hypotheses = await analyzer.analyze(compression)

    engine = ConditionalScenarioEngine(ConditionalModelConfig())
    return await engine.simulate(hypotheses)


async def _run_pipeline_up_to_decision() -> DecisionResult:
    """Run the full pipeline up to the decision stage."""
    simulation = await _run_pipeline_up_to_simulation()
    emitter = ConditionalAlertEmitter(AlertConfig())
    return await emitter.decide(simulation)


class TestSyntheticCollector:
    """Tests for SyntheticCollector (stages.collectors.synthetic)."""

    @pytest.mark.offline
    async def test_collect_returns_correct_number_of_events(self):
        cfg = SyntheticCollectorConfig(
            n_records=90, seed=42, anomaly_start=75, anomaly_magnitude=0.25, failure_rate=0.1
        )
        collector = SyntheticCollector(cfg)
        result = await collector.collect()

        assert len(result.events) == 90

    @pytest.mark.offline
    async def test_collect_is_deterministic_with_seed(self):
        cfg = SyntheticCollectorConfig(
            n_records=90, seed=42, anomaly_start=75, anomaly_magnitude=0.25, failure_rate=0.1
        )
        result_a = await SyntheticCollector(cfg).collect()
        result_b = await SyntheticCollector(cfg).collect()

        prices_a = [e.data.get("price") for e in result_a.events]
        prices_b = [e.data.get("price") for e in result_b.events]
        assert prices_a == prices_b

    @pytest.mark.offline
    async def test_collect_injects_anomalies_after_start(self):
        cfg_no_anomaly = SyntheticCollectorConfig(
            n_records=90, seed=42, anomaly_start=None, anomaly_magnitude=0.0, failure_rate=0.0
        )
        cfg_anomaly = SyntheticCollectorConfig(
            n_records=90, seed=42, anomaly_start=75, anomaly_magnitude=0.25, failure_rate=0.0
        )
        result_clean = await SyntheticCollector(cfg_no_anomaly).collect()
        result_anomaly = await SyntheticCollector(cfg_anomaly).collect()

        for day in range(75, 90):
            clean_price = result_clean.events[day].data.get("price", 0)
            anomaly_price = result_anomaly.events[day].data.get("price", 0)
            assert anomaly_price > clean_price, (
                f"Day {day}: anomaly price {anomaly_price} should exceed clean price {clean_price}"
            )

    @pytest.mark.offline
    async def test_collect_injects_failures(self):
        cfg = SyntheticCollectorConfig(
            n_records=90, seed=42, anomaly_start=75, anomaly_magnitude=0.25, failure_rate=0.1
        )
        result = await SyntheticCollector(cfg).collect()

        report = result.quality_report
        assert report.valid_records < report.total_records
        assert len(report.flags) > 0

    @pytest.mark.offline
    async def test_collect_reliability_score_positive(self):
        cfg = SyntheticCollectorConfig(
            n_records=90, seed=42, anomaly_start=75, anomaly_magnitude=0.25, failure_rate=0.1
        )
        result = await SyntheticCollector(cfg).collect()

        assert result.quality_report.reliability_score > 0


class TestAggregatorProcessor:
    """Tests for AggregatorProcessor (stages.processors.aggregator)."""

    @pytest.mark.offline
    async def test_process_produces_market_states(self):
        collector = SyntheticCollector(
            SyntheticCollectorConfig(n_records=90, seed=42, failure_rate=0.0)
        )
        collection = await collector.collect()

        processor = AggregatorProcessor(AggregatorConfig(domain="test"))
        compression = await processor.process(collection)

        assert len(compression.states) > 0
        assert all(isinstance(s, MarketState) for s in compression.states)

    @pytest.mark.offline
    async def test_process_weekly_granularity_bucketing(self):
        collector = SyntheticCollector(
            SyntheticCollectorConfig(n_records=14, seed=7, failure_rate=0.0)
        )
        collection = await collector.collect()

        processor = AggregatorProcessor(
            AggregatorConfig(domain="test", granularity=Granularity.WEEKLY)
        )
        compression = await processor.process(collection)

        assert len(compression.states) == 2
        for state in compression.states:
            assert state.granularity == Granularity.WEEKLY

    @pytest.mark.offline
    async def test_process_signal_aggregation(self):
        collector = SyntheticCollector(
            SyntheticCollectorConfig(n_records=7, seed=99, failure_rate=0.0)
        )
        collection = await collector.collect()

        processor = AggregatorProcessor(AggregatorConfig(domain="test"))
        compression = await processor.process(collection)

        assert len(compression.states) >= 1
        state = compression.states[0]
        signal_names = {s.name for s in state.signals}
        assert "price" in signal_names
        assert "demand" in signal_names

    @pytest.mark.offline
    async def test_process_records_consumed_matches_events(self, collection_result):
        processor = AggregatorProcessor(AggregatorConfig(domain="test"))
        compression = await processor.process(collection_result)

        assert compression.records_consumed == len(collection_result.events)


class TestSeasonalAnomalyDetector:
    """Tests for SeasonalAnomalyDetector (stages.analyzers.seasonal)."""

    @pytest.mark.offline
    async def test_detects_anomaly_with_high_deviation(self):
        prices = [100.0, 101.0, 99.0, 100.5, 200.0]
        states = _make_market_states(5, price_values=prices)
        compression = _compression_from_states(states)

        analyzer = SeasonalAnomalyDetector(SeasonalAnalyzerConfig())
        result = await analyzer.analyze(compression)

        assert len(result.hypotheses) >= 1
        assert "above" in result.hypotheses[0].statement.lower()

    @pytest.mark.offline
    async def test_returns_no_hypotheses_for_normal_data(self):
        prices = [100.0, 100.1, 99.9, 100.0, 100.05]
        states = _make_market_states(5, price_values=prices)
        compression = _compression_from_states(states)

        analyzer = SeasonalAnomalyDetector(SeasonalAnalyzerConfig())
        result = await analyzer.analyze(compression)

        assert len(result.hypotheses) == 0

    @pytest.mark.offline
    async def test_needs_minimum_periods_for_baseline(self):
        prices = [100.0, 200.0, 300.0]
        assert len(prices) < MIN_PERIODS_FOR_BASELINE
        states = _make_market_states(len(prices), price_values=prices)
        compression = _compression_from_states(states)

        analyzer = SeasonalAnomalyDetector(SeasonalAnalyzerConfig())
        result = await analyzer.analyze(compression)

        assert len(result.hypotheses) == 0

    @pytest.mark.offline
    async def test_states_analyzed_count(self, compression_result):
        analyzer = SeasonalAnomalyDetector(SeasonalAnalyzerConfig())
        result = await analyzer.analyze(compression_result)

        assert result.states_analyzed == len(compression_result.states)


class TestConditionalScenarioEngine:
    """Tests for ConditionalScenarioEngine (stages.models.conditional)."""

    @pytest.mark.offline
    async def test_generates_cartesian_product_plus_baseline(self, hypothesis_result):
        cfg = ConditionalModelConfig()
        engine = ConditionalScenarioEngine(cfg)
        result = await engine.simulate(hypothesis_result)

        expected_cartesian = 3 * 3
        assert len(result.scenarios) == expected_cartesian + 1

    @pytest.mark.offline
    async def test_baseline_probability_is_half(self, hypothesis_result):
        engine = ConditionalScenarioEngine(ConditionalModelConfig())
        result = await engine.simulate(hypothesis_result)

        assert result.baseline is not None
        assert result.baseline.probability == 0.5

    @pytest.mark.offline
    async def test_at_least_two_scenarios(self, hypothesis_result):
        engine = ConditionalScenarioEngine(ConditionalModelConfig())
        result = await engine.simulate(hypothesis_result)

        assert len(result.scenarios) >= 2

    @pytest.mark.offline
    async def test_baseline_is_in_scenarios_list(self, hypothesis_result):
        engine = ConditionalScenarioEngine(ConditionalModelConfig())
        result = await engine.simulate(hypothesis_result)

        assert result.baseline is not None
        baseline_ids = {s.scenario_id for s in result.scenarios}
        assert result.baseline.scenario_id in baseline_ids


class TestConditionalAlertEmitter:
    """Tests for ConditionalAlertEmitter (stages.actions.alert)."""

    @pytest.mark.offline
    async def test_produces_at_least_one_decision(self, simulation_result):
        emitter = ConditionalAlertEmitter(AlertConfig())
        result = await emitter.decide(simulation_result)

        assert len(result.decisions) >= 1

    @pytest.mark.offline
    async def test_no_action_decision_when_nothing_qualifies(self):
        cfg = AlertConfig(min_probability=1.0, min_risk_level=RiskLevel.CRITICAL)

        from universal_gear.core.contracts import Assumption, Scenario

        base_scenario = Scenario(
            name="baseline (status quo)",
            description="Baseline",
            assumptions=[Assumption(variable="x", assumed_value=1.0, justification="test")],
            projected_outcome={"price": 100.0},
            confidence_interval=(90.0, 110.0),
            probability=0.5,
            risk_level=RiskLevel.LOW,
            source_hypotheses=[uuid4()],
        )
        other_scenario = Scenario(
            name="mild",
            description="Mild scenario",
            assumptions=[Assumption(variable="x", assumed_value=1.1, justification="test")],
            projected_outcome={"price": 101.0},
            confidence_interval=(91.0, 111.0),
            probability=0.2,
            risk_level=RiskLevel.LOW,
            source_hypotheses=[uuid4()],
        )
        sim = SimulationResult(scenarios=[base_scenario, other_scenario], baseline=base_scenario)

        emitter = ConditionalAlertEmitter(cfg)
        result = await emitter.decide(sim)

        assert len(result.decisions) == 1
        assert result.decisions[0].decision_type == DecisionType.REPORT
        assert "no actionable" in result.decisions[0].title.lower()

    @pytest.mark.offline
    async def test_decision_from_full_pipeline(self):
        result = await _run_pipeline_up_to_decision()

        assert len(result.decisions) >= 1


class TestBacktestMonitor:
    """Tests for BacktestMonitor (stages.monitors.backtest)."""

    @pytest.mark.offline
    async def test_produces_one_scorecard_per_decision(self, decision_result):
        monitor = BacktestMonitor(BacktestConfig(seed=42))
        feedback = await monitor.evaluate(decision_result)

        assert len(feedback.scorecards) == len(decision_result.decisions)

    @pytest.mark.offline
    async def test_deterministic_with_seed(self, decision_result):
        monitor_a = BacktestMonitor(BacktestConfig(seed=42))
        monitor_b = BacktestMonitor(BacktestConfig(seed=42))

        feedback_a = await monitor_a.evaluate(decision_result)
        feedback_b = await monitor_b.evaluate(decision_result)

        for sc_a, sc_b in zip(feedback_a.scorecards, feedback_b.scorecards, strict=True):
            for pvr_a, pvr_b in zip(
                sc_a.predictions_vs_reality, sc_b.predictions_vs_reality, strict=True
            ):
                assert pvr_a.actual == pvr_b.actual
                assert pvr_a.error_pct == pvr_b.error_pct

    @pytest.mark.offline
    async def test_scorecard_decision_id_matches(self, decision_result):
        monitor = BacktestMonitor(BacktestConfig(seed=42))
        feedback = await monitor.evaluate(decision_result)

        expected_ids = {d.decision_id for d in decision_result.decisions}
        actual_ids = {sc.decision_id for sc in feedback.scorecards}
        assert actual_ids == expected_ids
