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

| Option                       | Short | Default | Description                                                                 |
|------------------------------|-------|---------|-----------------------------------------------------------------------------|
| `--verbose`                  | `-v`  | `false` | Enable DEBUG-level logging (default is INFO).                               |
| `--json`                     |       | `false` | Emit structured JSON log output instead of human-readable text.             |
| `--fail-fast / --no-fail-fast` |     | `true`  | Abort the pipeline on the first stage failure (`--no-fail-fast` to continue). |

**Available pipelines**

| Name   | Description                                                                   |
|--------|-------------------------------------------------------------------------------|
| `toy`  | Synthetic data pipeline. Uses a synthetic collector, aggregator processor, seasonal anomaly detector, conditional scenario engine, alert emitter, and backtest monitor. Useful for development and demonstration. |
| `agro` | Agribusiness pipeline. Pulls real data via the agrobr collector and runs agro-specific processor, analyzer, scenario engine, action emitter, and monitor stages. |

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
