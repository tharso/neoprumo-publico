import hashlib
from pathlib import Path

from .despacho_workspace import resolver_workspace_despacho
from .destinos_textuais import (
    despachar_pauta,
    despachar_projeto,
    fotografar_destinos,
    marcador_em_destinos,
)
from .resultado_despacho import (
    emitir,
    envelope,
    recusa,
    recusa_falha,
    recusa_reconferencia,
)
from .validacao_despacho import nome_projeto_valido


DESTINOS = ("pauta", "acervo", "projeto", "lixo")
AVISO_ACERVO_RECRIADO = (
    "A pasta Acervo estava faltando e foi recriada. "
    "Rode doctor para conferir o workspace."
)


def _esta_dentro(caminho, workspace):
    try:
        caminho.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def _encontrar_item(inbox, nome):
    exato = inbox / nome
    if exato.is_file():
        return exato, None
    candidatos = [
        caminho
        for caminho in inbox.iterdir()
        if caminho.is_file() and caminho.stem == nome
    ]
    if len(candidatos) == 1:
        return candidatos[0], None
    if len(candidatos) > 1:
        return None, "ambiguo"
    return None, "inexistente"


def _validar_nome_projeto(nome, workspace):
    if nome_projeto_valido(nome):
        return None
    vazio = nome is None or not isinstance(nome, str) or not nome.strip()
    return recusa(
        (
            "O destino projeto precisa do nome do projeto."
            if vazio
            else "O nome do projeto precisa caber em uma linha e não pode ter caracteres de controle."
        ),
        "O nome do projeto não foi informado." if vazio else "O nome do projeto tem formato inválido.",
        "Informe o nome depois de projeto." if vazio else "Use um nome em uma única linha, sem caracteres de controle.",
        workspace,
        "projeto",
    )


def _localizar(item, workspace, destino):
    if not item or Path(item).name != item:
        return None, recusa(
            "Informe somente o nome do arquivo que está na Inbox.",
            "O item deve ser um nome de arquivo, não um caminho.",
            "Use o nome do arquivo com ou sem extensão.",
            workspace,
            destino,
        )
    inbox = workspace / "Inbox"
    if not inbox.is_dir() or not _esta_dentro(inbox, workspace):
        return None, recusa(
            "A Inbox não pôde ser lida. Rode doctor para conferir o workspace.",
            "A pasta Inbox está ausente ou aponta para fora do workspace.",
            "Rode doctor para conferir o workspace.",
            workspace,
            destino,
        )
    try:
        encontrado, problema = _encontrar_item(inbox, item)
    except OSError:
        return None, recusa(
            "A Inbox não pôde ser lida. Rode doctor para conferir o workspace.",
            "A pasta Inbox não pôde ser lida.",
            "Rode doctor para conferir o workspace.",
            workspace,
            destino,
        )
    if problema == "ambiguo":
        return None, recusa(
            f"Há mais de um item com o radical {item}. Informe o nome completo.",
            "O radical corresponde a mais de um arquivo na Inbox.",
            "Informe o nome completo, incluindo a extensão.",
            workspace,
            destino,
        )
    if problema == "inexistente":
        return None, recusa(
            f"O item {item} não foi encontrado na Inbox.",
            "O item não existe na Inbox.",
            "Confira o nome do arquivo e tente novamente.",
            workspace,
            destino,
        )
    if not _esta_dentro(encontrado, workspace):
        return None, recusa(
            "O item aponta para fora do workspace e não pode ser despachado.",
            "O item não está contido no workspace.",
            "Mova o arquivo para dentro da Inbox e tente novamente.",
            workspace,
            destino,
        )
    return encontrado, None


def _ler_item_textual(item, workspace, destino):
    try:
        return item.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, recusa(
            f"O item {item.name} não é texto UTF-8. Mova-o pro acervo.",
            "O item não é texto UTF-8.",
            "Use o destino acervo para preservar o arquivo sem interpretá-lo.",
            workspace,
            destino,
            item=item,
            identificador=item.stem,
        )
    except OSError as erro:
        return None, recusa_falha(item, workspace, destino, erro)


def _caminho_sem_colisao(pasta, nome):
    original = pasta / nome
    if not original.exists():
        return original
    caminho = Path(nome)
    numero = 2
    while True:
        candidato = pasta / f"{caminho.stem}-{numero}{caminho.suffix}"
        if not candidato.exists():
            return candidato
        numero += 1


def _despachar_movendo(item, workspace, destino):
    pasta = workspace / "Acervo" if destino == "acervo" else workspace / ".neoprumo" / "lixo"
    acoes = []
    try:
        if not _esta_dentro(pasta, workspace):
            raise OSError("o destino aponta para fora do workspace")
        if destino == "acervo" and not pasta.exists():
            pasta.mkdir()
            acoes.append(AVISO_ACERVO_RECRIADO)
        elif destino == "lixo":
            pasta.mkdir(parents=True, exist_ok=True)
        destino_final = _caminho_sem_colisao(pasta, item.name)
        item.replace(destino_final)
    except OSError as erro:
        return 1, recusa_falha(item, workspace, destino, erro)
    mensagem = (
        f"Movido pro acervo: {destino_final.name}."
        if destino == "acervo"
        else f"Movido pro lixo (recuperável): {destino_final.name}."
    )
    if acoes:
        mensagem += f" {acoes[0]}"
    return 0, envelope(
        "despachado",
        mensagem,
        workspace,
        destino,
        item=destino_final,
        identificador=item.stem,
        acoes=acoes,
    )


def _reconferir(item, workspace, destino, digital_esperada):
    if digital_esperada is None:
        return None
    try:
        atuais = item.read_bytes()
    except OSError as erro:
        return recusa_falha(item, workspace, destino, erro)
    if hashlib.sha256(atuais).hexdigest() != digital_esperada:
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            "O item mudou depois da conferência e não foi despachado; gere a página de novo.",
            "O conteúdo do item mudou antes da execução.",
        )
    destinos, problemas = fotografar_destinos(workspace)
    if problemas or any(not foto["regular"] for foto in destinos.values()):
        motivo = problemas[0] if problemas else "Um destino textual deixou de ser um arquivo regular."
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            "Não foi possível reconferir o item agora; ele ficou na Inbox.",
            motivo,
        )
    marcadores = marcador_em_destinos(destinos, item.stem)
    if marcadores:
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            f"Já há registro deste item em {marcadores[0]}; confira o destino e despache-o na conversa.",
            "Surgiu um registro no destino depois da conferência.",
        )
    return None


def operar_despacho(
    item,
    destino,
    nome_do_projeto=None,
    caminho=None,
    item_resolvido=None,
    bytes_validados=None,
    digital_esperada=None,
):
    workspace, falha = resolver_workspace_despacho(caminho, destino)
    if falha:
        return 1, falha
    if destino not in DESTINOS:
        return 1, recusa(
            f"Destino desconhecido: {destino}. Use pauta, acervo, projeto ou lixo.",
            f"O destino {destino} não existe.",
            "Escolha pauta, acervo, projeto ou lixo.",
            workspace,
            destino,
        )
    if destino == "projeto":
        falha = _validar_nome_projeto(nome_do_projeto, workspace)
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
    if destino in ("acervo", "lixo"):
        return _despachar_movendo(encontrado, workspace, destino)
    if bytes_validados is None:
        conteudo, falha = _ler_item_textual(encontrado, workspace, destino)
        if falha:
            return 1, falha
    else:
        conteudo = bytes_validados.decode("utf-8")
    if destino == "pauta":
        return despachar_pauta(encontrado, conteudo, workspace)
    return despachar_projeto(encontrado, conteudo, nome_do_projeto, workspace)


def operar_adiamento(
    item, caminho, item_resolvido=None, digital_esperada=None
):
    workspace, falha = resolver_workspace_despacho(caminho, None)
    if falha:
        return 1, falha
    if item_resolvido is None:
        encontrado, falha = _localizar(item, workspace, None)
        if falha:
            return 1, falha
    else:
        encontrado = Path(item_resolvido)
    falha = _reconferir(encontrado, workspace, None, digital_esperada)
    if falha:
        return 1, falha
    return 0, envelope(
        "adiado",
        "Adiado: fica na Inbox.",
        workspace,
        None,
        identificador=encontrado.stem,
    )


def despachar(item, destino, nome_do_projeto=None, caminho=None, usar_json=False):
    codigo, resultado = operar_despacho(item, destino, nome_do_projeto, caminho)
    emitir(resultado, usar_json, erro=codigo != 0)
    return codigo
