---
name: despacho
description: Decide o destino dos itens da Inbox. Use quando o usuário quiser despachar, processar ou esvaziar a inbox, ou decidir se algo vira pauta, acervo, projeto ou lixo.
---

# Despacho

Conduzir uma conversa curta, um item por vez. Localizar o workspace ativo, ler o item da Inbox e apresentar seu conteúdo fiel junto da idade. Perguntar o destino: pauta, acervo, projeto ou lixo. Se for projeto, colher o nome.

Executar a decisão somente pelo núcleo: `bin/neoprumo despacho <item> <destino> [nome-do-projeto]`. Quando estiver rodando como plugin, usar `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo despacho`. Reportar o resultado com a resposta do comando. Nunca mover, apagar ou editar os arquivos na mão.

Quando o usuário pedir para decidir no visual ou gerar a página, executar `bin/neoprumo superficie despacho`, informar o caminho devolvido e orientar a abrir o arquivo HTML no navegador. No plugin, usar o mesmo prefixo `${CLAUDE_PLUGIN_ROOT}`.

Quando o usuário colar o bloco de respostas da página, passá-lo intacto pela entrada padrão de `bin/neoprumo superficie aplicar`. Nunca interpretar nem executar o bloco na mão. Apresentar o relatório devolvido pelo núcleo e trazer cada observação para a conversa, sem gravá-la no item ou no destino.

Ao aplicar, distinguir a causa devolvida pelo núcleo. Página `envelhecida` por item que não está mais na Inbox ou por digital divergente: explicar que o retrato mudou e oferecer gerar a página de novo, nunca gerar sozinho. Se o problema disser “já há registro”, conferir o destino com o usuário e oferecer o despacho daquele item em conversa; não oferecer página nova para ele. Num caso misto, resolver primeiro em conversa os itens com registro e só depois oferecer página nova para o restante. Recusa estrutural: orientar recopiar o bloco da página. Falha de conferência ou recusa de domínio: apresentar `mensagem`, `problemas` e `acoes` do núcleo sem inventar outro remédio.

Lixo exige confirmação explícita do usuário na conversa, mesmo sendo recuperável. Sem essa confirmação, não executar. Não transformar silêncio, hesitação nem uma sugestão do agente em autorização.

Na superfície, o clique em lixo já é a confirmação do usuário; aplicar o bloco não pede confirmação de novo.

Depois de cada despacho, seguir para o próximo item até a Inbox acabar ou o usuário parar. Ser econômico: conteúdo, idade, pergunta; depois, confirmação concreta.
