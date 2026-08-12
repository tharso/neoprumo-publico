import json
import sys

from .orientacao import orientar


def campos_nulos():
    return {"hoje": None, "anterior": None, "primeiro_do_dia": None}


def envelope(
    status,
    mensagem,
    workspace,
    hoje,
    anterior,
    primeiro_do_dia,
    problemas=None,
    acoes=None,
):
    return {
        "status": status,
        "problemas": problemas or [],
        "acoes": acoes or [],
        "mensagem": mensagem,
        "workspace": str(workspace) if workspace is not None else None,
        "hoje": hoje,
        "anterior": anterior,
        "primeiro_do_dia": primeiro_do_dia,
    }


def recusar_workspace(workspace):
    guia = orientar(workspace, "caminho_explicito")
    mensagem = "O caminho não é um workspace do NeoPrumo. " + guia["mensagem"]
    return {
        "status": "recusado",
        "problemas": ["O caminho não é um workspace do NeoPrumo."],
        "acoes": guia["acoes"],
        "mensagem": mensagem,
        "workspace": str(workspace),
        **campos_nulos(),
    }


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        print(resultado["mensagem"], file=sys.stderr if erro else sys.stdout)
