# Machine EV Final Regression Report

## Data da regressao

- Data: 2026-06-09
- Workspace validado: BJ-back e BJ-front

## Escopo validado

- backend
- frontend
- endpoints
- benchmarks
- accuracy audit
- documentacao
- UI da Machine EV

## Status inicial dos repositorios

O working tree nao estava limpo no inicio desta etapa.

Backend (status inicial):

- M .gitignore
- M README.md
- M app/pre_round_schemas.py
- M app/routes/pre_round.py
- ?? MACHINE_EV_ACCURACY_AUDIT.md
- ?? MACHINE_EV_COMPARISON.md
- ?? MACHINE_EV_FEATURE_SUMMARY.md
- ?? MACHINE_EV_PRE_ROUND.md
- ?? benchmarks/audit_machine_ev_accuracy.py
- ?? benchmarks/benchmark_machine_ev.py
- ?? benchmarks/compare_machine_ev_vs_counting_systems.py
- ?? src/blackjack_risk_engine/engine_core/pre_round/machine_ev/
- ?? tests/test_machine_ev_accuracy_audit.py
- ?? tests/test_machine_ev_api.py
- ?? tests/test_machine_ev_benchmark.py
- ?? tests/test_machine_ev_evaluator.py
- ?? tests/test_machine_ev_models.py
- ?? tests/test_machine_ev_predeal_enumerator.py

Frontend (status inicial):

- M README.md
- M src/app/app.component.html
- M src/app/app.component.spec.ts
- M src/app/app.component.ts
- M src/app/models/pre-round-analysis.models.ts
- M src/app/services/blackjack-analysis.service.spec.ts
- M src/app/services/blackjack-analysis.service.ts
- M src/styles.scss

Nenhuma dessas alteracoes pendentes foi sobrescrita por necessidade desta etapa.

## Resumo executivo

- Machine EV validada em regressao geral final.
- Endpoint dedicado permaneceu preservado em /pre-round-analysis/machine-ev.
- /pre-round-analysis continuou com apenas Hi-Lo, Hi-Opt II e Wong Halves.
- Card separado de Machine EV no frontend permaneceu preservado.
- Metricas internas continuam opt-in no backend e nao aparecem na UI.
- Nao houve adicao de sugestao de aposta para Machine EV.

## Comandos executados

| Repositorio | Comando | Resultado | Observacoes |
|---|---|---|---|
| BJ-back | git status --short | OK | Working tree ja estava com alteracoes pendentes de etapas anteriores. |
| BJ-front | git status --short | OK | Working tree ja estava com alteracoes pendentes de etapas anteriores. |
| BJ-back | .venv/Scripts/python.exe -m pytest tests/test_machine_ev_models.py tests/test_machine_ev_predeal_enumerator.py tests/test_machine_ev_evaluator.py tests/test_machine_ev_api.py tests/test_machine_ev_benchmark.py tests/test_machine_ev_accuracy_audit.py -q | PASS | 117 passed, 1 warning (StarletteDeprecationWarning). |
| BJ-back | .venv/Scripts/python.exe -m pytest -q | PASS | 476 passed, 1 warning (StarletteDeprecationWarning). |
| BJ-back | .venv/Scripts/python.exe benchmarks/compare_machine_ev_vs_counting_systems.py --smoke | PASS | 2 cenarios executados. |
| BJ-back | .venv/Scripts/python.exe benchmarks/audit_machine_ev_accuracy.py --smoke | PASS | Overall PASS. |
| BJ-back | .venv/Scripts/python.exe benchmarks/benchmark_machine_ev.py | PASS | 4 cenarios; 2 com timed_out true (observacional), resultado mantido exato. |
| BJ-front | git diff --check | OK | Sem erro de diff; avisos CRLF no working copy. |
| BJ-front | npm test -- --watch=false | PASS | TOTAL: 155 SUCCESS; logs de erro esperados em testes de falha controlada; aviso Node v19 nao-LTS. |
| BJ-front | npm run build | PASS | Bundle inicial: 437.04 kB raw, 107.51 kB estimated transfer; aviso Node v19 nao-LTS. |
| BJ-front | npm pkg get scripts.lint | OK | Sem script de lint definido ({}). Lint nao executado por nao existir script. |
| BJ-back | git diff --check (final) | OK | Sem erro de diff; avisos CRLF no working copy. |
| BJ-back | git status --short (final) | OK | Mantem alteracoes pendentes de etapas anteriores; inclui MACHINE_EV_FINAL_REGRESSION.md. |
| BJ-front | git diff --check (final) | OK | Sem erro de diff; avisos CRLF no working copy. |
| BJ-front | git status --short (final) | OK | Mantem alteracoes pendentes de etapas anteriores; sem alteracoes acidentais de build/cache. |

## Resultados backend

- Testes Machine EV focados: PASS (117).
- Suite backend completa: PASS (476).
- Benchmark comparativo smoke: PASS.
- Accuracy audit smoke: PASS.
- Benchmark Machine EV basico: PASS.
- Warning relevante: StarletteDeprecationWarning em fastapi.testclient (nao bloqueante).

## Regressao de endpoints backend

Confirmacoes por testes e inspecao:

- /pre-round-analysis continua retornando apenas sistemas humanos:
  - hi_lo
  - hi_opt_ii
  - wong_halves
- /pre-round-analysis/machine-ev continua separado.
- /analyze-hand permanece intacto.
- Machine EV nao foi adicionada como quarto sistema humano.
- Resposta padrao de Machine EV nao retorna debug_metrics e campos internos.
- Resposta padrao de Machine EV nao retorna suggested_units/suggested_amount.
- Resposta padrao de Machine EV nao expoe campos humanos de contagem.

Evidencias principais:

- tests/test_pre_round_analysis_api.py
- tests/test_machine_ev_api.py
- app/routes/pre_round.py
- app/pre_round_schemas.py
- app/routes/analysis.py

## Resultados frontend

- Testes: PASS (155 SUCCESS).
- Build: PASS.
- Bundle inicial (build):
  - main-X534NJNB.js: 370.56 kB raw, 90.24 kB transfer.
  - polyfills-FFHMD2TL.js: 33.71 kB raw, 11.02 kB transfer.
  - styles-GFI4MHSR.css: 32.77 kB raw, 6.26 kB transfer.
  - total inicial: 437.04 kB raw, 107.51 kB transfer.
- Lint: nao executado (script ausente no package.json).
- Warnings relevantes:
  - aviso de Node v19 nao-LTS em test/build.
  - avisos CRLF no git diff --check.

## Regressao UX/frontend da Machine EV

Confirmacoes por inspecao e testes:

- [x] Card separado de Machine EV preservado.
- [x] Nao aparece como quarto sistema humano.
- [x] Mostra apenas 3 campos principais (vantagem, risco do minimo, banca necessaria).
- [x] Debug metrics nao aparecem na UI.
- [x] Campos humanos de contagem nao aparecem no card Machine EV.
- [x] Nao ha suggested_units/suggested_amount no card Machine EV.
- [x] Loading de Machine EV e isolado.
- [x] Erro de Machine EV e isolado.
- [x] Estado stale funciona.
- [x] Respostas antigas sao descartadas por snapshot/generation.
- [x] null/undefined/NaN/Infinity renderizam como —.
- [x] Textos permanecem eticos.

Evidencias principais:

- src/app/app.component.html
- src/app/app.component.ts
- src/app/app.component.spec.ts
- src/app/services/blackjack-analysis.service.ts

## Validacao de linguagem etica

Termos varridos:

- garantido
- garantia
- aposta segura
- certeza
- vencer o cassino
- lucro certo
- infalivel/infalível
- jogue agora
- aposta recomendada

Resultado:

- Backend docs: ocorrencias em contexto negativo/documental (aceitavel), sem promessa positiva.
- Frontend codigo e README: sem promessa positiva; ocorrencias em testes de proibicao e asserts de ausencia (aceitavel).

## Validacao de documentacao

Backend confirmado:

- MACHINE_EV_FEATURE_SUMMARY.md existe.
- MACHINE_EV_PRE_ROUND.md existe.
- MACHINE_EV_COMPARISON.md existe.
- MACHINE_EV_ACCURACY_AUDIT.md existe.
- README.md aponta para os quatro documentos.

Frontend confirmado:

- README.md tem secao Machine EV UI.
- A secao explica card separado, 3 campos visiveis, loading/erro/stale e ausencia de debug metrics.

Consistencia semantica confirmada na documentacao:

- Machine EV nao e contagem humana.
- Machine EV nao e replicavel manualmente.
- Machine EV usa composicao real do shoe.
- Machine EV usa endpoint dedicado.
- Machine EV nao e quarto sistema humano.
- Machine EV nao garante lucro.
- Machine EV nao recomenda aposta real.
- Risco usa variancia fallback.
- Debug metrics sao internas.

## Checagem de diff e arquivos alterados

- Esta etapa adicionou somente MACHINE_EV_FINAL_REGRESSION.md.
- Nao foram introduzidas alteracoes acidentais em dist, cache ou artefatos de build.
- Alteracoes de codigo ja existentes no working tree permanecem de etapas anteriores.

## Criterios finais

- [x] Machine EV continua separada.
- [x] /pre-round-analysis nao contem Machine EV.
- [x] /pre-round-analysis/machine-ev existe.
- [x] /analyze-hand intacto.
- [x] Frontend mostra card separado.
- [x] UI mostra apenas tres campos.
- [x] Debug metrics ocultas na UI.
- [x] Dealer hole card nao exposto.
- [x] Campos humanos nao expostos na Machine EV.
- [x] suggested_units ausente na Machine EV.
- [x] suggested_amount ausente na Machine EV.
- [x] Documentacao final criada e conectada.
- [x] Benchmark criado e executavel.
- [x] Accuracy audit criado e executavel.
- [x] Linguagem etica validada.

## Limitacoes conhecidas

- Variancia de risco da Machine EV ainda e fallback configurado.
- Benchmark e audit validam coerencia tecnica, nao provam lucro.
- Machine EV depende da engine atual e das regras configuradas.
- Inspecao visual manual interativa completa pode depender do ambiente local de execucao.

## Conclusao

A feature Machine EV esta pronta para fechamento oficial da trilha 23.x no
escopo definido, sem regressao funcional detectada em backend, frontend,
endpoints, benchmark, audit, documentacao e UX.

Proximos passos opcionais:

- consolidar eventuais melhorias da etapa 24 em trilha separada;
- manter monitoramento de performance e regressao em CI continuo.
