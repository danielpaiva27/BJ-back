# blackjack-risk-engine

Engine educacional em Python para analisar decisoes em blackjack em ambiente
controlado, usando simulacao Monte Carlo, valor esperado, contagem Hi-Lo e
modelos simples de risco.

Este projeto e exclusivamente academico e simulacional. Ele nao realiza
apostas, nao se conecta a cassinos online, nao automatiza decisoes em
plataformas externas e nao garante lucro.

## Objetivo

O sistema recebe um estado de jogo, como mao do jogador, carta aberta do
dealer, cartas conhecidas e regras da mesa, e retorna uma analise estruturada
com EV por acao, recomendacao, contagem Hi-Lo e sugestao teorica de unidade de
aposta.

## Estrutura

```text
blackjack-risk-engine/
|-- main.py
|-- pyproject.toml
|-- README.md
|-- src/
|   `-- blackjack_risk_engine/
|       |-- __init__.py
|       |-- cards.py
|       |-- counting.py
|       |-- dealer.py
|       |-- deck.py
|       |-- decisions.py
|       |-- ev.py
|       |-- hand.py
|       |-- risk.py
|       |-- rules.py
|       |-- simulation.py
|       `-- strategy.py
`-- tests/
    |-- test_cli.py
    |-- test_counting.py
    |-- test_dealer.py
    |-- test_decisions.py
    |-- test_deck.py
    |-- test_ev.py
    |-- test_hand.py
    |-- test_risk.py
    |-- test_rules.py
    |-- test_simulation.py
    `-- test_strategy.py
```

## Modulos

- `cards.py`: cartas por valor, sem naipes.
- `deck.py`: baralho e shoe com multiplos decks.
- `hand.py`: avaliacao de maos, ases flexiveis, blackjack, pares e split.
- `rules.py`: configuracao de regras da mesa.
- `dealer.py`: politica automatica do dealer, incluindo soft 17.
- `decisions.py`: acoes legais do jogador.
- `simulation.py`: simulacao de uma rodada 1v1.
- `ev.py`: Monte Carlo, EV, estatisticas e retorno JSON.
- `counting.py`: contagem Hi-Lo, running count e true count.
- `strategy.py`: estrategia basica simplificada.
- `risk.py`: sugestao teorica de aposta por true count.
- `main.py`: CLI; nao contem regra central da engine.

## Como instalar e rodar

Requisitos: Python 3.11+.

Rodar direto no workspace:

```bash
python main.py --help
```

Opcionalmente, instalar em modo editavel:

```bash
python -m pip install -e .
```

Rodar testes:

```bash
python -m unittest discover -s tests -t .
```

## Exemplos de CLI

Analise padrao:

```bash
python main.py --player 10,6 --dealer 10 --seen 2,5,6,A,10 --decks 6 --simulations 50000
```

Par com split disponivel:

```bash
python main.py --player 8,8 --dealer 6 --decks 6 --simulations 20000
```

Saida JSON:

```bash
python main.py --player A,7 --dealer 9 --decks 6 --simulations 20000 --json
```

Seed para reproducibilidade e parametros de aposta teorica:

```bash
python main.py --player 10,6 --dealer 10 --decks 6 --simulations 10000 --seed 42 --minimum-bet 10 --bankroll 1000 --risk-profile moderate
```

## Retorno JSON

`analyze_hand` retorna um dicionario Python limpo, serializavel por
`json.dumps`, com estas chaves principais:

- `input`: mao do jogador, carta aberta do dealer e cartas vistas adicionais.
- `rules`: regras usadas na analise.
- `hand_analysis`: total, soft/hard, bust, blackjack natural, par e split.
- `counting`: `running_count`, `true_count`, `cards_remaining` e `deck_status`.
- `actions`: lista ordenada por EV.
- `recommendation`: melhor acao por Monte Carlo, estrategia basica, confianca e explicacao.
- `betting`: sugestao teorica de aposta.
- `metadata`: versao da engine, seed, simulacoes e tempo de execucao.

Exemplo abreviado:

```json
{
  "input": {"player": ["10", "6"], "dealer": "10", "seen": []},
  "actions": [
    {"action": "hit", "ev": -0.12, "win_rate": 0.41, "lose_rate": 0.53, "push_rate": 0.06, "simulations": 10000}
  ],
  "recommendation": {
    "best_action": "hit",
    "confidence": 0.42,
    "explanation": "Melhor acao por EV Monte Carlo..."
  },
  "metadata": {"engine_version": "0.1.0", "simulation_seed": 42, "simulations": 10000}
}
```

## Conceitos

Valor esperado (EV): media dos resultados simulados para uma acao. Vitorias
valem positivo, derrotas negativo e empates zero. Double multiplica o resultado
por 2; surrender retorna -0.5; split soma os resultados das maos splitadas.

Monte Carlo: cada acao legal e simulada muitas vezes com decks embaralhados a
partir das cartas restantes. A media dos resultados estima o EV.

Hi-Lo: cartas 2-6 valem +1, 7-9 valem 0, e 10/A valem -1. O true count e
`running_count / (cards_remaining / 52)`.

## Limitacoes conhecidas

- A estrategia basica e simplificada e parametrizavel, nao uma tabela perfeita
  de cassino.
- A continuacao apos `hit` usa uma politica estrategica simples, nao busca
  recursiva completa por EV.
- Split e simples: nao ha re-split recursivo nem double after split nesta etapa.
- `seen` na CLI representa cartas vistas adicionais. A engine tambem remove a
  mao do jogador e a carta aberta do dealer.
- A sugestao de aposta e apenas modelo teorico de risco em unidades. Nao e
  orientacao financeira.

## Status para proxima etapa

A engine esta preparada para ser chamada por uma API: a regra de negocio esta
nos modulos de `src/blackjack_risk_engine`, a CLI apenas faz parsing e
formatacao, e `analyze_hand` ja retorna JSON serializavel.
