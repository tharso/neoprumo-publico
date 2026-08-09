---
name: captura
description: Guarda anotações fiéis na Inbox do workspace ativo. Use tanto em pedidos explícitos para anotar, guardar, capturar ou pôr na inbox quanto em comentários casuais com intenção clara de lembrar, não esquecer ou deixar uma ideia para depois.
---

# Captura

Em um pedido comandado — “anota”, “guarda”, “captura”, “põe na inbox” — executar `bin/neoprumo captura` com o texto. Quando estiver rodando como plugin, usar `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo captura`. Confirmar com a resposta do comando.

Em uma anotação casual com intenção clara de guardar — algo para lembrar, não esquecer ou retomar depois — capturar direto e confirmar em uma linha. Se a intenção for ambígua, oferecer a captura antes de gravar. Nunca capturar o fluxo da conversa em si.

Preservar as palavras do usuário. Não resumir, reescrever nem traduzir. Diante de um referente vago, como “anota isso”, resolver pelo contexto qual texto o usuário indicou antes de capturar.

Na dúvida — texto com várias linhas, com aspas ou que comece com hífen — executar `neoprumo captura -` e enviar o texto inteiro pela entrada padrão. Aplicar o mesmo caminho do executável indicado acima.

Quando o usuário perguntar como capturar pelo celular, consultar [atalho-celular.md](atalho-celular.md).
