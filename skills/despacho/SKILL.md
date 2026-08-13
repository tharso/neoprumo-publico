---
name: despacho
description: Decide itens da Inbox: pauta, acervo, assunto/projeto ou lixo, inclusive associação ao guardar.
---

# Despacho

Conduzir conversa curta, um item por vez. Localizar o workspace, ler o item fielmente e mostrar conteúdo e idade. Perguntar: pauta, acervo, assunto/projeto ou lixo. “Guarda isso pro X” significa acervo associado ao assunto X.

Executar somente pelo núcleo: `bin/neoprumo despacho <item> <destino> [referencia]`; associação usa `acervo --assunto <ref>`. No plugin, prefixar `${CLAUDE_PLUGIN_ROOT}/`. Nunca mover, apagar nem editar fichas na mão.

`projeto <nome>` é atalho verbal de `assunto <ref>`. Se vier `assunto_inexistente`, oferecer nascimento: “não existe `<id_sugerido>` — criar agora?”, acrescentando o `tipo_sugerido` quando houver. Mostrar o ID e esperar confirmação do batismo antes de `assunto registrar`. Sem `id_sugerido`, pedir um ID, mostrá-lo e confirmar antes de chamar `registrar --id`; se o núcleo recusar, apresentar a recusa e pedir outro. Nunca criar por efeito colateral.

Assunto arquivado exige confirmação específica antes de repetir com `--confirmado`; escolher o destino não confirma o uso do arquivado. Na associação, se o despacho acontecer mas a nota falhar, avisar obrigatoriamente e reparar fielmente com os campos de `nota_perdida`: `assunto nota --data <data> --origem <origem> <id> -`, enviando `texto` pela entrada padrão, após conduzir a decisão com o dono.

Na pauta, aceitar `--regime a-vista`, `--regime em-espera`, `--regime dormindo --ate AAAA-MM-DD` e/ou `--vence AAAA-MM-DD`. Sem opção, nasce normal. Traduzir data natural, mostrar a data completa e só executar após confirmação. Se o prazo anteceder o despertar, explicar que cobrará mesmo dormindo e pedir confirmação específica antes de `--confirmado`. Nunca usar a flag por hábito.

Lixo exige confirmação explícita; silêncio, hesitação ou sugestão do agente não autorizam. Na superfície, o clique em lixo já confirma.

Para decisão visual, executar `superficie despacho`, devolver o caminho e orientar a abrir o HTML. Ao receber o bloco, passá-lo intacto pela entrada padrão de `superficie aplicar`; nunca interpretar ou executar na mão. Apresentar relatório, problemas e observações.

Página `envelhecida` por item que não está mais na Inbox ou por digital divergente: oferecer gerar outra, nunca gerar sozinho. Se o problema disser “já há registro”, conferir o destino com o dono e resolver o item na conversa. Em caso misto, resolver sobras primeiro. Recusa isolada de domínio do assunto: os outros itens já podem ter sido aplicados; apresentar o filho recusado e conduzir nascimento, desambiguação, nova referência ou confirmação conforme o envelope. Recusa estrutural: pedir para copiar novamente o bloco. Falha de conferência nunca fica muda.

Depois de cada despacho, seguir até a Inbox acabar ou o dono parar. Ser econômico: conteúdo, idade, pergunta; depois, confirmação concreta.
