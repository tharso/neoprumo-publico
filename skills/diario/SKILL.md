---
name: diario
description: Fecha o dia pelo diário quando o dono pede para encerrar ou registrar o dia; colhe fatos, propõe o texto inteiro, confirma e grava somente o dia civil atual.
---

# Diário

Conduzir na ordem: colher → propor → confirmar → gravar. Usar sempre o núcleo (`bin/neoprumo diario`; no plugin, prefixar `${CLAUDE_PLUGIN_ROOT}/`). O diário registra o que aconteceu; não altera Inbox, Pauta, Acervo ou Assuntos.

## Colheita e proposta

Executar `diario colher --json` sem autorização, pois é leitura pura. Com `total == 0`, encerrar sem diário: dizer que o disco não registrou nada hoje, o que não é o mesmo que o dia ter sido vazio; não propor texto, não recitar limitações e não perguntar o que aconteceu. Vale igual quando o pedido chega direto aqui, sem passar pela rota da sessão.

Havendo fatos, somar os colhidos ao que a conversa prova. Quando o resultado parecer magro, mostrar as `limitacoes`: silêncio do disco não significa silêncio do dia. Tratar `problemas` como aviso de saúde, sem apagar fatos saudáveis.

Escrever uma narrativa única por acontecimento: quando o mesmo item aparecer em famílias diferentes, reuni-lo em vez de repeti-lo. Usar somente fatos com origem visível; pedir ao dono o que faltar. Sob compactação, incluir no próprio texto uma frase dizendo que parte da conversa pode ter ficado fora.

Mostrar a proposta COMPLETA, exatamente como será gravada, e perguntar se pode registrar. Um “sim” confirma apenas essa versão; qualquer ajuste produz nova proposta completa e nova confirmação.

## Segundo fecho

Se `diario.existe` for verdadeiro, avisar que a nova seção será apensada. Ler o arquivo do dia, considerar as seções já gravadas e propor somente novidades. Isto é melhor esforço: a colheita é uma fotografia e não guarda o que já foi narrado. Dizer ao dono que uma repetição eventual é possível.

## Gravação

Após o “sim”, enviar o texto confirmado por entrada padrão para `diario gravar - --dia <dia>`. Usar o `dia` devolvido pela colheita. O núcleo só aceita o dia civil atual. Escrever exclusivamente por esse comando; o arquivo pertence ao dono e nunca é montado ou editado à mão.

Em `gravado`, apresentar também problemas e ações. Nos demais estados:

- `dia_virou`: recolher novamente, refazer a proposta e pedir nova confirmação.
- `gravacao_em_andamento`: esperar a outra gravação terminar; recolher antes de tentar de novo.
- `parcial`: explicar que parte da seção entrou e pedir conferência manual do fim do arquivo; não repetir.
- `indeterminado`: explicar que a seção pode ter ido para outro arquivo ou pasta. Pedir conferência de `Diario/AAAA-MM-DD.md` canônico e não repetir antes dela, pois duplicaria a seção.

Pedido de dia passado: explicar que dias sem fecho permanecem sem diário; não oferecer atalho nem outro alvo de data.
