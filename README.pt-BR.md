# Universal Gear

*[Read in English](README.md)*

[![CI](https://github.com/bruno-portfolio/Universal-Gear/actions/workflows/ci.yml/badge.svg)](https://github.com/bruno-portfolio/Universal-Gear/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/universal-gear)](https://pypi.org/project/universal-gear/)
[![Python](https://img.shields.io/pypi/pyversions/universal-gear)](https://pypi.org/project/universal-gear/)
[![License](https://img.shields.io/github/license/bruno-portfolio/Universal-Gear)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Toda semana você toma decisões com dados incompletos.
O Universal Gear estrutura esse processo -- pra você decidir melhor, explicar o porquê, e aprender com os erros.

## O Que Ele Faz?

O Universal Gear roda um loop de decisão em seis estágios sobre dados reais de mercado e devolve resultados estruturados e auditáveis.

**Trader de commodities** -- "Soja caiu três semanas seguidas. É sazonal ou tendência? Devo fazer hedge?"
Rode `ugear run agro` com dados reais do agronegócio brasileiro. O pipeline detecta anomalias, simula cenários e indica se o sinal vale uma ação.

**Analista financeiro** -- "USD/BRL disparou de um dia pro outro. Ruído ou mudança de regime?"
Rode `ugear run finance` com dados do Banco Central. Mesmos seis estágios, domínio diferente -- observação, compressão, hipótese, simulação, decisão, feedback.

**Qualquer pessoa com decisões recorrentes** -- Você não precisa ser trader. Qualquer decisão que você toma repetidamente sob incerteza (compras, precificação, estoque) se encaixa nesse loop. O framework te obriga a mostrar o trabalho: o que você observou, o que assumiu, o que decidiu e se deu certo.

## Os Seis Estágios

Todo pipeline segue o mesmo loop:

```
  Observar --> Comprimir --> Hipotetizar --> Simular --> Decidir --> Feedback
      ^                                                                |
      +----------------------------------------------------------------+
```

| Estágio | O que responde |
|---------|----------------|
| **Observar** | O que está acontecendo no mercado agora? |
| **Comprimir** | Qual é o padrão das últimas semanas? |
| **Hipotetizar** | Isso é normal ou fora do comum? |
| **Simular** | Se continuar assim, o que pode acontecer? |
| **Decidir** | O que eu deveria fazer? |
| **Feedback** | Minha última decisão funcionou? |

Nenhum estágio finge ser perfeito. Cada um carrega suas limitações adiante, pra você sempre saber com o que está trabalhando.

## Instalar e Rodar

```bash
pip install universal-gear
ugear run toy          # teste agora -- offline, sem configuração
ugear run agro         # dados reais de preço de soja do Brasil
ugear run finance      # taxas de câmbio USD/BRL do BCB
```

A saída fica assim:

```
┌──────── Universal Gear - agro pipeline ───────┐
│ OK  Observation  90 events │ reliability: 0.93 │
│ OK  Compression  13 states │ weekly            │
│ OK  Hypothesis   1 hypotheses                  │
│ OK  Simulation   baseline + 10 scenarios       │
│ OK  Decision     9 decisions │ alert            │
│ OK  Feedback     9 scorecards │ hit_rate: 1.00  │
└────── SUCCESS - total: 0.0s ──────────────────┘
```

Cada estágio reporta o que fez e quanto tempo levou. Se algo falhar, falha alto -- sem erros silenciosos.

## Pra Quem É

- **Analistas e traders de commodities** -- Inteligência de mercado estruturada para produtos agrícolas, com dados reais de fontes brasileiras.
- **Analistas financeiros e macro** -- Pipelines de decisão para câmbio, juros e indicadores macroeconômicos.
- **Times de business intelligence** -- Exporte resultados em JSON e importe no Power BI, Tableau ou qualquer ferramenta de BI.
- **Qualquer pessoa que toma decisões recorrentes sob incerteza** -- Compras, precificação, estoque, logística -- qualquer domínio onde você decide regularmente com informação imperfeita.
- **Desenvolvedores construindo pipelines de decisão** -- Troque qualquer estágio, adicione novas fontes de dados ou crie um plugin de domínio inteiramente novo.

## Exportar para Ferramentas de BI

Use `--output json` pra obter saída estruturada que alimenta dashboards e relatórios:

```bash
ugear run agro --output json
```

A saída é JSON estruturado que pode ser importado diretamente no Power BI, Tableau, Metabase ou qualquer ferramenta que consome dados em JSON. CSV também disponível via `--output csv`.

## Não Programa? Comece Aqui

Você não precisa saber programar. O Universal Gear inclui uma planilha que te guia pelo mesmo processo de decisão, passo a passo.

**O que você recebe:** Um arquivo Excel com sete abas. Cada aba é um passo do processo. Cada aba tem instruções no topo dizendo exatamente o que fazer. As células verdes são pra você preencher. Tem um exemplo completo já preenchido (compra de café pro escritório) pra você ver como um ciclo pronto fica antes de começar o seu.

Os sete passos:

| Aba | O que você faz |
|-----|----------------|
| **OBSERVAR** | Anote o que você viu: preços, quantidades, notícias. Uma linha por observação. |
| **COMPRIMIR** | Resuma: qual a média? Está subindo ou descendo? Quanto variou? |
| **HIPÓTESE** | Escreva o que você acha que está acontecendo -- e o que provaria que está errado. |
| **SIMULAR** | Imagine pelo menos dois futuros: um onde dá certo e um onde dá errado. |
| **DECIDIR** | Tome sua decisão. Qual sua confiança? O que acontece se você errar? |
| **FEEDBACK** | Depois que o tempo passou: o que realmente aconteceu? Você acertou? O que aprendeu? |
| **DASHBOARD** | Seu placar ao longo do tempo. Quantas decisões você acertou? |

Pra gerar a planilha:

```bash
pip install universal-gear[sheets]
ugear template
```

Isso cria `ugear-decisao.xlsx`. Abra no Excel ou Google Sheets e comece a preencher.

Quando quiser experimentar a versão em código, exporte a planilha pra um formato que o programa entende:

```bash
ugear import-sheet minhas-decisoes.xlsx
```

## Crie Seu Próprio Plugin

O Universal Gear é agnóstico de domínio no seu núcleo. Os pipelines `toy` e `agro` são plugins -- e você pode criar o seu pra qualquer domínio.

Registre um coletor, processador, analisador ou qualquer outro estágio com um único decorator:

```python
from universal_gear.core.registry import register_collector

@register_collector("my_source")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

Guia completo: [docs/plugins.md](docs/plugins.md)

## Roadmap

O Universal Gear cresce em camadas -- cada uma torna o framework acessível pra mais pessoas:

- ~~**Output do CLI**~~ -- Painéis de decisão, histórico de acertos, exportação JSON/CSV
- ~~**Scaffold de plugins**~~ -- `ugear new-plugin` e `ugear check-plugin` pra criar domínios
- ~~**Planilha template**~~ -- `ugear template` gera xlsx guiado pra não-programadores
- **Conteúdo e tutoriais** -- Artigos explicando a metodologia em linguagem acessível
- **Interface web** -- Webapp mínima pra pipelines de decisão pelo navegador

Veja o [MANIFESTO.pt-BR.md](MANIFESTO.pt-BR.md) pra entender a filosofia por trás de cada camada.

## Documentação

- [MANIFESTO.pt-BR.md](MANIFESTO.pt-BR.md) -- Filosofia de design: por que cada estágio reconhece seus limites
- [docs/quickstart.md](docs/quickstart.md) -- Começando em cinco minutos
- [docs/architecture.md](docs/architecture.md) -- Arquitetura do sistema e contratos
- [docs/plugins.md](docs/plugins.md) -- Construindo plugins customizados
- [docs/tutorial-first-plugin.md](docs/tutorial-first-plugin.md) -- Passo a passo: seu primeiro plugin
- [docs/cli.md](docs/cli.md) -- Referência completa do CLI

## Licença

MIT -- feito no Brasil, pensado pro mundo.
