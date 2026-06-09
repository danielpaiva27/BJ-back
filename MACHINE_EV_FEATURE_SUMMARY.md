# Machine EV feature summary

## 1. O que e Machine EV

Machine EV e uma analise computacional pre-rodada que estima a vantagem da
proxima mao a partir da composicao real restante do shoe. O calculo usa a
engine atual de decisao do projeto para avaliar estados iniciais observaveis e
produzir um EV medio ponderado.

## 2. O que ela nao e

Machine EV nao e:

- um quarto sistema humano de contagem;
- uma sugestao de aposta real;
- prova de lucro;
- garantia de resultado individual;
- substituto da avaliacao de acoes da mao atual.

## 3. Diferenca para sistemas humanos

Hi-Lo, Hi-Opt II e Wong Halves sao proxies comprimidos baseados em contagem.
Machine EV usa composicao real do shoe e avaliacao computacional por estado.

- Hi-Lo: resumo por running/true count.
- Hi-Opt II: separa playing count e betting count com ajuste de ases.
- Wong Halves: contagem fracionaria escalada para auditoria.
- Machine EV: enumera estados observaveis e consulta a engine atual para cada
  estado.

Divergencia entre Machine EV e um sistema humano nao significa erro automatico.
Ela pode refletir a diferenca entre um proxy comprimido e uma leitura por
composicao real.

## 4. Fluxo tecnico resumido

1. Constroi o shoe atual com base em `number_of_decks` e `seen_cards`.
2. Enumera estados iniciais observaveis da proxima mao (sem dealer hole card).
3. Avalia cada estado com a engine atual de decisao.
4. Calcula media ponderada do melhor EV por estado.
5. Gera diagnostico de risco para aposta minima (quando bankroll/minimo estao
   presentes).

## 5. Endpoint e contrato de produto

Endpoint dedicado:

- `POST /pre-round-analysis/machine-ev`

A Machine EV permanece separada de `POST /pre-round-analysis` e nao e adicionada
como quarto sistema humano.

Resposta publica focada em:

- `estimated_next_hand_edge`;
- `risk_if_minimum_bet`;
- `minimum_bankroll_required_for_minimum_bet`;
- `recommendation_status` e `recommendation_text`.

## 6. UI (frontend)

A UI apresenta a Machine EV em card separado dos sistemas humanos e mostra
somente:

- vantagem estimada da proxima mao;
- risco se apostar o minimo;
- banca estimada necessaria para o minimo.

A UI nao exibe `suggested_units`, `suggested_amount` nem metricas de debug.

## 7. Performance e observabilidade

- Enumeracao exata dos estados iniciais observaveis (sem sampling).
- Cache local por chamada para evitar reavaliacao de estados repetidos.
- `duration_ms` e `timed_out` sao metricas internas de observabilidade/debug.
- `timed_out` nao interrompe o calculo exato nesta etapa.

## 8. Benchmark e accuracy audit

Benchmark comparativo:

- `benchmarks/compare_machine_ev_vs_counting_systems.py`
- `benchmarks/benchmark_machine_ev.py`

Accuracy audit:

- `benchmarks/audit_machine_ev_accuracy.py`
- `MACHINE_EV_ACCURACY_AUDIT.md`

Leitura recomendada:

- Benchmark mostra convergencias/divergencias entre modelos.
- Accuracy audit valida invariantes, cenarios e direcoes no modelo atual.
- Divergencia em benchmark nao implica falha automatica.

## 9. Limitacoes conhecidas

- O diagnostico de risco ainda usa variancia fallback configurada.
- A feature nao prova lucratividade e nao elimina variancia de curto prazo.
- A feature nao recomenda valor real de aposta.
- Os valores dependem da engine atual, das regras e do snapshot analisado.

## 10. Linguagem etica

A documentacao da Machine EV deve manter linguagem educacional e tecnica:

- sem promessas de lucro;
- sem linguagem de aposta segura;
- sem afirmacoes de infalibilidade;
- com limites e incertezas explicitos.

## Glossario curto

- Machine EV: analise computacional pre-rodada baseada na composicao real.
- Estado inicial observavel: combinacao das duas cartas do jogador e upcard do
  dealer, sem hole card.
- Shoe composition: distribuicao atual de cartas remanescentes no shoe.
- EV ponderado: media do EV por estado, ponderada pela probabilidade de cada
  estado.
- Contagem humana: proxy comprimido de vantagem (Hi-Lo, Hi-Opt II, Wong
  Halves).
- Risk of ruin: probabilidade aproximada de quebrar a banca em uma politica de
  aposta.
- Banca necessaria para minimo: bankroll estimado para manter a aposta minima
  sob limite de risco.
- Debug metrics: metricas internas de engenharia, nao foco de UI.

## Checklist final da feature

- [x] Backend evaluator implementado.
- [x] Endpoint dedicado criado.
- [x] Frontend card separado.
- [x] Debug metrics ocultas por padrao.
- [x] Benchmark criado.
- [x] Accuracy audit criado.
- [x] Testes backend passando.
- [x] Testes frontend passando.
- [x] Machine EV nao e quarto sistema humano.
- [x] Nao revela dealer hole card.
- [x] Nao sugere unidade/valor de aposta.
- [x] Nao usa linguagem de lucro garantido.

## Documentos relacionados

- [MACHINE_EV_PRE_ROUND.md](MACHINE_EV_PRE_ROUND.md)
- [MACHINE_EV_COMPARISON.md](MACHINE_EV_COMPARISON.md)
- [MACHINE_EV_ACCURACY_AUDIT.md](MACHINE_EV_ACCURACY_AUDIT.md)
