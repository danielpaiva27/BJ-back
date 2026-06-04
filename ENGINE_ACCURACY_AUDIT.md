# Engine accuracy audit

Data da auditoria: 2026-06-04

## Objetivo

Auditar a precisao matematica da engine apos a Etapa 20.6, priorizando corretude sobre performance.

Esta etapa nao alterou frontend, nao alterou o contrato obrigatorio da API e nao reimplementou a engine. As mudancas ficaram restritas ao backend, testes, benchmark de comparacao e documentacao.

Conclusao curta: precisao aprovada para os caminhos atualmente suportados por DP (`stand`, `hit`, `double`, `surrender`) e para o modo recomendado `hybrid`, com limitacoes documentadas para split completo e regras avancadas.

## Metodologia

- Revisao dos modulos centrais:
  - `engine_core/hand.py`
  - `engine_core/dealer_dp.py`
  - `engine_core/action_ev.py`
  - `engine_core/monte_carlo_analysis.py`
  - `ev.py`
- Criacao de testes em `tests/test_engine_accuracy.py`.
- Uso de oraculos independentes pequenos nos testes:
  - recursao independente para distribuicao do dealer em decks sinteticos;
  - EV independente de Stand a partir da distribuicao do dealer;
  - enumeracao independente de Hit e Double em decks pequenos;
  - validacao manual de blackjack natural e composicao do shoe.
- Comparacao entre modos por script:
  - `benchmarks/compare_engine_modes.py`
  - `benchmarks/compare_engine_accuracy.py`
- Monte Carlo foi usado como validacao estatistica, nao como verdade absoluta.
- Tolerancia do auditor estatistico:
  - deterministic vs hybrid em acoes deterministicas: delta esperado `0`;
  - hybrid vs Monte Carlo: `max(0.02, 2.58 * erro_padrao_combinado)`;
  - seed fixa por cenario.

## Cenarios testados

O comparador de precisao cobre:

| Cenario | Mao do jogador | Dealer | Leitura |
| --- | --- | --- | --- |
| A | `["10", "6"]` | `10` | hard 16 vs 10 |
| B | `["A", "7"]` | `9` | soft 18 vs 9 |
| C | `["5", "6"]` | `6` | hard 11 vs 6 |
| D | `["8", "8"]` | `10` | par 8,8 vs 10 |
| E | `["A", "10"]` | `9` | blackjack natural |
| F | `["10", "2"]` | `2` | hard 12 vs 2 |
| G | `["10", "10"]` | `10` | hard 20 vs 10; tambem e par e aciona split |
| H | `["4", "5"]` | `3` | hard 9 vs 3 |

Tambem foram testadas composicoes alteradas do shoe:

- shoe rico em cartas altas: muitas cartas baixas removidas;
- shoe pobre em cartas altas: cartas `10` e `A` removidas;
- shoe quase neutro: remocao balanceada.

No cenario `11 vs 6`, o EV de Double ficou maior no shoe rico em cartas altas do que no shoe pobre em cartas altas, como esperado.

## Invariantes matematicos verificados

- Avaliacao de maos:
  - hard 16, soft 18, soft-to-hard, soft 21, hard 21, bust e blackjack natural;
  - `A,10,10` e `A,5,5` nao sao blackjack natural.
- Dealer:
  - hard 17 para;
  - 16 compra;
  - soft 17 para quando `dealer_hits_soft_17=False`;
  - soft 17 compra quando `dealer_hits_soft_17=True`;
  - distribuicao soma aproximadamente `1.0`;
  - probabilidades ficam em `[0, 1]`;
  - resultados validos: `17,18,19,20,21,bust`;
  - mesma entrada produz mesma saida.
- Stand:
  - jogador bust retorna `-1`;
  - empate contribui `0`;
  - dealer bust contribui `+1`;
  - formula direta por distribuicao foi validada;
  - 21 nao natural perde para blackjack natural do dealer.
- Surrender:
  - EV `-0.5` quando permitido;
  - nao aparece quando a regra desabilita;
  - nao aparece apos hit;
  - nao aparece em blackjack natural.
- Double:
  - compra exatamente uma carta;
  - bust apos double retorna `-2`;
  - win/loss de double usa multiplicador `2`;
  - push permanece `0`;
  - blackjack natural do dealer segue o fluxo existente e perde apenas a aposta original, pois e resolvido antes da acao.
- Hit:
  - enumera ranks restantes por `count_rank / total_remaining`;
  - ranks com count `0` nao entram na soma;
  - apos hit, a continuacao deterministica considera apenas `hit/stand`;
  - bust apos hit retorna `-1`.
- Sanidade:
  - sem `NaN`;
  - sem `Infinity`;
  - EV normal dentro dos limites esperados;
  - EV de Double dentro de `[-2, 2]`;
  - ranking ordenado por EV decrescente;
  - `best_action` e sempre a primeira acao retornada quando ha acoes validas.

## Comparacao entre modos

Resultado final do auditor `benchmarks/compare_engine_accuracy.py`, com `10000` simulacoes por acao Monte Carlo:

| Cenario | deterministic | hybrid | monte_carlo | legacy | Observacao |
| --- | --- | --- | --- | --- | --- |
| A | hit | hit | hit | hit | Todos dentro da tolerancia estatistica |
| B | hit | hit | hit | hit | Todos dentro da tolerancia estatistica |
| C | double | double | double | double | Amostra alta adicional confirmou convergencia |
| D | hit | split | split | split | Deterministic omite split; hybrid usa fallback |
| E | stand | stand | stand | stand | Blackjack natural exato |
| F | hit | hit | hit | hit | Todos dentro da tolerancia estatistica |
| G | stand | stand | stand | stand | `10,10` tambem permite split como fallback |
| H | double | double | double | double | Todos dentro da tolerancia estatistica |

Pontos quantitativos importantes:

- `deterministic` e `hybrid` tiveram delta `0` nas acoes DP suportadas.
- Em cenarios com split, `deterministic` marcou `split` como unsupported e `hybrid` usou Monte Carlo apenas para `split`.
- Todos os checks `hybrid vs monte_carlo` ficaram `mc_status=ok` no auditor final.
- O cenario C (`11 vs 6`) passou por checagem extra com `100000` simulacoes por acao:
  - hybrid Double: `0.6826646957912995`;
  - monte_carlo Double: `0.67666`, erro padrao `0.005725`;
  - legacy Double: `0.67974`, erro padrao `0.005721`.

## Discrepancias encontradas

### 21 nao natural contra blackjack natural do dealer

Impacto:

- Um 21 nao natural podia empatar contra blackjack natural do dealer no caminho deterministico.
- Isso afetava `stand` e continuacoes de `hit/double` que chegavam a total 21.

Causa provavel:

- `dealer_outcome_distribution` agrupa todo dealer `21` no mesmo bucket, sem distinguir blackjack natural de 21 feito com tres ou mais cartas.

Correcao feita:

- Adicionado `dealer_natural_blackjack_probability`.
- Ajustado `ev_stand` para mover a probabilidade de blackjack natural do dealer de `push` para `loss` quando o jogador tem 21 nao natural.

### Double contra blackjack natural do dealer

Impacto:

- O DP de Double multiplicava por 2 a perda contra blackjack natural do dealer.
- O fluxo existente de Monte Carlo/legado resolve blackjack natural do dealer antes da acao; nesse caso a perda e de uma unidade, nao duas.

Causa provavel:

- `ev_double` calculava `2 * EV(stand)` para todos os outcomes nao bust, incluindo o evento especial de blackjack natural do dealer.

Correcao feita:

- Ajustado `ev_double` para somar de volta a probabilidade inicial de blackjack natural do dealer no EV e corrigir o segundo momento.
- Isso alinhou Double deterministico com Monte Carlo/legado nos cenarios com dealer `A` ou `10`.

## Problemas nao corrigidos nesta etapa

### DP completa de Split

Impacto:

- `split` nao possui DP completa.
- `deterministic` omite `split` e marca como unsupported.
- `hybrid` usa fallback Monte Carlo para `split`.

Causa provavel:

- Split exige modelar multiplas maos, resplit, aces splitados, double after split e possiveis variacoes de regra.

Por que nao foi corrigido agora:

- Exigiria reescrita extensa de algoritmo e maior superficie de regras, fora do escopo da Etapa 20.7.

Plano futuro:

- Criar DP especifica de split basico antes de incluir resplit e regras avancadas.

### Regras avancadas de split e peek/no-peek

Impacto:

- Campos como `dealer_peek`, `double_after_split`, `hit_split_aces` e `resplit_aces` sao preservados no contrato, mas ainda nao governam uma modelagem matematica completa.

Causa provavel:

- A engine historicamente aceitou esses campos antes de implementar todas as variacoes de regra no nucleo de EV.

Por que nao foi corrigido agora:

- Corrigir no-peek e split avancado exigiria mudanca estrutural no modelo de ordem de eventos e no fallback de split.

Plano futuro:

- Definir formalmente variantes suportadas.
- Adicionar testes por variante.
- Implementar fluxo separado para regras no-peek se esse modo continuar publico.

### Politica de continuacao do Monte Carlo

Impacto:

- O DP deterministico de `hit` usa melhor continuacao entre `hit/stand`.
- Monte Carlo e legacy usam politica simplificada de estrategia basica para continuacao apos hit.
- Em alguns cenarios, Monte Carlo pode validar estatisticamente uma politica diferente, nao exatamente o mesmo controle otimo usado pela DP.

Por que nao foi corrigido agora:

- Trocar a politica do Monte Carlo por uma chamada otima de DP por estado aumentaria acoplamento e custo, e deve ser desenhado em etapa propria.

Plano futuro:

- Adicionar modo de Monte Carlo com continuacao otima ou deixar a diferenca mais explicita na metadata.

## Correcoes feitas

- `src/blackjack_risk_engine/engine_core/dealer_dp.py`
  - novo helper `dealer_natural_blackjack_probability`.
- `src/blackjack_risk_engine/engine_core/action_ev.py`
  - Stand corrige dealer natural contra 21 nao natural;
  - Double corrige dealer natural para perder uma unidade no fluxo atual.
- `tests/test_regression_baseline.py`
  - baseline atualizado para os EVs corrigidos.

## Testes adicionados

Arquivo novo:

- `tests/test_engine_accuracy.py`

Cobertura adicionada:

- avaliacao de hard/soft/bust/natural;
- regras S17/H17;
- invariantes da distribuicao do dealer;
- Stand por formula direta e oracle independente;
- Surrender permitido/nao permitido;
- Double por oracle independente;
- Hit por oracle independente;
- blackjack natural e 21 nao natural;
- composicao alterada do shoe;
- ranking e sanidade de EVs/probabilidades;
- consistencia deterministic/hybrid;
- fallback controlado para split.

## Scripts atualizados ou criados

- `benchmarks/compare_engine_modes.py`
  - expandido para cenarios A-H.
- `benchmarks/compare_engine_accuracy.py`
  - novo auditor de precisao entre modos;
  - registra melhor acao, EV por acao, metodo, simulacoes usadas, tempo e deltas;
  - calcula tolerancia estatistica com erro padrao combinado.

## Validacao final

Comandos executados no backend (`BJ-back`):

```powershell
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\python.exe benchmarks\compare_engine_modes.py
.\.venv\Scripts\python.exe benchmarks\compare_engine_accuracy.py
```

Resultado:

- `pytest`: `170 passed, 1 warning`.
- Warning remanescente: `StarletteDeprecationWarning` vindo de `fastapi.testclient`/`httpx`; sem impacto na engine.
- `compare_engine_modes.py`: executou os cenarios A-H sem erro.
- `compare_engine_accuracy.py`: executou os cenarios A-H com `10000` simulacoes por acao Monte Carlo; todos os checks Monte Carlo finais ficaram `mc_status=ok`.

## Recomendacoes futuras

1. Implementar DP de split basico.
2. Formalizar suporte a regras no-peek antes de prometer precisao plena para `dealer_peek=False`.
3. Separar explicitamente Monte Carlo de validacao estatistica e Monte Carlo de decisao, principalmente para politica de continuacao apos hit.
4. Adicionar testes parametrizados para blackjack natural com dealer `A` e `10` em mais composicoes sinteticas.
5. Adicionar auditoria especifica de regras avancadas de split quando elas forem implementadas.

## Conclusao

Precisao aprovada para o modo recomendado `hybrid` e para as acoes principais suportadas por DP.

Precisao pendente apenas para uma etapa futura de split completo, regras avancadas de split e modelagem formal de no-peek.
