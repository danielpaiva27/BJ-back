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
|-- app/
|   |-- __init__.py
|   |-- main.py
|   |-- schemas.py
|   `-- routes/
|       |-- __init__.py
|       `-- analysis.py
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
    |-- test_api.py
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
- `app/`: camada HTTP com FastAPI; apenas validacao e roteamento.

## Como instalar e rodar

Requisitos: Python 3.11+.

Instalar dependencias do projeto:

```bash
python -m pip install -e .
```

Rodar CLI direto no workspace:

```bash
python main.py --help
```

Rodar testes:

```bash
python -m unittest discover -s tests -t .
```

Rodar API FastAPI:

```bash
uvicorn app.main:app --reload
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

## API FastAPI (Etapa 16)

Endpoints disponiveis:

- `GET /health`
- `POST /analyze-hand`
- `POST /pre-round-analysis`

`GET /health` retorna:

```json
{
  "status": "ok",
  "service": "blackjack-risk-engine",
  "version": "0.1.0"
}
```

Exemplo de request para `POST /analyze-hand`:

```json
{
  "player_hand": ["10", "6"],
  "dealer_upcard": "10",
  "seen_cards": ["2", "5", "6", "A", "10"],
  "rules": {
    "number_of_decks": 6,
    "dealer_hits_soft_17": false,
    "blackjack_payout": "3:2",
    "double_allowed": true,
    "double_after_split": true,
    "surrender_allowed": false,
    "max_splits": 3,
    "dealer_peek": true
  },
  "simulations": 50000,
  "seed": 42,
  "bankroll": 1000,
  "minimum_bet": 10,
  "risk_profile": "moderate"
}
```

Exemplo de chamada com `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/analyze-hand" \
  -H "Content-Type: application/json" \
  -d '{"player_hand":["10","6"],"dealer_upcard":"10","seen_cards":["2","5","6","A","10"],"rules":{"number_of_decks":6,"dealer_hits_soft_17":false,"blackjack_payout":"3:2","double_allowed":true,"double_after_split":true,"surrender_allowed":false,"max_splits":3,"dealer_peek":true},"simulations":10000,"seed":42,"bankroll":1000,"minimum_bet":10,"risk_profile":"moderate"}'
```

Exemplo de response (abreviado):

```json
{
  "input": {"player": ["10", "6"], "dealer": "10", "seen": ["2", "5", "6", "A", "10"]},
  "rules": {"number_of_decks": 6, "dealer_hits_soft_17": false, "blackjack_payout": "3:2"},
  "hand_analysis": {"total": 16, "is_soft": false},
  "counting": {"running_count": 1, "true_count": 0.17},
  "actions": [{"action": "hit", "ev": -0.11}],
  "recommendation": {"best_action": "hit", "confidence": 0.41},
  "betting": {"suggested_bet": 10.0, "risk_profile": "moderate"},
  "metadata": {"engine_version": "0.1.0", "simulations": 10000}
}
```

Validacao de entrada usa Pydantic. Entradas invalidas retornam erro HTTP 422.

### Analise pre-rodada multi-sistema

`POST /pre-round-analysis` estima a favorabilidade do shoe antes da mao usando
Hi-Lo, Hi-Opt II e Wong Halves. A resposta combina contagem, betting true
count, vantagem estimada e exposicao simulada limitada pela banca.

Documentacao tecnica completa:

- [`PRE_ROUND_COUNTING_SYSTEMS.md`](PRE_ROUND_COUNTING_SYSTEMS.md)
- [`PRE_ROUND_ANALYSIS_AUDIT.md`](PRE_ROUND_ANALYSIS_AUDIT.md)

O frontend consome este endpoint manualmente e renderiza um card por sistema.
A politica de banca e unica, sem perfis de risco. A decisao durante a mao
continua independente e usa a composicao real do shoe para calcular EV por
acao.

Exemplo de request:

```json
{
  "number_of_decks": 6,
  "seen_cards": ["2", "5", "10", "A"],
  "bankroll": 1000,
  "minimum_bet": 10,
  "rules": {
    "dealer_hits_soft_17": false,
    "blackjack_payout": "3:2",
    "double_after_split": true,
    "surrender_allowed": false,
    "dealer_peek": true
  },
  "systems": ["hi_lo", "hi_opt_ii", "wong_halves"]
}
```

Exemplo resumido de response:

```json
{
  "cards_seen": 4,
  "cards_remaining": 308,
  "decks_remaining": 5.9230769231,
  "bankroll": 1000,
  "minimum_bet": 10,
  "policy": {
    "policy_id": "risk_capped_growth",
    "policy_label": "Crescimento com risco de quebra limitado",
    "variance_per_unit": 1.3,
    "risk_of_ruin_limit": 0.05,
    "max_single_round_exposure": 0.05,
    "max_bankroll_exposure": 0.05,
    "risk_model": "approx_exponential_gambler_ruin"
  },
  "systems": [
    {
      "system_id": "hi_lo",
      "running_count": 0,
      "true_count": 0,
      "betting_true_count": 0,
      "estimated_player_edge": -0.004,
      "suggested_units": 0,
      "estimated_risk_of_ruin": 0,
      "risk_of_ruin_limit": 0.05,
      "recommendation_status": "observe"
    }
  ],
  "most_favorable_estimate_system_id": "hi_lo"
}
```

- Hi-Lo usa o true count diretamente para a estimativa de aposta.
- Hi-Opt II separa playing count e betting count, ajustando este ultimo pelo
  side count de ases.
- Wong Halves preserva a contagem inteira escalada por 2 para auditoria.

A analise pre-rodada nao substitui a engine de decisao da mao. Hit, stand,
double, split e surrender continuam sendo avaliados pela engine probabilistica
baseada na composicao real do shoe.

Nao ha perfis conservador, moderado ou agressivo neste endpoint. A politica e
unica e busca vantagem estimada positiva com exposicao limitada pela banca
simulada.

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
- Simulacoes Monte Carlo com valores altos, como 50000 rodadas, podem aumentar
  o tempo de processamento. Otimizacao de performance nao faz parte da etapa
  atual.

## Melhorias futuras de performance

- Otimizacao do loop Monte Carlo.
- Cache de cenarios ou subresultados recorrentes.
- Execucao assincrona da analise.
- Worker ou background job para simulacoes mais longas.
- Reducao dinamica de simulacoes quando o resultado ja estiver estavel.
- Pesquisa futura com analise exata ou programacao dinamica.

## Status para proxima etapa

Etapa 16 concluida: a API FastAPI foi adicionada sem mover regra de negocio
para controllers/endpoints. A funcao central continua em
`src/blackjack_risk_engine/ev.py` via `analyze_hand`, e o CLI permanece ativo.
