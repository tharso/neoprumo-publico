import json
import sys


VERSAO_MINIMA = (3, 10)


def mensagem_de_versao(versao):
    versao_atual = ".".join(map(str, versao[:3]))
    return (
        "O NeoPrumo precisa do Python 3.10 ou mais recente; "
        f"este host tem {versao_atual}. Instale um Python atual e garanta "
        "que `python3` o encontre."
    )


def envelope_do_hook(texto):
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": texto,
        }
    }


def verificar_versao(informacoes_versao=None):
    versao = sys.version_info if informacoes_versao is None else informacoes_versao
    if tuple(versao[:2]) >= VERSAO_MINIMA:
        return True
    print(mensagem_de_versao(versao), file=sys.stderr)
    return False


def main(informacoes_versao=None):
    versao = sys.version_info if informacoes_versao is None else informacoes_versao
    if tuple(versao[:2]) < VERSAO_MINIMA and sys.argv[1:] == ["sonda", "--hook"]:
        print(json.dumps(envelope_do_hook(mensagem_de_versao(versao)), ensure_ascii=False))
        return 0
    if not verificar_versao(informacoes_versao):
        return 2

    from .cli import executar

    return executar()


if __name__ == "__main__":
    raise SystemExit(main())
