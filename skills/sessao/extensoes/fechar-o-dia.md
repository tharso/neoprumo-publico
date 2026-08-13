# Fechar o dia

Momento: o dono sinalizou que vai encerrar. Executar uma vez por sessão, sem autorização prévia, `bin/neoprumo diario colher --json`; no plugin, `${CLAUDE_PLUGIN_ROOT}/bin/neoprumo diario colher --json`. É leitura pura.

Apresentar `problemas` e `acoes` como aviso de saúde em paralelo. Com `total == 0`, despedir-se de modo simples, sem perguntar sobre diário. Com `total > 0`, dizer brevemente que há fatos do dia e oferecer registrá-los. Só com o aceite conduzir pela skill `diario`.

O sinal do dono é a condição do momento: nunca antecipar a oferta, nunca cobrar dia passado sem fecho e nunca fazer mais de uma oferta na mesma sessão.
