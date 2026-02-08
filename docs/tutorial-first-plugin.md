# Tutorial: Your First Plugin

This tutorial walks you through creating a complete domain plugin from scratch using the CLI scaffold, validating it, and running it in a pipeline.

---

## 1. Generate the Scaffold

Use the `new-plugin` command to generate all required files:

```
ugear new-plugin weather
```

This creates nine files:

```
src/universal_gear/plugins/weather/
    __init__.py
    config.py          # WeatherConfig (Pydantic BaseModel)
    collector.py        # WeatherCollector (BaseCollector)
    processor.py        # WeatherProcessor (BaseProcessor)
    analyzer.py         # WeatherAnalyzer (BaseAnalyzer)
    model.py            # WeatherScenarioEngine (BaseSimulator)
    action.py           # WeatherActionEmitter (BaseDecider)
    monitor.py          # WeatherMonitor (BaseMonitor)

tests/
    test_weather_plugin.py
```

Every file is a working skeleton that imports the correct base class, registers itself via the decorator, and implements the required async method with a placeholder body.

---

## 2. Validate the Scaffold

Before writing any logic, verify that the generated plugin satisfies all interface contracts:

```
ugear check-plugin weather
```

Expected output:

```
Plugin 'weather' passed all checks.
```

The checker verifies:

- All seven modules exist (config + six stages)
- Each stage module contains a class inheriting from the correct ABC
- The config module exports a Pydantic `BaseModel` subclass

---

## 3. Add Configuration Fields

Open `config.py` and add domain-specific fields:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class WeatherConfig(BaseModel):
    domain: str = "weather"
    api_url: str = "https://api.open-meteo.com/v1/forecast"
    latitude: float = Field(default=-23.55, description="Latitude")
    longitude: float = Field(default=-46.63, description="Longitude")
    forecast_days: int = 7
```

All six stage implementations receive `self.config` with these fields automatically via `BaseStage.__init__`.

---

## 4. Implement the Collector

Open `collector.py`. The scaffold already provides the structure. Replace the placeholder body:

```python
async def collect(self) -> CollectionResult:
    import httpx
    from datetime import datetime

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            self.config.api_url,
            params={
                "latitude": self.config.latitude,
                "longitude": self.config.longitude,
                "daily": "temperature_2m_max,precipitation_sum",
                "forecast_days": self.config.forecast_days,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    source = SourceMeta(
        source_id="open-meteo",
        source_type=SourceType.API,
        url_or_path=self.config.api_url,
        reliability=SourceReliability.HIGH,
    )

    events = []
    for i, date in enumerate(data["daily"]["time"]):
        events.append(
            RawEvent(
                source=source,
                timestamp=datetime.fromisoformat(date),
                schema_version="weather-v1",
                data={
                    "temp_max": data["daily"]["temperature_2m_max"][i],
                    "precip_mm": data["daily"]["precipitation_sum"][i],
                },
            )
        )

    quality_report = DataQualityReport(
        source=source,
        total_records=len(events),
        valid_records=len(events),
        reliability_score=0.9,
    )

    return CollectionResult(events=events, quality_report=quality_report)
```

---

## 5. Implement Remaining Stages

Follow the same pattern for each stage:

| Stage | What to implement |
|---|---|
| **Processor** | Normalize raw events into `MarketState` objects with temporal granularity |
| **Analyzer** | Detect anomalies or patterns, generate `Hypothesis` objects |
| **Model** | Project at least 2 `Scenario` objects from hypotheses |
| **Action** | Produce `DecisionObject` items based on scenario analysis |
| **Monitor** | Compare past decisions against reality, produce `Scorecard` items |

Each method signature and return type is already in the scaffold. The `contracts.py` reference documents every field: see [contracts.md](contracts.md).

---

## 6. Write Tests

The scaffold generates `tests/test_weather_plugin.py` with a config test and TODO markers. Add tests for each stage following the pattern from existing plugins:

```python
@pytest.mark.offline
class TestWeatherCollector:
    @pytest.mark.asyncio
    async def test_collect_returns_events(self):
        config = WeatherConfig()
        collector = WeatherCollector(config)
        result = await collector.collect()
        assert len(result.events) > 0
        assert result.quality_report.reliability_score > 0
```

Run your tests:

```
pytest tests/test_weather_plugin.py -m offline
```

---

## 7. Validate Again

After implementing all stages, run the checker once more to confirm everything is wired correctly:

```
ugear check-plugin weather
```

---

## 8. Wire Into the CLI (Optional)

To make your plugin available as `ugear run weather`, add a `_run_weather_pipeline` function in `cli/main.py` and a new `case "weather":` branch in the `run` command. Follow the pattern from the existing `agro` or `finance` pipelines.

---

## 9. Run It

Once wired, run the full pipeline:

```
ugear run weather
```

Use `--decisions-only` to focus on outputs, `--all` to see every decision, or `--output json` to pipe results to other tools.

---

## Reference

- [architecture.md](architecture.md) -- Pipeline design and data flow
- [contracts.md](contracts.md) -- Full schema reference for all stage types
- [plugins.md](plugins.md) -- Plugin system internals and entry points
- [cli.md](cli.md) -- CLI command reference
