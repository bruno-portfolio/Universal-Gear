"""Rich panels for decision summary and track record display."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import Console

    from universal_gear.core.contracts import (
        DecisionObject,
        DecisionType,
        FeedbackResult,
        RiskLevel,
    )

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

_PCT_RE = re.compile(r"\(([+-]?\d+\.?\d*)% vs baseline\)")
_FN_PCT_RE = re.compile(r"(\d+\.?\d*)%")

RISK_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


@dataclass
class DecisionGroup:
    """Visual grouping of similar decisions for Rich output."""

    title: str
    decision_type: DecisionType
    recommendation: str
    decisions: list[DecisionObject]
    confidence_range: tuple[float, float]
    risk_levels: set[RiskLevel]
    cost_of_error_fp: str
    cost_of_error_fn: str
    scenario_summary: str
    drivers: str


def _title_prefix(title: str) -> str:
    """Extract the title prefix before the first colon."""
    idx = title.find(":")
    return title[:idx].strip() if idx != -1 else title.strip()


def _extract_pct(text: str) -> list[float]:
    """Extract percentage values from recommendation text."""
    return [float(m) for m in _PCT_RE.findall(text)]


def _extract_fn_pct(text: str) -> list[float]:
    """Extract percentage values from FN cost-of-error text."""
    return [float(m) for m in _FN_PCT_RE.findall(text)]


_DRIVER_SPLIT_RE = re.compile(r"\s+x\s+|\s*\+\s*")
_DRIVER_TOKEN_RE = re.compile(r"^(.+)\s+(\S+)$")
MAX_DRIVER_EXAMPLES = 2


def _extract_drivers(titles: list[str]) -> str:
    """Aggregate driver categories from decision titles."""
    suffixes = _extract_suffixes(titles)
    if not suffixes:
        return ""
    structured = _parse_structured_drivers(suffixes)
    if structured:
        return structured
    return _fallback_driver_examples(suffixes)


def _extract_suffixes(titles: list[str]) -> list[str]:
    """Extract the part after the colon from each title."""
    result: list[str] = []
    for title in titles:
        idx = title.find(":")
        if idx != -1:
            result.append(title[idx + 1 :].strip())
    return result


def _parse_structured_drivers(suffixes: list[str]) -> str:
    """Try to parse drivers into category(value) format."""
    categories: dict[str, set[str]] = defaultdict(set)
    for suffix in suffixes:
        for raw_part in _DRIVER_SPLIT_RE.split(suffix):
            clean = raw_part.strip()
            if not clean:
                continue
            m = _DRIVER_TOKEN_RE.match(clean)
            if not m:
                return ""
            categories[m.group(1).strip()].add(m.group(2).strip())
    if not categories:
        return ""
    parts: list[str] = []
    for cat, vals in categories.items():
        vals_sorted = sorted(vals)
        parts.append(f"{cat} ({'/'.join(vals_sorted)})")
    return " + ".join(parts)


def _fallback_driver_examples(suffixes: list[str]) -> str:
    """Show up to 2 example suffixes when structured parsing fails."""
    examples = suffixes[:MAX_DRIVER_EXAMPLES]
    return "e.g. " + ", ".join(examples)


def _consolidate_fn(fn_texts: list[str]) -> str:
    """Consolidate FN texts into a range when percentages vary."""
    if len(set(fn_texts)) == 1:
        return fn_texts[0]
    all_pcts: list[float] = []
    for text in fn_texts:
        all_pcts.extend(_extract_fn_pct(text))
    min_needed = 2
    if len(all_pcts) >= min_needed:
        lo, hi = min(all_pcts), max(all_pcts)
        if lo != hi:
            base = fn_texts[0]
            first_match = _FN_PCT_RE.search(base)
            if first_match:
                rng = f"{lo:.1f}%-{hi:.1f}%"
                return base[: first_match.start()] + rng + base[first_match.end() :]
    return fn_texts[0]


def _build_scenario_summary(decisions: list[DecisionObject], total_scenarios: int) -> str:
    """Build a scenario summary line with upside/downside range."""
    pcts: list[float] = []
    for d in decisions:
        pcts.extend(_extract_pct(d.recommendation))
    n = len(decisions)
    if pcts:
        lo, hi = min(pcts), max(pcts)
        direction = "upside" if lo > 0 else "downside"
        lo_abs, hi_abs = abs(lo), abs(hi)
        if lo_abs == hi_abs:
            spread = f"{lo_abs:.1f}%"
        else:
            spread = f"{min(lo_abs, hi_abs):.1f}% and {max(lo_abs, hi_abs):.1f}%"
        return f"{n} of {total_scenarios} scenarios project {direction} between {spread}"
    return f"{n} of {total_scenarios} scenarios"


def _risk_range_label(risk_levels: set[RiskLevel]) -> str:
    """Format a risk range label from a set of risk levels."""
    sorted_risks = sorted(risk_levels, key=lambda r: RISK_ORDER.get(r.value, 0))
    if len(sorted_risks) == 1:
        return sorted_risks[0].value.upper()
    return f"{sorted_risks[0].value.upper()}-{sorted_risks[-1].value.upper()}"


def _conf_range_label(conf_range: tuple[float, float]) -> str:
    """Format confidence range as percentage string."""
    lo, hi = conf_range
    if lo == hi:
        return f"{lo:.0%}"
    return f"{lo:.0%}-{hi:.0%}"


def _group_decisions(decisions: list[DecisionObject]) -> list[DecisionGroup]:
    """Group semantically similar decisions for consolidated display."""
    buckets: dict[tuple[str, str], list[DecisionObject]] = defaultdict(list)
    for d in decisions:
        key = (_title_prefix(d.title), d.decision_type.value)
        buckets[key].append(d)

    total_scenarios = len(decisions)
    groups: list[DecisionGroup] = []
    for (prefix, _dt_val), members in buckets.items():
        confs = [d.confidence for d in members]
        risks: set[RiskLevel] = {d.risk_level for d in members}
        fp_texts = [d.cost_of_error.false_positive for d in members]
        fn_texts = [d.cost_of_error.false_negative for d in members]
        fp = fp_texts[0]
        fn = _consolidate_fn(fn_texts)
        titles = [d.title for d in members]
        drivers = _extract_drivers(titles)
        action = members[0].recommendation.split(". ")[0] + "."
        group_title = prefix

        groups.append(
            DecisionGroup(
                title=group_title,
                decision_type=members[0].decision_type,
                recommendation=action,
                decisions=members,
                confidence_range=(min(confs), max(confs)),
                risk_levels=risks,
                cost_of_error_fp=fp,
                cost_of_error_fn=fn,
                scenario_summary=_build_scenario_summary(members, total_scenarios),
                drivers=drivers,
            )
        )
    return groups


_ACTIONABLE_TYPES = {"recommendation", "trigger", "alert"}


def _render_summary_line(groups: list[DecisionGroup], total: int) -> str:
    """Build a 1-2 line summary for the top of the decisions panel."""
    action_count = sum(
        len(g.decisions)
        for g in groups
        if g.decision_type.value in _ACTIONABLE_TYPES
    )
    all_pcts: list[float] = []
    for g in groups:
        for d in g.decisions:
            all_pcts.extend(_extract_pct(d.recommendation))

    parts: list[str] = []
    if all_pcts:
        lo, hi = min(all_pcts), max(all_pcts)
        lo_abs, hi_abs = abs(lo), abs(hi)
        direction = "upside" if lo > 0 else "movement"
        if lo_abs == hi_abs:
            parts.append(f"scenarios indicate {lo_abs:.1f}% {direction}")
        else:
            lo_fmt = min(lo_abs, hi_abs)
            hi_fmt = max(lo_abs, hi_abs)
            parts.append(
                f"scenarios indicate {lo_fmt:.1f}%-{hi_fmt:.1f}% {direction}"
            )
    parts.append(f"{action_count} of {total} decisions recommend action")
    return "Summary: " + ". ".join(parts) + "."


def _add_group_row(
    table: Table,
    group: DecisionGroup,
) -> None:
    """Add a grouped decision row to the table."""
    icon = DECISION_TYPE_ICONS.get(group.decision_type.value, " ")
    title_line = Text(group.title, style="bold")
    body_parts = [group.scenario_summary]
    if group.drivers:
        body_parts.append(f"Drivers: {group.drivers}")
    body_parts.append(f"Action: {group.recommendation}")
    body_parts.append(f"FP: {group.cost_of_error_fp}")
    body_parts.append(f"FN: {group.cost_of_error_fn}")
    body = Text("\n".join(body_parts), style="dim")
    cell = Text()
    cell.append_text(title_line)
    cell.append("\n")
    cell.append_text(body)

    risk_label = _risk_range_label(group.risk_levels)
    max_risk = max(group.risk_levels, key=lambda r: RISK_ORDER.get(r.value, 0))
    risk_text = Text(risk_label, style=_risk_style(max_risk.value))
    conf_text = _conf_range_label(group.confidence_range)
    table.add_row(icon, cell, risk_text, conf_text)


def _add_single_row(
    table: Table,
    decision: DecisionObject,
) -> None:
    """Add a single ungrouped decision row to the table."""
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


def render_decision_panel(
    decisions: list[DecisionObject],
    console: Console,
    *,
    show_all: bool = False,
) -> None:
    """Render a Rich panel summarizing pipeline decisions."""
    if not decisions:
        return

    groups = _group_decisions(decisions)

    table = Table(show_header=True, show_edge=False, pad_edge=False, box=None, expand=True)
    table.add_column("", width=1)
    table.add_column("Decision", min_width=24, no_wrap=False)
    table.add_column("Risk", width=12, justify="center")
    table.add_column("Conf", width=8, justify="right")

    total = len(decisions)
    summary = _render_summary_line(groups, total)

    visible_groups: list[DecisionGroup | DecisionObject] = []
    for group in groups:
        if len(group.decisions) == 1:
            visible_groups.append(group.decisions[0])
        else:
            visible_groups.append(group)

    displayed = visible_groups if show_all else visible_groups[:DEFAULT_MAX_DECISIONS]
    hidden_count = len(visible_groups) - len(displayed)

    for item in displayed:
        if isinstance(item, DecisionGroup):
            _add_group_row(table, item)
        else:
            _add_single_row(table, item)

    subtitle = ""
    if hidden_count > 0:
        subtitle = f"{hidden_count} more -- use --all to show all"

    panel = Panel(
        Text(summary, style="dim italic"),
        title="[bold]Decisions[/]",
        border_style="cyan",
    )
    console.print(panel)

    panel2 = Panel(
        table,
        subtitle=subtitle if subtitle else None,
        border_style="cyan",
    )
    console.print(panel2)


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
