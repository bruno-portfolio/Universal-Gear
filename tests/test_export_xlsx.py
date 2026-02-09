"""Tests for xlsx export of pipeline results."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

openpyxl = pytest.importorskip("openpyxl", reason="openpyxl not installed")
load_workbook = openpyxl.load_workbook

from universal_gear.cli.export import export_xlsx  # noqa: E402
from universal_gear.cli.spreadsheet import SHEET_NAMES  # noqa: E402
from universal_gear.core.contracts import (  # noqa: E402
    Assumption,
    CollectionResult,
    CompressionResult,
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
    MarketState,
    PredictionVsReality,
    RawEvent,
    RiskLevel,
    Scenario,
    Scorecard,
    SignalValue,
    SimulationResult,
    SourceMeta,
    SourceType,
    ValidationCriterion,
)
from universal_gear.core.metrics import PipelineMetrics, StageMetrics  # noqa: E402
from universal_gear.core.pipeline import PipelineResult  # noqa: E402

EXPECTED_SHEETS = 7
NOW = datetime.now(tz=UTC)
EVENT_COUNT = 3
SCENARIO_COUNT = 2


def _make_result(*, include_feedback: bool = True) -> PipelineResult:
    source = SourceMeta(source_id="test", source_type=SourceType.SYNTHETIC)
    events = [
        RawEvent(
            source=source,
            timestamp=NOW - timedelta(days=i),
            data={"value": 100 + i, "unit": "BRL", "metric": f"price_{i}"},
        )
        for i in range(EVENT_COUNT)
    ]
    quality = DataQualityReport(
        source=source, total_records=EVENT_COUNT, valid_records=EVENT_COUNT,
    )
    collection = CollectionResult(events=events, quality_report=quality)

    sig = SignalValue(name="price", value=100.0, unit="BRL")
    state = MarketState(
        domain="test", period_start=NOW - timedelta(days=7), period_end=NOW,
        granularity=Granularity.WEEKLY, signals=[sig], lineage=[events[0].event_id],
        source_reliability=0.95,
    )
    compression = CompressionResult(
        states=[state], records_consumed=EVENT_COUNT, records_produced=1,
    )

    crit = ValidationCriterion(
        metric="price", operator=">=", threshold=110.0, description="Price rises",
    )
    hyp = Hypothesis(
        statement="Price will rise", rationale="Upward trend",
        confidence=0.7, valid_until=NOW + timedelta(days=30),
        validation_criteria=[crit], falsification_criteria=[crit],
        source_states=[state.state_id],
    )
    hypothesis = HypothesisResult(hypotheses=[hyp], states_analyzed=1)

    assumption = Assumption(variable="demand", assumed_value=1.2, justification="High")
    scenarios = [
        Scenario(
            name=f"Scenario {i}", description=f"Test scenario {i}",
            assumptions=[assumption],
            projected_outcome={"price": 110.0 + i * 10},
            confidence_interval=(0.5, 0.9), probability=0.5,
            risk_level=RiskLevel.MEDIUM, source_hypotheses=[hyp.hypothesis_id],
        )
        for i in range(SCENARIO_COUNT)
    ]
    simulation = SimulationResult(scenarios=scenarios)

    decisions = [
        DecisionObject(
            decision_type=DecisionType.RECOMMENDATION,
            title="Buy now", recommendation="Forward purchase",
            drivers=[DecisionDriver(name="trend", weight=0.8, description="Up")],
            confidence=0.75, risk_level=RiskLevel.LOW,
            cost_of_error=CostOfError(
                false_positive="Unnecessary purchase",
                false_negative="Missed opportunity",
            ),
            source_scenarios=[scenarios[0].scenario_id],
        ),
        DecisionObject(
            decision_type=DecisionType.ALERT,
            title="Watch price", recommendation="Monitor closely",
            drivers=[DecisionDriver(name="vol", weight=0.5, description="High")],
            confidence=0.6, risk_level=RiskLevel.MEDIUM,
            cost_of_error=CostOfError(
                false_positive="False alarm", false_negative="Missed drop",
            ),
            source_scenarios=[scenarios[1].scenario_id],
        ),
    ]
    decision = DecisionResult(decisions=decisions)

    feedback = None
    if include_feedback:
        scorecard = Scorecard(
            decision_id=decisions[0].decision_id,
            predictions_vs_reality=[
                PredictionVsReality(
                    metric="price", predicted=110.0, actual=108.0,
                    error_pct=1.8, within_confidence=True,
                ),
            ],
            decision_outcome="Profitable",
        )
        feedback = FeedbackResult(
            scorecards=[scorecard], sources_updated=0, thresholds_adjusted=0,
        )

    metrics = PipelineMetrics()
    for stage_name in ("observation", "compression", "hypothesis",
                       "simulation", "decision", "feedback"):
        metrics.add(StageMetrics(stage=stage_name, duration_seconds=0.1, success=True))

    return PipelineResult(
        collection=collection, compression=compression,
        hypothesis=hypothesis, simulation=simulation,
        decision=decision, feedback=feedback,
        metrics=metrics, success=True,
    )


@pytest.fixture
def xlsx_path(tmp_path: Path) -> Path:
    result = _make_result()
    return export_xlsx(result, tmp_path / "test-report.xlsx")


@pytest.mark.offline
class TestExportXlsx:
    def test_creates_file(self, xlsx_path: Path):
        assert xlsx_path.exists()
        assert xlsx_path.suffix == ".xlsx"

    def test_has_seven_sheets(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        assert len(wb.sheetnames) == EXPECTED_SHEETS

    def test_sheet_names_match(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        assert tuple(wb.sheetnames) == SHEET_NAMES

    def test_observe_has_data_rows(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        ws = wb[SHEET_NAMES[0]]
        data_rows = [
            row for row in ws.iter_rows(min_row=3, values_only=True)
            if any(v is not None for v in row)
        ]
        assert len(data_rows) == EVENT_COUNT

    def test_decide_has_correct_columns(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        ws = wb[SHEET_NAMES[4]]
        header_row = [ws.cell(row=2, column=c).value for c in range(1, 8)]
        assert "Decisao" in header_row
        assert "Tipo" in header_row
        assert "Recomendacao" in header_row

    def test_decide_has_data_rows(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        ws = wb[SHEET_NAMES[4]]
        data_rows = [
            row for row in ws.iter_rows(min_row=3, values_only=True)
            if any(v is not None for v in row)
        ]
        expected_decisions = 2
        assert len(data_rows) == expected_decisions

    def test_dashboard_has_computed_metrics(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        ws = wb[SHEET_NAMES[6]]
        metrics_dict = {}
        for row in ws.iter_rows(min_row=3, values_only=True):
            if row[0] is not None:
                metrics_dict[row[0]] = row[1]

        expected_decisions = 2
        assert metrics_dict["Total de decisoes"] == expected_decisions
        assert metrics_dict["Hit rate"] == "100%"
        assert metrics_dict["Erro medio"] == "1.8%"
        assert metrics_dict["Status"] == "SUCCESS"

    def test_dashboard_actionable_count(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        ws = wb[SHEET_NAMES[6]]
        metrics_dict = {}
        for row in ws.iter_rows(min_row=3, values_only=True):
            if row[0] is not None:
                metrics_dict[row[0]] = row[1]

        expected_actionable = 2
        assert metrics_dict["Decisoes acionaveis"] == expected_actionable

    def test_simulate_has_scenarios(self, xlsx_path: Path):
        wb = load_workbook(str(xlsx_path))
        ws = wb[SHEET_NAMES[3]]
        data_rows = [
            row for row in ws.iter_rows(min_row=3, values_only=True)
            if any(v is not None for v in row)
        ]
        assert len(data_rows) == SCENARIO_COUNT

    def test_missing_feedback_still_creates_sheet(self, tmp_path: Path):
        result = _make_result(include_feedback=False)
        path = export_xlsx(result, tmp_path / "no-feedback.xlsx")
        wb = load_workbook(str(path))
        assert SHEET_NAMES[5] in wb.sheetnames
        data_rows = [
            row for row in wb[SHEET_NAMES[5]].iter_rows(min_row=3, values_only=True)
            if any(v is not None for v in row)
        ]
        assert len(data_rows) == 0

    def test_dashboard_without_feedback_shows_na(self, tmp_path: Path):
        result = _make_result(include_feedback=False)
        path = export_xlsx(result, tmp_path / "no-feedback.xlsx")
        wb = load_workbook(str(path))
        ws = wb[SHEET_NAMES[6]]
        metrics_dict = {}
        for row in ws.iter_rows(min_row=3, values_only=True):
            if row[0] is not None:
                metrics_dict[row[0]] = row[1]

        assert metrics_dict["Hit rate"] == "N/A"
        assert metrics_dict["Erro medio"] == "N/A"
