# Machine EV pre-round

## 1. Conceito

Machine EV e uma analise computacional pre-rodada para estimar a vantagem da
proxima mao com base na composicao real restante do shoe.

Ela nao e sistema humano de contagem e nao entra como quarto sistema em
`POST /pre-round-analysis`.

## 2. Arquitetura

O modulo interno de Machine EV organiza:

- input estrutural da analise;
- configuracao de avaliacao;
- resumo publico da feature;
- metricas internas de engenharia/debug;
- resultado interno completo.

O resumo publico da Machine EV permanece focado em edge e risco, sem campos de
contagem humana.

## 3. Enumerador de estados observaveis

O enumerador pre-deal calcula todos os estados iniciais observaveis da proxima
mao, em ordem:

1. primeira carta do jogador;
2. carta aberta do dealer;
3. segunda carta do jogador.

Cada caminho usa probabilidade sem reposicao. O `shoe_after` remove somente
essas tres cartas.

Regras importantes:

- dealer hole card nao e enumerada e permanece desconhecida;
- estados equivalentes sao canonizados e agregados;
- shoes invalidos (contagem negativa, rank invalido, menos de 3 cartas) sao
	rejeitados.

## 4. Evaluator pela engine atual

Cada estado observavel e convertido para estado da engine atual. A Machine EV
nao cria uma segunda estrategia de blackjack; ela reutiliza o motor existente
para avaliar a melhor acao por estado.

No caminho publico padrao, `stand`, `double` e `surrender` usam avaliacao
deterministica. `hit` usa uma aproximacao deterministica por composicao, com
probabilidades fixas do shoe restante nas compras futuras. Monte Carlo curto
nao participa da escolha do melhor EV publico.

O agregador publico aplica essa politica mesmo se um modo experimental for
solicitado. Modos Monte Carlo/legacy permanecem restritos a avaliacao interna
por estado e nao controlam o edge retornado pela Machine EV publica.

Enquanto nao houver EV deterministico robusto de split, `split` fica fora do
`best_ev` publico. A exclusao e registrada apenas em warnings/debug internos
como `split_ev_not_used_in_public_edge`.

O EV final e calculado por media ponderada:

```text
machine_ev = soma(probabilidade_do_estado * melhor_ev_do_estado)
```

Esse valor alimenta `estimated_next_hand_edge` e `raw_ev_per_unit`.

## 5. Risco da aposta minima

Com `bankroll` e `minimum_bet` disponiveis, a Machine EV calcula:

- `risk_if_minimum_bet`;
- `minimum_bankroll_required_for_minimum_bet`.

O diagnostico reutiliza a politica existente (`risk_capped_growth`) e a
variancia fallback configurada nesta etapa.

## 6. Performance e guardrails

Nesta feature, a enumeracao dos estados observaveis e exata (sem sampling).

Metricas internas:

- `states_evaluated`;
- `duration_ms`;
- `cache_hits` e `cache_misses`;
- `timed_out`;
- `warnings`.

O cache e local por chamada. `max_duration_ms` e observacional: pode marcar
`timed_out`, mas nao interrompe o calculo.

Os caminhos `--smoke` de benchmark e audit usam um cenario curto. Validacoes
full-shoe de 6/8 decks ficam em scripts/benchmarks explicitos ou testes `slow`,
fora do `pytest` padrao.

## 7. Endpoint dedicado

Endpoint da feature:

- `POST /pre-round-analysis/machine-ev`

Contrato publico por padrao:

- identificacao da Machine EV;
- `estimated_next_hand_edge`;
- `risk_if_minimum_bet`;
- `minimum_bankroll_required_for_minimum_bet`;
- `recommendation_status` e `recommendation_text`.

`debug_metrics` so aparece quando `include_debug_metrics=true`.

Importante:

- Machine EV continua separada de `POST /pre-round-analysis`;
- nao altera `POST /analyze-hand`;
- nao adiciona campos de sistemas humanos.

## 8. UI atual

No frontend, Machine EV aparece em card separado e mostra somente:

- vantagem estimada da proxima mao;
- risco se apostar o minimo;
- banca estimada necessaria para o minimo.

Debug metrics nao sao exibidas na UI.

## 9. Limitacoes

- diagnostico de risco depende da variancia fallback atual;
- EV de `hit` usa aproximacao deterministica por composicao;
- EV de `split` nao participa do edge publico nesta etapa;
- valores dependem da engine, regras e snapshot analisado;
- nao e prova de lucratividade;
- nao recomenda valor real de aposta.

## 10. Etica e uso responsavel

Machine EV e ferramenta tecnica e educacional. A documentacao evita promessas
de lucro, linguagem de aposta segura e afirmacoes de infalibilidade.

## Referencias

- [MACHINE_EV_FEATURE_SUMMARY.md](MACHINE_EV_FEATURE_SUMMARY.md)
- [MACHINE_EV_COMPARISON.md](MACHINE_EV_COMPARISON.md)
- [MACHINE_EV_ACCURACY_AUDIT.md](MACHINE_EV_ACCURACY_AUDIT.md)
