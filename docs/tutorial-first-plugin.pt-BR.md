# Tutorial: Seu Primeiro Plugin

*[Read in English](tutorial-first-plugin.md)*

Este tutorial guia você na criação de um plugin de domínio completo do zero, usando o scaffold da CLI, validando-o e executando-o em um pipeline.

---

## 1. Gerar o Scaffold

Use o comando `new-plugin` para gerar todos os arquivos necessários:

```
ugear new-plugin weather
```

Isso cria nove arquivos:

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

Cada arquivo é um esqueleto funcional que importa a classe base correta, registra-se via decorator e implementa o método assíncrono necessário com um corpo provisório.

---

## 2. Validar o Scaffold

Antes de escrever qualquer lógica, verifique se o plugin gerado satisfaz todos os contratos de interface:

```
ugear check-plugin weather
```

Saída esperada:

```
Plugin 'weather' passed all checks.
```

O verificador confere:

- Todos os sete módulos existem (config + seis estágios)
- Cada módulo de estágio contém uma classe que herda da ABC correta
- O módulo de configuração exporta uma subclasse de `BaseModel` do Pydantic

---

## 3. Adicionar Campos de Configuração

Abra `config.py` e adicione campos específicos do domínio:

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

Todas as seis implementações de estágio recebem `self.config` com esses campos automaticamente via `BaseStage.__init__`.

---

## 4. Implementar o Collector

Abra `collector.py`. O scaffold já fornece a estrutura. Substitua o corpo provisório:

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

## 5. Implementar os Estágios Restantes

Siga o mesmo padrão para cada estágio:

| Estágio | O que implementar |
|---|---|
| **Processor** | Normalizar eventos brutos em objetos `MarketState` com granularidade temporal |
| **Analyzer** | Detectar anomalias ou padrões, gerar objetos `Hypothesis` |
| **Model** | Projetar pelo menos 2 objetos `Scenario` a partir das hipóteses |
| **Action** | Produzir itens `DecisionObject` com base na análise de cenários |
| **Monitor** | Comparar decisões passadas com a realidade, produzir itens `Scorecard` |

Cada assinatura de método e tipo de retorno já está no scaffold. A referência `contracts.py` documenta cada campo: veja [contracts.pt-BR.md](contracts.pt-BR.md).

---

## 6. Escrever Testes

O scaffold gera `tests/test_weather_plugin.py` com um teste de configuração e marcadores TODO. Adicione testes para cada estágio seguindo o padrão dos plugins existentes:

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

Execute seus testes:

```
pytest tests/test_weather_plugin.py -m offline
```

---

## 7. Validar Novamente

Após implementar todos os estágios, execute o verificador mais uma vez para confirmar que tudo está conectado corretamente:

```
ugear check-plugin weather
```

---

## 8. Integrar à CLI (Opcional)

Para disponibilizar seu plugin como `ugear run weather`, adicione uma função `_run_weather_pipeline` em `cli/main.py` e um novo branch `case "weather":` no comando `run`. Siga o padrão dos pipelines existentes `agro` ou `finance`.

---

## 9. Executar

Uma vez integrado, execute o pipeline completo:

```
ugear run weather
```

Use `--decisions-only` para focar nas saídas, `--all` para ver todas as decisões, ou `--output json` para encaminhar resultados a outras ferramentas.

---

## Referência

- [architecture.pt-BR.md](architecture.pt-BR.md) -- Design do pipeline e fluxo de dados
- [contracts.pt-BR.md](contracts.pt-BR.md) -- Referência completa de schemas para todos os tipos de estágio
- [plugins.pt-BR.md](plugins.pt-BR.md) -- Detalhes internos do sistema de plugins e pontos de entrada
- [cli.pt-BR.md](cli.pt-BR.md) -- Referência de comandos da CLI
