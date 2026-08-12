import json
import sys
from pathlib import Path

from .ativo import e_workspace, informar_indisponivel, resolver


def workspace_resolvido(caminho, usar_json, extras=None):
    explícito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explícito else resolver()
    if workspace is None:
        informar_indisponivel(usar_json=usar_json, extras=extras)
        return None, "argumento" if explícito else "maquina"
    workspace = Path(workspace).expanduser().resolve()
    if not e_workspace(workspace):
        informar_indisponivel(workspace, usar_json=usar_json, extras=extras)
        return None, "argumento" if explícito else "maquina"
    return workspace, "argumento" if explícito else "maquina"


def envelope(workspace, status, mensagem, problemas=None, acoes=None, **extras):
    return {"status": status, "problemas": problemas or [], "acoes": acoes or [],
            "mensagem": mensagem, "workspace": str(workspace) if workspace is not None else None,
            **extras}


def emitir(resultado, usar_json, codigo=0):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        destino = sys.stderr if codigo else sys.stdout
        print(resultado["mensagem"], file=destino)
        for problema in resultado["problemas"]:
            print(problema, file=destino)
        for acao in resultado["acoes"]:
            print(acao, file=destino)
    return codigo


def recusar(workspace, mensagem, problemas=None, acoes=None):
    return envelope(workspace, "recusada", mensagem, problemas or [mensagem], acoes or [])
