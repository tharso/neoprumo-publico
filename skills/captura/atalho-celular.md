# Atalho de captura no iPhone

Você anota no celular, a nota vira um arquivo na `Inbox/` e o sistema segura aquilo para você. O caminho é simples: texto → nome com a data → arquivo salvo na pasta sincronizada.

## Antes de começar

Você precisa ter:

- um workspace já criado numa pasta sincronizada sua;
- o endereço da pasta `Inbox/` desse workspace;
- o app Atalhos no iPhone;
- o iCloud Drive visível no app Arquivos.

Ainda não tem um workspace? Rode o comando `setup` do NeoPrumo e escolha uma pasta do iCloud Drive, ou de outro serviço que sincronize seus arquivos.

## Caminho rápido: adaptar um atalho que você já tem

Se você já usa um atalho que salva uma nota como arquivo — por exemplo, o atalho do Prumo atual — não precisa reconstruí-lo.

1. Toque e segure o atalho existente.
2. Toque em “Duplicar”. Assim, o original continua intacto.
3. Abra a cópia e troque a pasta de destino pela `Inbox/` do novo workspace.
4. Se quiser o envelope completo do NeoPrumo, troque o nome do arquivo pela data no formato `yyyy-MM-dd-HHmmss`. Se o atalho já monta um nome com data, não recrie essa parte: abra a ação “Formatar Data”, escolha “Personalizado” e edite o campo do formato.
5. Confira se o nome termina em `.md`.

Só a troca da pasta já faz o atalho funcionar: qualquer arquivo dentro da `Inbox/` é um item válido. Ajustar o nome é um polimento. Ele dá ao item uma identidade própria e permite calcular sua idade com precisão; sem esse padrão, o sistema usa a data de modificação do arquivo.

## Montando do zero

São cinco etapas. Reserve cerca de dez minutos na primeira vez.

Os nomes das ações podem variar um pouco conforme a versão do iOS. Se não encontrar uma ação, busque pelo nome aproximado.

### Etapa 1 — Criar o atalho e dar o nome

1. Abra o app Atalhos.
2. Toque em “+”.
3. Toque no nome do novo atalho.
4. Escolha “Renomear”.
5. Digite `Guardar na inbox`.

### Etapa 2 — Configurar o recebimento

1. Abra os detalhes do atalho.
2. Ative “Mostrar ao Compartilhar” ou “Mostrar na Folha de Compartilhamento”.
3. Toque nos tipos aceitos em “Receber”.
4. Deixe marcado apenas “Texto”. Isso permite enviar uma seleção de texto de outro app para o atalho.

### Etapa 3 — Garantir que sempre exista uma nota

1. Adicione a ação “Se”.
2. No primeiro campo de “Se”, escolha “Entrada do Atalho” e configure a condição “não tem valor”.
3. Dentro desse bloco, adicione “Ditar Texto”. Essa será a forma de criar uma nota quando nenhum texto tiver sido compartilhado.
4. Se preferir digitar, substitua “Ditar Texto” por “Solicitar Entrada” ou “Pedir Entrada” e escolha o tipo “Texto”.
5. Abaixo de “Caso Contrário”, adicione a ação “Texto”.
6. No campo de “Texto”, apague o conteúdo e insira a variável “Entrada do Atalho”. Agora “Resultado de Se” sempre será a nota, venha ela de outro app, da voz ou do teclado.

### Etapa 4 — Montar o nome com a data

1. Adicione a ação “Data Atual” depois de “Terminar Se”.
2. Adicione a ação “Formatar Data” logo abaixo.
3. Em “Formato da Data”, escolha “Personalizado”.
4. No campo do formato, digite `yyyy-MM-dd-HHmmss`. Use exatamente essa sequência: maiúsculas e minúsculas importam.
5. Adicione a ação “Definir Nome”.
6. Como item a renomear, escolha a variável “Resultado de Se”.
7. No campo do nome, insira a variável “Data Formatada” e acrescente `.md`. O resultado deve parecer com `2026-08-04-213045.md`.

### Etapa 5 — Salvar na Inbox

1. Adicione a ação “Salvar Arquivo”.
2. Como arquivo a salvar, escolha o resultado de “Definir Nome”.
3. Em destino, escolha uma pasta fixa: a `Inbox/` do seu workspace sincronizado.
4. Desligue “Perguntar Onde Salvar”.

Ao terminar, o nome do arquivo será também o identificador do item. O corpo do arquivo será o texto que você anotou, sem reescrita.

## Testar

1. Rode o atalho com o texto `teste do atalho`.
2. Abra o app Arquivos e entre na `Inbox/` do workspace.
3. Confira se apareceu um arquivo `.md` com aquele texto dentro.

Se preferir, abra uma sessão do agente e peça para listar a inbox.

## Se algo não funcionar

- **A pasta não aparece na hora de salvar.** Confira se o iCloud Drive está ligado e visível para os apps Arquivos e Atalhos.

- **O atalho pergunta onde salvar toda vez.** Abra “Salvar Arquivo” e desligue “Perguntar Onde Salvar”.

- **O nome sai com a data em outro formato.** Confira `yyyy-MM-dd-HHmmss` caractere por caractere, inclusive maiúsculas e minúsculas.

- **O arquivo demora a aparecer no computador.** Aguarde e confira a sincronização do iCloud. Essa demora é do serviço de arquivos, não do NeoPrumo.

O v1 aceita o risco de duas notas no mesmo segundo ficarem com o mesmo nome: um gesto físico dificilmente se repete tão rápido. Não é preciso ajustar quebras de linha; a leitura tolera o arquivo como ele vier.

Qualquer app ou automação que deposite um arquivo na `Inbox/` serve. Android fica fora da receita oficial do v1, mas essa regra geral também vale por lá.
