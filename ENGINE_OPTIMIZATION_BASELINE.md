# Engine optimization baseline

Data do baseline: 2026-06-04

Este documento congela o comportamento atual da engine antes de qualquer otimizacao estrutural. O frontend e o contrato de `POST /analyze-hand` nao foram alterados.

## Como rodar os testes

Na raiz do backend (`BJ-back`):

```bash
pytest
```

Se o ambiente ainda nao tiver `pytest`, instale o extra de desenvolvimento:

```bash
python -m pip install -e ".[dev]"
```

Os testes de regressao adicionados ficam em `tests/test_regression_baseline.py` e cobrem:

- cenarios fixos com seed e EVs atuais;
- reprodutibilidade com seed, ignorando apenas `metadata.execution_time_ms`;
- payload atual do endpoint `/analyze-hand`;
- ranking de acoes na resposta.

Resultado desta etapa: `117 passed, 1 warning` com `pytest-8.4.2`. O warning vem de `fastapi.testclient`/Starlette e nao bloqueia a suite.

## Como rodar o benchmark

Na raiz do backend (`BJ-back`):

```bash
python benchmarks/benchmark_analyze_hand.py
```

O script roda os cenarios A-E com `10000`, `50000` e `100000` simulacoes por acao legal. Para iteracoes locais mais rapidas:

```bash
python benchmarks/benchmark_analyze_hand.py --simulations 1000 5000
```

Cada entrada imprime tempo total, tempo medio por analise, seed, resposta principal da engine, melhor acao e EVs por acao.

## Como rodar o profiling

Na raiz do backend (`BJ-back`):

```bash
python benchmarks/profile_analyze_hand.py
```

O script usa `cProfile` em um cenario pesado (`10,6` contra dealer `10`, com cartas vistas) e salva `profile.out`. Ele imprime:

- top 20 funcoes por tempo cumulativo;
- top 20 funcoes por tempo interno;
- resumo curto dos gargalos provaveis.

Para analisar depois:

```bash
python -m pstats profile.out
```

Comandos uteis dentro do pstats:

```text
sort cumulative
stats 20
sort tottime
stats 20
```

## Tempos encontrados

Ambiente de medicao: Windows, Python 3.14.3 da `.venv` do backend, rodando a partir de `BJ-back`.

| Cenario | Simulacoes | Seed | Tempo medio | Melhor acao | EVs |
| --- | ---: | ---: | ---: | --- | --- |
| A hard 16 vs 10 | 10000 | 30100 | 2.349731s | stand | stand=-0.57400, hit=-0.58150, double=-1.07720 |
| A hard 16 vs 10 | 50000 | 70100 | 11.690224s | stand | stand=-0.57364, hit=-0.57776, double=-1.08020 |
| A hard 16 vs 10 | 100000 | 120100 | 23.070434s | hit | hit=-0.57774, stand=-0.58068, double=-1.08080 |
| B soft 18 vs 9 | 10000 | 30200 | 2.624762s | hit | hit=-0.10930, stand=-0.18570, double=-0.29640 |
| B soft 18 vs 9 | 50000 | 70200 | 13.003721s | hit | hit=-0.09910, stand=-0.18358, double=-0.28444 |
| B soft 18 vs 9 | 100000 | 120200 | 26.255441s | hit | hit=-0.09560, stand=-0.18187, double=-0.28756 |
| C hard 11 vs 6 | 10000 | 30300 | 2.662229s | double | double=0.67340, hit=0.33280, stand=-0.15920 |
| C hard 11 vs 6 | 50000 | 70300 | 13.290812s | double | double=0.67444, hit=0.34310, stand=-0.14932 |
| C hard 11 vs 6 | 100000 | 120300 | 26.548921s | double | double=0.68146, hit=0.34351, stand=-0.15108 |
| D par 8 vs 10 | 10000 | 30400 | 3.339711s | split | split=-0.52750, hit=-0.55670, stand=-0.57400, double=-1.06470 |
| D par 8 vs 10 | 50000 | 70400 | 16.753942s | split | split=-0.53352, hit=-0.56566, stand=-0.57412, double=-1.07734 |
| D par 8 vs 10 | 100000 | 120400 | 33.319926s | split | split=-0.53041, hit=-0.57350, stand=-0.57362, double=-1.06222 |
| E blackjack natural | 10000 | 30500 | 0.636672s | stand | stand=1.50000 |
| E blackjack natural | 50000 | 70500 | 3.138435s | stand | stand=1.50000 |
| E blackjack natural | 100000 | 120500 | 6.369258s | stand | stand=1.50000 |

## Gargalos encontrados

Profile executado com cenario A, `100000` simulacoes por acao, seed `120100`.

- Tempo total perfilado: 93.804s em `cProfile`; tempo reportado pela engine: 94442.473ms.
- Gargalo cumulativo principal: `ev.py:370(_shuffle_simulation_deck)` com 71.885s em 300000 chamadas, dominado por `random.py:356(shuffle)` com 71.463s.
- Gargalo de tempo interno principal: `random.py:245(_randbelow_with_getrandbits)` com 33.075s em 90000003 chamadas.
- Segundo custo interno relevante: `random.py:356(shuffle)` com 17.538s.
- Custo de avaliacao de mao: `hand.py:53(total)` acumulou 14.116s e `hand.py:42(values)` acumulou 12.455s.
- Custo da simulacao de rodada: `simulation.py:49(simulate_round)` acumulou 22.091s.

Top cumulativo observado:

```text
ev.py:146(analyze_hand)                       cumtime=94.443s
ev.py:60(analyze_action)                      cumtime=94.442s
ev.py:370(_shuffle_simulation_deck)           cumtime=71.885s
random.py:356(shuffle)                        cumtime=71.463s
random.py:245(_randbelow_with_getrandbits)    cumtime=53.885s
```

Top tempo interno observado:

```text
random.py:245(_randbelow_with_getrandbits)    tottime=33.075s
random.py:356(shuffle)                        tottime=17.538s
Random.getrandbits                            tottime=12.849s
int.bit_length                                tottime=7.961s
hand.py:42(values)                            tottime=2.805s
```

## Observacoes

- Ainda nao foi feita nenhuma otimizacao.
- O benchmark mede o comportamento atual, inclusive custos de criar/embaralhar deck por simulacao.
- `profile.out`, arquivos `.pyc`, `__pycache__/` e saidas locais de benchmark estao no `.gitignore`.
- Ja existia um `app/__pycache__/main.cpython-314.pyc` rastreado/modificado antes desta etapa; este baseline nao remove nem reverte esse arquivo.

## Recomendacao para a proxima etapa

Usar o profile para atacar primeiro o maior custo cumulativo, provavelmente a combinacao de loop Monte Carlo, copia/embaralhamento de deck e reavaliacao de mao. A proxima etapa deve propor otimizacoes pequenas e mensuraveis, mantendo os testes de regressao e comparando cada mudanca contra este baseline.

## Etapa 20.2 — Normalizacao do estado interno

A camada matematica compacta foi separada em `src/blackjack_risk_engine/engine_core/`:

- `cards.py`: conversao string/rank, valores, pesos Hi-Lo, `deck_counts` e expansao/remocao de ranks.
- `hand.py`: funcoes puras de avaliacao por ranks, blackjack, bust e total incremental.
- `rules.py`: `CoreRules` normalizado e hashable.
- `state.py`: `CoreGameState` com `player_ranks`, `dealer_upcard_rank`, `seen_ranks`, `deck_counts` e regras.
- `adapters.py`: ponte entre tipos publicos/API e estado interno compacto.

Representacao interna:

```text
0=A, 1=2, 2=3, 3=4, 4=5, 5=6, 6=7, 7=8, 8=9, 9=10
```

`deck_counts` para 1 deck:

```text
(4, 4, 4, 4, 4, 4, 4, 4, 4, 16)
```

`deck_counts` para 6 decks:

```text
(24, 24, 24, 24, 24, 24, 24, 24, 24, 96)
```

Compatibilidade:

- `POST /analyze-hand` continua aceitando e retornando cartas como strings (`"A"` ate `"10"`).
- A rota FastAPI cria `CoreGameState` via adapter e passa para `analyze_hand`.
- A resposta publica continua sendo montada com as mesmas chaves: `input`, `rules`, `hand_analysis`, `counting`, `actions`, `recommendation`, `betting`, `metadata`.
- A ordem historica do shoe foi preservada na expansao usada pela simulacao, para manter seeds e testes de regressao estaveis.

Centralizacao de logica:

- `Hand` agora guarda ranks compactos internamente e atualiza total/soft aces de forma incremental com `engine_core.hand.add_card_to_total`.
- `Hand.values`, `Hand.total`, `is_soft`, `is_bust`, `is_blackjack` e split derivam do mesmo nucleo de ranks.
- `counting.hi_lo_value` delega para `engine_core.cards.hi_lo_weight`.

Resultado dos testes:

```text
127 passed, 1 warning
```

Comparacao rapida de benchmark em `100000` simulacoes por acao:

| Cenario | Baseline 20.1 | Etapa 20.2 | Variacao | Melhor acao preservada |
| --- | ---: | ---: | ---: | --- |
| A hard 16 vs 10 | 23.070434s | 21.094321s | -8.6% | sim |
| B soft 18 vs 9 | 26.255441s | 23.039421s | -12.2% | sim |
| C hard 11 vs 6 | 26.548921s | 23.603633s | -11.1% | sim |
| D par 8 vs 10 | 33.319926s | 30.229812s | -9.3% | sim |
| E blackjack natural | 6.369258s | 6.482078s | +1.8% | sim |

Observacao: antes do cache incremental no `Hand`, a primeira versao da separacao ficou mais lenta por reavaliar maos no loop quente. O ajuste manteve a nova arquitetura compacta e recuperou desempenho, ainda sem trocar o algoritmo Monte Carlo principal.

Preparacao para proximas etapas:

- `CoreGameState` e `CoreRules` sao hashable e podem servir como chave para cache/DP.
- `deck_counts` compacto ja esta disponivel para substituir listas de cartas em loops futuros.
- A camada FastAPI ficou isolada da representacao matematica interna.

## Etapa 20.3 — DP/cache da distribuicao do dealer

Foi criado `src/blackjack_risk_engine/engine_core/dealer_dp.py` com:

- `dealer_outcome_distribution(dealer_upcard_rank, deck_counts, dealer_hits_soft_17)`;
- `stand_ev_from_distribution(player_total, distribution)`;
- `natural_blackjack_stand_ev(...)`;
- helpers de cache `dealer_distribution_cache_info()` e `dealer_distribution_cache_clear()`.

Formato interno da distribuicao:

```text
(prob_17, prob_18, prob_19, prob_20, prob_21, prob_bust)
```

Algoritmo:

- O estado inicial adiciona a carta aberta do dealer ao total.
- `deck_counts` representa a composicao restante do shoe depois das cartas conhecidas.
- A recursao compra cada rank possivel com probabilidade `count / remaining_cards`.
- A cada compra, o rank e removido de uma nova tupla de contagens, evitando mutacao compartilhada.
- O cache usa a chave `(dealer_total, soft_aces, deck_counts_tuple, dealer_hits_soft_17)`.
- Estados terminais retornam distribuicoes unitarias para 17, 18, 19, 20, 21 ou bust.

Tratamento de soft 17:

- Se `dealer_hits_soft_17=False`, dealer para em total 17 mesmo com `soft_aces > 0`.
- Se `dealer_hits_soft_17=True`, dealer compra em `total == 17 and soft_aces > 0`.
- `soft_aces` e mantido pelo mesmo helper incremental `add_card_to_total` usado pelo nucleo de mao.

Integracao no EV:

- `analyze_action(..., action="stand")` agora usa DP deterministica.
- `hit`, `double`, `split` e `surrender` seguem o caminho existente.
- Para blackjack natural, `natural_blackjack_stand_ev` trata push contra blackjack do dealer e payout configurado.
- A resposta da API nao mudou; `actions[*]` continua expondo `ev`, taxas, contagens, desvio e intervalo.
- Para `stand`, `standard_error=0` e o intervalo 95% e exatamente `(EV, EV)`, pois nao ha erro amostral.

Resultado dos testes:

```text
134 passed, 1 warning
```

Benchmark completo apos a integracao do DP de stand:

| Cenario | Simulacoes | Etapa 20.2 | Etapa 20.3 | Variacao |
| --- | ---: | ---: | ---: | ---: |
| A hard 16 vs 10 | 100000 | 21.094321s | 14.121302s | -33.1% |
| B soft 18 vs 9 | 100000 | 23.039421s | 15.602711s | -32.3% |
| C hard 11 vs 6 | 100000 | 23.603633s | 15.803298s | -33.0% |
| D par 8 vs 10 | 100000 | 30.229812s | 23.101241s | -23.6% |
| E blackjack natural | 100000 | 6.482078s | 0.000291s | ~100% |

Benchmark direto da DP do dealer:

| Cenario | DP fria | DP cacheada media | Stand EV DP | Stand EV MC 10000 |
| --- | ---: | ---: | ---: | ---: |
| A hard 16 vs 10 | 0.000334600s | 0.000001849300s | -0.579830 | -0.575000 |
| B soft 18 vs 9 | 0.000532000s | 0.000001864100s | -0.182640 | -0.175700 |
| C hard 11 vs 6 | 0.001441400s | 0.000002023400s | -0.150826 | -0.153600 |
| D par 8 vs 10 | 0.000335400s | 0.000001840700s | -0.572826 | -0.572200 |
| E blackjack natural | 0.000531100s | 0.000001883700s | 1.500000 | 1.500000 |

Observacoes:

- A variacao de `stand_ev_monte_carlo` e esperada por amostragem; o DP e deterministico.
- Alguns rankings de baixa simulacao podem mudar porque `stand` deixou de ter ruido Monte Carlo.
- O maior ganho vem de remover uma acao inteira do loop de simulacao em maos comuns, e de eliminar completamente a simulacao de blackjack natural.

## Etapa 20.4 — EV deterministico de acoes principais

Foi criado `src/blackjack_risk_engine/engine_core/action_ev.py` com EV deterministico/memoizado para:

- `stand`;
- `hit`;
- `double`;
- `surrender`.

`split` permanece como fallback Monte Carlo nesta etapa.

Como cada EV e calculado:

- Stand: usa `dealer_outcome_distribution` e compara o total do jogador contra 17, 18, 19, 20, 21 e bust.
- Hit: expande cada rank disponivel em `deck_counts`, pondera por `count / total_remaining`, remove a carta e escolhe recursivamente a melhor continuacao entre `hit` e `stand`.
- Double: expande cada rank disponivel uma unica vez; se estourar retorna `-2`, caso contrario retorna `2 * EV(stand)` com o novo total.
- Surrender: retorna `-0.5` quando permitido.

Memoizacao:

- A classe `ActionEvCalculator` usa caches locais por calculo, evitando crescimento global descontrolado.
- O cache de hit/best/stand e limitado por `max_cache_states` (padrao `200000`).
- Se o limite for excedido, a integracao pode cair para Monte Carlo.
- A DP do dealer continua com `lru_cache(maxsize=200000)`, contendo total do dealer, soft aces, `deck_counts` e regra H17/S17 na chave.

Integracao:

- `analyze_hand` calcula `hit`, `stand`, `double` e `surrender` por `calculate_action_evs_deterministic`.
- Acoes nao suportadas pelo DP, atualmente `split`, sao calculadas pelo caminho Monte Carlo antigo.
- Para preservar reproducibilidade do fallback, sub-seeds continuam sendo gerados para todas as acoes legais na ordem historica.
- O contrato externo nao mudou. A resposta ganhou apenas metadata adicional dentro de `metadata`:
  - `analysis_method`;
  - `deterministic_actions`;
  - `monte_carlo_fallback_actions`;
  - `deterministic_cache_states`.

Resultado dos testes:

```text
141 passed, 1 warning
```

Benchmark completo apos a integracao de EV deterministico para acoes principais:

| Cenario | Simulacoes | Etapa 20.3 | Etapa 20.4 | Observacao |
| --- | ---: | ---: | ---: | --- |
| A hard 16 vs 10 | 100000 | 14.121302s | 0.000878s | sem Monte Carlo |
| B soft 18 vs 9 | 100000 | 15.602711s | 0.009509s | sem Monte Carlo, dealer cache quente |
| C hard 11 vs 6 | 100000 | 15.803298s | 0.003940s | sem Monte Carlo, dealer cache quente |
| D par 8 vs 10 | 100000 | 23.101241s | 8.633680s | split ainda usa Monte Carlo |
| E blackjack natural | 100000 | 0.000291s | 0.000294s | ja era deterministico |

Benchmark direto de `calculate_action_evs_deterministic`:

| Cenario | Tempo | Cache states | EVs | Fallback |
| --- | ---: | ---: | --- | --- |
| A hard 16 vs 10 | 0.005522s | 56 | hit=-0.572086, stand=-0.579830, double=-1.144172 | nenhum |
| B soft 18 vs 9 | 0.108395s | 1097 | hit=-0.098469, stand=-0.182640, double=-0.284825 | nenhum |
| C hard 11 vs 6 | 0.106792s | 416 | double=0.682665, hit=0.341332, stand=-0.150826 | nenhum |
| D par 8 vs 10 | 0.005880s | 56 | hit=-0.565397, stand=-0.572826, double=-1.130795 | split |
| E blackjack natural | 0.000019s | 0 | stand=1.500000 | nenhum |

Observacoes:

- Em cenarios sem split, `simulations` praticamente deixa de impactar a latencia do ranking.
- Em cenarios com split, a latencia ainda cresce com `simulations`, porque split continua no Monte Carlo.
- Como `hit`, `double` e `stand` agora sao deterministicos, seeds diferentes geram o mesmo ranking quando nao ha fallback Monte Carlo.
- O ranking pode mudar em relacao a benchmarks antigos porque o ruido amostral foi removido das acoes deterministicas.

## Etapa 20.5 - Monte Carlo otimizado, batch e paralelismo opcional

Foi criada uma camada explicita para separar os caminhos de analise:

- `engine_core/deterministic_analysis.py`: wrapper do EV deterministico.
- `engine_core/monte_carlo_analysis.py`: Monte Carlo otimizado por ranks/deck_counts.
- `engine_core/hybrid_analysis.py`: planejamento hibrido, mantendo DP por padrao e mandando apenas acoes sem suporte para Monte Carlo.

O que ainda usa Monte Carlo:

- `split` segue como fallback, pois ainda nao ha DP completa para split/resplit/double-after-split.
- Benchmarks estatisticos de comparacao ainda podem chamar `simulate_round` legado.
- Simulacoes de sessao/risk podem continuar usando Monte Carlo quando necessario.

Mudancas no loop Monte Carlo:

- O loop novo trabalha com ranks inteiros e `deck_counts` compacto.
- O sorteio nao embaralha uma lista grande por rodada; ele compra por composicao restante do shoe.
- Totais de mao iniciais sao pre-computados por chunk.
- Compras usam soma incremental rapida no loop quente.
- O contrato externo da API nao mudou. Foram adicionados campos opcionais no payload:
  - `monte_carlo_parallel_enabled`;
  - `simulation_chunk_size`;
  - `max_workers`.

Seeds e paralelismo:

- Single-process com a mesma seed e mesma configuracao e reprodutivel.
- Em modo paralelo, a seed principal gera seeds independentes por chunk.
- A agregacao soma EV, vitorias, derrotas, pushes e segundo momento sem depender da ordem de conclusao.
- Por padrao, o paralelismo fica desligado; quando ligado, so e usado acima de `parallel_threshold` e com mais de um chunk/worker.

Resultado dos testes:

```text
147 passed, 1 warning
```

Benchmark completo apos otimizar o fallback Monte Carlo:

| Cenario | Simulacoes | Etapa 20.4 | Etapa 20.5 | Observacao |
| --- | ---: | ---: | ---: | --- |
| A hard 16 vs 10 | 100000 | 0.000878s | 0.000699s | deterministico |
| B soft 18 vs 9 | 100000 | 0.009509s | 0.009923s | deterministico/cache |
| C hard 11 vs 6 | 100000 | 0.003940s | 0.003647s | deterministico/cache |
| D par 8 vs 10 | 100000 | 8.633680s | 0.583136s | split Monte Carlo otimizado |
| E blackjack natural | 100000 | 0.000294s | 0.000109s | deterministico |

Benchmark isolado do fallback Monte Carlo em `split`:

| Simulacoes | Legado objetos/shuffle | Otimizado single | Otimizado paralelo | Speedup single | Speedup paralelo | Delta EV single |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20000 | 1.788092s | 0.115800s | 0.221020s | 15.441x | 8.090x | +0.013900 |

Observacao sobre paralelo:

- Neste ambiente Windows/local, o single-process otimizado foi mais rapido que ProcessPool para 20000 simulacoes.
- O paralelo funcionou e agregou corretamente, mas o overhead de criar processos superou o ganho nesse tamanho.
- Para cargas maiores ou multiplos splits/cenarios em lote, o ponto de corte deve ser medido novamente.

Profiling atualizado:

Comando usado:

```powershell
python benchmarks/profile_analyze_hand.py --scenario split88 --simulations 100000
```

Top gargalos restantes por tempo interno:

| Funcao | Tempo interno | Chamadas | Observacao |
| --- | ---: | ---: | --- |
| `monte_carlo_analysis.py:_draw_rank` | 0.345990s | 450398 | sorteio ponderado por deck_counts |
| `monte_carlo_analysis.py:_simulate_round_from_counts` | 0.318115s | 100000 | corpo principal da rodada |
| `random.py:_randbelow_with_getrandbits` | 0.207576s | 450412 | custo do RNG |
| `random.py:randrange` | 0.169551s | 450412 | custo do RNG |
| `monte_carlo_analysis.py:_play_until_17_policy` | 0.124527s | 184010 | politica simplificada de split hands |

Leitura dos gargalos:

- O gargalo deixou de ser criacao de objetos, strings, validacao de ranks e recomputacao completa de maos.
- O custo dominante agora e o sorteio aleatorio ponderado e a propria simulacao restante de split.
- Numba nao foi adotado nesta etapa: o loop ainda esta simples em Python puro, com fallback seguro e sem nova dependencia obrigatoria.

Recomendacao para a proxima etapa:

- Implementar DP especifica para split basico ou uma aproximacao deterministica limitada.
- Se Monte Carlo continuar necessario em lotes grandes, avaliar um sampler por counts ainda mais compacto ou NumPy opcional com streams independentes.
- Medir novo ponto de corte do ProcessPool em cenarios realmente grandes antes de habilitar paralelismo por padrao.

## Etapa 20.6 - Modos de engine, validacao final e rollout seguro

Foi criado `engine_core/engine_mode.py` com os modos:

- `legacy`: usa o caminho antigo baseado em `simulate_round`, objetos `Card`/`Hand` e shuffle por rodada.
- `deterministic`: usa apenas EV deterministico/DP para acoes suportadas; acoes sem suporte, como `split`, sao omitidas e aparecem em `metadata.unsupported_actions`.
- `hybrid`: modo recomendado. Usa DP para `stand`, `hit`, `double` e `surrender`; usa Monte Carlo otimizado apenas para fallback, atualmente `split`.
- `monte_carlo`: usa Monte Carlo otimizado para todas as acoes legais, util para comparacao/validacao estatistica.

Configuracao:

- Variavel de ambiente: `ENGINE_MODE=hybrid`.
- Campo opcional no request: `engine_mode`.
- Se o request omite `engine_mode`, a engine usa `ENGINE_MODE`; se a variavel tambem estiver ausente, usa `hybrid`.
- O contrato obrigatorio do endpoint nao mudou. A metadata recebeu campos adicionais:
  - `engine_mode`;
  - `elapsed_ms`;
  - `simulations_used`;
  - `cache_hits`;
  - `cache_misses`;
  - `unsupported_actions`.

Scripts finais:

```powershell
python benchmarks/benchmark_analyze_hand.py
python benchmarks/profile_analyze_hand.py --scenario split88 --simulations 100000
python benchmarks/compare_engine_modes.py --simulations 1000
```

Comparacao entre modos, `1000` simulacoes:

| Cenario | Modo | Tempo | Melhor acao | Simulacoes reais | Observacao |
| --- | --- | ---: | --- | ---: | --- |
| A hard 16 vs 10 | legacy | 0.218268s | stand | 3000 | ruido MC mudou ranking |
| A hard 16 vs 10 | deterministic | 0.000827s | hit | 0 | igual ao DP |
| A hard 16 vs 10 | hybrid | 0.006134s | hit | 0 | recomendado |
| A hard 16 vs 10 | monte_carlo | 0.008402s | stand | 3000 | MC otimizado |
| D par 8 vs 10 | legacy | 0.316374s | stand | 4000 | ruido MC com split |
| D par 8 vs 10 | deterministic | 0.000924s | hit | 0 | split omitido |
| D par 8 vs 10 | hybrid | 0.012672s | hit | 1000 | split via MC otimizado |
| D par 8 vs 10 | monte_carlo | 0.014782s | hit | 4000 | todas as acoes via MC otimizado |
| E blackjack natural | legacy | 0.066074s | stand | 1000 | simula sem necessidade |
| E blackjack natural | hybrid | 0.000152s | stand | 0 | deterministico |

Benchmark final do modo `hybrid`, `100000` simulacoes:

| Cenario | Antes baseline 20.1 | Etapa 20.5/20.6 | Speedup aproximado | Metodo |
| --- | ---: | ---: | ---: | --- |
| A hard 16 vs 10 | 23.070434s | 0.000694s | 33243x | DP |
| B soft 18 vs 9 | 26.255441s | 0.009754s | 2692x | DP |
| C hard 11 vs 6 | 26.548921s | 0.003667s | 7240x | DP |
| D par 8 vs 10 | 33.319926s | 0.578513s | 58x | DP + split MC |
| E blackjack natural | 6.369258s | 0.000118s | 53977x | DP |

Benchmark isolado do fallback Monte Carlo:

| Simulacoes | Legado | Otimizado single | Otimizado paralelo | Speedup single |
| ---: | ---: | ---: | ---: | ---: |
| 20000 | 1.744195s | 0.116874s | 0.239780s | 14.924x |

Profiling final, `split88` com `100000` simulacoes:

| Gargalo restante | Tempo interno | Chamadas | Leitura |
| --- | ---: | ---: | --- |
| `_draw_rank` | 0.353764s | 450398 | sorteio ponderado por composicao |
| `_simulate_round_from_counts` | 0.324592s | 100000 | corpo principal da rodada MC |
| `random._randbelow_with_getrandbits` | 0.224159s | 450412 | custo do RNG |
| `random.randrange` | 0.174317s | 450412 | custo do RNG |
| `_play_until_17_policy` | 0.123139s | 184010 | politica temporaria das maos splitadas |

Limitacoes conhecidas:

- `split` ainda nao tem DP completa.
- `double_after_split`, resplit e regras avancadas de split continuam limitadas no modelo atual.
- `surrender` depende da regra `surrender_allowed`.
- Numba nao foi adotado; permanece como otimizacao opcional futura.
- Monte Carlo paralelo pode ter pequenas diferencas estatisticas por chunk/seed e nao e default.
- O modo `deterministic` pode omitir `split`; use `hybrid` para producao.

Recomendacao de rollout:

- Usar `ENGINE_MODE=hybrid` por padrao.
- Manter `legacy` disponivel apenas para comparacao e rollback tecnico.
- Usar `monte_carlo` em validacoes estatisticas ou investigacoes.
- Usar `deterministic` para cenarios em que a decisao precisa ser totalmente sem ruido e sem acoes nao suportadas.

Proximos passos:

- Criar DP limitada para split basico.
- Medir ProcessPool apenas em jobs maiores antes de habilitar paralelismo por default.
- Avaliar um sampler vetorizado opcional para Monte Carlo em massa.

## Fechamento operacional da Etapa 20.6 (validacao final)

Comandos executados no backend (`BJ-back`) nesta validacao final:

```powershell
pytest
pytest -k "engine_mode or analyze_hand or rollout or compare"
python benchmarks/compare_engine_modes.py
python benchmarks/benchmark_analyze_hand.py
python benchmarks/profile_analyze_hand.py
Remove-Item -LiteralPath "profile.out" -ErrorAction SilentlyContinue
git ls-files | Select-String "\.pyc$" | ForEach-Object { git rm --cached $_.Line }
```

Resultado dos testes:

- Suite completa: `154 passed, 1 warning`.
- Suite focada de rollout/modos: `26 passed, 128 deselected, 1 warning`.
- Warning remanescente: deprecacao de `starlette.testclient`/`httpx`, sem impacto funcional no rollout de engine mode.

Resultado do comparador de modos:

- Modos validados sem crash: `legacy`, `deterministic`, `hybrid`, `monte_carlo`.
- `hybrid` e `deterministic` alinharam EV em cenarios sem fallback.
- Em par `8,8` vs dealer `10`, `deterministic` reportou limitacao controlada com `unsupported=['split']` e sem excecao inesperada.
- `hybrid` executou fallback de `split` com Monte Carlo otimizado e manteve metadata de metodo/simulacoes.

Resultado do benchmark final (`benchmark_analyze_hand.py`):

- O output incluiu `engine_mode`, `method`/`analysis_method`, `simulations_used`, tempo total e `best_action`.
- Cenarios sem fallback (A/B/C/E) executaram com `simulations_used=0` em `hybrid`.
- Cenario de split (D) usou `deterministic_dp_with_monte_carlo_fallback` com `simulations_used` proporcional ao volume configurado.

Resultado do profile final (`profile_analyze_hand.py`):

- O output incluiu `engine_mode=hybrid`, `analysis_method=deterministic_dp` e `simulations_used=0` no cenario perfilado.
- Top cumulativo: `ev.py:395(analyze_hand)`, `ev.py:290(_run_engine_mode)`, `hybrid_analysis.py:20`, `deterministic_analysis.py:9`.
- Top interno: `dealer_dp.py:122(_cached_dealer_distribution)` seguido de validacao de rank/soma incremental.
- `profile.out` foi removido apos o profile.

Higiene de repositorio apos validacao:

- `.pyc` historicamente rastreados foram removidos do indice com `git rm --cached`.
- `profile.out` nao permaneceu rastreado.
- `.gitignore` cobre `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`, `.pytest_cache/` e `profile.out`.

Contrato da API e rollout:

- `engine_mode` permanece opcional no request.
- Ausencia de `engine_mode` no payload continua usando `ENGINE_MODE`, com fallback para `hybrid`.
- O payload principal usado pelo frontend foi preservado; apenas metadata adicional foi expandida.
