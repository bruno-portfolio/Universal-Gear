# Universal Gear -- Guia Rápido

*[Read in English](quickstart.md)*

Universal Gear é um framework de decisão em Python que transforma observações brutas em decisões acionáveis por meio de um pipeline de seis estágios. Este guia leva você do zero a um pipeline funcional em menos de cinco minutos.

---

## Requisitos

- Python 3.11 ou superior

---

## Instalação

Instale a partir do PyPI:

```
pip install universal-gear
```

Para desenvolvimento local (instalação editável):

```
pip install -e .
```

Para incluir dependências de teste e lint:

```
pip install -e ".[dev]"
```

Para incluir o plugin de dados agrícolas (requer `agrobr`):

```
pip install -e ".[agro]"
```

---

## Execute o Pipeline de Exemplo

O pipeline de exemplo é totalmente offline e determinístico. Ele usa dados sintéticos e não requer serviços externos ou chaves de API.

```
ugear run toy
```

Saída esperada:

```
┌──────── Universal Gear - toy pipeline ────────┐
│ OK  Observation  90 events │ reliability: 0.93 │
│ OK  Compression  13 states │ weekly            │
│ OK  Hypothesis   1 hypotheses                  │
│ OK  Simulation   baseline + 10 scenarios       │
│ OK  Decision     9 decisions │ alert            │
│ OK  Feedback     9 scorecards │ hit_rate: 1.00  │
└────── SUCCESS - total: 0.0s ──────────────────┘
```

Os seis estágios são executados em ordem:

1. **Observation** -- Coleta eventos brutos das fontes de dados.
2. **Compression** -- Normaliza e agrega eventos em estados de mercado.
3. **Hypothesis** -- Gera hipóteses testáveis a partir dos estados comprimidos.
4. **Simulation** -- Projeta múltiplos cenários a partir das hipóteses.
5. **Decision** -- Produz recomendações acionáveis a partir da análise de cenários.
6. **Feedback** -- Avalia decisões passadas em relação à realidade e retroalimenta o aprendizado no próximo ciclo.

---

## Execute o Pipeline Agro

O pipeline agro utiliza dados agrícolas reais do Brasil por meio da biblioteca `agrobr`. Certifique-se de que o extra `agro` esteja instalado antes de executá-lo.

```
ugear run agro
```

---

## Liste os Plugins Disponíveis

Inspecione quais plugins estão registrados no seu ambiente:

```
ugear plugins list
```

---

## Use o Pipeline a Partir do Python

```python
from universal_gear import Pipeline

pipeline = Pipeline.from_config({
    "collector": {"plugin": "synthetic"},
    "processor": {"plugin": "aggregator"},
    "analyzer": {"plugin": "seasonal_anomaly"},
    "model": {"plugin": "conditional_scenario"},
    "action": {"plugin": "conditional_alert"},
    "monitor": {"plugin": "backtest"},
})

result = await pipeline.run()
```

Cada estágio passa sua saída tipada para o próximo. O pipeline valida os contratos entre os estágios em tempo de execução.

---

## Escreva um Plugin Personalizado

Cada estágio possui uma classe base correspondente e um decorador de registro. Para criar um coletor personalizado, por exemplo:

```python
from universal_gear.core.interfaces import BaseCollector, CollectionResult
from universal_gear.core.registry import register_collector

@register_collector("my_source")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

O conjunto completo de decoradores, um por estágio:

| Decorador | Estágio |
|---|---|
| `@register_collector` | Observation |
| `@register_processor` | Compression |
| `@register_analyzer` | Hypothesis |
| `@register_model` | Simulation |
| `@register_action` | Decision |
| `@register_monitor` | Feedback |

Ou use o scaffold para gerar um esqueleto completo de plugin:

```
ugear new-plugin weather
ugear check-plugin weather
```

Para um passo a passo completo, consulte [tutorial-first-plugin.pt-BR.md](tutorial-first-plugin.pt-BR.md).

---

## Use Sem Código

Peça pra alguém técnico exportar os resultados do pipeline como planilha:

```bash
pip install universal-gear[sheets]
ugear run agro --sample --output xlsx
```

Abra o arquivo `ugear-agro-report.xlsx` gerado no Excel ou Google Sheets.

---

## Próximos Passos

- [architecture.pt-BR.md](architecture.pt-BR.md) -- Decisões arquiteturais, diagrama de componentes e fluxo de dados.
- [contracts.pt-BR.md](contracts.pt-BR.md) -- Referência completa de schemas para os tipos de entrada e saída de cada estágio.
- [plugins.pt-BR.md](plugins.pt-BR.md) -- Guia detalhado para criar, registrar e distribuir plugins.
- [tutorial-first-plugin.pt-BR.md](tutorial-first-plugin.pt-BR.md) -- Passo a passo: seu primeiro plugin.
- [cli.pt-BR.md](cli.pt-BR.md) -- Referência completa da CLI.
