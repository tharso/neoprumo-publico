import json
import sys

from .orientacao import orientar


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    saida = sys.stderr if erro else sys.stdout
    print(resultado["mensagem"], file=saida)


def envelope(
    status,
    mensagem,
    workspace,
    destino,
    item=None,
    identificador=None,
    problemas=None,
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
    }


def recusa(
    mensagem,
    problema,
    acao,
    workspace,
    destino,
    item=None,
    identificador=None,
):
    return envelope(
        "recusado",
        mensagem,
        workspace,
        destino,
        item=item,
        identificador=identificador,
        problemas=[problema],
        acoes=[acao] if acao else [],
    )


def recusa_workspace_explicito(workspace, destino):
    guia = orientar(workspace, "caminho_explicito")
    return recusa(
        "O caminho não é um workspace do NeoPrumo. " + guia["mensagem"],
        "O caminho não é um workspace do NeoPrumo.",
        guia["acoes"][0] if guia["acoes"] else None,
        workspace,
        destino,
    )


def recusa_item_vazio(item, workspace, destino):
    return recusa(
        f"O item {item.name} não tem nenhuma linha com texto. Mova-o pro acervo.",
        "O item não contém texto aproveitável neste destino.",
        "Use o destino acervo para preservar o arquivo como está.",
        workspace,
        destino,
        item=item,
        identificador=item.stem,
    )


def recusa_falha(item, workspace, destino, erro):
    return recusa(
        f"Não foi possível despachar {item.name}; o item ficou na inbox.",
        f"Falha ao gravar o destino: {erro}",
        "Confira o workspace com doctor e tente novamente.",
        workspace,
        destino,
        item=item,
        identificador=item.stem,
    )


def recusa_reconferencia(item, workspace, destino, mensagem, problema):
    return recusa(
        mensagem,
        problema,
        "Gere a página de novo ou despache este item na conversa.",
        workspace,
        destino,
        item=item,
        identificador=item.stem,
    )
