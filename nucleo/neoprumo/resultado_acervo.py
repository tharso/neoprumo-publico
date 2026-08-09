from .resultado_despacho import emitir, envelope


def recusa(mensagem, problema, acao, workspace, destino, item=None):
    return envelope(
        "recusado",
        mensagem,
        workspace,
        destino,
        item=item,
        identificador=item.stem if item is not None else None,
        problemas=[problema],
        acoes=[acao],
    )


def recusa_falha(item, workspace, destino, erro):
    return recusa(
        f"Não foi possível mover {item.name}; o item ficou no Acervo.",
        f"Falha ao gravar o destino: {erro}",
        "Confira o workspace com doctor e tente novamente.",
        workspace,
        destino,
        item,
    )


def recusa_reconferencia(item, workspace, destino, mensagem, problema):
    return recusa(
        mensagem,
        problema,
        "Gere a página de novo ou resolva este item na conversa.",
        workspace,
        destino,
        item,
    )


def recusa_item_vazio(item, workspace, destino):
    return recusa(
        f"O item {item.name} não tem nenhuma linha com texto.",
        "O item não contém texto aproveitável neste destino.",
        "Use lixo ou deixe o item no acervo.",
        workspace,
        destino,
        item,
    )
