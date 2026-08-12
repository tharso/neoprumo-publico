import json
import sys


def envelope(
    status,
    mensagem,
    workspace,
    problemas=None,
    acoes=None,
    manchete=None,
    origem=None,
    regime=None,
    vence=None,
    anterior=None,
    candidatas=None,
):
    return {
        "status": status,
        "problemas": problemas or [],
        "acoes": acoes or [],
        "mensagem": mensagem,
        "workspace": str(workspace) if workspace is not None else None,
        "manchete": manchete,
        "origem": origem,
        "regime": regime,
        "vence": vence,
        "anterior": anterior,
        "candidatas": candidatas or [],
    }


def campos_nulos():
    return {
        "manchete": None,
        "origem": None,
        "regime": None,
        "vence": None,
        "anterior": None,
        "candidatas": [],
    }


def recusar(mensagem, workspace, problemas=None, **campos):
    return envelope(
        "recusado", mensagem, workspace, problemas=problemas or [mensagem], **campos
    )


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        print(resultado["mensagem"], file=sys.stderr if erro else sys.stdout)
