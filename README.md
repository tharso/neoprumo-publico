# NeoPrumo

NeoPrumo é o codinome de desenvolvimento da nova geração do Prumo, sistema de organização pessoal com um compromisso central: **nada se perde**. No lançamento, o produto assume o nome Prumo.

Este repositório é o **espelho público do produto**, sob licença MIT. O desenvolvimento acontece num repositório privado; cada merge é publicado aqui num commit único — por isso não há histórico de desenvolvimento nem issues neste espelho.

O projeto está em construção e ainda não teve release.

## O que tem aqui

- `nucleo/` — núcleo em Python 3, só biblioteca padrão (piso 3.10), com a suíte de testes
- `skills/` — skills de agente no padrão aberto (agentskills.io)
- `hooks/`, `bin/`, `.claude-plugin/` — ativação por sessão e empacotamento do plugin

## Experimentar (instalação local)

Requisito: Python 3.10 ou mais recente acessível como `python3` no `PATH`. Com um Python antigo, a sessão ainda abre e apresenta uma mensagem legível com a correção.

No Claude Code:

```sh
claude plugin marketplace add <caminho-deste-clone>
claude plugin install neoprumo@neoprumo-dev
```

No Codex:

```sh
codex plugin marketplace add <caminho-deste-clone>
codex plugin add neoprumo --marketplace neoprumo-dev
```

No Codex, hooks de plugin exigem confiança concedida na primeira sessão interativa de terminal (`Hooks need review`); em execução não interativa, hook não confiado é pulado em silêncio.

## Testes

```sh
uv run --with pytest --with pytest-cov --python 3.13 -- pytest nucleo/tests -q
uv run --with pytest --with pytest-cov --python 3.10 -- pytest nucleo/tests -q
```

## Licença

MIT — ver [LICENSE](LICENSE).
