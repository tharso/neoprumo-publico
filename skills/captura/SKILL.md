---
name: captura
description: Guarda anotações e tarefas de reuniões na Inbox do workspace ativo. Use tanto em pedidos explícitos para anotar, guardar, capturar, pôr na inbox ou pegar tarefas de uma reunião quanto em comentários casuais com intenção clara de lembrar, não esquecer ou deixar uma ideia para depois.
---

# Captura

Em um pedido comandado — “anota”, “guarda”, “captura”, “põe na inbox” — executar `bin/neoprumo captura` com o texto. Quando estiver rodando como plugin, usar `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo captura`. Confirmar com a resposta do comando.

Em uma anotação casual com intenção clara de guardar — algo para lembrar, não esquecer ou retomar depois — capturar direto e confirmar em uma linha. Se a intenção for ambígua, oferecer a captura antes de gravar. Nunca capturar o fluxo da conversa em si.

Preservar as palavras do usuário. Não resumir, reescrever nem traduzir. Diante de um referente vago, como “anota isso”, resolver pelo contexto qual texto o usuário indicou antes de capturar.

Na dúvida — texto com várias linhas, com aspas ou que comece com hífen — executar `neoprumo captura -` e enviar o texto inteiro pela entrada padrão. Aplicar o mesmo caminho do executável indicado acima.

Em pedidos como “pega as tarefas da reunião X”, usar as ferramentas de reuniões/transcrições disponíveis no host para ler a fonte apontada, sem janela de datas. Extrair somente compromissos de ação do dono e apresentar uma lista numerada para ele filtrar. Em cada candidato, mostrar a linha de origem proposta `— da reunião "<nome>", <data>`; quando o nome ou apelido casar com assunto conhecido, acrescentar o palpite visível `· projeto <nome>`, pelo mesmo casamento best-effort dos demais sinais. Evento de hora marcada não vira item: fica na agenda.

Nunca gravar sem o sim do dono. Capturar um item por tarefa. Para cada aprovada, fazer uma chamada e enviar o texto multilinha com a linha de origem ao fim pela entrada padrão de `neoprumo captura -`, usando o executável indicado acima, e confirmar com a resposta do comando.

Quando o usuário perguntar como capturar pelo celular, consultar [atalho-celular.md](atalho-celular.md).
