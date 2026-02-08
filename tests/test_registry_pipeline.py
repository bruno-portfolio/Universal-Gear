"""Tests for the plugin registry and pipeline orchestrator."""

from __future__ import annotations

import socket
from typing import Any

import pytest

from universal_gear.core.exceptions import PluginNotFoundError
from universal_gear.core.pipeline import Pipeline
from universal_gear.core.registry import (
    _REGISTRY,
    get_plugin,
    list_plugins,
    register,
    register_action,
    register_analyzer,
    register_collector,
    register_model,
    register_monitor,
    register_processor,
)
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

_real_socket = socket.socket


@pytest.fixture(autouse=True)
def _block_network_for_offline(request, monkeypatch):
    """Block outbound connections for @pytest.mark.offline tests.

    This replaces the global conftest version so that the async event-loop
    can still create its internal pipe sockets on Windows.
    """
    if "offline" not in [m.name for m in request.node.iter_markers()]:
        return

    class _OfflineSocket(_real_socket):
        """socket.socket subclass that forbids connect / bind to external hosts."""

        def connect(self, address):
            host = address[0] if isinstance(address, tuple) else address
            if host not in ("127.0.0.1", "::1", "localhost"):
                raise RuntimeError("Offline test attempted to open socket")
            return super().connect(address)

        def connect_ex(self, address):
            host = address[0] if isinstance(address, tuple) else address
            if host not in ("127.0.0.1", "::1", "localhost"):
                raise RuntimeError("Offline test attempted to open socket")
            return super().connect_ex(address)

    monkeypatch.setattr(socket, "socket", _OfflineSocket)


class TestRegistry:
    """Tests for universal_gear.core.registry."""

    def setup_method(self):
        """Snapshot the registry so we can restore it after each test."""
        self._snapshot = {stage: dict(plugins) for stage, plugins in _REGISTRY.items()}

    def teardown_method(self):
        """Restore the registry to its pre-test state."""
        for stage in _REGISTRY:
            _REGISTRY[stage].clear()
            _REGISTRY[stage].update(self._snapshot.get(stage, {}))

    @pytest.mark.offline()
    def test_register_and_retrieve_plugin(self):
        """register() + get_plugin() round-trip returns the original class."""

        @register("collector", "test_dummy")
        class DummyCollector:
            pass

        retrieved = get_plugin("collector", "test_dummy")
        assert retrieved is DummyCollector

    @pytest.mark.offline()
    def test_list_plugins_returns_registered_items(self):
        """list_plugins() includes a freshly registered plugin."""

        @register("processor", "test_proc")
        class DummyProcessor:
            pass

        result = list_plugins("processor")
        assert "test_proc" in result["processor"]

    @pytest.mark.offline()
    def test_list_plugins_with_stage_filter(self):
        """list_plugins(stage=...) returns only the requested stage."""

        @register("analyzer", "test_ana")
        class DummyAnalyzer:
            pass

        result = list_plugins("analyzer")
        assert set(result.keys()) == {"analyzer"}
        assert "test_ana" in result["analyzer"]

    @pytest.mark.offline()
    def test_get_plugin_raises_plugin_not_found_error(self):
        """get_plugin() raises PluginNotFoundError for an unknown name."""
        with pytest.raises(PluginNotFoundError):
            get_plugin("collector", "absolutely_nonexistent_plugin")

    @pytest.mark.offline()
    def test_register_invalid_stage_raises_value_error(self):
        """register() with an invalid stage name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown stage"):

            @register("invalid_stage", "test_plugin")
            class Bad:
                pass

    @pytest.mark.offline()
    def test_re_registration_overwrites_existing(self):
        """Registering the same stage/name twice replaces the first class."""

        @register("model", "overwrite_me")
        class First:
            pass

        @register("model", "overwrite_me")
        class Second:
            pass

        assert get_plugin("model", "overwrite_me") is Second

    @pytest.mark.offline()
    def test_convenience_shortcuts_work(self):
        """register_collector/processor/analyzer/model/action/monitor register correctly."""
        shortcuts = [
            (register_collector, "collector", "shortcut_coll"),
            (register_processor, "processor", "shortcut_proc"),
            (register_analyzer, "analyzer", "shortcut_ana"),
            (register_model, "model", "shortcut_mod"),
            (register_action, "action", "shortcut_act"),
            (register_monitor, "monitor", "shortcut_mon"),
        ]

        classes: list[type] = []
        for shortcut_fn, _stage, name in shortcuts:

            @shortcut_fn(name)
            class _Cls:
                pass

            classes.append(_Cls)

        for (_shortcut_fn, stage, name), cls in zip(shortcuts, classes, strict=True):
            assert get_plugin(stage, name) is cls

    @pytest.mark.offline()
    def test_list_plugins_returns_all_six_stages_when_no_filter(self):
        """list_plugins() with no stage argument returns all 6 valid stages."""
        result = list_plugins()
        expected_stages = {"collector", "processor", "analyzer", "model", "action", "monitor"}
        assert set(result.keys()) == expected_stages


def _build_pipeline(
    *,
    fail_fast: bool = True,
    validate_transitions: bool = True,
    collector_config: SyntheticCollectorConfig | None = None,
) -> Pipeline:
    """Build a full pipeline from the real toy stage implementations."""
    return Pipeline(
        collector=SyntheticCollector(collector_config or SyntheticCollectorConfig()),
        processor=AggregatorProcessor(AggregatorConfig()),
        analyzer=SeasonalAnomalyDetector(SeasonalAnalyzerConfig()),
        model=ConditionalScenarioEngine(ConditionalModelConfig()),
        action=ConditionalAlertEmitter(AlertConfig()),
        monitor=BacktestMonitor(BacktestConfig()),
        fail_fast=fail_fast,
        validate_transitions=validate_transitions,
    )


class _FailingCollector:
    """Mock collector that always raises an exception."""

    async def collect(self) -> Any:
        raise RuntimeError("Collector exploded on purpose")


class _FailingProcessor:
    """Mock processor that always raises an exception."""

    async def process(self, collection: Any) -> Any:
        raise RuntimeError("Processor exploded on purpose")


class TestPipeline:
    """Tests for universal_gear.core.pipeline."""

    @pytest.mark.offline()
    async def test_full_pipeline_runs_successfully(self):
        """End-to-end pipeline with real toy stages completes without error."""
        pipe = _build_pipeline(validate_transitions=False)
        result = await pipe.run()
        assert result.success is True
        assert result.error is None

    @pytest.mark.offline()
    async def test_pipeline_result_has_all_six_stages_populated(self):
        """PipelineResult has non-None values for all 6 stage outputs."""
        pipe = _build_pipeline(validate_transitions=False)
        result = await pipe.run()

        assert result.collection is not None
        assert result.compression is not None
        assert result.hypothesis is not None
        assert result.simulation is not None
        assert result.decision is not None
        assert result.feedback is not None

    @pytest.mark.offline()
    async def test_pipeline_metrics_records_all_stages(self):
        """Pipeline metrics contain an entry for each of the 6 stages."""
        pipe = _build_pipeline(validate_transitions=False)
        result = await pipe.run()

        stage_names = [m.stage for m in result.metrics.stages]
        assert "observation" in stage_names
        assert "compression" in stage_names
        assert "hypothesis" in stage_names
        assert "simulation" in stage_names
        assert "decision" in stage_names
        assert "feedback" in stage_names
        assert len(result.metrics.stages) == 6

        for m in result.metrics.stages:
            assert m.duration_seconds >= 0
            assert m.success is True

    @pytest.mark.offline()
    async def test_fail_fast_true_stops_on_first_error(self):
        """With fail_fast=True, the pipeline stops at the first failing stage."""
        pipe = Pipeline(
            collector=_FailingCollector(),
            processor=AggregatorProcessor(AggregatorConfig()),
            analyzer=SeasonalAnomalyDetector(SeasonalAnalyzerConfig()),
            model=ConditionalScenarioEngine(ConditionalModelConfig()),
            action=ConditionalAlertEmitter(AlertConfig()),
            monitor=BacktestMonitor(BacktestConfig()),
            fail_fast=True,
            validate_transitions=False,
        )
        result = await pipe.run()

        assert result.success is False
        assert result.error is not None
        assert "Collector exploded on purpose" in result.error
        assert len(result.metrics.stages) == 1
        assert result.metrics.stages[0].success is False

    @pytest.mark.offline()
    async def test_fail_fast_false_continues_after_error(self):
        """With fail_fast=False, the pipeline continues past failing stages."""
        pipe = Pipeline(
            collector=_FailingCollector(),
            processor=AggregatorProcessor(AggregatorConfig()),
            analyzer=SeasonalAnomalyDetector(SeasonalAnalyzerConfig()),
            model=ConditionalScenarioEngine(ConditionalModelConfig()),
            action=ConditionalAlertEmitter(AlertConfig()),
            monitor=BacktestMonitor(BacktestConfig()),
            fail_fast=False,
            validate_transitions=False,
        )
        result = await pipe.run()

        assert result.success is True
        assert len(result.metrics.stages) > 1

    @pytest.mark.offline()
    async def test_transition_validation_catches_low_reliability(self):
        """Transition validation raises StageTransitionError for low reliability_score."""
        cfg = SyntheticCollectorConfig(
            n_records=10,
            failure_rate=1.0,
            anomaly_start=None,
            seed=99,
        )
        pipe = _build_pipeline(
            fail_fast=True,
            validate_transitions=True,
            collector_config=cfg,
        )
        result = await pipe.run()

        assert result.success is False
        assert result.error is not None
        assert "Reliability score too low" in result.error or "observation" in result.error

    @pytest.mark.offline()
    async def test_pipeline_with_validate_transitions_false_skips_validation(self):
        """Pipeline with validate_transitions=False does not raise StageTransitionError."""
        cfg = SyntheticCollectorConfig(
            n_records=10,
            failure_rate=1.0,
            anomaly_start=None,
            seed=99,
        )
        pipe = _build_pipeline(
            fail_fast=True,
            validate_transitions=False,
            collector_config=cfg,
        )
        result = await pipe.run()

        if not result.success and result.error:
            assert "Reliability score too low" not in result.error

    @pytest.mark.offline()
    async def test_pipeline_success_flag_is_true_on_success(self):
        """A fully successful run sets PipelineResult.success to True."""
        pipe = _build_pipeline(validate_transitions=False)
        result = await pipe.run()

        assert result.success is True
        assert result.error is None
        assert result.metrics.all_success is True
