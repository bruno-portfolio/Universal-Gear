"""CLI entry point for Universal Gear."""

from __future__ import annotations

import asyncio
import os
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from universal_gear.core.logging import setup_logging
from universal_gear.core.registry import list_plugins

if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")

app = typer.Typer(name="ugear", help="Universal Gear - Market Intelligence Pipeline")
console = Console()


def _run_toy_pipeline(
    *,
    verbose: bool,
    json_output: bool,
    fail_fast: bool,
    output: str,
    decisions_only: bool = False,
    show_all: bool = False,
) -> None:
    """Build and execute the toy pipeline."""
    from universal_gear.core.pipeline import Pipeline
    from universal_gear.stages.actions.alert import (
        AlertConfig,
        ConditionalAlertEmitter,
    )
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
    from universal_gear.stages.monitors.backtest import (
        BacktestConfig,
        BacktestMonitor,
    )
    from universal_gear.stages.processors.aggregator import (
        AggregatorConfig,
        AggregatorProcessor,
    )

    setup_logging(json_output=json_output, level="DEBUG" if verbose else "INFO")

    pipeline = Pipeline(
        collector=SyntheticCollector(SyntheticCollectorConfig()),
        processor=AggregatorProcessor(AggregatorConfig(domain="toy")),
        analyzer=SeasonalAnomalyDetector(SeasonalAnalyzerConfig()),
        model=ConditionalScenarioEngine(ConditionalModelConfig()),
        action=ConditionalAlertEmitter(AlertConfig()),
        monitor=BacktestMonitor(BacktestConfig()),
        fail_fast=fail_fast,
    )

    result = asyncio.run(pipeline.run())

    _emit_result(
        result,
        pipeline_name="toy",
        output=output,
        decisions_only=decisions_only,
        show_all=show_all,
    )


def _run_agro_pipeline(
    *,
    verbose: bool,
    json_output: bool,
    fail_fast: bool,
    output: str,
    sample: bool,
    decisions_only: bool = False,
    show_all: bool = False,
) -> None:
    """Build and execute the agro pipeline with real data from agrobr."""
    from universal_gear.core.pipeline import Pipeline
    from universal_gear.plugins.agro.action import AgroActionEmitter
    from universal_gear.plugins.agro.analyzer import AgroAnalyzer
    from universal_gear.plugins.agro.collector import AgrobrCollector
    from universal_gear.plugins.agro.config import AgroConfig
    from universal_gear.plugins.agro.model import (
        AgroModelConfig,
        AgroScenarioEngine,
    )
    from universal_gear.plugins.agro.monitor import AgroMonitor
    from universal_gear.plugins.agro.processor import AgroProcessor

    setup_logging(json_output=json_output, level="DEBUG" if verbose else "INFO")

    config = AgroConfig(sample=sample)

    pipeline = Pipeline(
        collector=AgrobrCollector(config),
        processor=AgroProcessor(config),
        analyzer=AgroAnalyzer(config),
        model=AgroScenarioEngine(AgroModelConfig()),
        action=AgroActionEmitter(config),
        monitor=AgroMonitor(config),
        fail_fast=fail_fast,
    )

    result = asyncio.run(pipeline.run())
    _emit_result(
        result,
        pipeline_name="agro",
        output=output,
        decisions_only=decisions_only,
        show_all=show_all,
    )


def _run_finance_pipeline(
    *,
    verbose: bool,
    json_output: bool,
    fail_fast: bool,
    output: str,
    decisions_only: bool = False,
    show_all: bool = False,
) -> None:
    """Build and execute the finance pipeline with real data from BCB."""
    from universal_gear.core.pipeline import Pipeline
    from universal_gear.plugins.finance.action import FinanceActionEmitter
    from universal_gear.plugins.finance.analyzer import FinanceAnalyzer
    from universal_gear.plugins.finance.collector import BCBCollector
    from universal_gear.plugins.finance.config import FinanceConfig
    from universal_gear.plugins.finance.model import (
        FinanceModelConfig,
        FinanceScenarioEngine,
    )
    from universal_gear.plugins.finance.monitor import FinanceMonitor
    from universal_gear.plugins.finance.processor import FinanceProcessor

    setup_logging(json_output=json_output, level="DEBUG" if verbose else "INFO")

    config = FinanceConfig()

    pipeline = Pipeline(
        collector=BCBCollector(config),
        processor=FinanceProcessor(config),
        analyzer=FinanceAnalyzer(config),
        model=FinanceScenarioEngine(FinanceModelConfig()),
        action=FinanceActionEmitter(config),
        monitor=FinanceMonitor(config),
        fail_fast=fail_fast,
    )

    result = asyncio.run(pipeline.run())
    _emit_result(
        result,
        pipeline_name="finance",
        output=output,
        decisions_only=decisions_only,
        show_all=show_all,
    )


def _emit_result(
    result: object,
    *,
    pipeline_name: str = "toy",
    output: str = "terminal",
    decisions_only: bool = False,
    show_all: bool = False,
) -> None:
    """Dispatch result rendering based on output format."""
    from universal_gear.core.pipeline import PipelineResult

    if not isinstance(result, PipelineResult):
        return

    if output == "json":
        from universal_gear.cli.export import export_json

        stderr_console = Console(stderr=True)
        _render_decision_panels(result, stderr_console, show_all=show_all)
        print(export_json(result))
        return

    if output == "csv":
        from universal_gear.cli.export import export_csv

        print(export_csv(result), end="")
        return

    _render_result(
        result,
        pipeline_name=pipeline_name,
        decisions_only=decisions_only,
        show_all=show_all,
    )


def _render_result(
    result: object,
    *,
    pipeline_name: str = "toy",
    decisions_only: bool = False,
    show_all: bool = False,
) -> None:
    """Render pipeline result to console using Rich."""
    from universal_gear.core.pipeline import PipelineResult

    if not isinstance(result, PipelineResult):
        return

    if not decisions_only:
        table = Table(show_header=False, show_edge=False, pad_edge=False, box=None)
        table.add_column("Status", width=3)
        table.add_column("Stage", min_width=14)
        table.add_column("Detail", min_width=20)
        table.add_column("Duration", justify="right", min_width=6)

        for stage_metric in result.metrics.stages:
            icon = "[green]OK[/]" if stage_metric.success else "[red]FAIL[/]"
            detail = _stage_detail(result, stage_metric.stage)
            duration = f"{stage_metric.duration_seconds:.1f}s"
            table.add_row(icon, stage_metric.stage.title(), detail, duration)

        total = f"total: {result.metrics.total_duration:.1f}s"
        status = "[green]SUCCESS[/]" if result.success else f"[red]FAILED: {result.error}[/]"

        panel = Panel(
            table,
            title=f"[bold]Universal Gear[/] - {pipeline_name} pipeline",
            subtitle=f"{status} - {total}",
            border_style="green" if result.success else "red",
        )
        console.print(panel)

    _render_decision_panels(result, console, show_all=show_all)


def _render_decision_panels(
    result: object,
    target_console: Console,
    *,
    show_all: bool = False,
) -> None:
    """Render decision summary and track record panels."""
    from universal_gear.cli.panels import render_decision_panel, render_track_record
    from universal_gear.core.pipeline import PipelineResult

    if not isinstance(result, PipelineResult):
        return

    if result.decision and result.decision.decisions:
        render_decision_panel(
            result.decision.decisions,
            target_console,
            show_all=show_all,
        )

    if result.feedback:
        render_track_record(result.feedback, target_console)


def _stage_detail(result: object, stage: str) -> str:  # noqa: PLR0911, PLR0912
    from universal_gear.core.pipeline import PipelineResult

    if not isinstance(result, PipelineResult):
        return ""

    match stage:
        case "observation":
            if result.collection:
                n = len(result.collection.events)
                rel = result.collection.quality_report.reliability_score
                return f"{n} events | reliability: {rel:.2f}"
        case "compression":
            if result.compression:
                n = len(result.compression.states)
                gran = (
                    result.compression.states[0].granularity.value
                    if result.compression.states
                    else "?"
                )
                return f"{n} states | {gran}"
        case "hypothesis":
            if result.hypothesis:
                n = len(result.hypothesis.hypotheses)
                return f"{n} hypotheses"
        case "simulation":
            if result.simulation:
                n = len(result.simulation.scenarios)
                has_bl = "baseline + " if result.simulation.baseline else ""
                return f"{has_bl}{n} scenarios"
        case "decision":
            if result.decision:
                n = len(result.decision.decisions)
                types = {d.decision_type.value for d in result.decision.decisions}
                return f"{n} decisions | {', '.join(types)}"
        case "feedback":
            if result.feedback:
                from universal_gear.stages.monitors.scorecard import (
                    summary as sc_summary,
                )

                n = len(result.feedback.scorecards)
                metrics = sc_summary(result.feedback)
                hr = metrics["hit_rate"]
                return f"{n} scorecards | hit_rate: {hr:.2f}"
    return ""


@app.command()
def run(
    pipeline: str = typer.Argument(
        help="Pipeline name: 'toy', 'agro', or path to YAML",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    json_output: bool = typer.Option(False, "--json"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
    output: str = typer.Option(
        "terminal",
        "--output",
        "-o",
        help="Output format: terminal (default), json, csv",
    ),
    sample: bool = typer.Option(
        False,
        "--sample",
        help="Use bundled sample data instead of live APIs (offline mode)",
    ),
    decisions_only: bool = typer.Option(
        False,
        "--decisions-only",
        help="Show only decisions and track record, skip stage logs",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Show all decisions (default: top 5 by confidence)",
    ),
) -> None:
    """Run a pipeline end-to-end."""
    if output not in ("terminal", "json", "csv"):
        console.print(f"[red]Invalid output format '{output}'. Choose from: terminal, json, csv[/]")
        raise typer.Exit(code=1)

    match pipeline:
        case "toy":
            _run_toy_pipeline(
                verbose=verbose,
                json_output=json_output,
                fail_fast=fail_fast,
                output=output,
                decisions_only=decisions_only,
                show_all=show_all,
            )
        case "agro":
            _run_agro_pipeline(
                verbose=verbose,
                json_output=json_output,
                fail_fast=fail_fast,
                output=output,
                sample=sample,
                decisions_only=decisions_only,
                show_all=show_all,
            )
        case "finance":
            _run_finance_pipeline(
                verbose=verbose,
                json_output=json_output,
                fail_fast=fail_fast,
                output=output,
                decisions_only=decisions_only,
                show_all=show_all,
            )
        case _:
            console.print(f"[red]Pipeline '{pipeline}' not yet implemented.[/]")
            raise typer.Exit(code=1)


@app.command()
def plugins(
    stage: str | None = typer.Argument(None, help="Filter by stage"),
) -> None:
    """List registered plugins."""
    _ensure_plugins_loaded()

    registry = list_plugins(stage)
    table = Table(title="Registered Plugins")
    table.add_column("Stage", style="cyan")
    table.add_column("Plugins", style="green")

    for stage_name, plugin_names in sorted(registry.items()):
        table.add_row(stage_name, ", ".join(plugin_names) if plugin_names else "(none)")

    console.print(table)


@app.command("new-plugin")
def new_plugin(
    name: str = typer.Argument(help="Plugin name (snake_case, e.g. 'energy')"),
) -> None:
    """Scaffold a new domain plugin with all six pipeline stages."""
    import re

    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        console.print(f"[red]Invalid plugin name '{name}'. Use lowercase snake_case.[/]")
        raise typer.Exit(code=1)

    from universal_gear.cli.scaffold import generate_plugin

    try:
        created = generate_plugin(name)
    except FileExistsError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from None

    console.print(f"[green]Plugin '{name}' created ({len(created)} files):[/]")
    for path in created:
        console.print(f"  {path}")


@app.command("check-plugin")
def check_plugin(
    name: str = typer.Argument(help="Plugin name to validate"),
) -> None:
    """Validate that a plugin implements all required interfaces."""
    from universal_gear.cli.checker import check_plugin as do_check

    errors = do_check(name)

    if errors:
        console.print(f"[red]Plugin '{name}' has {len(errors)} issue(s):[/]")
        for err in errors:
            console.print(f"  [red]x[/] {err}")
        raise typer.Exit(code=1)

    console.print(f"[green]Plugin '{name}' passed all checks.[/]")


@app.command()
def template(
    output: str = typer.Option(
        "ugear-decisao.xlsx",
        "--output",
        "-o",
        help="Output file path for the xlsx template",
    ),
    lang: str = typer.Option(
        "pt",
        "--lang",
        help="Language: 'pt' (Portuguese) or 'en' (English)",
    ),
) -> None:
    """Generate a decision-framework spreadsheet template (xlsx)."""
    import importlib.util
    from pathlib import Path

    if importlib.util.find_spec("openpyxl") is None:
        console.print("[red]openpyxl is required. Run: pip install openpyxl[/]")
        raise typer.Exit(code=1)

    from universal_gear.cli.spreadsheet import generate_template

    path = generate_template(Path(output), lang=lang)
    console.print(f"[green]Template saved to {path}[/]")


@app.command("import-sheet")
def import_sheet(
    xlsx_path: str = typer.Argument(help="Path to the filled xlsx template"),
    output: str = typer.Option(
        "-",
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    ),
) -> None:
    """Convert a filled spreadsheet template to JSON."""
    import importlib.util
    import json
    from pathlib import Path

    if importlib.util.find_spec("openpyxl") is None:
        console.print("[red]openpyxl is required. Run: pip install openpyxl[/]")
        raise typer.Exit(code=1)

    sheet_path = Path(xlsx_path)
    if not sheet_path.exists():
        console.print(f"[red]File not found: {xlsx_path}[/]")
        raise typer.Exit(code=1)

    from universal_gear.cli.spreadsheet import read_sheet_as_json

    data = read_sheet_as_json(sheet_path)

    json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    if output == "-":
        print(json_str)
    else:
        Path(output).write_text(json_str, encoding="utf-8")
        console.print(f"[green]JSON saved to {output}[/]")


@app.command(hidden=True)
def validate(
    config: str = typer.Argument(help="Path to pipeline config YAML"),  # noqa: ARG001 — CLI stub
) -> None:
    """Validate a pipeline config without running it."""
    console.print("[yellow]Config validation not yet implemented.[/]")


@app.command(hidden=True)
def scorecard(
    pipeline: str = typer.Argument(help="Pipeline to show scorecard for"),
    last: int = typer.Option(  # noqa: ARG001 — CLI stub
        5,
        "--last",
        "-n",
        help="Number of recent runs to display",
    ),
) -> None:
    """Show scorecards from previous runs."""
    console.print(
        f"[yellow]Scorecard history for '{pipeline}' "
        f"not yet available (requires persistence layer).[/]"
    )


def _ensure_plugins_loaded() -> None:
    """Import stage modules so their @register decorators fire."""
    import universal_gear.plugins.agro.action
    import universal_gear.plugins.agro.analyzer
    import universal_gear.plugins.agro.collector
    import universal_gear.plugins.agro.model
    import universal_gear.plugins.agro.monitor
    import universal_gear.plugins.agro.processor
    import universal_gear.plugins.finance.action
    import universal_gear.plugins.finance.analyzer
    import universal_gear.plugins.finance.collector
    import universal_gear.plugins.finance.model
    import universal_gear.plugins.finance.monitor
    import universal_gear.plugins.finance.processor
    import universal_gear.stages.actions.alert
    import universal_gear.stages.analyzers.seasonal
    import universal_gear.stages.analyzers.zscore
    import universal_gear.stages.collectors.synthetic
    import universal_gear.stages.models.conditional
    import universal_gear.stages.models.montecarlo
    import universal_gear.stages.monitors.backtest
    import universal_gear.stages.processors.aggregator  # noqa: F401
