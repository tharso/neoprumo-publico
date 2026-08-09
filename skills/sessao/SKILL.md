---
name: sessao
description: Conduz a abertura de sessão pelo estado injetado e atende pedidos de ajuda sobre o ciclo do NeoPrumo.
---

# Sessão

Apresente naturalmente o estado injetado. Aplique, nesta ordem:

1. Python incompatível, falha do hook ou workspace indisponível: explique o impedimento sem fingir estado; preserve imediatamente a orientação sobre Python.
2. Workspace válido: **insistente** se o mais velho tiver ≥7 dias; senão **explícita** se tiver ≥3 dias OU a Inbox somar ≥5 itens; senão **leve**.
3. Inbox vazia: apresente o estado sem oferecer despacho.
4. Inbox ilegível (`null`, idade indefinida): não aplique limiar; avise e trate como saúde.
5. Problema estrutural: avise em paralelo, sem mudar o nível, e ofereça tentativa de reparo mediante confirmação.
6. Nenhuma oferta bloqueia ou posterga a intenção explícita do usuário.

Abra em uma mensagem curta, máximo de duas frases, sem lista. **Leve:** estado + oferta. **Explícita:** cite idade/volume, sem nomear item: “há um item com N dias; quer despachar o mais antigo agora?”. **Insistente:** proponha resolver primeiro o mais velho. Sempre respeite a regra 6.

Nunca edite arquivos. Após autorização explícita, delegue escrita somente a `bin/neoprumo despacho` ou `bin/neoprumo doctor --reparar`; reparo é tentativa e pode deixar problemas. No plugin, prefixe `${CLAUDE_PLUGIN_ROOT}/`.

Sob pedido de ajuda, explique o ciclo captura → Inbox → despacho → pauta/acervo/projeto/lixo. Ofereça execução apenas dos gestos existentes: captura e despacho.

## Extensões

No momento candidato, consulte o arquivo existente; a extensão decide sua condição fina e ação. Sem arquivo, use o default. O seed é o dado inicial garantido; extensões podem ler mais. Estender é criar o arquivo, que pode referenciar outra skill, sem editar esta rota.

- `primeira-sessao-do-dia`: toda abertura válida; `extensoes/primeira-sessao-do-dia.md`; default: abertura normal.
- `pilha-grande`: toda oferta de despacho; `extensoes/pilha-grande.md`; default: despacho em conversa.
- `ressurgimento`: cobrança feita e acervo com `total > 0`; `extensoes/ressurgimento.md`; default: nada.
- `fechar-o-dia`: usuário sinaliza encerrar; `extensoes/fechar-o-dia.md`; default: despedida simples.

Prioridade: impedimentos > cobrança da Inbox > extensões > intenção; intenção explícita nunca espera. Extensões futuras podem delegar a novos comandos do núcleo conforme sua spec e autorização. O hook permanece somente-leitura.
