"""Shared fixtures for Universal Gear test suite."""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from universal_gear.core.contracts import (
    Assumption,
    CollectionResult,
    CompressionResult,
    Condition,
    CostOfError,
    DataQualityReport,
    DecisionDriver,
    DecisionObject,
    DecisionResult,
    DecisionType,
    FeedbackResult,
    Granularity,
    Hypothesis,
    HypothesisResult,
    HypothesisStatus,
    MarketState,
    PredictionVsReality,
    QualityFlag,
    RawEvent,
    RiskLevel,
    Scenario,
    Scorecard,
    SignalValue,
    SimulationResult,
    SourceMeta,
    SourceReliability,
    SourceType,
    ValidationCriterion,
)


@pytest.fixture(autouse=True)
def _block_network_for_offline(request, monkeypatch):
    """Block outbound connections in tests marked as offline.

    We patch ``socket.create_connection`` instead of ``socket.socket``
    because the asyncio event loop on Windows (ProactorEventLoop) needs
    ``socket.socketpair`` internally to create its self-pipe.  Blocking
    ``socket.socket`` entirely prevents the loop from starting.
    """
    if "offline" in [m.name for m in request.node.iter_markers()]:

        def _blocked(*_args, **_kwargs):
            raise RuntimeError("Offline test attempted to open a network connection")

        monkeypatch.setattr(socket, "create_connection", _blocked)


def pytest_configure(config):
    config.addinivalue_line("markers", "offline: mark test as offline (no network)")


NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


def _source_meta(
    source_id: str = "test-source",
    source_type: SourceType = SourceType.SYNTHETIC,
) -> SourceMeta:
    return SourceMeta(
        source_id=source_id,
        source_type=source_type,
        expected_schema_version="1.0",
        reliability=SourceReliability.HIGH,
    )


@pytest.fixture()
def source_meta() -> SourceMeta:
    return _source_meta()


@pytest.fixture()
def raw_events() -> list[RawEvent]:
    """20 events with a mix of quality."""
    source = _source_meta()
    events: list[RawEvent] = []
    base = datetime(2024, 1, 1, tzinfo=UTC)

    for day in range(20):
        data: dict = {"price": 100.0 + day * 0.5, "demand": 500.0 - day * 2}
        if day == 5:
            data["price"] = None
        if day == 10:
            data.pop("demand")
        if day == 15:
            data["price"] = "INVALID"

        events.append(
            RawEvent(
                source=source,
                timestamp=base + timedelta(days=day),
                data=data,
                schema_version="1.0",
            )
        )
    return events


@pytest.fixture()
def quality_report(source_meta) -> DataQualityReport:
    return DataQualityReport(
        source=source_meta,
        total_records=20,
        valid_records=17,
        flags=[
            QualityFlag(field_name="price", issue="null_value", severity="warning"),
            QualityFlag(field_name="demand", issue="missing", severity="warning"),
            QualityFlag(field_name="price", issue="type_mismatch", severity="error"),
        ],
        reliability_score=0.85,
    )


@pytest.fixture()
def collection_result(raw_events, quality_report) -> CollectionResult:
    return CollectionResult(events=raw_events, quality_report=quality_report)


@pytest.fixture()
def market_states() -> list[MarketState]:
    """4 weeks of market data with increasing prices."""
    states: list[MarketState] = []
    base = datetime(2024, 1, 1, tzinfo=UTC)

    for week in range(4):
        price = 100.0 + week * 5.0
        demand = 500.0 - week * 10.0
        states.append(
            MarketState(
                domain="test",
                period_start=base + timedelta(weeks=week),
                period_end=base + timedelta(weeks=week + 1),
                granularity=Granularity.WEEKLY,
                signals=[
                    SignalValue(name="price", value=price, unit="BRL"),
                    SignalValue(name="demand", value=demand, unit="units"),
                ],
                lineage=[uuid4()],
                source_reliability=0.9,
            )
        )
    return states


@pytest.fixture()
def compression_result(market_states) -> CompressionResult:
    return CompressionResult(
        states=market_states,
        records_consumed=28,
        records_produced=4,
    )


@pytest.fixture()
def hypotheses() -> list[Hypothesis]:
    """2 testable hypotheses."""
    now = NOW
    return [
        Hypothesis(
            statement="Price is 2.5 std devs above seasonal mean",
            rationale="Current price 115 vs mean 107.5 (std 3.0)",
            status=HypothesisStatus.PENDING,
            confidence=0.65,
            valid_until=now + timedelta(days=30),
            validation_criteria=[
                ValidationCriterion(
                    metric="price_deviation_pct",
                    operator="gt",
                    threshold=2.0,
                    description="Deviation persists above 2 std devs",
                ),
            ],
            falsification_criteria=[
                ValidationCriterion(
                    metric="price_deviation_pct",
                    operator="lt",
                    threshold=1.0,
                    description="Price returns within 1 std dev of mean",
                ),
            ],
            competing_hypotheses=["data_error", "one_off"],
            source_states=[uuid4()],
        ),
        Hypothesis(
            statement="Demand trending downward",
            rationale="3 consecutive weeks of declining demand",
            status=HypothesisStatus.PENDING,
            confidence=0.5,
            valid_until=now + timedelta(days=14),
            validation_criteria=[
                ValidationCriterion(
                    metric="demand_trend",
                    operator="lt",
                    threshold=0.0,
                    description="Demand continues falling",
                ),
            ],
            falsification_criteria=[
                ValidationCriterion(
                    metric="demand_trend",
                    operator="gt",
                    threshold=0.0,
                    description="Demand reverses upward",
                ),
            ],
            source_states=[uuid4()],
        ),
    ]


@pytest.fixture()
def hypothesis_result(hypotheses) -> HypothesisResult:
    return HypothesisResult(hypotheses=hypotheses, states_analyzed=4)


@pytest.fixture()
def scenarios(hypotheses) -> list[Scenario]:
    """3 scenarios + baseline."""
    source_ids = [h.hypothesis_id for h in hypotheses]
    return [
        Scenario(
            name="baseline (status quo)",
            description="Median scenario",
            assumptions=[
                Assumption(variable="exchange_rate", assumed_value=5.2, justification="Median"),
            ],
            projected_outcome={"price": 100.0},
            confidence_interval=(85.0, 115.0),
            probability=0.5,
            risk_level=RiskLevel.MEDIUM,
            sensitivity={"exchange_rate": 0.6},
            source_hypotheses=source_ids,
        ),
        Scenario(
            name="upside",
            description="Strong FX scenario",
            assumptions=[
                Assumption(variable="exchange_rate", assumed_value=5.6, justification="High"),
            ],
            projected_outcome={"price": 120.0},
            confidence_interval=(102.0, 138.0),
            probability=0.3,
            risk_level=RiskLevel.MEDIUM,
            sensitivity={"exchange_rate": 0.6},
            source_hypotheses=source_ids,
        ),
        Scenario(
            name="downside",
            description="Weak FX scenario",
            assumptions=[
                Assumption(variable="exchange_rate", assumed_value=4.8, justification="Low"),
            ],
            projected_outcome={"price": 85.0},
            confidence_interval=(72.0, 98.0),
            probability=0.3,
            risk_level=RiskLevel.HIGH,
            sensitivity={"exchange_rate": 0.6},
            source_hypotheses=source_ids,
        ),
    ]


@pytest.fixture()
def simulation_result(scenarios) -> SimulationResult:
    return SimulationResult(scenarios=scenarios, baseline=scenarios[0])


@pytest.fixture()
def decision_objects(scenarios) -> list[DecisionObject]:
    return [
        DecisionObject(
            decision_type=DecisionType.ALERT,
            title="Downside alert: weak FX",
            recommendation="Consider hedging",
            conditions=[
                Condition(
                    description="Spread > 15%",
                    metric="spread_pct",
                    operator="lt",
                    threshold=-15.0,
                    window="7 days",
                ),
            ],
            drivers=[
                DecisionDriver(
                    name="exchange_rate",
                    weight=0.6,
                    description="Assumed exchange_rate = 4.8",
                ),
            ],
            confidence=0.3,
            risk_level=RiskLevel.HIGH,
            cost_of_error=CostOfError(
                false_positive="Unnecessary hedge cost",
                false_negative="Unhedged loss",
            ),
            source_scenarios=[scenarios[2].scenario_id],
        ),
    ]


@pytest.fixture()
def decision_result(decision_objects) -> DecisionResult:
    return DecisionResult(decisions=decision_objects)


@pytest.fixture()
def scorecards(decision_objects) -> list[Scorecard]:
    return [
        Scorecard(
            decision_id=decision_objects[0].decision_id,
            predictions_vs_reality=[
                PredictionVsReality(
                    metric="spread_pct",
                    predicted=-15.0,
                    actual=-14.2,
                    error_pct=5.3,
                    within_confidence=True,
                ),
            ],
            decision_outcome="beneficial",
        ),
    ]


@pytest.fixture()
def feedback_result(scorecards) -> FeedbackResult:
    return FeedbackResult(
        scorecards=scorecards,
        sources_updated=0,
        thresholds_adjusted=0,
    )
