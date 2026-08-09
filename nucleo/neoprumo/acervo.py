import hashlib
import unicodedata
from pathlib import Path

from .acervo_base import (
    encontrar_item,
    esta_dentro,
    fotografar_pauta,
    marcador_no_acervo,
    ler_bytes,
    validar_pasta_acervo,
)
from .acervo_destinos import incluir_na_pauta, mover_pro_lixo
from .despacho_workspace import resolver_workspace_despacho
from .resultado_acervo import (
    emitir,
    recusa,
    recusa_falha,
    recusa_item_vazio,
    recusa_reconferencia,
)
from .resultado_despacho import envelope
from .superficie_base import codificavel_utf8


DECISOES_UNITARIAS = ("pauta", "lixo")


def _destino(decisao):
    if decisao in ("pauta", "atacar"):
        return "pauta"
    if decisao == "lixo":
        return "lixo"
    return None


def _nome_valido(item):
    return (
        codificavel_utf8(item)
        and bool(item)
        and item not in (".", "..")
        and Path(item).name == item
        and not any(unicodedata.category(caractere) == "Cc" for caractere in item)
    )


def _localizar(item, workspace, destino):
    if not _nome_valido(item):
        return None, recusa(
            "Informe somente o nome do arquivo que está no Acervo.",
            "O item deve ser um nome-base de arquivo válido.",
            "Use o nome do arquivo com ou sem extensão.",
            workspace,
            destino,
        )
    acervo = workspace / "Acervo"
    problema = validar_pasta_acervo(acervo, workspace)
    if problema:
        return None, recusa(
            "O Acervo não pôde ser usado. Rode doctor para conferir o workspace.",
            problema,
            "Rode doctor para conferir o workspace.",
            workspace,
            destino,
        )
    try:
        encontrado, motivo = encontrar_item(acervo, item)
    except OSError as erro:
        return None, recusa(
            "O Acervo não pôde ser lido. Rode doctor para conferir o workspace.",
            f"O Acervo não pôde ser lido: {erro}",
            "Rode doctor para conferir o workspace.",
            workspace,
            destino,
        )
    if motivo == "ambiguo":
        return None, recusa(
            f"Há mais de um item com o radical {item}. Informe o nome completo.",
            "O radical corresponde a mais de um arquivo no Acervo.",
            "Informe o nome completo, incluindo a extensão.",
            workspace,
            destino,
        )
    if motivo == "inexistente":
        return None, recusa(
            f"O item {item} não foi encontrado no Acervo.",
            "O item não existe no Acervo.",
            "Confira o nome do arquivo e tente novamente.",
            workspace,
            destino,
        )
    if not esta_dentro(encontrado, workspace):
        return None, recusa(
            "O item aponta para fora do workspace e não pode ser movido.",
            "O item não está contido no workspace.",
            "Mova o arquivo para dentro do Acervo e tente novamente.",
            workspace,
            destino,
        )
    return encontrado.resolve(), None


def _reconferir(item, workspace, destino, digital_esperada):
    if digital_esperada is None:
        return None
    try:
        atuais = ler_bytes(item)
    except OSError as erro:
        return recusa_falha(item, workspace, destino, erro)
    if hashlib.sha256(atuais).hexdigest() != digital_esperada:
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            "O item mudou depois da conferência e ficou no Acervo; gere a página de novo.",
            "O conteúdo do item mudou antes da execução.",
        )
    fotografia, problema = fotografar_pauta(workspace)
    if problema or not fotografia["regular"]:
        motivo = problema or "Pauta.md deixou de ser um arquivo regular."
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            "Não foi possível reconferir o item agora; ele ficou no Acervo.",
            motivo,
        )
    if marcador_no_acervo(fotografia, item.stem):
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            "Já há registro deste item em Pauta.md; confira o destino e resolva-o na conversa.",
            "Surgiu um registro na pauta depois da conferência.",
        )
    return None


def _ler_texto(item, workspace, destino):
    try:
        dados = ler_bytes(item)
    except OSError as erro:
        return None, recusa_falha(item, workspace, destino, erro)
    try:
        conteudo = dados.decode("utf-8")
    except UnicodeDecodeError:
        return None, recusa(
            f"O item {item.name} não é texto UTF-8.",
            "O item não é texto UTF-8.",
            "Use lixo ou deixe o item no acervo.",
            workspace,
            destino,
            item,
        )
    if not any(linha.strip() for linha in conteudo.splitlines()):
        return None, recusa_item_vazio(item, workspace, destino)
    return conteudo, None


def operar_acervo(
    item,
    decisao,
    caminho=None,
    item_resolvido=None,
    bytes_validados=None,
    digital_esperada=None,
):
    destino = _destino(decisao)
    workspace, falha = resolver_workspace_despacho(caminho, destino)
    if falha:
        return 1, falha
    if item_resolvido is None:
        encontrado, falha = _localizar(item, workspace, destino)
        if falha:
            return 1, falha
    else:
        encontrado = Path(item_resolvido)
    falha = _reconferir(encontrado, workspace, destino, digital_esperada)
    if falha:
        return 1, falha
    if decisao == "deixar":
        return 0, envelope(
            "deixado", "Fica no acervo.", workspace, None,
            identificador=encontrado.stem,
        )
    if decisao == "lixo":
        return mover_pro_lixo(encontrado, workspace)
    if bytes_validados is None:
        conteudo, falha = _ler_texto(encontrado, workspace, destino)
        if falha:
            return 1, falha
    else:
        conteudo = bytes_validados.decode("utf-8")
    return incluir_na_pauta(encontrado, conteudo, workspace)


def operar_acervo_unitario(item, decisao, caminho=None):
    workspace, falha = resolver_workspace_despacho(caminho, _destino(decisao))
    if falha:
        return 1, falha
    if decisao not in DECISOES_UNITARIAS:
        return 1, recusa(
            "Decisão desconhecida. Use pauta ou lixo.",
            "A decisão não existe no fluxo do acervo.",
            "Escolha pauta ou lixo.",
            workspace,
            _destino(decisao),
        )
    return operar_acervo(item, decisao, workspace)


def decidir_acervo(item, decisao, caminho=None, usar_json=False):
    codigo, resultado = operar_acervo_unitario(item, decisao, caminho)
    emitir(resultado, usar_json, erro=codigo != 0)
    return codigo
