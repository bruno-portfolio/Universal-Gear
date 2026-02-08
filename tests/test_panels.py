"""Tests for CLI decision panels and track record rendering."""

from __future__ import annotations

from io import StringIO
from uuid import uuid4

import pytest
from rich.console import Console

from universal_gear.cli.panels import (
    DEFAULT_MAX_DECISIONS,
    _consolidate_fn,
    _extract_fn_pct,
    _extract_pct,
    _group_decisions,
    _render_summary_line,
    _title_prefix,
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
    recommendation: str = "Take action",
    confidence: float = 0.7,
    decision_type: DecisionType = DecisionType.ALERT,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    fp: str = "Unnecessary action",
    fn: str = "Missed opportunity",
) -> DecisionObject:
    return DecisionObject(
        decision_type=decision_type,
        title=title,
        recommendation=recommendation,
        drivers=[
            DecisionDriver(name="driver", weight=0.5, description="Test driver"),
        ],
        confidence=confidence,
        risk_level=risk_level,
        cost_of_error=CostOfError(
            false_positive=fp,
            false_negative=fn,
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
    def test_renders_unique_decisions(self):
        con, buf = _make_console()
        decisions = [
            _make_decision(title="Low conf", confidence=0.3),
            _make_decision(title="High conf", confidence=0.9),
            _make_decision(title="Mid conf", confidence=0.6),
        ]

        render_decision_panel(decisions, con)
        output = buf.getvalue()

        assert "High conf" in output
        assert "Mid conf" in output
        assert "Low conf" in output

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

    def test_displays_summary_line(self):
        con, buf = _make_console()
        render_decision_panel([_make_decision()], con)
        output = buf.getvalue()

        assert "Summary:" in output


@pytest.mark.offline
class TestGroupDecisions:
    def test_single_decision_no_grouping(self):
        decisions = [_make_decision(title="Opportunity: scenario A")]
        groups = _group_decisions(decisions)

        assert len(groups) == 1
        assert len(groups[0].decisions) == 1

    def test_multiple_similar_decisions_grouped(self):
        rec_mid = (
            "Scenario projects price at 2268 BRL"
            " (+5.8% vs baseline). Consider forward selling."
        )
        rec_high = (
            "Scenario projects price at 2430 BRL"
            " (+13.2% vs baseline). Consider forward selling."
        )
        decisions = [
            _make_decision(
                title="Commercialisation opportunity: mid FX x weak harvest",
                recommendation=rec_mid,
                confidence=0.75,
                risk_level=RiskLevel.LOW,
                decision_type=DecisionType.RECOMMENDATION,
                fn="Missed 5.8% upside opportunity",
            ),
            _make_decision(
                title="Commercialisation opportunity: high FX x weak harvest",
                recommendation=rec_high,
                confidence=0.50,
                risk_level=RiskLevel.MEDIUM,
                decision_type=DecisionType.RECOMMENDATION,
                fn="Missed 13.2% upside opportunity",
            ),
        ]
        groups = _group_decisions(decisions)

        assert len(groups) == 1
        g = groups[0]
        assert len(g.decisions) == 2
        assert g.confidence_range == (0.50, 0.75)
        assert RiskLevel.LOW in g.risk_levels
        assert RiskLevel.MEDIUM in g.risk_levels

    def test_mixed_types_not_grouped(self):
        decisions = [
            _make_decision(
                title="Opportunity: scenario A",
                decision_type=DecisionType.RECOMMENDATION,
            ),
            _make_decision(
                title="Opportunity: scenario B",
                decision_type=DecisionType.ALERT,
            ),
        ]
        groups = _group_decisions(decisions)

        assert len(groups) == 2

    def test_different_prefixes_not_grouped(self):
        decisions = [
            _make_decision(title="Commercialisation opportunity: A"),
            _make_decision(title="Downside risk: B"),
        ]
        groups = _group_decisions(decisions)

        assert len(groups) == 2


@pytest.mark.offline
class TestSummaryLine:
    def test_contains_action_count(self):
        decisions = [
            _make_decision(
                title="Opportunity: A",
                recommendation="Price at 100 (+5.0% vs baseline).",
            ),
            _make_decision(
                title="Opportunity: B",
                recommendation="Price at 110 (+10.0% vs baseline).",
            ),
        ]
        groups = _group_decisions(decisions)
        summary = _render_summary_line(groups, total=2)

        assert "2 of 2 decisions recommend action" in summary

    def test_contains_pct_range(self):
        decisions = [
            _make_decision(
                title="Opportunity: A",
                recommendation="Price at 100 (+5.0% vs baseline).",
            ),
            _make_decision(
                title="Opportunity: B",
                recommendation="Price at 110 (+10.0% vs baseline).",
            ),
        ]
        groups = _group_decisions(decisions)
        summary = _render_summary_line(groups, total=2)

        assert "5.0%" in summary
        assert "10.0%" in summary

    def test_report_not_counted_as_action(self):
        decisions = [
            _make_decision(
                title="No signal",
                decision_type=DecisionType.REPORT,
            ),
        ]
        groups = _group_decisions(decisions)
        summary = _render_summary_line(groups, total=1)

        assert "0 of 1 decisions recommend action" in summary


@pytest.mark.offline
class TestFnRangeExtraction:
    def test_extract_pct_from_recommendation(self):
        text = "Scenario projects price at 2268 BRL (+5.8% vs baseline)."
        result = _extract_pct(text)

        assert result == [5.8]

    def test_extract_fn_pct(self):
        text = "Missed 13.2% upside opportunity"
        result = _extract_fn_pct(text)

        assert result == [13.2]

    def test_consolidate_fn_identical(self):
        texts = ["Missed 5.0% upside", "Missed 5.0% upside"]
        result = _consolidate_fn(texts)

        assert result == "Missed 5.0% upside"

    def test_consolidate_fn_range(self):
        texts = [
            "Missed 5.8% upside opportunity",
            "Missed 13.2% upside opportunity",
            "Missed 8.7% upside opportunity",
        ]
        result = _consolidate_fn(texts)

        assert "5.8%" in result
        assert "13.2%" in result

    def test_title_prefix_with_colon(self):
        result = _title_prefix("Commercialisation opportunity: soja")
        assert result == "Commercialisation opportunity"

    def test_title_prefix_without_colon(self):
        assert _title_prefix("No signal detected") == "No signal detected"


@pytest.mark.offline
class TestToyPipelineRegression:
    """Toy pipeline has no percentages in recommendations."""

    def test_no_pct_in_recommendation_renders_cleanly(self):
        con, buf = _make_console()
        decisions = [
            _make_decision(
                title="Upside alert: demand=0.8 x rate=5.6",
                recommendation="Scenario 'demand=0.8 x rate=5.6' projects upside. Risk level: low.",
                confidence=0.5,
                decision_type=DecisionType.ALERT,
            ),
            _make_decision(
                title="Downside alert: demand=0.8 x rate=4.8",
                recommendation=(
                    "Scenario 'demand=0.8 x rate=4.8' projects"
                    " downside. Risk level: medium."
                ),
                confidence=0.5,
                decision_type=DecisionType.ALERT,
            ),
        ]
        render_decision_panel(decisions, con)
        output = buf.getvalue()

        assert "Summary:" in output
        assert "2 of 2 decisions recommend action" in output
        assert "Upside alert" in output or "Downside alert" in output

    def test_grouping_no_pct_has_scenario_count(self):
        decisions = [
            _make_decision(
                title="Upside alert: A",
                recommendation="Scenario projects upside.",
            ),
            _make_decision(
                title="Upside alert: B",
                recommendation="Scenario projects upside.",
            ),
        ]
        groups = _group_decisions(decisions)

        assert len(groups) == 1
        assert "2 of 2 scenarios" in groups[0].scenario_summary

    def test_drivers_fallback_shows_examples(self):
        decisions = [
            _make_decision(title="Alert: demand_index=0.8"),
            _make_decision(title="Alert: demand_index=1.2"),
        ]
        groups = _group_decisions(decisions)

        assert len(groups) == 1
        assert "e.g." in groups[0].drivers


@pytest.mark.offline
class TestRenderGroupedVsUngrouped:
    def test_single_decision_renders_ungrouped(self):
        con, buf = _make_console()
        decisions = [
            _make_decision(
                title="Commercialisation opportunity: mid FX",
                recommendation="Consider forward selling. (+5.8% vs baseline).",
            ),
        ]
        render_decision_panel(decisions, con)
        output = buf.getvalue()

        assert "Commercialisation opportunity: mid FX" in output
        assert "Action:" not in output

    def test_grouped_decisions_render_consolidated(self):
        con, buf = _make_console()
        rec_mid = (
            "Scenario projects price at 2268 BRL"
            " (+5.8% vs baseline). Consider forward selling."
        )
        rec_high = (
            "Scenario projects price at 2430 BRL"
            " (+13.2% vs baseline). Consider forward selling."
        )
        decisions = [
            _make_decision(
                title="Commercialisation opportunity: mid FX x weak harvest",
                recommendation=rec_mid,
                confidence=0.75,
                risk_level=RiskLevel.LOW,
                decision_type=DecisionType.RECOMMENDATION,
            ),
            _make_decision(
                title="Commercialisation opportunity: high FX x weak harvest",
                recommendation=rec_high,
                confidence=0.50,
                risk_level=RiskLevel.MEDIUM,
                decision_type=DecisionType.RECOMMENDATION,
            ),
        ]
        render_decision_panel(decisions, con)
        output = buf.getvalue()

        assert "Commercialisation opportunity" in output
        assert "Action:" in output
        assert "2 of 2 scenarios" in output
        assert "Summary:" in output


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
