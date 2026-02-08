"""Comprehensive unit tests for universal_gear.core.contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from universal_gear.core.contracts import (
    MIN_SCENARIOS,
    Assumption,
    CostOfError,
    DataQualityReport,
    DecisionDriver,
    DecisionObject,
    DecisionType,
    Granularity,
    Hypothesis,
    HypothesisStatus,
    MarketState,
    PredictionVsReality,
    QualityFlag,
    RawEvent,
    RiskLevel,
    Scenario,
    SignalValue,
    SimulationResult,
    SourceDegradation,
    SourceMeta,
    SourceReliability,
    SourceType,
    ValidationCriterion,
)

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


def _make_signal(**overrides) -> SignalValue:
    defaults = {"name": "price", "value": 100.0, "unit": "BRL", "confidence": 0.9}
    defaults.update(overrides)
    return SignalValue(**defaults)


def _make_source_meta(**overrides) -> SourceMeta:
    defaults = {
        "source_id": "test-src",
        "source_type": SourceType.SYNTHETIC,
        "reliability": SourceReliability.HIGH,
    }
    defaults.update(overrides)
    return SourceMeta(**defaults)


def _make_validation_criterion(**overrides) -> ValidationCriterion:
    defaults = {
        "metric": "price_dev",
        "operator": "gt",
        "threshold": 2.0,
        "description": "Deviation persists",
    }
    defaults.update(overrides)
    return ValidationCriterion(**defaults)


def _make_scenario(**overrides) -> Scenario:
    defaults = {
        "name": "base",
        "description": "Baseline scenario",
        "assumptions": [
            Assumption(
                variable="exchange_rate",
                assumed_value=5.2,
                justification="Median forecast",
            ),
        ],
        "projected_outcome": {"price": 100.0},
        "confidence_interval": (85.0, 115.0),
        "probability": 0.5,
        "risk_level": RiskLevel.MEDIUM,
        "source_hypotheses": [uuid4()],
    }
    defaults.update(overrides)
    return Scenario(**defaults)


@pytest.mark.offline
def test_source_meta_valid_construction():
    sm = _make_source_meta()
    assert sm.source_id == "test-src"
    assert sm.source_type == SourceType.SYNTHETIC
    assert sm.reliability == SourceReliability.HIGH
    assert sm.url_or_path is None
    assert sm.expected_schema_version is None


@pytest.mark.offline
def test_raw_event_default_factories():
    source = _make_source_meta()
    before = datetime.now(UTC)
    event = RawEvent(
        source=source,
        timestamp=NOW,
        data={"price": 42.0},
    )
    after = datetime.now(UTC)

    assert isinstance(event.event_id, UUID)
    assert before <= event.collected_at <= after
    assert event.schema_version is None


@pytest.mark.offline
def test_quality_flag_valid_construction():
    flag = QualityFlag(
        field_name="price",
        issue="null_value",
        severity="warning",
        details="Row 5 is null",
    )
    assert flag.field_name == "price"
    assert flag.issue == "null_value"
    assert flag.details == "Row 5 is null"


@pytest.mark.offline
def test_data_quality_report_valid_ratio_normal(quality_report):
    ratio = quality_report.valid_ratio
    assert ratio == pytest.approx(17 / 20)


@pytest.mark.offline
def test_data_quality_report_valid_ratio_zero_total():
    source = _make_source_meta()
    report = DataQualityReport(
        source=source,
        total_records=0,
        valid_records=0,
        reliability_score=1.0,
    )
    assert report.valid_ratio == 0.0


@pytest.mark.offline
def test_data_quality_report_reliability_score_bounds():
    source = _make_source_meta()
    with pytest.raises(ValidationError):
        DataQualityReport(
            source=source,
            total_records=10,
            valid_records=10,
            reliability_score=1.5,
        )
    with pytest.raises(ValidationError):
        DataQualityReport(
            source=source,
            total_records=10,
            valid_records=10,
            reliability_score=-0.1,
        )


@pytest.mark.offline
def test_collection_result_valid_construction(collection_result):
    assert collection_result.stage == "observation"
    assert len(collection_result.events) == 20
    assert collection_result.quality_report.total_records == 20


@pytest.mark.offline
def test_signal_value_valid_construction():
    sig = _make_signal()
    assert sig.name == "price"
    assert sig.value == 100.0
    assert sig.confidence == 0.9
    assert sig.original_unit is None


@pytest.mark.offline
def test_signal_value_confidence_bounds():
    with pytest.raises(ValidationError):
        _make_signal(confidence=1.01)
    with pytest.raises(ValidationError):
        _make_signal(confidence=-0.01)


@pytest.mark.offline
def test_market_state_valid_construction(market_states):
    ms = market_states[0]
    assert isinstance(ms.state_id, UUID)
    assert ms.domain == "test"
    assert ms.granularity == Granularity.WEEKLY
    assert len(ms.signals) == 2
    assert ms.source_reliability == 0.9


@pytest.mark.offline
def test_market_state_requires_at_least_one_signal():
    with pytest.raises(ValidationError, match="at least 1 signal"):
        MarketState(
            domain="test",
            period_start=NOW,
            period_end=NOW + timedelta(days=7),
            granularity=Granularity.WEEKLY,
            signals=[],
            lineage=[uuid4()],
            source_reliability=0.9,
        )


@pytest.mark.offline
def test_market_state_source_reliability_bounds():
    with pytest.raises(ValidationError):
        MarketState(
            domain="test",
            period_start=NOW,
            period_end=NOW + timedelta(days=7),
            granularity=Granularity.WEEKLY,
            signals=[_make_signal()],
            lineage=[uuid4()],
            source_reliability=1.5,
        )


@pytest.mark.offline
def test_compression_result_valid_construction(compression_result):
    assert compression_result.stage == "compression"
    assert compression_result.records_consumed == 28
    assert compression_result.records_produced == 4
    assert len(compression_result.states) == 4
    assert compression_result.normalization_log == []


@pytest.mark.offline
def test_hypothesis_valid_construction(hypotheses):
    h = hypotheses[0]
    assert isinstance(h.hypothesis_id, UUID)
    assert h.status == HypothesisStatus.PENDING
    assert h.confidence == 0.65
    assert len(h.validation_criteria) == 1
    assert len(h.falsification_criteria) == 1
    assert len(h.competing_hypotheses) == 2


@pytest.mark.offline
def test_hypothesis_requires_at_least_one_validation_criterion():
    with pytest.raises(ValidationError, match="at least 1 validation criterion"):
        Hypothesis(
            statement="Test",
            rationale="Test",
            confidence=0.5,
            valid_until=NOW + timedelta(days=30),
            validation_criteria=[],
            falsification_criteria=[_make_validation_criterion()],
            source_states=[uuid4()],
        )


@pytest.mark.offline
def test_hypothesis_requires_at_least_one_falsification_criterion():
    with pytest.raises(ValidationError, match="at least 1 falsification criterion"):
        Hypothesis(
            statement="Test",
            rationale="Test",
            confidence=0.5,
            valid_until=NOW + timedelta(days=30),
            validation_criteria=[_make_validation_criterion()],
            falsification_criteria=[],
            source_states=[uuid4()],
        )


@pytest.mark.offline
def test_hypothesis_confidence_bounds():
    with pytest.raises(ValidationError):
        Hypothesis(
            statement="Test",
            rationale="Test",
            confidence=1.1,
            valid_until=NOW + timedelta(days=30),
            validation_criteria=[_make_validation_criterion()],
            falsification_criteria=[_make_validation_criterion()],
            source_states=[uuid4()],
        )


@pytest.mark.offline
def test_hypothesis_result_valid_construction(hypothesis_result):
    assert hypothesis_result.stage == "hypothesis"
    assert hypothesis_result.states_analyzed == 4
    assert len(hypothesis_result.hypotheses) == 2


@pytest.mark.offline
def test_scenario_valid_construction(scenarios):
    s = scenarios[0]
    assert isinstance(s.scenario_id, UUID)
    assert s.name == "baseline (status quo)"
    assert s.probability == 0.5
    assert s.risk_level == RiskLevel.MEDIUM
    assert len(s.assumptions) == 1


@pytest.mark.offline
def test_scenario_probability_bounds():
    with pytest.raises(ValidationError):
        _make_scenario(probability=1.5)
    with pytest.raises(ValidationError):
        _make_scenario(probability=-0.1)


@pytest.mark.offline
def test_simulation_result_requires_at_least_two_scenarios():
    assert MIN_SCENARIOS == 2
    single_scenario = _make_scenario()
    with pytest.raises(ValidationError, match="at least 2 scenarios"):
        SimulationResult(scenarios=[single_scenario])


@pytest.mark.offline
def test_simulation_result_valid_construction(simulation_result):
    assert simulation_result.stage == "simulation"
    assert len(simulation_result.scenarios) == 3
    assert simulation_result.baseline is not None
    assert simulation_result.baseline.name == "baseline (status quo)"


@pytest.mark.offline
def test_simulation_result_exactly_two_scenarios_is_valid():
    s1 = _make_scenario(name="scenario-a")
    s2 = _make_scenario(name="scenario-b")
    result = SimulationResult(scenarios=[s1, s2])
    assert len(result.scenarios) == 2


@pytest.mark.offline
def test_decision_driver_weight_bounds():
    with pytest.raises(ValidationError):
        DecisionDriver(name="test", weight=1.5, description="Too high")
    with pytest.raises(ValidationError):
        DecisionDriver(name="test", weight=-0.1, description="Too low")


@pytest.mark.offline
def test_decision_object_valid_construction(decision_objects):
    d = decision_objects[0]
    assert isinstance(d.decision_id, UUID)
    assert d.decision_type == DecisionType.ALERT
    assert d.risk_level == RiskLevel.HIGH
    assert d.confidence == 0.3
    assert len(d.conditions) == 1
    assert len(d.drivers) == 1


@pytest.mark.offline
def test_decision_object_confidence_bounds():
    with pytest.raises(ValidationError):
        DecisionObject(
            decision_type=DecisionType.ALERT,
            title="Test",
            recommendation="Test",
            drivers=[DecisionDriver(name="x", weight=0.5, description="d")],
            confidence=2.0,
            risk_level=RiskLevel.LOW,
            cost_of_error=CostOfError(false_positive="fp", false_negative="fn"),
            source_scenarios=[uuid4()],
        )


@pytest.mark.offline
def test_decision_result_valid_construction(decision_result):
    assert decision_result.stage == "decision"
    assert len(decision_result.decisions) == 1


@pytest.mark.offline
def test_prediction_vs_reality_valid_construction():
    pvr = PredictionVsReality(
        metric="spread_pct",
        predicted=-15.0,
        actual=-14.2,
        error_pct=5.3,
        within_confidence=True,
    )
    assert pvr.metric == "spread_pct"
    assert pvr.within_confidence is True


@pytest.mark.offline
def test_source_degradation_valid_construction():
    sd = SourceDegradation(
        source_id="src-1",
        previous_reliability=0.95,
        current_reliability=0.70,
        reason="Frequent missing fields",
    )
    assert sd.source_id == "src-1"
    assert sd.previous_reliability == 0.95


@pytest.mark.offline
def test_scorecard_valid_construction(scorecards):
    sc = scorecards[0]
    assert isinstance(sc.scorecard_id, UUID)
    assert isinstance(sc.decision_id, UUID)
    assert sc.decision_outcome == "beneficial"
    assert len(sc.predictions_vs_reality) == 1
    assert sc.source_degradations == []
    assert sc.model_adjustments == []
    assert sc.threshold_updates == {}
    assert sc.lessons_learned is None


@pytest.mark.offline
def test_feedback_result_valid_construction(feedback_result):
    assert feedback_result.stage == "feedback"
    assert feedback_result.sources_updated == 0
    assert feedback_result.thresholds_adjusted == 0
    assert len(feedback_result.scorecards) == 1


@pytest.mark.offline
def test_frozen_source_meta_rejects_mutation(source_meta):
    with pytest.raises(ValidationError):
        source_meta.source_id = "changed"


@pytest.mark.offline
def test_frozen_signal_value_rejects_mutation():
    sig = _make_signal()
    with pytest.raises(ValidationError):
        sig.value = 999.0


@pytest.mark.offline
def test_frozen_hypothesis_rejects_mutation(hypotheses):
    with pytest.raises(ValidationError):
        hypotheses[0].status = HypothesisStatus.CONFIRMED


@pytest.mark.offline
def test_frozen_scenario_rejects_mutation(scenarios):
    with pytest.raises(ValidationError):
        scenarios[0].probability = 0.99


@pytest.mark.offline
def test_enum_values_are_strings():
    assert str(SourceType.API) == "api"
    assert str(Granularity.DAILY) == "daily"
    assert str(SourceReliability.HIGH) == "high"
    assert str(HypothesisStatus.PENDING) == "pending"
    assert str(RiskLevel.CRITICAL) == "critical"
    assert str(DecisionType.TRIGGER) == "trigger"


@pytest.mark.offline
def test_enum_serialise_in_model_dump():
    sm = _make_source_meta()
    dumped = sm.model_dump()
    assert dumped["source_type"] == "synthetic"
    assert dumped["reliability"] == "high"
