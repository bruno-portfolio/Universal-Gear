# CLI Reference

Universal Gear exposes the `ugear` command, a Typer-based CLI for running
market-intelligence pipelines, inspecting plugins, and managing configuration.

```
ugear [COMMAND] [OPTIONS]
```

---

## Commands

### `ugear run`

Run a pipeline end-to-end.

```
ugear run <PIPELINE> [OPTIONS]
```

**Arguments**

| Argument   | Required | Description                                         |
|------------|----------|-----------------------------------------------------|
| `PIPELINE` | Yes      | Pipeline name: `toy`, `agro`, or path to YAML file. |

**Options**

| Option                       | Short | Default    | Description                                                                 |
|------------------------------|-------|------------|-----------------------------------------------------------------------------|
| `--verbose`                  | `-v`  | `false`    | Enable DEBUG-level logging (default is INFO).                               |
| `--json`                     |       | `false`    | Emit structured JSON log output instead of human-readable text.             |
| `--fail-fast / --no-fail-fast` |     | `true`     | Abort the pipeline on the first stage failure (`--no-fail-fast` to continue). |
| `--output`                   | `-o`  | `terminal` | Output format: `terminal`, `json`, or `csv`.                               |
| `--sample`                   |       | `false`    | Use bundled sample data instead of live APIs (offline mode).                |
| `--decisions-only`           |       | `false`    | Show only decisions and track record, skip stage logs.                      |
| `--all`                      |       | `false`    | Show all decisions (default: top 5 by confidence).                          |

**Available pipelines**

| Name   | Description                                                                   |
|--------|-------------------------------------------------------------------------------|
| `toy`     | Synthetic data pipeline. Uses a synthetic collector, aggregator processor, seasonal anomaly detector, conditional scenario engine, alert emitter, and backtest monitor. Useful for development and demonstration. |
| `agro`    | Agribusiness pipeline. Pulls real data via the agrobr collector and runs agro-specific processor, analyzer, scenario engine, action emitter, and monitor stages. |
| `finance` | Finance pipeline. Pulls macroeconomic data from BCB (Brazilian Central Bank) and runs finance-specific stages. |

Any other value for `PIPELINE` prints an error and exits with code 1.

**Examples**

```bash
# Run the toy pipeline with default settings
ugear run toy

# Run the agro pipeline with verbose logging
ugear run agro --verbose

# Run with JSON log output and no fail-fast
ugear run toy --json --no-fail-fast

# Combine short and long flags
ugear run agro -v --json --fail-fast
```

After execution, a Rich-formatted panel is printed to the terminal showing
each stage's status (OK / FAIL), a one-line detail summary, the stage
duration, and the overall pipeline result.

**Decision grouping.** When multiple decisions share the same title prefix
and decision type, they are collapsed into a single grouped row. The grouped
row shows a scenario count, driver categories, a consolidated FP/FN range,
and confidence/risk as ranges instead of single values. This reduces noise
when many scenarios lead to the same conclusion. Single decisions render
ungrouped. JSON output is not affected -- grouping is presentation-only.

---

### `ugear plugins`

List registered plugins.

```
ugear plugins [STAGE]
```

**Arguments**

| Argument | Required | Description                                                        |
|----------|----------|--------------------------------------------------------------------|
| `STAGE`  | No       | Filter results to a single stage. Omit to list all stages.         |

Valid stage names: `collector`, `processor`, `analyzer`, `model`, `action`, `monitor`.

**Examples**

```bash
# List all registered plugins across every stage
ugear plugins

# List only collector plugins
ugear plugins collector
```

Output is a Rich table with two columns: **Stage** and **Plugins**.

---

### `ugear new-plugin`

Scaffold a new domain plugin with all six pipeline stages.

```
ugear new-plugin <NAME>
```

**Arguments**

| Argument | Required | Description                                         |
|----------|----------|-----------------------------------------------------|
| `NAME`   | Yes      | Plugin name in snake_case (e.g. `energy`, `weather`). |

Creates nine files:

- `src/universal_gear/plugins/<name>/` — `__init__.py`, `config.py`, `collector.py`, `processor.py`, `analyzer.py`, `model.py`, `action.py`, `monitor.py`
- `tests/test_<name>_plugin.py` — test skeleton with config test and TODO markers

Each generated file follows project conventions: correct base class, register decorator, async method signature, and import order.

**Examples**

```bash
ugear new-plugin weather
ugear new-plugin supply_chain
```

---

### `ugear check-plugin`

Validate that a plugin implements all required interfaces.

```
ugear check-plugin <NAME>
```

**Arguments**

| Argument | Required | Description                 |
|----------|----------|-----------------------------|
| `NAME`   | Yes      | Plugin name to validate.    |

Checks:

- All seven modules exist (config + six stages)
- Each stage module contains a class inheriting from the correct ABC
- The config module exports a Pydantic `BaseModel` subclass

Exits with code 0 if all checks pass, code 1 if issues are found.

**Examples**

```bash
ugear check-plugin weather
ugear check-plugin agro
```

---

### `ugear template`

Generate a decision-framework spreadsheet template (xlsx).

```
ugear template [OPTIONS]
```

**Options**

| Option     | Short | Default              | Description                                      |
|------------|-------|----------------------|--------------------------------------------------|
| `--output` | `-o`  | `ugear-decisao.xlsx` | Output file path for the xlsx template.          |
| `--lang`   |       | `pt`                 | Language: `pt` (Portuguese) or `en` (English).   |

Requires `openpyxl`. Install with `pip install universal-gear[sheets]`.

**Examples**

```bash
ugear template
ugear template --output my-decisions.xlsx --lang en
```

---

### `ugear import-sheet`

Convert a filled spreadsheet template to JSON.

```
ugear import-sheet <XLSX_PATH> [OPTIONS]
```

**Arguments**

| Argument    | Required | Description                          |
|-------------|----------|--------------------------------------|
| `XLSX_PATH` | Yes      | Path to the filled xlsx template.    |

**Options**

| Option     | Short | Default | Description                                      |
|------------|-------|---------|--------------------------------------------------|
| `--output` | `-o`  | `-`     | Output file path (default: stdout).              |

Requires `openpyxl`. Install with `pip install universal-gear[sheets]`.

**Examples**

```bash
ugear import-sheet planilha.xlsx
ugear import-sheet planilha.xlsx --output result.json
ugear import-sheet planilha.xlsx | jq '.decisions'
```

---

### `ugear validate`

Validate a pipeline configuration file without executing it.

> **Note:** This command is a stub. Validation logic is not yet implemented.

```
ugear validate <CONFIG>
```

**Arguments**

| Argument | Required | Description                          |
|----------|----------|--------------------------------------|
| `CONFIG` | Yes      | Path to a pipeline configuration YAML file. |

**Examples**

```bash
ugear validate pipelines/my-pipeline.yaml
```

---

### `ugear scorecard`

Show scorecards from previous pipeline runs.

> **Note:** This command is a stub. It requires a persistence layer that is not yet available.

```
ugear scorecard <PIPELINE> [OPTIONS]
```

**Arguments**

| Argument   | Required | Description                            |
|------------|----------|----------------------------------------|
| `PIPELINE` | Yes      | Pipeline whose scorecard history to show. |

**Options**

| Option   | Short | Default | Description                           |
|----------|-------|---------|---------------------------------------|
| `--last` | `-n`  | `5`     | Number of recent runs to display.     |

**Examples**

```bash
# Show the last 5 runs for the agro pipeline
ugear scorecard agro

# Show the last 10 runs
ugear scorecard agro --last 10
ugear scorecard agro -n 10
```

---

## Global behaviour

- **Logging** is configured per-run through the `--verbose` and `--json`
  flags on `ugear run`. Verbose mode sets the level to DEBUG; otherwise INFO
  is used.
- **Exit codes**: commands exit with `0` on success. `ugear run` exits with
  `1` when an unknown pipeline name is given.
- **Rich output**: all terminal output (tables, panels, status indicators)
  is rendered through Rich with forced terminal mode.

---

## Entry point

The CLI is registered as a console script in `pyproject.toml`:

```toml
[project.scripts]
ugear = "universal_gear.cli.main:app"
```

After installing the package (`pip install -e .`), the `ugear` command
becomes available in the active environment.
