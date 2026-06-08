# Analise pre-rodada multi-sistema

## Objetivo

A analise pre-rodada estima a favorabilidade de um shoe observavel antes do
inicio da mao. Ela compara sistemas de contagem e usa a banca simulada para
sugerir uma exposicao limitada.

Esta analise:

- resume as cartas vistas por diferentes sistemas de contagem;
- estima uma vantagem aproximada a partir do betting true count;
- sugere observar ou expor unidades simuladas;
- nao garante resultado;
- nao substitui a decisao durante a mao.

## Separacao arquitetural

Os sistemas de contagem orientam apenas a leitura pre-rodada:

- vale continuar observando;
- existe vantagem estimada para entrar;
- qual exposicao a politica de banca permite.

A engine de decisao da mao continua independente dos sistemas multi-sistema.
Ela usa:

- mao do jogador;
- carta aberta do dealer;
- regras da mesa;
- composicao real restante do shoe;
- EV por acao;
- programacao dinamica e fallback Monte Carlo, conforme o modo.

**A analise de decisao da mao nao depende diretamente de Hi-Lo, Hi-Opt II ou
Wong Halves. Ela usa a composicao real do shoe para calcular EV por acao. Os
sistemas de contagem sao resumos uteis para leitura pre-rodada, mas a engine de
decisao opera com mais informacao do que um count.**

O frontend pode guardar o resultado pre-rodada como snapshot da rodada. Esse
snapshot e informativo e nao e enviado como entrada para o calculo de Hit,
Stand, Double, Split ou Surrender.

O response legado de `/analyze-hand` ainda contem blocos auxiliares
`counting` e `betting`. Eles sao montados depois da leitura do estado e nao
alimentam o ranking de EV das acoes. A separacao auditada nesta etapa e entre
o motor de decisao por EV e a nova camada multi-sistema de pre-rodada.

## Sistemas implementados

Todos os sistemas usam os ranks `A`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`
e `10`. O rank `10` representa 10, J, Q e K.

### Hi-Lo

| Rank | A | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Peso | -1 | +1 | +1 | +1 | +1 | +1 | 0 | 0 | 0 | -1 |

Propriedades:

- `system_id`: `hi_lo`
- level 1
- balanced
- ace-reckoned
- baseline classico

O betting true count e o proprio true count do sistema.

### Hi-Opt II

| Rank | A | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Peso | 0 | +1 | +1 | +2 | +2 | +1 | +1 | 0 | 0 | -2 |

Propriedades:

- `system_id`: `hi_opt_ii`
- level 2
- balanced
- ace-neutral
- requer side count de ases para a leitura de aposta

O running count e o true count principais sao apresentados como playing
count. A exposicao usa o betting true count ajustado pelos ases restantes.

### Wong Halves

| Rank | A | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Peso real | -1 | +0.5 | +1 | +1 | +1.5 | +1 | +0.5 | 0 | -0.5 | -1 |
| Peso escalado | -2 | +1 | +2 | +2 | +3 | +2 | +1 | 0 | -1 | -2 |

Propriedades:

- `system_id`: `wong_halves`
- level 3
- balanced
- ace-reckoned
- fractional
- escala interna igual a 2

O acumulador interno usa apenas inteiros. `scaled_running_count` guarda a soma
dos pesos escalados e `running_count` e calculado dividindo essa soma por 2.
Isso evita acumulo de erro de ponto flutuante durante a contagem.

## Ace side count do Hi-Opt II

O As vale zero no playing count do Hi-Opt II. Para a leitura de aposta, a
implementacao compara os ases restantes com a quantidade esperada na
profundidade atual do shoe:

```text
total_aces = number_of_decks * 4
seen_aces = quantidade de ases vistos
aces_remaining = total_aces - seen_aces
expected_aces_remaining = decks_remaining * 4
excess_aces = aces_remaining - expected_aces_remaining
```

O ajuste atual usa fator 2:

```text
betting_running_count =
    playing_running_count + excess_aces * 2

betting_true_count =
    betting_running_count / decks_remaining
```

Quando nao ha decks restantes, os true counts retornam zero para impedir
`NaN` ou infinito. O fator e uma aproximacao explicita e pode ser recalibrado
por simulacao em uma etapa futura.

## Estimativa de vantagem

A vantagem pre-rodada e uma heuristica, nao o EV exato da proxima mao:

```text
estimated_player_edge =
    betting_true_count * 0.005 - adjusted_base_house_edge
```

Base:

- `BASE_HOUSE_EDGE = 0.005`, equivalente a 0.5%.
- cada ponto de betting true count adiciona aproximadamente 0.5% ao jogador.

Ajustes de regra:

| Regra | Ajuste no house edge |
| --- | ---: |
| Blackjack 6:5 | +0.014 |
| Dealer hits soft 17 | +0.002 |
| Surrender allowed | -0.0005 |
| Double after split | -0.001 |
| Dealer peek | sem ajuste nesta etapa |

Um ajuste positivo na tabela piora a estimativa para o jogador. Formatos
desconhecidos de payout usam o baseline em vez de interromper a analise.

## Politica unica de banca

Identificacao:

- `policy_id`: `risk_capped_growth`
- `policy_label`: `Crescimento com risco de quebra limitado`
- `VARIANCE_PER_UNIT = 1.3`
- `RISK_OF_RUIN_LIMIT = 0.05`
- `MAX_SINGLE_ROUND_EXPOSURE = 0.05`
- `RISK_MODEL = approx_exponential_gambler_ruin`

A politica deixou de usar quarter-Kelly como formula principal. Ela procura a
maior exposicao simulada permitida por uma aproximacao exponencial de risco de
quebra:

```text
risk_of_ruin =
    exp(
        -2 * estimated_player_edge * bankroll
        / (variance_per_unit * bet_amount)
    )
```

Resolvendo a formula para um limite de risco:

```text
max_bet_by_risk =
    2 * estimated_player_edge * bankroll
    / (
        variance_per_unit
        * ln(1 / risk_of_ruin_limit)
    )

max_bet_by_exposure =
    bankroll * max_single_round_exposure

raw_amount =
    min(max_bet_by_risk, max_bet_by_exposure, bankroll)

suggested_units = floor(raw_amount / minimum_bet)
suggested_amount = suggested_units * minimum_bet
```

Regras de preservacao:

- edge menor ou igual a zero sugere observar;
- edge positivo pequeno ainda pode sugerir observar se nao sustenta a unidade
  minima;
- o valor e arredondado para baixo em multiplos da unidade minima;
- o risco estimado da sugestao positiva nao passa de 5%;
- a exposicao por rodada nunca passa de 5% da banca simulada;
- se o arredondamento produzir risco acima do limite, unidades sao removidas
  ate o limite ser respeitado;
- nao existem perfis conservador, moderado ou agressivo na pre-rodada.

Os status objetivos sao `observe`, `marginal_observe`, `minimum_unit`,
`positive_edge_minimum_bet_exceeds_risk_cap`, `favorable_risk_capped`,
`invalid_bankroll`,
`invalid_minimum_bet` e `insufficient_bankroll`.

## Por que uma vantagem positiva ainda pode sugerir observar?

Mesmo com edge positivo, a politica pode retornar `suggested_units = 0` quando
a unidade minima da mesa e maior do que a exposicao maxima permitida pelo
limite aproximado de risco de quebra.

Diagnosticos adicionados no resultado por sistema:

- `risk_if_minimum_bet`: risco estimado se a menor aposta for usada.
- `minimum_bankroll_required_for_minimum_bet`: banca necessaria para apostar a
  unidade minima mantendo risco menor ou igual a 5%.
- `minimum_bet_exceeds_risk_cap`: indica quando a unidade minima excede o teto
  de risco.

Exemplo observado:

```text
bankroll = 200
minimum_bet = 5
estimated_player_edge = 0.0196

max_bet_by_risk ~= 2.01
minimum_bet = 5
risk_if_minimum_bet ~= 29.93%
minimum_bankroll_required_for_minimum_bet ~= 496.73
status = positive_edge_minimum_bet_exceeds_risk_cap
```

Conclusao: a recomendacao de observar nao significa shoe ruim. Ela indica que,
com a banca atual, a menor aposta disponivel excede o limite aproximado de
risco de quebra adotado pela politica.

Exemplo de calibracao:

```text
bankroll = 1000
minimum_bet = 10
estimated_player_edge = 0.05

max_bet_by_risk = 25.6775...
max_bet_by_exposure = 50
suggested_units = floor(25.6775 / 10) = 2
suggested_amount = 20
estimated_risk_of_ruin = 2.1361%
```

O risco e uma aproximacao matematica dependente do edge estimado. Ele nao e
uma garantia e nao representa todos os limites de mesa, sequencias de aposta
ou comportamentos reais.

## Endpoint

### `POST /pre-round-analysis`

Request:

```json
{
  "number_of_decks": 6,
  "seen_cards": ["2", "5", "10", "A"],
  "bankroll": 1000,
  "minimum_bet": 10,
  "rules": {
    "blackjack_payout": "3:2",
    "dealer_hits_soft_17": false,
    "double_after_split": true,
    "surrender_allowed": false
  }
}
```

Response resumido:

```json
{
  "policy": {
    "policy_id": "risk_capped_growth",
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
    },
    {
      "system_id": "hi_opt_ii",
      "playing_true_count": 0.34,
      "betting_true_count": 0.28,
      "ace_side_count": {
        "excess_aces": -0.08
      },
      "suggested_units": 0,
      "recommendation_status": "observe"
    },
    {
      "system_id": "wong_halves",
      "scaled_running_count": 0,
      "scale": 2,
      "running_count": 0,
      "suggested_units": 0,
      "recommendation_status": "observe"
    }
  ],
  "most_favorable_estimate_system_id": "hi_opt_ii"
}
```

O parametro `systems` pode filtrar os sistemas. Quando omitido, os tres sao
retornados.

## Comparador reproduzivel

O script `benchmarks/compare_pre_round_systems.py` executa cenarios fixos:

```powershell
.\.venv\Scripts\python.exe benchmarks\compare_pre_round_systems.py
```

Ele imprime contagens, edge, exposicao e status dos tres sistemas, incluindo
os detalhes especificos de Hi-Opt II e Wong Halves.

## Limitacoes conhecidas

- A analise pre-rodada e uma estimativa baseada em contagem, nao uma garantia.
- Ela nao substitui o EV calculado durante a mao.
- O ajuste de ases do Hi-Opt II e simplificado.
- O edge por true count usa uma heuristica aproximada.
- Nao ha side bets.
- Nao ha indices especificos de estrategia por sistema.
- A politica pode sugerir observar mesmo com edge positivo pequeno.
- O risco de quebra e uma aproximacao sensivel ao edge estimado e nao uma
  probabilidade real garantida.
- A formula nao modela todos os limites de mesa, mudancas de unidade,
  sequencias de exposicao ou comportamento humano.
- `dealer_peek=false` ainda nao recebe ajuste especifico no edge pre-rodada.
- O modelo assume um shoe finito e observavel; RNG ou computerized blackjack
  nao e o foco.
- Split continua usando as limitacoes e fallbacks documentados na auditoria da
  engine de decisao.

## Uso educacional e linguagem de risco

O projeto nao promete lucro e nao classifica exposicoes como garantidas. Ele
nao incentiva aposta. A feature existe para estudar probabilidade, risco,
valor esperado, variancia e a diferenca entre percepcao de sorte e evidencia
matematica em um modelo controlado.
