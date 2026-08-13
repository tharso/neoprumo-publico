---
name: assunto
description: Cria, consulta, anota, arquiva, reativa e migra assuntos da memória do workspace.
---

# Assunto

Usar sempre o núcleo (`bin/neoprumo assunto`; no plugin, prefixar `${CLAUDE_PLUGIN_ROOT}/`). Nunca criar ou editar ficha na mão.

## Nascimento

Colher nome e, se informado, tipo, caminho, caminhos relacionados e apelidos. Primeiro obter a sugestão por uma tentativa de resolução ou proposta conversacional. Sempre mostrar o ID sugerido e esperar o dono confirmar o batismo; só então executar `assunto registrar <nome> [--id <id>]`. A escolha de criar não confirma o ID.

Se o envelope não trouxer `id_sugerido`, pedir um ID, mostrá-lo e confirmar. Executar `registrar --id`; o núcleo valida. Em recusa, apresentar o motivo e repetir o pedido. Em `id_em_uso`, mostrar ID, Nome quando houver e problemas, e decidir com o dono; nunca sobrescrever.

## Gestos

- Consultar: `assunto mostrar <ref>` ou `assunto listar [--todos]`.
- Anotar: `assunto nota <ref> <texto|->`. Usar `-` para multilinha. `--data` e `--origem` só quando o dono mandar ou durante reparo/migração consciente.
- Arquivar: repetir o que ficará arquivado — estado e notas vêm do envelope de `mostrar`, nunca da linha humana — e pedir um “sim” explícito antes de `assunto arquivar <ref>`; escolher o verbo não é confirmação.
- Reativar: `assunto reativar <ref>` após confirmar qual ficha foi resolvida.

Referência ambígua: mostrar candidatas e repetir com ID. Inexistente: oferecer nascimento. Resolução incerta ou ficha quebrada: apresentar os problemas; não declarar unicidade nem contornar o núcleo. Anotação direta em arquivado é permitida por ser gesto consciente do dono: explicitar o estado antes de executar.

## Migração assistida

Se o dono pedir para migrar o documento antigo de projetos, lê-lo sem alterá-lo e trabalhar UMA seção por vez:

1. Mostrar nome, ponteiro/prosa e notas reconhecidas; linhas fora do formato ficam visíveis para decisão.
2. Propor tipo `projeto`, mostrar o ID sugerido e confirmar o batismo antes de registrar.
3. Para cada nota, na ordem, preservar a data com `assunto nota --data <data> <id> -` e enviar o texto multilinha pela entrada padrão.
4. Nunca transformar origem antiga em `--origem`. Acrescentá-la visivelmente à cabeça: ` — origem legada: <literal>`. Assim ela não vira marcador de um item atual.
5. Para linha não reconhecida, o dono decide se vira nota de conversa e escolhe a data; executar somente após confirmação.

Mostrar a proposta completa de cada seção antes dos efeitos. O documento fonte permanece intacto, inclusive depois de uma migração bem-sucedida.
