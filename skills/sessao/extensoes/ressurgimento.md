# Ressurgimento

Momento: a cobrança já aconteceu e `acervo.total > 0`. Apresentar o estado da abertura conta como cobrança feita, inclusive com Inbox vazia. Condição fina: abertura no nível leve, sem cobrança explícita ou insistente, sem impedimento e com Inbox legível; a apresentação só acontece se o comando devolver `candidato`. Fora disso, não fazer nada.

Executar, sem autorização prévia porque é leitura pura, `bin/neoprumo ressurgimento --json`; no plugin, `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo ressurgimento --json`. Recusa vira aviso de saúde em paralelo, com `mensagem`, `problemas` e `acoes`, sem mudar o nível. Fazer o mesmo com problemas em qualquer saída. Silêncio somente em `sem_candidato` com `problemas` vazio.

Com `candidato`, concluir primeiro a abertura curta da rota. Depois, fora da abertura, enviar uma mensagem própria e curta, uma vez por sessão: mostrar o vislumbre — substância, nunca só o nome —, a idade e perguntar “ainda vale?”, oferecendo pauta, morrer ou deixa. Sugestão descritiva, nunca prescritiva: pode acrescentar fatos e oferecer o próprio trabalho, mas nunca recomendar o veredito, atribuir prioridade ou dizer o que entra na pauta do dia.

Executar o gesto imediatamente pelo unitário: pauta → `bin/neoprumo acervo <item> pauta`; morrer → `bin/neoprumo acervo <item> lixo`, só após confirmação explícita. No plugin, usar o mesmo prefixo `${CLAUDE_PLUGIN_ROOT}/`. “Atacar agora” significa pauta e abrir o trabalho somente com status `incluido`. “Deixa” não executa nada e não volta ao tema nesta sessão.

Entre o vislumbre e o gesto, se o item mudou ou sumiu, vale o que o unitário encontrar pelo nome, inclusive recusa; apresentar o resultado do núcleo. Executar logo após a resposta apenas encurta esse vão entre o vislumbre e o gesto — não cria garantia nova.

Com `elegiveis >= 5`, oferecer também, na mesma mensagem, abrir o garimpo pela skill `acervo`: `bin/neoprumo superficie acervo`. Gerar a página só com o sim.

Nunca sequestrar nem postergar uma intenção explícita, conforme a regra 6 da rota. Há no máximo um ressurgimento por sessão; outra sessão no mesmo dia pode repetir o candidato, custo aceito do funcionamento sem estado.
