# blackjack-risk-engine

Engine em Python para analisar decisoes em blackjack com foco em valor esperado,
simulacao Monte Carlo, contagem de cartas Hi-Lo e analise de risco.

Esta primeira etapa cria apenas a base do projeto. A engine completa de decisao,
simulacao e calculo de valor esperado sera implementada nas proximas iteracoes.

## Objetivo

O sistema deve receber um estado de jogo, como:

- mao do jogador;
- carta aberta do dealer;
- cartas ja vistas;
- regras da mesa;
- numero de baralhos e penetracao do shoe;
- estrategia de dealer;

e retornar, futuramente, a melhor decisao baseada em simulacoes e valor esperado.

## Estrutura

```text
blackjack-risk-engine/
├── main.py
├── pyproject.toml
├── README.md
├── src/
│   └── blackjack_risk_engine/
│       ├── __init__.py
│       ├── cards.py
│       ├── counting.py
│       ├── dealer.py
│       ├── deck.py
│       ├── decisions.py
│       ├── ev.py
│       ├── hand.py
│       ├── risk.py
│       ├── rules.py
│       └── simulation.py
└── tests/
    ├── __init__.py
    ├── test_counting.py
    ├── test_deck.py
    ├── test_dealer.py
    └── test_hand.py
```

## Modulos iniciais

- `cards.py`: representacao de cartas, naipes e ranks.
- `deck.py`: baralho e shoe com multiplos decks.
- `hand.py`: avaliacao basica de maos, incluindo ases flexiveis.
- `dealer.py`: politica inicial de compra/parada do dealer.
- `rules.py`: regras configuraveis da mesa.
- `counting.py`: contagem Hi-Lo.
- `decisions.py`: acoes possiveis do jogador.
- `simulation.py`: contratos iniciais para simulacao Monte Carlo.
- `ev.py`: modelos iniciais para valor esperado.
- `risk.py`: modelos iniciais para analise de risco.

## Como rodar

Execute o exemplo simples:

```bash
python main.py
```

Rode os testes:

```bash
python -m unittest discover -s tests -t .
```

## Status

Implementado nesta etapa:

- estrutura inicial do projeto;
- modelos basicos de carta, baralho, mao, regras e contagem;
- testes unitarios basicos;
- `main.py` demonstrando que o pacote funciona.

Ainda nao implementado:

- simulacao Monte Carlo real;
- calculo completo de valor esperado por decisao;
- estrategias de split, double, surrender e insurance;
- analise estatistica avancada de risco.
