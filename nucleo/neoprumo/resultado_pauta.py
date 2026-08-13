import json
import sys


def campos_nulos():
    return {
        "destino": None,
        "manchete": None,
        "origem_entrada": None,
        "candidatas": [],
    }


def envelope(
    status, mensagem, workspace, item=None, identificador=None, destino=None,
    manchete=None, origem_entrada=None, candidatas=None, problemas=None,
    acoes=None,
):
    return {
        "status": status,
        "problemas": problemas or [],
        "acoes": acoes or [],
        "mensagem": mensagem,
        "workspace": str(workspace) if workspace is not None else None,
        "item": str(item) if item is not None else None,
        "id": identificador,
        "destino": destino,
        "manchete": manchete,
        "origem_entrada": origem_entrada,
        "candidatas": candidatas or [],
    }


def recusar(mensagem, workspace, **campos):
    return envelope(
        "recusado", mensagem, workspace, problemas=[mensagem], **campos
    )


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        print(resultado["mensagem"], file=sys.stderr if erro else sys.stdout)
