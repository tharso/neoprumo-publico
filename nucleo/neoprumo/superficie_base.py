import json
import sys
from pathlib import Path

from .ativo import e_workspace, resolver
from .orientacao import orientar, orientar_sem_ativo


def codificavel_utf8(valor):
    if not isinstance(valor, str):
        return False
    try:
        valor.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def campos_builder_nulos():
    return {"pagina": None, "id": None, "itens": None}


def campos_aplicar_nulos():
    return {
        "resultados": None,
        "despachados": None,
        "recusados": None,
        "adiados": None,
    }


def campos_aplicar_acervo_nulos():
    return {
        "resultados": None,
        "incluidos": None,
        "excluidos": None,
        "deixados": None,
        "recusados": None,
    }


def _indisponivel(workspace, extras):
    caminho = str(workspace) if workspace is not None else None
    guia = (
        orientar(workspace, "ponteiro_ativo")
        if workspace is not None
        else orientar_sem_ativo()
    )
    return {
        "status": "ativo_invalido" if caminho else "sem_ativo",
        "problemas": [
            f"O caminho configurado não é um workspace válido: {caminho}"
            if caminho
            else "Não há um workspace ativo resolvível."
        ],
        "acoes": guia["acoes"],
        "mensagem": (
            f"O workspace ativo {caminho} não pôde ser usado. {guia['mensagem']}"
            if caminho
            else guia["mensagem"]
        ),
        "workspace": caminho,
        **extras,
    }


def resolver_workspace(caminho, extras):
    explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None:
        return None, _indisponivel(None, extras)
    workspace = Path(workspace).expanduser().resolve()
    if e_workspace(workspace):
        return workspace, None
    if not explicito:
        return None, _indisponivel(workspace, extras)
    guia = orientar(workspace, "caminho_explicito")
    return None, {
        "status": "recusado",
        "problemas": ["O caminho não é um workspace do NeoPrumo."],
        "acoes": guia["acoes"],
        "mensagem": "O caminho não é um workspace do NeoPrumo. " + guia["mensagem"],
        "workspace": str(workspace),
        **extras,
    }


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    saida = sys.stderr if erro else sys.stdout
    print(resultado["mensagem"], file=saida)
