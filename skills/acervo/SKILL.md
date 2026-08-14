---
name: acervo
description: Navega e decide itens guardados no Acervo. Use por pedido explícito para abrir o acervo, revisitar ideias guardadas, garimpar o acervo ou ver o que ficou parado.
---

# Acervo

Oferecer duas portas: página para decidir em volume ou conversa para poucos itens e para quem preferir ditar as decisões.

Na página, executar somente pelo núcleo: `bin/neoprumo superficie acervo`. No plugin, usar `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo superficie acervo`. Informar o caminho devolvido e orientar a abrir, decidir, copiar e colar o bloco na conversa.

Passar o bloco colado INTACTO pela entrada padrão de `bin/neoprumo superficie aplicar`. Nunca interpretar o bloco, chamar os destinos por conta própria nem mover arquivos na mão. Apresentar o relatório do núcleo e trazer cada observação para a conversa; não gravá-la.

Na conversa, executar cada decisão pelo unitário `bin/neoprumo acervo <item> <pauta|lixo>`, com o mesmo prefixo do plugin quando necessário. Para excluir, repetir o que sairá do Acervo e pedir um “sim” explícito antes do comando; escolher o verbo não é confirmação. Na página, o clique já confirmou. “Atacar agora” ditado significa executar `acervo <item> pauta` e abrir o trabalho somente depois do status `incluido`.

Ao aplicar uma página:

- Para `envelhecida` por ausência ou digital divergente, explicar que o retrato mudou e oferecer gerar outra página; nunca gerar sozinho.
- Para problema de marcador (“já há registro”), conferir o destino com o usuário e resolver AQUELE item na conversa.
- Num caso misto, resolver primeiro os itens com marcador e depois oferecer página nova para o restante.
- Para recusa estrutural, orientar a recopiar o bloco. Para falha de conferência ou domínio, apresentar `mensagem`, `problemas` e `acoes` sem inventar outro remédio.

Depois do relatório, localizar itens com `decisao: "atacar"` E `status: "incluido"`. Puxá-los para a conversa e começar o trabalho um por vez, na ordem do bloco. Nunca abrir trabalho para `atacar` recusado.
