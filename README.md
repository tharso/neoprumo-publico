# NeoPrumo

NeoPrumo é o codinome de desenvolvimento da nova geração do Prumo, sistema de organização pessoal com um compromisso central: **nada se perde**. No lançamento, o produto assume o nome Prumo.

Este repositório é o **canal público do produto**, sob licença MIT. O desenvolvimento acontece em outro repositório; cada versão chega aqui num commit único.

## O que tem aqui

- `nucleo/` — núcleo em Python 3, só biblioteca padrão (piso 3.10), com a suíte de testes
- `skills/` — skills de agente no padrão aberto (agentskills.io)
- `hooks/`, `bin/`, `.claude-plugin/` — ativação por sessão e empacotamento do plugin

## Instalar

Requisito: Python 3.10 ou mais recente acessível como `python3` no `PATH`. Com um Python antigo, a sessão ainda abre e apresenta uma mensagem legível com a correção.

No Claude Code:

```sh
claude plugin marketplace add tharso/neoprumo-publico
claude plugin install neoprumo@neoprumo
```

No Codex:

```sh
codex plugin marketplace add tharso/neoprumo-publico
codex plugin add neoprumo@neoprumo
```

No Codex, hooks de plugin exigem confiança concedida na primeira sessão interativa de terminal (`Hooks need review`); em execução não interativa, hook não confiado é pulado em silêncio.

No Claude Code, marketplaces de terceiros vêm com atualização automática desligada. Depois de instalar, abra `/plugin`, entre em **Marketplaces**, selecione `neoprumo` e ligue o auto-update.

## Conferir atualizações manualmente

No Claude Code:

```sh
claude plugin update neoprumo@neoprumo
```

No Codex, são dois passos — atualizar o catálogo e reinstalar o plugin:

```sh
codex plugin marketplace upgrade neoprumo
codex plugin add neoprumo@neoprumo
```

## Testes

```sh
uv run --with pytest --with pytest-cov --python 3.13 -- pytest nucleo/tests -q
uv run --with pytest --with pytest-cov --python 3.10 -- pytest nucleo/tests -q
```

## Licença

MIT — ver [LICENSE](LICENSE).
