# Machine EV comparison benchmark

## Objetivo

Este benchmark compara sinais de Machine EV e dos sistemas humanos (Hi-Lo,
Hi-Opt II e Wong Halves) em cenarios controlados de shoe e regras.

A comparacao e uma ferramenta de analise tecnica. Ela nao prova lucro e nao
substitui validacao de risco real.

## Modelos comparados

Sistemas humanos:

- comprimem informacao em contagens (running/true/betting count);
- sao proxies simplificados e manualmente replicaveis.

Machine EV:

- usa composicao real do shoe;
- enumera estados iniciais observaveis;
- avalia cada estado na engine atual;
- agrega o resultado por EV ponderado;
- nao e replicavel manualmente durante o jogo.

No benchmark, os grupos permanecem separados em `counting_systems` e
`machine_ev`.

## Cenarios

O script cobre cenarios como:

1. shoe neutro de seis decks;
2. remocao intensa de cartas baixas;
3. remocao intensa de cartas altas;
4. shoe rico em dez e pobre em ases;
5. shoe rico em ases com dezenas perto do neutro;
6. composicao avancada;
7. regra 6:5 versus 3:2;
8. H17 versus S17;
9. surrender permitido;
10. banca pequena com aposta minima alta.

## Execucao

Completo:

```powershell
.venv\Scripts\python.exe benchmarks\compare_machine_ev_vs_counting_systems.py
```

Smoke:

```powershell
.venv\Scripts\python.exe benchmarks\compare_machine_ev_vs_counting_systems.py --smoke
```

Opcional com JSON local:

```powershell
.venv\Scripts\python.exe benchmarks\compare_machine_ev_vs_counting_systems.py --write-output
```

## Como interpretar divergencias

Edges sao classificados com limiar de `0.001` em positivo, negativo ou neutro.
As classes incluem `aligned_positive`, `aligned_negative` e cenarios de
divergencia entre modelos.

Divergencia nao significa automaticamente erro. Em varios casos, ela reflete a
diferenca entre:

- um proxy comprimido de contagem humana; e
- uma avaliacao por composicao real na Machine EV.

## Relacao com accuracy audit

O benchmark mede convergencia/divergencia de sinais entre modelos. A validacao
de coerencia interna da Machine EV esta no accuracy audit:

- [MACHINE_EV_ACCURACY_AUDIT.md](MACHINE_EV_ACCURACY_AUDIT.md)

O audit cobre invariantes, cenarios, repetibilidade e direcoes validadas para
o modelo atual. Os dois documentos se complementam.

## Limites

- Os resultados dependem da engine e das regras atuais.
- O diagnostico de risco da Machine EV ainda usa variancia fallback.
- O benchmark nao cobre todo o espaco de regras/composicoes.
- A duracao varia por maquina e carga.
- A saida nao e recomendacao de aposta real.
- O benchmark nao prova lucratividade.
