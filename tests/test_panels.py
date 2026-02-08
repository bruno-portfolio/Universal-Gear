"""Tests for CLI decision panels and track record rendering."""

from __future__ import annotations

from io import StringIO
from uuid import uuid4

import pytest
from rich.console import Console

from universal_gear.cli.panels import (
    DEFAULT_MAX_DECISIONS,
    render_decision_panel,
    render_track_record,
)
from universal_gear.core.contracts import (
    CostOfError,
    DecisionDriver,
    DecisionObject,
    DecisionType,
    FeedbackResult,
    PredictionVsReality,
    RiskLevel,
    Scorecard,
    SourceDegradation,
)


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=120), buf


def _make_decision(
    *,
    title: str = "Test decision",
    confidence: float = 0.7,
    decision_type: DecisionType = DecisionType.ALERT,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
) -> DecisionObject:
    return DecisionObject(
        decision_type=decision_type,
        title=title,
        recommendation="Take action",
        drivers=[
            DecisionDriver(name="driver", weight=0.5, description="Test driver"),
        ],
        confidence=confidence,
        risk_level=risk_level,
        cost_of_error=CostOfError(
            false_positive="Unnecessary action",
            false_negative="Missed opportunity",
        ),
        source_scenarios=[uuid4()],
    )


def _make_feedback(
    n_scorecards: int = 3,
    *,
    within_confidence: bool = True,
    error_pct: float = 5.0,
    degradations: int = 0,
) -> FeedbackResult:
    scorecards: list[Scorecard] = []
    for _ in range(n_scorecards):
        degs = [
            SourceDegradation(
                source_id="test",
                previous_reliability=0.9,
                current_reliability=0.7,
                reason="API timeout",
            )
            for _ in range(degradations)
        ]
        scorecards.append(
            Scorecard(
                decision_id=uuid4(),
                predictions_vs_reality=[
                    PredictionVsReality(
                        metric="price",
                        predicted=100.0,
                        actual=105.0,
                        error_pct=error_pct,
                        within_confidence=within_confidence,
                    ),
                ],
                decision_outcome="beneficial",
                source_degradations=degs,
            )
        )
    return FeedbackResult(
        scorecards=scorecards,
        sources_updated=0,
        thresholds_adjusted=0,
    )


@pytest.mark.offline
class TestDecisionPanel:
    def test_renders_decisions_sorted_by_confidence(self):
        con, buf = _make_console()
        decisions = [
            _make_decision(title="Low conf", confidence=0.3),
            _make_decision(title="High conf", confidence=0.9),
            _make_decision(title="Mid conf", confidence=0.6),
        ]

        render_decision_panel(decisions, con)
        output = buf.getvalue()

        high_pos = output.find("High conf")
        mid_pos = output.find("Mid conf")
        low_pos = output.find("Low conf")

        assert high_pos < mid_pos < low_pos

    def test_limits_to_default_max(self):
        con, buf = _make_console()
        decisions = [
            _make_decision(title=f"Decision {i}", confidence=0.5 + i * 0.01)
            for i in range(DEFAULT_MAX_DECISIONS + 3)
        ]

        render_decision_panel(decisions, con)
        output = buf.getvalue()

        assert "3 more" in output
        assert "--all" in output

    def test_show_all_renders_everything(self):
        con, buf = _make_console()
        decisions = [
            _make_decision(title=f"Decision {i}", confidence=0.5 + i * 0.01)
            for i in range(DEFAULT_MAX_DECISIONS + 3)
        ]

        render_decision_panel(decisions, con, show_all=True)
        output = buf.getvalue()

        assert "more" not in output
        for i in range(DEFAULT_MAX_DECISIONS + 3):
            assert f"Decision {i}" in output

    def test_empty_decisions_produces_no_output(self):
        con, buf = _make_console()
        render_decision_panel([], con)

        assert buf.getvalue() == ""

    def test_displays_cost_of_error(self):
        con, buf = _make_console()
        render_decision_panel([_make_decision()], con)
        output = buf.getvalue()

        assert "Unnecessary action" in output
        assert "Missed opportunity" in output

    def test_displays_risk_level(self):
        con, buf = _make_console()
        render_decision_panel(
            [_make_decision(risk_level=RiskLevel.CRITICAL)],
            con,
        )
        output = buf.getvalue()

        assert "CRITICAL" in output

    def test_displays_confidence_percentage(self):
        con, buf = _make_console()
        render_decision_panel([_make_decision(confidence=0.85)], con)
        output = buf.getvalue()

        assert "85%" in output


@pytest.mark.offline
class TestTrackRecord:
    def test_renders_hit_rate(self):
        con, buf = _make_console()
        feedback = _make_feedback(within_confidence=True)

        render_track_record(feedback, con)
        output = buf.getvalue()

        assert "Hit Rate" in output
        assert "100%" in output

    def test_renders_mean_absolute_error(self):
        con, buf = _make_console()
        feedback = _make_feedback(error_pct=12.5)

        render_track_record(feedback, con)
        output = buf.getvalue()

        assert "Mean Abs Error" in output
        assert "12.5%" in output

    def test_renders_source_degradations(self):
        con, buf = _make_console()
        feedback = _make_feedback(degradations=2)

        render_track_record(feedback, con)
        output = buf.getvalue()

        assert "degradation" in output.lower()

    def test_empty_scorecards_produces_no_output(self):
        con, buf = _make_console()
        feedback = FeedbackResult(
            scorecards=[],
            sources_updated=0,
            thresholds_adjusted=0,
        )

        render_track_record(feedback, con)
        assert buf.getvalue() == ""

    def test_renders_scorecard_count(self):
        con, buf = _make_console()
        feedback = _make_feedback(n_scorecards=7)

        render_track_record(feedback, con)
        output = buf.getvalue()

        assert "7" in output
