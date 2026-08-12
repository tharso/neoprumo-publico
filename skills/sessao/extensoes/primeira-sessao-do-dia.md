# Primeira sessão do dia

Este arquivo compõe consumidores do momento “toda abertura válida”. Cada seção decide por suas próprias condições; nenhuma depende de outra ter sido acionada. Consumidores futuros acrescentam seções aqui sem editar a rota em `skills/sessao/SKILL.md`.

## Regimes na abertura

As quatro condições abaixo são independentes e não alteram os limiares 3/5/7 nem postergam uma intenção explícita:

1. Se `pauta.regimes.a_vista > 0`, apresentar o pódio do à vista em toda sessão, usando `pauta.a_vista` na ordem recebida.
2. Se `pauta.regimes.a_vista > 5`, cobrar a redução: “o à vista só funciona pequeno — qual desce?”. O sexto item entra; o teto é macio.
3. Se `pauta.acordaram_hoje > 0`, anunciar quem acordou hoje, mesmo quando `pauta.regimes.a_vista == 0`.
4. Se `pauta.prazos.vencidos > 0`, cobrar os prazos estourados junto da cobrança da Inbox, mesmo sem à vista e inclusive quando o item continua marcado como dormindo.

Se outra seção desta mesma abertura já apresentou o à vista, não repetir o pódio.

## Composição

Seções são independentes e consultam apenas suas próprias condições. A seção futura do retrato terá como condição a primeira sessão do dia civil e será acrescentada neste arquivo. Enquanto ela não existir, vale a abertura normal da rota para o que não foi coberto acima.
