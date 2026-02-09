# Referência da CLI

*[Read in English](cli.md)*

O Universal Gear disponibiliza o comando `ugear`, uma CLI baseada em Typer para
executar pipelines de inteligência de mercado, inspecionar plugins e gerenciar
configurações.

```
ugear [COMMAND] [OPTIONS]
```

---

## Comandos

### `ugear run`

Executa um pipeline de ponta a ponta.

```
ugear run <PIPELINE> [OPTIONS]
```

**Argumentos**

| Argumento  | Obrigatório | Descrição                                              |
|------------|-------------|--------------------------------------------------------|
| `PIPELINE` | Sim         | Nome do pipeline: `toy`, `agro`, ou caminho para arquivo YAML. |

**Opções**

| Opção                        | Curto | Padrão     | Descrição                                                                          |
|------------------------------|-------|------------|-------------------------------------------------------------------------------------|
| `--verbose`                  | `-v`  | `false`    | Habilita logging no nível DEBUG (o padrão é INFO).                                  |
| `--json`                     |       | `false`    | Emite saída de log estruturada em JSON em vez de texto legível.                     |
| `--fail-fast / --no-fail-fast` |     | `true`     | Aborta o pipeline na primeira falha de estágio (`--no-fail-fast` para continuar).   |
| `--output`                   | `-o`  | `terminal` | Formato de saída: `terminal` (padrão), `json`, `csv` ou `xlsx`.                    |
| `--output-file`              |       | `None`     | Caminho do arquivo de saída para export xlsx (padrão: `ugear-<pipeline>-report.xlsx`). |
| `--sample`                   |       | `false`    | Usa dados de amostra inclusos em vez de APIs ao vivo (modo offline).                |
| `--decisions-only`           |       | `false`    | Mostra apenas decisões e histórico de acertos, pula logs de estágios.               |
| `--all`                      |       | `false`    | Mostra todas as decisões (padrão: top 5 por confiança).                             |

**Pipelines disponíveis**

| Nome   | Descrição                                                                   |
|--------|-----------------------------------------------------------------------------|
| `toy`     | Pipeline de dados sintéticos. Usa um coletor sintético, processador agregador, detector de anomalias sazonais, motor de cenários condicional, emissor de alertas e monitor de backtest. Útil para desenvolvimento e demonstração. |
| `agro`    | Pipeline de agronegócio. Coleta dados reais via coletor agrobr e executa estágios específicos de agro: processador, analisador, motor de cenários, emissor de ações e monitor. |
| `finance` | Pipeline financeiro. Coleta dados macroeconômicos do BCB (Banco Central do Brasil) e executa estágios específicos de finanças. |

Qualquer outro valor para `PIPELINE` imprime um erro e encerra com código 1.

**Exemplos**

```bash
# Executar o pipeline toy com configurações padrão
ugear run toy

# Executar o pipeline agro com logging detalhado
ugear run agro --verbose

# Executar com saída de log em JSON e sem fail-fast
ugear run toy --json --no-fail-fast

# Combinar flags curtas e longas
ugear run agro -v --json --fail-fast

# Exportar resultados para planilha Excel
ugear run agro --sample --output xlsx

# Exportar com nome de arquivo personalizado
ugear run agro --sample --output xlsx --output-file relatorio.xlsx
```

Após a execução, um painel formatado com Rich é exibido no terminal mostrando
o status de cada estágio (OK / FAIL), um resumo em uma linha, a duração do
estágio e o resultado geral do pipeline.

**Agrupamento de decisões.** Quando múltiplas decisões compartilham o mesmo
prefixo de título e tipo de decisão, elas são agrupadas em uma única linha.
A linha agrupada mostra contagem de cenários, categorias de drivers, faixa
consolidada de FP/FN, e confiança/risco como faixas em vez de valores únicos.
Isso reduz ruído quando vários cenários levam à mesma conclusão. Decisões
únicas são exibidas sem agrupamento. A saída JSON não é afetada -- o
agrupamento é apenas visual.

---

### `ugear plugins`

Lista os plugins registrados.

```
ugear plugins [STAGE]
```

**Argumentos**

| Argumento | Obrigatório | Descrição                                                            |
|-----------|-------------|----------------------------------------------------------------------|
| `STAGE`   | Não         | Filtra os resultados para um único estágio. Omita para listar todos. |

Nomes de estágio válidos: `collector`, `processor`, `analyzer`, `model`, `action`, `monitor`.

**Exemplos**

```bash
# Listar todos os plugins registrados em todos os estágios
ugear plugins

# Listar apenas plugins do tipo collector
ugear plugins collector
```

A saída é uma tabela Rich com duas colunas: **Stage** e **Plugins**.

---

### `ugear new-plugin`

Cria a estrutura de um novo plugin de domínio com todos os seis estágios do pipeline.

```
ugear new-plugin <NAME>
```

**Argumentos**

| Argumento | Obrigatório | Descrição                                              |
|-----------|-------------|--------------------------------------------------------|
| `NAME`    | Sim         | Nome do plugin em snake_case (ex.: `energy`, `weather`). |

Cria nove arquivos:

- `src/universal_gear/plugins/<name>/` — `__init__.py`, `config.py`, `collector.py`, `processor.py`, `analyzer.py`, `model.py`, `action.py`, `monitor.py`
- `tests/test_<name>_plugin.py` — esqueleto de testes com teste de configuração e marcadores TODO

Cada arquivo gerado segue as convenções do projeto: classe base correta, decorador de registro, assinatura de método assíncrono e ordem de importação.

**Exemplos**

```bash
ugear new-plugin weather
ugear new-plugin supply_chain
```

---

### `ugear check-plugin`

Valida se um plugin implementa todas as interfaces exigidas.

```
ugear check-plugin <NAME>
```

**Argumentos**

| Argumento | Obrigatório | Descrição                    |
|-----------|-------------|------------------------------|
| `NAME`    | Sim         | Nome do plugin a ser validado. |

Verificações:

- Todos os sete módulos existem (config + seis estágios)
- Cada módulo de estágio contém uma classe que herda da ABC correta
- O módulo de config exporta uma subclasse de `BaseModel` do Pydantic

Encerra com código 0 se todas as verificações passarem, código 1 se problemas forem encontrados.

**Exemplos**

```bash
ugear check-plugin weather
ugear check-plugin agro
```

---

### `ugear validate`

Valida um arquivo de configuração de pipeline sem executá-lo.

> **Nota:** Este comando é um stub. A lógica de validação ainda não foi implementada.

```
ugear validate <CONFIG>
```

**Argumentos**

| Argumento | Obrigatório | Descrição                                        |
|-----------|-------------|--------------------------------------------------|
| `CONFIG`  | Sim         | Caminho para um arquivo YAML de configuração de pipeline. |

**Exemplos**

```bash
ugear validate pipelines/my-pipeline.yaml
```

---

### `ugear scorecard`

Exibe scorecards de execuções anteriores de pipelines.

> **Nota:** Este comando é um stub. Ele requer uma camada de persistência que ainda não está disponível.

```
ugear scorecard <PIPELINE> [OPTIONS]
```

**Argumentos**

| Argumento  | Obrigatório | Descrição                                              |
|------------|-------------|--------------------------------------------------------|
| `PIPELINE` | Sim         | Pipeline cujo histórico de scorecard será exibido.      |

**Opções**

| Opção    | Curto | Padrão  | Descrição                                      |
|----------|-------|---------|-------------------------------------------------|
| `--last` | `-n`  | `5`     | Número de execuções recentes a exibir.          |

**Exemplos**

```bash
# Mostrar as últimas 5 execuções do pipeline agro
ugear scorecard agro

# Mostrar as últimas 10 execuções
ugear scorecard agro --last 10
ugear scorecard agro -n 10
```

---

## Comportamento global

- **Logging** é configurado por execução através das flags `--verbose` e `--json`
  no `ugear run`. O modo verbose define o nível como DEBUG; caso contrário,
  INFO é utilizado.
- **Códigos de saída**: comandos encerram com `0` em caso de sucesso. `ugear run`
  encerra com `1` quando um nome de pipeline desconhecido é fornecido.
- **Saída Rich**: toda a saída no terminal (tabelas, painéis, indicadores de status)
  é renderizada através do Rich com modo de terminal forçado.

---

## Ponto de entrada

A CLI é registrada como um console script no `pyproject.toml`:

```toml
[project.scripts]
ugear = "universal_gear.cli.main:app"
```

Após instalar o pacote (`pip install -e .`), o comando `ugear` fica disponível
no ambiente ativo.
