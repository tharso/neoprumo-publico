# Ressurgimento

Momento: a cobrança já aconteceu e há algo no acervo ou em espera. Apresentar o estado da abertura conta como cobrança feita, inclusive com Inbox vazia. Condição fina: abertura no nível leve, sem cobrança explícita ou insistente, sem impedimento e com Inbox legível; a apresentação só acontece se o comando devolver `candidato`. Fora disso, não fazer nada.

Executar, sem autorização prévia porque é leitura pura, `bin/neoprumo ressurgimento --json`; no plugin, `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo ressurgimento --json`. Recusa vira aviso de saúde em paralelo, com `mensagem`, `problemas` e `acoes`, sem mudar o nível. Fazer o mesmo com problemas em qualquer saída. Silêncio somente em `sem_candidato` com `problemas` vazio.

Com `candidato`, concluir primeiro a abertura curta da rota. Depois, fora da abertura, enviar uma mensagem própria e curta, uma vez por sessão: mostrar o vislumbre — substância, nunca só o nome —, a idade ou “sem data conhecida” e perguntar “ainda vale?”. Sugestão descritiva, nunca prescritiva: pode acrescentar fatos e oferecer o próprio trabalho, mas nunca recomendar o veredito, atribuir prioridade ou dizer o que entra na pauta do dia.

Se `origem` for `acervo`, oferecer pauta, morrer ou deixa. Executar o gesto pelo unitário: pauta → `bin/neoprumo acervo <item> pauta`; morrer → `bin/neoprumo acervo <item> lixo`, só após confirmação explícita. “Atacar agora” significa pauta e abrir o trabalho somente com status `incluido`. “Deixa” não executa nada nem volta ao tema nesta sessão.

Se `origem` for `em_espera`, oferecer: voltar ao normal → `bin/neoprumo regime "<trecho>" normal`; subir à vista → `bin/neoprumo regime "<trecho>" a-vista`; seguir esperando → não executar nada nem voltar ao tema nesta sessão; morreu → `bin/neoprumo pauta "<trecho>" lixo`, só após confirmação explícita. O trecho vem da manchete. Se houver ambiguidade, repetir com `--origem` usando `origem_entrada`, quando presente, ou a origem das `candidatas` devolvidas.

Em qualquer dos dois gestos que apagam — “morrer” e “morreu” —, escolher o verbo não é confirmação: repetir o que sairá e esperar um “sim” próprio antes de executar.

No plugin, usar o mesmo prefixo `${CLAUDE_PLUGIN_ROOT}/`. Entre o vislumbre e o gesto, se o item mudou ou sumiu, vale o que o núcleo encontrar pelo nome ou trecho, inclusive recusa; apresentar o resultado. Esse vão entre o vislumbre e o gesto não cria garantia nova.

Com `elegiveis_acervo >= 5`, oferecer também, na mesma mensagem, abrir o garimpo pela skill `acervo`: `bin/neoprumo superficie acervo`. Gerar a página só com o sim; entradas em espera não têm página própria.

O ressurgimento fica fora da abertura e do retrato. Contagens não repetem conteúdo, e entrada em espera com prazo vencido não chega aqui. Nunca sequestrar nem postergar uma intenção explícita, conforme a regra 6 da rota. Há no máximo um ressurgimento por sessão; outra sessão no mesmo dia pode repetir o candidato, custo aceito do funcionamento sem estado.
