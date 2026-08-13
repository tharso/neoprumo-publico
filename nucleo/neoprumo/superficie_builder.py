import hashlib
import os
import stat
import unicodedata
from datetime import datetime
from pathlib import Path

from .seed import _data_pelo_nome
from .assunto_marcadores import fotografar_marcadores
from .destinos_textuais import fotografar_destinos, marcador_em_destinos
from .superficie_base import (
    campos_builder_nulos,
    codificavel_utf8,
    emitir,
    resolver_workspace,
)
from .superficie_pagina import (
    caminho_da_pagina,
    gravar_pagina,
    preparar_pasta,
    renderizar,
)


AVISO_CONTEUDO = "O conteúdo não pôde ser lido. O destino ainda pode ser escolhido."
AVISO_NAO_CONFERIDO = (
    "Este item não pôde ser conferido; despache-o na conversa."
)
AVISO_MARCADOR = (
    "Já há registro deste item no destino; confira e despache-o na conversa."
)
AVISO_RADICAL = (
    "O nome deste item não pode viajar com segurança pela página; despache-o na conversa."
)


def _motivo(erro):
    return getattr(erro, "strerror", None) or str(erro)


def _esta_dentro(caminho, workspace):
    try:
        caminho.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def _recusa(workspace, problema, acao, mensagem):
    return {
        "status": "recusado",
        "problemas": [problema],
        "acoes": [acao],
        "mensagem": mensagem,
        "workspace": str(workspace),
        **campos_builder_nulos(),
    }


def _validar_inbox(inbox, workspace):
    try:
        estado = inbox.lstat()
    except FileNotFoundError:
        return "A Inbox não existe."
    except OSError as erro:
        return f"A Inbox não pôde ser observada ({_motivo(erro)})."
    if stat.S_ISLNK(estado.st_mode):
        return "A Inbox é um atalho simbólico e não será seguida."
    if not stat.S_ISDIR(estado.st_mode):
        return "A Inbox deveria ser uma pasta."
    if not _esta_dentro(inbox, workspace):
        return "A Inbox aponta para fora do workspace."
    return None


def _idade(nome, estado, referencia):
    data = _data_pelo_nome(nome)
    if data is None:
        data = datetime.fromtimestamp(
            estado.st_mtime, tz=referencia.tzinfo
        ).date()
    return max(0, (referencia.date() - data).days)


def _nome_tem_controle(nome):
    return any(unicodedata.category(caractere) == "Cc" for caractere in nome)


def _observar_item(entrada, referencia, problemas, destinos, marcadores_assunto):
    if entrada.name.startswith("."):
        return None
    if not codificavel_utf8(entrada.name):
        problemas.append(
            "Inbox: um item tem nome incompatível com UTF-8 e não foi incluído."
        )
        return None
    if _nome_tem_controle(entrada.name):
        problemas.append(
            "Inbox: um item tem nome com caracteres de controle e não foi incluído."
        )
        return None
    try:
        estado = entrada.stat(follow_symlinks=False)
    except OSError as erro:
        problemas.append(
            f"Inbox: não foi possível observar {entrada.name} "
            f"({_motivo(erro)}); o item não foi incluído."
        )
        return None
    if not stat.S_ISREG(estado.st_mode):
        return None
    try:
        idade = _idade(entrada.name, estado, referencia)
    except (OSError, OverflowError, ValueError) as erro:
        idade = None
        problemas.append(
            f"Inbox: não foi possível ler a data de {entrada.name} "
            f"({_motivo(erro)})."
        )
    try:
        dados = Path(entrada.path).read_bytes()
    except OSError as erro:
        dados = None
        digital = None
        conteudo = AVISO_NAO_CONFERIDO
        aviso = AVISO_NAO_CONFERIDO
        problemas.append(
            f"Inbox: o conteúdo de {entrada.name} não pôde ser lido "
            f"({_motivo(erro)})."
        )
    else:
        digital = hashlib.sha256(dados).hexdigest()
        try:
            conteudo = dados.decode("utf-8")
            aviso = None
        except UnicodeDecodeError as erro:
            conteudo = AVISO_CONTEUDO
            aviso = AVISO_CONTEUDO
            problemas.append(
                f"Inbox: o conteúdo de {entrada.name} não pôde ser lido "
                f"({_motivo(erro)})."
            )
    if dados is not None and "): " in Path(entrada.name).stem:
        digital = None
        aviso = AVISO_RADICAL
        problemas.append(
            f"Inbox: {entrada.name} tem um nome que não pode ser decidido pela página."
        )
    if dados is not None and (
        marcador_em_destinos(destinos, Path(entrada.name).stem)
        or marcadores_assunto.get(entrada.name)
    ):
        digital = None
        aviso = AVISO_MARCADOR
        problemas.append(
            f"Inbox: já há registro de {entrada.name} num destino textual."
        )
    if dados is None:
        conteudo = AVISO_CONTEUDO
        aviso = AVISO_NAO_CONFERIDO
    return {
        "nome": entrada.name,
        "conteudo": conteudo,
        "idade": idade,
        "aviso": aviso,
        "digital": digital,
    }


def _enumerar(inbox, referencia, destinos, marcadores_assunto, problemas_assunto):
    itens = []
    problemas = list(problemas_assunto)
    try:
        with os.scandir(inbox) as entradas:
            for entrada in entradas:
                item = _observar_item(
                    entrada, referencia, problemas, destinos, marcadores_assunto
                )
                if item is not None:
                    itens.append(item)
    except OSError as erro:
        return None, [f"A Inbox não pôde ser lida ({_motivo(erro)})."]
    itens.sort(
        key=lambda item: (
            item["idade"] is None,
            -(item["idade"] or 0),
            item["nome"],
        )
    )
    return itens, problemas


def operar_builder(caminho=None, instante=None):
    workspace, falha = resolver_workspace(caminho, campos_builder_nulos())
    if falha:
        return 1, falha
    inbox = workspace / "Inbox"
    problema = _validar_inbox(inbox, workspace)
    if problema:
        return 1, _recusa(
            workspace,
            problema,
            "Rode doctor para conferir o workspace.",
            "A Inbox não pôde ser usada. Rode doctor para conferir o workspace.",
        )
    referencia = instante or datetime.now().astimezone()
    if referencia.tzinfo is None:
        referencia = referencia.astimezone()
    destinos, falhas_destinos = fotografar_destinos(workspace)
    if falhas_destinos:
        return 1, _recusa(
            workspace,
            falhas_destinos[0],
            "Confira as permissões, rode doctor e tente novamente.",
            "Os destinos textuais não puderam ser conferidos.",
        )
    destino_invalido = next(
        (nome for nome, foto in destinos.items() if foto["existe"] and not foto["regular"]),
        None,
    )
    if destino_invalido:
        return 1, _recusa(
            workspace,
            f"{destino_invalido} precisa ser um arquivo regular.",
            "Rode doctor para conferir o workspace e tente novamente.",
            "Os destinos textuais não puderam ser conferidos.",
        )
    marcadores_assunto, problemas_assunto = fotografar_marcadores(workspace)
    itens, problemas = _enumerar(
        inbox, referencia, destinos, marcadores_assunto, problemas_assunto
    )
    if itens is None:
        return 1, _recusa(
            workspace,
            problemas[0],
            "Confira as permissões da Inbox e tente novamente.",
            "A Inbox não pôde ser lida.",
        )
    if not itens:
        return 0, {
            "status": "sem_itens",
            "problemas": problemas,
            "acoes": [],
            "mensagem": "Nada a despachar.",
            "workspace": str(workspace),
            "pagina": None,
            "id": None,
            "itens": 0,
        }
    pasta, problema = preparar_pasta(workspace)
    if problema:
        return 1, _recusa(
            workspace,
            problema,
            "Remova o conflito sem apagar conteúdo e tente novamente.",
            "A pasta de superfícies não pôde ser usada.",
        )
    pagina = caminho_da_pagina(pasta, referencia)
    try:
        gravar_pagina(pagina, renderizar(itens, pagina.stem))
    except OSError as erro:
        return 1, _recusa(
            workspace,
            f"A página não pôde ser gravada ({_motivo(erro)}).",
            "Confira as permissões da pasta de superfícies e tente novamente.",
            "A superfície não pôde ser criada.",
        )
    return 0, {
        "status": "gerado",
        "problemas": problemas,
        "acoes": [],
        "mensagem": f"Superfície de despacho criada: {pagina}",
        "workspace": str(workspace),
        "pagina": str(pagina),
        "id": pagina.stem,
        "itens": len(itens),
    }


def gerar_superficie(caminho=None, usar_json=False):
    codigo, resultado = operar_builder(caminho)
    emitir(resultado, usar_json, erro=codigo != 0)
    if codigo == 0 and not usar_json:
        for problema in resultado["problemas"]:
            print(f"Aviso: {problema}")
    return codigo
