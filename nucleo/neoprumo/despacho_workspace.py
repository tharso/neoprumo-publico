from pathlib import Path

from .ativo import e_workspace, resolver
from .orientacao import orientar, orientar_sem_ativo
from .resultado_despacho import recusa_workspace_explicito


def _indisponivel(workspace, destino):
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
        "item": None,
        "id": None,
        "destino": destino,
    }


def resolver_workspace_despacho(caminho, destino):
    explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None:
        return None, _indisponivel(None, destino)
    workspace = Path(workspace).expanduser().resolve()
    if not e_workspace(workspace):
        resultado = (
            recusa_workspace_explicito(workspace, destino)
            if explicito
            else _indisponivel(workspace, destino)
        )
        return None, resultado
    return workspace, None
