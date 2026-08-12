---
name: pauta
description: Muda o regime ou o prazo de uma entrada existente da Pauta.
---

# Pauta

Use para pôr uma pendência à vista, fazê-la dormir, deixá-la em espera, devolvê-la ao normal ou ajustar seu prazo. Execute somente pelo núcleo: `bin/neoprumo regime <trecho> [a-vista|dormindo|em-espera|normal]`; no plugin, prefixe com `${CLAUDE_PLUGIN_ROOT}/`.

Para dormir, acrescente `--ate AAAA-MM-DD`. Para criar ou trocar prazo, use `--vence AAAA-MM-DD`; para removê-lo, `--sem-prazo`. O regime omitido preserva o atual. Se mais de uma manchete casar, mostre as candidatas e repita com a origem qualificada devolvida pelo núcleo, por exemplo `--origem "inbox 2026-08-05-101500"`. Nunca escolha sozinho nem edite `Pauta.md` na mão.

O núcleo só recebe data civil em `AAAA-MM-DD`. Traduza expressões como “sexta” ou “até setembro”, mostre a data completa e espere a confirmação do dono antes de executar.

Se o resultado pretendido vencer antes de acordar, pare e explique a consequência: o prazo cobrará na abertura mesmo com o item dormindo. Só depois de uma confirmação específica repita com `--confirmado`. Não use a flag fora dessa contradição.

Apresente a mensagem, os problemas, as ações e as candidatas devolvidas. Uma entrada concluída nunca é alterada; peça ao dono que a reabra ou escolha outra.
