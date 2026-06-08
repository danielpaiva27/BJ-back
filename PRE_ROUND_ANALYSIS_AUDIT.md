# Auditoria da analise pre-rodada multi-sistema

Data: 2026-06-08

Etapa original: 22.6

Calibracao atual: 22.7

## Escopo

Esta auditoria fecha a Etapa 22 sem alterar pesos de contagem, estimativa de
edge, politica de banca, endpoint ou engine de decisao da mao.

Foram auditados:

- nucleo de contagem em `engine_core/counting`;
- estimativa de edge e politica em `engine_core/pre_round`;
- funcao `analyze_pre_round`;
- endpoint `POST /pre-round-analysis`;
- modelos e UI Angular da pre-rodada;
- independencia comportamental de `POST /analyze-hand`;
- cenarios reproduziveis do comparador.

## Arquivos principais

- `src/blackjack_risk_engine/engine_core/counting/systems.py`
- `src/blackjack_risk_engine/engine_core/counting/counts.py`
- `src/blackjack_risk_engine/engine_core/pre_round/analysis.py`
- `src/blackjack_risk_engine/engine_core/pre_round/edge_estimation.py`
- `src/blackjack_risk_engine/engine_core/pre_round/bankroll_policy.py`
- `app/routes/pre_round.py`
- `app/pre_round_schemas.py`
- `benchmarks/compare_pre_round_systems.py`
- `PRE_ROUND_COUNTING_SYSTEMS.md`

No frontend:

- `src/app/models/pre-round-analysis.models.ts`
- `src/app/services/blackjack-analysis.service.ts`
- `src/app/app.component.ts`
- `src/app/app.component.html`

## Resultado arquitetural

O fluxo pre-rodada e:

```text
seen_cards
  -> snapshot de cada sistema
  -> betting true count
  -> edge estimado
  -> politica protegida de banca
  -> response multi-sistema
```

O fluxo de decisao da mao permanece:

```text
player hand + dealer upcard + regras + composicao real do shoe
  -> acoes legais
  -> EV por acao
  -> recomendacao da engine
```

O snapshot pre-rodada exibido pelo frontend nao entra no payload de decisao da
mao. Um teste de regressao chama a pre-rodada entre duas chamadas identicas de
`/analyze-hand` e confirma que a analise de acoes e a recomendacao permanecem
iguais.

O endpoint `/analyze-hand` preserva seus campos legados auxiliares de contagem
e sugestao teorica. Essa compatibilidade nao deve ser confundida com uma
dependencia da recomendacao de Hit, Stand, Double, Split ou Surrender em
Hi-Opt II, Wong Halves ou no betting true count da nova pre-rodada.

## Sistemas e politica

Sistemas auditados:

- Hi-Lo, level 1 e ace-reckoned;
- Hi-Opt II, level 2, ace-neutral e ajustado por side count de ases;
- Wong Halves, level 3, fracionario e acumulado internamente em escala 2.

Politica auditada:

- `risk_capped_growth`;
- maior exposicao permitida pelo modelo exponencial de risco de quebra;
- variancia aproximada de 1.3;
- limite aproximado de risco de quebra de 5%;
- cap secundario de 5% da banca por rodada;
- arredondamento para baixo pela unidade minima;
- observar quando o edge e menor ou igual a zero.

Nao existem perfis de risco no request, response ou UI da pre-rodada. O valor
legado `moderate` continua restrito ao contrato de `/analyze-hand`.

## Cenarios do comparador

O comparador cobre:

1. shoe neutro;
2. muitas cartas baixas vistas;
3. muitas cartas altas vistas;
4. concentracao de 4 e 5;
5. excesso relativo de ases restantes;
6. falta relativa de ases;
7. shoe favoravel extremo com cap de banca;
8. o mesmo shoe extremo com payout 6:5.

Invariantes verificadas pelos testes:

- todos os cenarios retornam tres sistemas;
- nenhum numero e `NaN` ou infinito;
- os ranks nao excedem a composicao de seis decks;
- Hi-Opt II reage mais a 4 e 5 que Hi-Lo;
- os cenarios de ases produzem excessos com sinais opostos;
- o Wong Halves preserva escala e acumulador inteiro;
- a exposicao respeita o cap secundario de 5%;
- toda exposicao positiva respeita o limite estimado de risco de 5%;
- 6:5 piora o edge do mesmo shoe em relacao a 3:2.

## Validacoes executadas

Resultados da execucao de 2026-06-08:

```text
Backend pre-round:
  .\.venv\Scripts\python.exe -m pytest \
    tests\test_pre_round_bankroll_policy.py \
    tests\test_pre_round_analysis.py \
    tests\test_pre_round_analysis_api.py -q
  Resultado: 114 passed, 1 warning preexistente.

Backend completo:
  .\.venv\Scripts\python.exe -m pytest -q
  Resultado: 337 passed, 1 warning preexistente.

Comparador:
  .\.venv\Scripts\python.exe benchmarks\compare_pre_round_systems.py
  Resultado: 8 cenarios executados; conclusao bem-sucedida.

Frontend:
  node.exe node_modules\@angular\cli\bin\ng.js \
    test --watch=false --browsers=ChromeHeadless
  Resultado: 129 SUCCESS.

Build:
  node.exe node_modules\@angular\cli\bin\ng.js build
  Resultado: concluido; bundle inicial 424.87 kB, transferencia estimada
  105.39 kB.

Integridade de diff:
  git diff --check
  Resultado: sem erros nos repositorios backend e frontend.
```

O warning backend e o `StarletteDeprecationWarning` preexistente emitido por
`fastapi.testclient` sobre a transicao futura de `httpx` para `httpx2`.

Os testes de politica agora cobrem a formula exponencial, parametros invalidos,
arredondamento, cap de rodada e o invariante de risco. Eles estao incluidos no
total de 337 testes backend.

## Resumo quantitativo do comparador

| Cenario | Leitura principal |
| --- | --- |
| Shoe neutro | todos observaram; edge de -0.40% com as regras usadas |
| Cartas baixas removidas | Hi-Opt II teve o maior edge estimado, +1.64% |
| Cartas altas removidas | todos observaram; counts e edges negativos |
| Muitos 4 e 5 | Hi-Opt II playing RC +10 contra Hi-Lo RC +4 |
| Excesso relativo de ases | Hi-Opt II ace excess +1.38 |
| Falta relativa de ases | Hi-Opt II ace excess -5.23 |
| Favoravel extremo 3:2 | tres sistemas limitaram a exposicao a 50.00 |
| Mesmo shoe 6:5 | edge caiu 1.40 ponto percentual em cada sistema |

O cenario extremo exercitou o cap de 5% sobre banca 1000. Todos os valores
numericos passaram pela verificacao de finitude, sem `NaN` ou infinito.

Com payout 3:2, a exposicao extrema de 50 resultou em risco estimado de 2.60%
para Hi-Lo/Wong Halves e 0.32% para Hi-Opt II. Com payout 6:5, os mesmos
valores ficaram em 4.00% e 0.49%, respectivamente, ainda abaixo do limite.

## Calibracao 22.7

A politica anterior usava quarter-Kelly e cap de 2%. Ela foi substituida pela
politica `risk_capped_growth`, que resolve a maior exposicao permitida pelo
limite aproximado de risco de quebra de 5% e aplica um cap secundario de 5% da
banca por rodada.

Exemplo de regressao principal:

```text
bankroll = 1000
minimum_bet = 10
estimated_player_edge = 0.05

politica anterior: 0 unidades
politica atual: 2 unidades / 20
risco estimado: 2.1361%
limite: 5%
```

O frontend passou a mostrar o risco estimado e o limite em cada card com
exposicao positiva. Quando a sugestao e zero, mostra que nao ha exposicao
sugerida.

## Por que vantagem positiva pode virar observar

A politica `risk_capped_growth` continua sem forcar aposta quando o risco
estimado ultrapassaria 5%. Isso pode acontecer mesmo com edge positivo quando
a unidade minima da mesa e alta para a banca atual.

Exemplo de referencia:

```text
bankroll = 200
minimum_bet = 5
estimated_player_edge = 0.0196

max_bet_by_risk ~= 2.01
minimum_bet = 5
risk_if_minimum_bet ~= 29.93%
minimum_bankroll_required_for_minimum_bet ~= 496.73
status = positive_edge_minimum_bet_exceeds_risk_cap
```

Interpretacao esperada: o shoe pode estar favoravel, mas a banca atual nao
suporta a unidade minima dentro do limite aproximado de risco da politica.

## Limitacoes conhecidas

- A estimativa de edge nao e o EV exato da proxima mao.
- O fator de ajuste de ases do Hi-Opt II ainda nao foi calibrado por uma
  simulacao dedicada.
- A politica e deliberadamente protetiva e pode recomendar zero unidades com
  edge positivo pequeno.
- O risco de quebra e uma aproximacao baseada no edge estimado, nao uma
  garantia ou medicao completa do risco real.
- O modelo nao representa todos os limites de mesa, mudancas de aposta ou
  comportamento humano.
- Nao existem side bets nem indices de estrategia por sistema.
- `dealer_peek=false` ainda nao e modelado na heuristica pre-rodada.
- O modelo pressupoe shoe finito observavel.
- A engine de decisao ainda possui as limitacoes de split documentadas em
  `ENGINE_ACCURACY_AUDIT.md`.

## Proximos passos possiveis

- calibrar edge por sistema com simulacoes;
- revisar a politica de banca apenas se dados mostrarem excesso de
  conservadorismo;
- adicionar comparacao historica entre snapshots;
- formalizar o efeito de `dealer_peek=false`;
- estudar side bets apenas com finalidade educacional;
- documentar indices de estrategia sem usa-los como motor da decisao;
- implementar DP completo para split.

## Conclusao

A Etapa 22 pode ser considerada concluida quando o comparador, as suites
backend e frontend, o build Angular e `git diff --check` passarem. A feature
permanece educacional, sem promessa de lucro e com separacao explicita entre
leitura pre-rodada e decisao matematica durante a mao.
