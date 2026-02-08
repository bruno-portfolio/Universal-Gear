"""Rich panels for decision summary and track record display."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import Console

    from universal_gear.core.contracts import DecisionObject, FeedbackResult

DEFAULT_MAX_DECISIONS = 5

HIT_RATE_GOOD = 0.7
HIT_RATE_FAIR = 0.4
MAE_GOOD = 10.0
MAE_FAIR = 25.0
BIAS_NOTABLE = 5.0
MIN_TREND_POINTS = 2

DECISION_TYPE_ICONS: dict[str, str] = {
    "alert": "[yellow]![/]",
    "recommendation": "[green]v[/]",
    "trigger": "[red]*[/]",
    "report": "[blue]#[/]",
}


def render_decision_panel(
    decisions: list[DecisionObject],
    console: Console,
    *,
    show_all: bool = False,
) -> None:
    """Render a Rich panel summarizing pipeline decisions."""
    if not decisions:
        return

    sorted_decisions = sorted(decisions, key=lambda d: d.confidence, reverse=True)

    visible = sorted_decisions if show_all else sorted_decisions[:DEFAULT_MAX_DECISIONS]
    hidden_count = len(sorted_decisions) - len(visible)

    table = Table(show_header=True, show_edge=False, pad_edge=False, box=None, expand=True)
    table.add_column("", width=1)
    table.add_column("Decision", min_width=24, no_wrap=False)
    table.add_column("Risk", width=8, justify="center")
    table.add_column("Conf", width=5, justify="right")

    for decision in visible:
        icon = DECISION_TYPE_ICONS.get(decision.decision_type.value, " ")
        title_line = Text(decision.title, style="bold")
        body_parts = [
            decision.recommendation,
            f"FP: {decision.cost_of_error.false_positive}",
            f"FN: {decision.cost_of_error.false_negative}",
        ]
        body = Text("\n".join(body_parts), style="dim")
        cell = Text()
        cell.append_text(title_line)
        cell.append("\n")
        cell.append_text(body)

        risk_style = _risk_style(decision.risk_level.value)
        risk_text = Text(decision.risk_level.value.upper(), style=risk_style)
        conf_text = f"{decision.confidence:.0%}"

        table.add_row(icon, cell, risk_text, conf_text)

    subtitle = ""
    if hidden_count > 0:
        subtitle = f"{hidden_count} more -- use --all to show all"

    panel = Panel(
        table,
        title="[bold]Decisions[/]",
        subtitle=subtitle if subtitle else None,
        border_style="cyan",
    )
    console.print(panel)


def render_track_record(
    feedback: FeedbackResult,
    console: Console,
) -> None:
    """Render a compact track record panel from feedback scorecards."""
    from universal_gear.stages.monitors.scorecard import (
        summary as sc_summary,
    )

    if not feedback.scorecards:
        return

    metrics = sc_summary(feedback)

    source_degradations = sum(len(s.source_degradations) for s in feedback.scorecards)

    table = Table(show_header=False, show_edge=False, pad_edge=False, box=None)
    table.add_column("Metric", min_width=16)
    table.add_column("Value", justify="right", min_width=8)

    hr = metrics["hit_rate"]
    hr_style = "green" if hr >= HIT_RATE_GOOD else "yellow" if hr >= HIT_RATE_FAIR else "red"
    table.add_row("Hit Rate", Text(f"{hr:.0%}", style=hr_style))

    mae = metrics["mae"]
    mae_style = "green" if mae <= MAE_GOOD else "yellow" if mae <= MAE_FAIR else "red"
    table.add_row("Mean Abs Error", Text(f"{mae:.1f}%", style=mae_style))

    bias_val = metrics["bias"]
    bias_label = "over-predicting" if bias_val > 0 else "under-predicting"
    bias_style = "dim" if abs(bias_val) < BIAS_NOTABLE else "yellow"
    table.add_row("Bias", Text(f"{bias_val:+.1f}% ({bias_label})", style=bias_style))

    table.add_row("Scorecards", str(len(feedback.scorecards)))

    if source_degradations > 0:
        table.add_row(
            "Source Issues",
            Text(f"{source_degradations} degradations", style="yellow"),
        )

    if feedback.accuracy_trend:
        trend = feedback.accuracy_trend
        improving = len(trend) >= MIN_TREND_POINTS and trend[-1] > trend[0]
        table.add_row("Trend", "improving" if improving else "stable")

    panel = Panel(
        table,
        title="[bold]Track Record[/]",
        border_style="blue",
    )
    console.print(panel)


def _risk_style(risk: str) -> str:
    """Map risk level to a Rich style."""
    match risk:
        case "critical":
            return "bold red"
        case "high":
            return "red"
        case "medium":
            return "yellow"
        case _:
            return "green"
