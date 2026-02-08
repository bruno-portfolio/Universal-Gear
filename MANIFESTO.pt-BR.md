# Universal Gear — Manifesto

*[Leia em Ingles](MANIFESTO.md)*

---

## Filosofia Central

Toda decisão é tomada sob incerteza.
O Universal Gear não finge eliminá-la — ele estrutura o processo
de decidir *apesar* dela.

O pipeline de 6 estágios espelha como humanos realmente raciocinam:

1. **Observar** dados imperfeitos
2. **Comprimir** em sinais
3. **Formar** hipóteses
4. **Simular** cenários
5. **Decidir**
6. **Aprender** com os resultados

Nenhum estágio finge ser perfeito. Cada um reconhece seus limites e os carrega adiante.

Código de qualidade é inegociável. O codebase é um produto público desde o dia zero.
"Funciona" não é o critério de qualidade — **"um dev sênior não teria nada a apontar"** é.

Transparência das limitações: se um modelo ou heurística tem uma limitação conhecida,
documente. Nunca venda certeza onde existe incerteza.
Honestidade acima da conveniência — sempre.

Aberto por padrão: licença MIT, extensível via plugins, core agnóstico de domínio.
A engrenagem pertence a quem quiser girá-la.

---

## Princípios

1. **Observação é imperfeita — e tudo bem.**
   Flags de qualidade viajam com os dados. Dados imperfeitos não são descartados;
   são rotulados.

2. **Compressão é lossy por design.**
   Abstrações servem a um propósito. Cada passo de compressão declara o que
   preserva e o que descarta.

3. **Hipóteses devem ser falsificáveis.**
   Toda hipótese carrega tanto critérios de validação *quanto* de falsificação.
   Uma hipótese que não pode ser refutada não é uma hipótese — é uma crença.

4. **Cenários são condicionais.**
   "Se X então Y" — com premissas explícitas. Sem premissas ocultas, sem constantes
   mágicas enterradas no código.

5. **Decisões têm custo-de-erro.**
   Falsos positivos e falsos negativos são documentados antecipadamente. O framework
   obriga você a dizer como é a falha *antes* de decidir.

6. **Feedback fecha o loop.**
   Scorecards avaliam decisões passadas para calibrar as futuras. Quem não mede
   seus próprios erros está condenado a repeti-los.

---

## Ética do Desenvolvedor

**Atribuição honesta.**
Nenhum código de terceiros sem licença compatível. Crédito a quem merece,
sem exceções.

**Sem dark patterns.**
Nenhum código que esconda falhas ou silencie exceções. Se algo quebra,
quebra alto. Um erro silencioso é um erro duas vezes.

**Dados do usuário.**
O framework nunca loga, persiste ou transmite dados do pipeline sem consentimento
explícito. Zero telemetria por padrão. A confiança do usuário é inegociável.

**Defaults conservadores.**
Menos acesso, não mais. Toda permissão é opt-in. Na dúvida, negue.

---

## Acessibilidade como Principio

Raciocinio estruturado nao e privilegio de quem programa.
O framework existe em multiplas camadas -- codigo, planilhas, conteudo -- pra que
qualquer pessoa possa decidir melhor com as ferramentas que ja tem.

A engrenagem gira pra traders e pra donos de pequeno negocio. Pra analistas com
Python e pra gente com um navegador. Cada camada baixa a barreira sem baixar o padrao.

---

## Nota Final

Universal Gear é um framework para raciocínio estruturado sob
incerteza. Não é um oráculo. Não vai te dizer o que fazer — vai te
obrigar a *mostrar seu trabalho* enquanto decide.

Se você quer respostas fáceis, aqui não é o lugar.
Se você quer decidir melhor sabendo que pode estar errado — bem-vindo.

---

*Licença MIT. Feito no Brasil, pensado para o mundo.*
