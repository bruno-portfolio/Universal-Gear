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

    _emit_result(result, pipeline_name="toy", output=output)


def _run_agro_pipeline(
    *,
    verbose: bool,
    json_output: bool,
    fail_fast: bool,
    output: str,
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

    config = AgroConfig()

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
    _emit_result(result, pipeline_name="agro", output=output)


def _run_finance_pipeline(
    *,
    verbose: bool,
    json_output: bool,
    fail_fast: bool,
    output: str,
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
    _emit_result(result, pipeline_name="finance", output=output)


def _emit_result(
    result: object,
    *,
    pipeline_name: str = "toy",
    output: str = "terminal",
) -> None:
    """Dispatch result rendering based on output format."""
    from universal_gear.core.pipeline import PipelineResult

    if not isinstance(result, PipelineResult):
        return

    if output == "json":
        from universal_gear.cli.export import export_json

        print(export_json(result))
        return

    if output == "csv":
        from universal_gear.cli.export import export_csv

        print(export_csv(result), end="")
        return

    _render_result(result, pipeline_name=pipeline_name)


def _render_result(result: object, *, pipeline_name: str = "toy") -> None:
    """Render pipeline result to console using Rich."""
    from universal_gear.core.pipeline import PipelineResult

    if not isinstance(result, PipelineResult):
        return

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


def _stage_detail(result: object, stage: str) -> str:  # noqa: PLR0911
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
) -> None:
    """Run a pipeline end-to-end."""
    if output not in ("terminal", "json", "csv"):
        console.print(
            f"[red]Invalid output format '{output}'. "
            f"Choose from: terminal, json, csv[/]"
        )
        raise typer.Exit(code=1)

    match pipeline:
        case "toy":
            _run_toy_pipeline(
                verbose=verbose,
                json_output=json_output,
                fail_fast=fail_fast,
                output=output,
            )
        case "agro":
            _run_agro_pipeline(
                verbose=verbose,
                json_output=json_output,
                fail_fast=fail_fast,
                output=output,
            )
        case "finance":
            _run_finance_pipeline(
                verbose=verbose,
                json_output=json_output,
                fail_fast=fail_fast,
                output=output,
            )
        case _:
            console.print(
                f"[red]Pipeline '{pipeline}' not yet implemented.[/]"
            )
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


@app.command()
def validate(
    config: str = typer.Argument(help="Path to pipeline config YAML"),  # noqa: ARG001 — CLI stub
) -> None:
    """Validate a pipeline config without running it."""
    console.print("[yellow]Config validation not yet implemented.[/]")


@app.command()
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
