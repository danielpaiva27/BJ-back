# Machine EV accuracy audit

## Objetivo

Este audit valida a coerencia da Machine EV pre-rodada no modelo atual e cria
protecao contra regressoes em invariantes importantes.

Os resultados devem ser lidos como coerentes com o modelo atual, nos cenarios
auditados. Eles nao provam lucratividade.

## Escopo

Inclui:

- composicao real remanescente do shoe;
- enumeracao dos estados iniciais observaveis;
- avaliacao por estado via engine atual;
- agregacao por EV ponderado;
- diagnostico de risco da aposta minima;
- contrato publico do endpoint dedicado.

## Fora de escopo

Nao inclui:

- promessa de resultado financeiro;
- recomendacao de aposta real;
- cobertura completa de todas as composicoes e regras possiveis;
- validacao absoluta de superioridade sobre contagens humanas.

## Invariantes validados

Os testes verificam, entre outros pontos:

1. edge finito em faixa plausivel ampla;
2. risco ausente ou no intervalo [0, 1];
3. banca necessaria ausente ou finita e positiva;
4. duracao finita e nao negativa;
5. ao menos um estado avaliado em shoes validos;
6. probabilidades agregadas proximas de 1;
7. `shoe_after` sem contagem negativa;
8. remocao correta de cartas vistas e das tres cartas observaveis;
9. ausencia de dealer hole card no estado observavel;
10. ausencia de campos humanos (`suggested_units`, `suggested_amount`) no
    summary Machine EV;
11. repetibilidade para input/config iguais;
12. nao mutacao do snapshot de entrada.
13. edge neutro positivo relevante tratado como regressao;
14. split aproximado sem participacao no `best_ev` publico;
15. caminho hybrid publico sem fallback Monte Carlo curto.

## Cenarios auditados

- shoe neutro de seis decks;
- low cards removed e high cards removed;
- composicao avancada de um deck;
- 3:2 versus 6:5 no mesmo shoe;
- S17 versus H17 no mesmo shoe;
- com e sem surrender;
- banca pequena com minimo alto;
- input sem bankroll;
- edge nao positivo.

## Direcoes validadas

Nos cenarios auditados, as seguintes direcoes foram confirmadas:

- low cards removed com EV acima de high cards removed;
- 6:5 sem melhora sobre 3:2 no mesmo shoe;
- H17 sem melhora sobre S17 no mesmo shoe;
- surrender permitido sem reducao do EV;
- repetibilidade para execucoes equivalentes.

Essas relacoes servem como protecao contra regressoes. Elas nao fixam valores
absolutos universais para qualquer shoe.

## Regras e remocao de cartas

O audit cobre propagacao de regras relevantes (`blackjack_payout`,
`dealer_hits_soft_17`, `surrender_allowed`, `double_after_split`) e confirma
consistencia de `deck_counts` com `shoe_after`.

Relacao estrutural auditada por estado:

```text
total shoe_after = total inicial - seen_cards - 3
```

As tres cartas removidas sao: carta 1 do jogador, upcard do dealer, carta 2 do
jogador. A dealer hole card permanece fora do estado observavel.

## Limitacoes

- O modo publico `hybrid` usa aproximacao deterministica por composicao para
  continuacoes de `hit`.
- `split` e excluido do edge publico enquanto nao houver EV deterministico
  robusto.
- A variancia do diagnostico de risco ainda e fallback configurado.
- A cobertura de cenarios e representativa, nao exaustiva.
- Magnitude de efeitos pode variar com outras composicoes/regras.
- Divergencia frente a contagem humana nao implica erro automatico.

## Proximos passos

- expandir matriz de composicoes auditadas;
- aprofundar auditoria de distribuicao de EV por estado;
- revisar modelo de variancia do diagnostico de risco;
- acompanhar regressao de performance junto da precisao.

## Execucao

- `benchmarks/audit_machine_ev_accuracy.py --smoke`: smoke curto.
- `benchmarks/audit_machine_ev_accuracy.py`: audit full-shoe explicito.
- `pytest -m slow`: validacoes full-shoe fora da suite padrao.
