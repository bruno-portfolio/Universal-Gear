# Universal Gear

*[Read in English](README.md)*

[![CI](https://github.com/bruno-portfolio/Universal-Gear/actions/workflows/ci.yml/badge.svg)](https://github.com/bruno-portfolio/Universal-Gear/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/universal-gear)](https://pypi.org/project/universal-gear/)
[![Python](https://img.shields.io/pypi/pyversions/universal-gear)](https://pypi.org/project/universal-gear/)
[![License](https://img.shields.io/github/license/bruno-portfolio/Universal-Gear)](LICENSE)

Toda semana voce toma decisoes com dados incompletos.
O Universal Gear estrutura esse processo -- pra voce decidir melhor, explicar o porque, e aprender com os erros.

## O Que Ele Faz?

O Universal Gear roda um loop de decisao em seis estagios sobre dados reais de mercado e devolve resultados estruturados e auditaveis.

**Trader de commodities** -- "Soja caiu tres semanas seguidas. E sazonal ou tendencia? Devo fazer hedge?"
Rode `ugear run agro` com dados reais do agronegocio brasileiro. O pipeline detecta anomalias, simula cenarios e indica se o sinal vale uma acao.

**Analista financeiro** -- "USD/BRL disparou de um dia pro outro. Ruido ou mudanca de regime?"
Rode `ugear run finance` com dados do Banco Central. Mesmos seis estagios, dominio diferente -- observacao, compressao, hipotese, simulacao, decisao, feedback.

**Qualquer pessoa com decisoes recorrentes** -- Voce nao precisa ser trader. Qualquer decisao que voce toma repetidamente sob incerteza (compras, precificacao, estoque) se encaixa nesse loop. O framework te obriga a mostrar o trabalho: o que voce observou, o que assumiu, o que decidiu e se deu certo.

## Os Seis Estagios

Todo pipeline segue o mesmo loop:

```
  Observar --> Comprimir --> Hipotetizar --> Simular --> Decidir --> Feedback
      ^                                                                |
      +----------------------------------------------------------------+
```

| Estagio | O que responde |
|---------|----------------|
| **Observar** | O que esta acontecendo no mercado agora? |
| **Comprimir** | Qual e o padrao das ultimas semanas? |
| **Hipotetizar** | Isso e normal ou fora do comum? |
| **Simular** | Se continuar assim, o que pode acontecer? |
| **Decidir** | O que eu deveria fazer? |
| **Feedback** | Minha ultima decisao funcionou? |

Nenhum estagio finge ser perfeito. Cada um carrega suas limitacoes adiante, pra voce sempre saber com o que esta trabalhando.

## Instalar e Rodar

```bash
pip install universal-gear
ugear run toy          # teste agora -- offline, sem configuracao
ugear run agro         # dados reais de preco de soja do Brasil
ugear run finance      # taxas de cambio USD/BRL do BCB
```

A saida fica assim:

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

Cada estagio reporta o que fez e quanto tempo levou. Se algo falhar, falha alto -- sem erros silenciosos.

## Pra Quem E

- **Analistas e traders de commodities** -- Inteligencia de mercado estruturada para produtos agricolas, com dados reais de fontes brasileiras.
- **Analistas financeiros e macro** -- Pipelines de decisao para cambio, juros e indicadores macroeconomicos.
- **Times de business intelligence** -- Exporte resultados em JSON e importe no Power BI, Tableau ou qualquer ferramenta de BI.
- **Qualquer pessoa que toma decisoes recorrentes sob incerteza** -- Compras, precificacao, estoque, logistica -- qualquer dominio onde voce decide regularmente com informacao imperfeita.
- **Desenvolvedores construindo pipelines de decisao** -- Troque qualquer estagio, adicione novas fontes de dados ou crie um plugin de dominio inteiramente novo.

## Exportar para Ferramentas de BI

Use `--output json` pra obter saida estruturada que alimenta dashboards e relatorios:

```bash
ugear run agro --output json
```

A saida e JSON estruturado que pode ser importado diretamente no Power BI, Tableau, Metabase ou qualquer ferramenta que consome dados em JSON. CSV tambem disponivel via `--output csv`.

## Nao Programa? Comece Aqui

Voce nao precisa saber programar. O Universal Gear inclui uma planilha que te guia pelo mesmo processo de decisao, passo a passo.

**O que voce recebe:** Um arquivo Excel com sete abas. Cada aba e um passo do processo. Cada aba tem instrucoes no topo dizendo exatamente o que fazer. As celulas verdes sao pra voce preencher. Tem um exemplo completo ja preenchido (compra de cafe pro escritorio) pra voce ver como um ciclo pronto fica antes de comecar o seu.

Os sete passos:

| Aba | O que voce faz |
|-----|----------------|
| **OBSERVAR** | Anote o que voce viu: precos, quantidades, noticias. Uma linha por observacao. |
| **COMPRIMIR** | Resuma: qual a media? Esta subindo ou descendo? Quanto variou? |
| **HIPOTESE** | Escreva o que voce acha que esta acontecendo -- e o que provaria que esta errado. |
| **SIMULAR** | Imagine pelo menos dois futuros: um onde da certo e um onde da errado. |
| **DECIDIR** | Tome sua decisao. Qual sua confianca? O que acontece se voce errar? |
| **FEEDBACK** | Depois que o tempo passou: o que realmente aconteceu? Voce acertou? O que aprendeu? |
| **DASHBOARD** | Seu placar ao longo do tempo. Quantas decisoes voce acertou? |

Pra gerar a planilha:

```bash
pip install universal-gear[sheets]
ugear template
```

Isso cria `ugear-decisao.xlsx`. Abra no Excel ou Google Sheets e comece a preencher.

Quando quiser experimentar a versao em codigo, exporte a planilha pra um formato que o programa entende:

```bash
ugear import-sheet minhas-decisoes.xlsx
```

## Crie Seu Proprio Plugin

O Universal Gear e agnóstico de dominio no seu nucleo. Os pipelines `toy` e `agro` sao plugins -- e voce pode criar o seu pra qualquer dominio.

Registre um coletor, processador, analisador ou qualquer outro estagio com um unico decorator:

```python
from universal_gear.core.registry import register_collector

@register_collector("my_source")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

Guia completo: [docs/plugins.md](docs/plugins.md)

## Roadmap

O Universal Gear cresce em camadas -- cada uma torna o framework acessivel pra mais pessoas:

- ~~**Output do CLI**~~ -- Paineis de decisao, historico de acertos, exportacao JSON/CSV
- ~~**Scaffold de plugins**~~ -- `ugear new-plugin` e `ugear check-plugin` pra criar dominios
- ~~**Planilha template**~~ -- `ugear template` gera xlsx guiado pra nao-programadores
- **Conteudo e tutoriais** -- Artigos explicando a metodologia em linguagem acessivel
- **Interface web** -- Webapp minima pra pipelines de decisao pelo navegador

Veja o [MANIFESTO.pt-BR.md](MANIFESTO.pt-BR.md) pra entender a filosofia por tras de cada camada.

## Documentacao

- [MANIFESTO.pt-BR.md](MANIFESTO.pt-BR.md) -- Filosofia de design: por que cada estagio reconhece seus limites
- [docs/quickstart.md](docs/quickstart.md) -- Comecando em cinco minutos
- [docs/architecture.md](docs/architecture.md) -- Arquitetura do sistema e contratos
- [docs/plugins.md](docs/plugins.md) -- Construindo plugins customizados
- [docs/tutorial-first-plugin.md](docs/tutorial-first-plugin.md) -- Passo a passo: seu primeiro plugin
- [docs/cli.md](docs/cli.md) -- Referencia completa do CLI

## Licenca

MIT -- feito no Brasil, pensado pro mundo.
