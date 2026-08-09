# Pilha grande

Condição: `inbox.total` não é `null` e `inbox.total >= 5`.

Na oferta de despacho, trocar o default pela oferta da superfície: “são N itens — quero gerar a página de despacho?”. Isso não muda a escalação e nunca posterga uma intenção explícita.

Com o sim, executar somente pelo núcleo: `bin/neoprumo superficie despacho`; no plugin, `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo superficie despacho`. Informar o caminho devolvido, orientar abrir o HTML no navegador, escolher os destinos, copiar as respostas e colá-las na conversa. Não gerar nem escrever nada antes da autorização.

Se o usuário preferir conversa, preservar o despacho normal, item a item.
