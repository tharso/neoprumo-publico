# Primeira sessão do dia

Este arquivo compõe consumidores do momento “toda abertura válida”. Cada seção decide por suas próprias condições; nenhuma depende de outra ter sido acionada. Consumidores futuros acrescentam seções aqui sem editar a rota em `skills/sessao/SKILL.md`.

## Regimes na abertura

As quatro condições abaixo são independentes e não alteram os limiares 3/5/7 nem postergam uma intenção explícita:

1. Se `pauta.regimes.a_vista > 0`, apresentar o pódio do à vista em toda sessão, usando `pauta.a_vista` na ordem recebida.
2. Se `pauta.regimes.a_vista > 5`, cobrar a redução: “o à vista só funciona pequeno — qual desce?”. O sexto item entra; o teto é macio.
3. Se `pauta.acordaram_hoje > 0`, anunciar quem acordou hoje, mesmo quando `pauta.regimes.a_vista == 0`.
4. Se `pauta.prazos.vencidos > 0`, cobrar os prazos estourados junto da cobrança da Inbox, mesmo sem à vista e inclusive quando o item continua marcado como dormindo.

Se a seção "Retrato do dia" apresentou o panorama NESTA abertura: não repetir o pódio (condição 1), o anúncio de acordou (condição 3) nem re-apresentar os prazos — a cobrança acionável dos vencidos (condição 4) acontece UMA vez, dentro do retrato. A condição 2 (teto macio — cobrar a redução com `a_vista > 5`) continua desta seção, com ou sem retrato. Sem retrato nesta abertura, as quatro condições valem integrais.

## Retrato do dia

Na abertura válida, executar `bin/neoprumo retrato --json`; no plugin, usar `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo retrato --json`.

- `primeiro_do_dia` verdadeiro: apresentar o retrato fora da abertura de duas frases da rota.
- `primeiro_do_dia` falso: seguir sem retrato.
- Indisponibilidade: seguir sem retrato; a rota já orienta o workspace.
- `carimbo_falhou`: apresentar normalmente e repassar cada `acao` do envelope. Ramificar por `status`, nunca só pelo código de saída.

### Modos de composição

**Modo automático (abertura).** As duas frases da rota — estado da Inbox e oferta — são obrigatórias e contam como a seção Inbox. Depois delas, abrir imediatamente o corpo pelo pódio: nada entra no meio. Não repetir total nem idades da Inbox. A cobrança leve, explícita ou insistente permanece na rota; juntar a ela a cobrança acionável de prazo vencido, quando houver.

**Modo explícito (pedido).** Usar o seed fresco obtido pela skill `retrato`; o modo não reexecuta a abertura da rota nem sua oferta. Depois do pódio e antes da pauta, incluir a Inbox com total + idades. O restante do corpo é igual ao modo automático.

### À vista

Apresentar primeiro as linhas `À vista:` do seed, na ordem recebida, com os prazos de cada item.

### Pauta

Apresentar abertos e concluídos, contagens por regime, `Acordou hoje:` e `Prazos:`. Se `prazos.vencidos > 0`, fazer aqui, uma única vez, um convite direto a agir, como “1 prazo estourado — atacamos?”. Juntar essa cobrança à da Inbox.

### Agenda de hoje

Pelas ferramentas de calendário disponíveis na sessão do host, buscar os eventos do dia civil local. Mostrar hora e título em ordem de horário.

### Email

Pelas ferramentas de email disponíveis no host, buscar mensagens recentes ou não lidas. A seleção é julgamento declarado da skill; não inventar uma quantidade fixa. Para cada mensagem, extrair remetente puro no formato `a@b` de formas como `Nome <a@b>`, assunto e um identificador único que correlacione pergunta e resposta.

Montar `{"dominio": "email", "alvos": [{"id": "<único>", "remetente": "a@b", "assunto": "..."}]}` e passar pela entrada padrão de `bin/neoprumo configuracao avaliar - --json`; no plugin, usar o prefixo `${CLAUDE_PLUGIN_ROOT}/`. Conferir cada retorno pelo `id` antes de apresentar:

- `efetiva`: reduzir ou aumentar o destaque e relatar a recomendação da regra. Nunca dizer que a ação foi feita nem executá-la; isso exige gesto posterior do dono.
- `conflito`: não aplicar regra alguma. Usar julgamento padrão provisório e avisar brevemente o conflito; a resolução fica em `configuracao mostrar`.
- `suspensas_que_casariam`: não aplicar. Fazer menção curta e oferecer revisão na primeira oportunidade.
- `semanticas_ativas`: aplicar por julgamento declarado da skill.
- `suspensas_semanticas`: não aplicar; mencionar brevemente só quando relevante.
- Alvo sem regra: usar destaque padrão para o que parece pedir resposta ou ação.
- `sem_regras` ou pendência: usar julgamento padrão em tudo, sem repetir o aviso de saúde já pertencente à rota.

Esses efeitos mudam somente a apresentação. Recomendações como “a regra do contador recomenda só guardar” são relato, não ação executada.

### Degradação

- Sem ferramenta de agenda, escrever `agenda: sem conexão neste host`.
- Sem ferramenta de email, escrever `email: sem conexão neste host`.
- Sem ambas, apresentar À vista e Pauta e usar uma única linha de aviso agregado.
- Se um conector falhar ou atingir o timeout exposto pelo próprio host, manter tudo já obtido e trocar somente aquela parte pela linha de indisponibilidade. A skill não controla um conector que o host mantém travado.
- Se `configuracao avaliar` for recusado ou estiver indisponível, apresentar o email com julgamento padrão e meia linha de aviso.

## Composição

As seções são independentes e consultam suas próprias condições. A abertura normal da rota continua valendo para tudo que o retrato não absorveu nominalmente.
