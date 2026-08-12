---
name: retrato
description: Apresenta o retrato ou panorama do dia por pedido explícito, mesmo quando o retrato automático já foi disparado.
---

# Retrato

Use quando o dono pedir “retrato”, “panorama do dia” ou equivalente fora da abertura.

Execute primeiro `bin/neoprumo seed --json` e trate o resultado como seed fresco; no plugin, prefixe com `${CLAUDE_PLUGIN_ROOT}/`. Depois execute `bin/neoprumo retrato --json` com o mesmo prefixo quando necessário.

Siga a seção “Retrato do dia” em `../sessao/extensoes/primeira-sessao-do-dia.md`, no modo explícito. O corpo inclui a Inbox entre o pódio e a pauta, usando total e idades do seed fresco. Não reexecute as duas frases da abertura nem repita sua oferta.

`repetido` nunca bloqueia o pedido explícito: ele governa apenas o disparo automático. Apresente o retrato com o seed fresco. Em `carimbo_falhou`, apresente também e repasse as ações do envelope. Em indisponibilidade, apresente a orientação devolvida pelo núcleo.
