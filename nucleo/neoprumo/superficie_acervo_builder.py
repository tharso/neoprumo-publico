import hashlib
import json
import os
import stat
import unicodedata
from datetime import datetime
from pathlib import Path

from .acervo_base import (
    fotografar_pauta,
    ler_bytes,
    marcador_no_acervo,
    motivo,
    validar_pasta_acervo,
)
from .seed import _data_pelo_nome
from .superficie_base import campos_builder_nulos, codificavel_utf8, emitir, resolver_workspace
from .superficie_pagina import gravar_pagina, preparar_pasta


AVISO_CONTEUDO = "O conteúdo não pôde ser lido. O destino ainda pode ser escolhido."
AVISO_NAO_CONFERIDO = "Este item não pôde ser conferido; resolva-o na conversa."
AVISO_MARCADOR = (
    "Já há registro deste item no destino; confira e resolva-o na conversa."
)


def _recusa(workspace, problema, acao, mensagem):
    return {
        "status": "recusado",
        "problemas": [problema],
        "acoes": [acao],
        "mensagem": mensagem,
        "workspace": str(workspace),
        **campos_builder_nulos(),
    }


def _idade(nome, estado, referencia):
    data = _data_pelo_nome(nome)
    if data is None:
        data = datetime.fromtimestamp(estado.st_mtime, tz=referencia.tzinfo).date()
    return max(0, (referencia.date() - data).days)


def _nome_tem_controle(nome):
    return any(unicodedata.category(caractere) == "Cc" for caractere in nome)


def _observar_item(entrada, referencia, problemas, pauta):
    if entrada.name.startswith("."):
        return None
    if not codificavel_utf8(entrada.name):
        problemas.append(
            "Acervo: um item tem nome incompatível com UTF-8 e não foi incluído."
        )
        return None
    if _nome_tem_controle(entrada.name):
        problemas.append(
            "Acervo: um item tem nome com caracteres de controle e não foi incluído."
        )
        return None
    try:
        estado = entrada.stat(follow_symlinks=False)
    except OSError as erro:
        problemas.append(
            f"Acervo: não foi possível observar {entrada.name} ({motivo(erro)}); "
            "o item não foi incluído."
        )
        return None
    if not stat.S_ISREG(estado.st_mode):
        return None
    try:
        idade = _idade(entrada.name, estado, referencia)
    except (OSError, OverflowError, ValueError) as erro:
        idade = None
        problemas.append(
            f"Acervo: não foi possível ler a data de {entrada.name} ({motivo(erro)})."
        )
    try:
        dados = ler_bytes(Path(entrada.path))
    except OSError as erro:
        problemas.append(
            f"Acervo: o conteúdo de {entrada.name} não pôde ser lido ({motivo(erro)})."
        )
        return {
            "nome": entrada.name,
            "conteudo": AVISO_NAO_CONFERIDO,
            "idade": idade,
            "aviso": AVISO_NAO_CONFERIDO,
            "digital": None,
        }
    digital = hashlib.sha256(dados).hexdigest()
    try:
        conteudo = dados.decode("utf-8")
        aviso = None
    except UnicodeDecodeError as erro:
        conteudo = aviso = AVISO_CONTEUDO
        problemas.append(
            f"Acervo: o conteúdo de {entrada.name} não pôde ser lido ({motivo(erro)})."
        )
    if marcador_no_acervo(pauta, Path(entrada.name).stem):
        digital = None
        aviso = AVISO_MARCADOR
        problemas.append(
            f"Acervo: já há registro de {entrada.name} em Pauta.md."
        )
    return {
        "nome": entrada.name,
        "conteudo": conteudo,
        "idade": idade,
        "aviso": aviso,
        "digital": digital,
    }


def _enumerar(acervo, referencia, pauta):
    itens, problemas = [], []
    try:
        with os.scandir(acervo) as entradas:
            for entrada in entradas:
                item = _observar_item(entrada, referencia, problemas, pauta)
                if item is not None:
                    itens.append(item)
    except OSError as erro:
        return None, [f"O Acervo não pôde ser lido ({motivo(erro)})."]
    itens.sort(key=lambda item: (
        item["idade"] is None,
        -(item["idade"] or 0),
        item["nome"],
    ))
    return itens, problemas


def _caminho_da_pagina(pasta, referencia):
    base = f"acervo-{referencia.strftime('%Y-%m-%d-%H%M%S')}"
    caminho = pasta / f"{base}.html"
    numero = 2
    while caminho.exists():
        caminho = pasta / f"{base}-{numero}.html"
        numero += 1
    return caminho


def _renderizar(itens, identificador):
    dados = json.dumps(
        {"pagina": identificador, "itens": itens}, ensure_ascii=False
    ).replace("<", "\\u003c")
    template = (
        Path(__file__).with_name("dados") / "superficie-acervo.html"
    ).read_text(encoding="utf-8")
    return template.replace("__DADOS_DA_SUPERFICIE__", dados)


def operar_builder_acervo(caminho=None, instante=None):
    workspace, falha = resolver_workspace(caminho, campos_builder_nulos())
    if falha:
        return 1, falha
    acervo = workspace / "Acervo"
    problema = validar_pasta_acervo(acervo, workspace)
    if problema:
        return 1, _recusa(
            workspace,
            problema,
            "Rode doctor para conferir o workspace.",
            "O Acervo não pôde ser usado. Rode doctor para conferir o workspace.",
        )
    referencia = instante or datetime.now().astimezone()
    if referencia.tzinfo is None:
        referencia = referencia.astimezone()
    pauta, problema = fotografar_pauta(workspace)
    if problema or (pauta["existe"] and not pauta["regular"]):
        detalhe = problema or "Pauta.md precisa ser um arquivo regular."
        return 1, _recusa(
            workspace,
            detalhe,
            "Confira as permissões, rode doctor e tente novamente.",
            "Pauta.md não pôde ser conferida.",
        )
    itens, problemas = _enumerar(acervo, referencia, pauta)
    if itens is None:
        return 1, _recusa(
            workspace,
            problemas[0],
            "Confira as permissões do Acervo e tente novamente.",
            "O Acervo não pôde ser lido.",
        )
    if not itens:
        return 0, {
            "status": "sem_itens",
            "problemas": problemas,
            "acoes": [],
            "mensagem": "Nada a garimpar.",
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
    pagina = _caminho_da_pagina(pasta, referencia)
    try:
        gravar_pagina(pagina, _renderizar(itens, pagina.stem))
    except OSError as erro:
        return 1, _recusa(
            workspace,
            f"A página não pôde ser gravada ({motivo(erro)}).",
            "Confira as permissões da pasta de superfícies e tente novamente.",
            "A superfície não pôde ser criada.",
        )
    return 0, {
        "status": "gerado",
        "problemas": problemas,
        "acoes": [],
        "mensagem": f"Navegador do acervo criado: {pagina}",
        "workspace": str(workspace),
        "pagina": str(pagina),
        "id": pagina.stem,
        "itens": len(itens),
    }


def gerar_superficie_acervo(caminho=None, usar_json=False):
    codigo, resultado = operar_builder_acervo(caminho)
    emitir(resultado, usar_json, erro=codigo != 0)
    if codigo == 0 and not usar_json:
        for problema in resultado["problemas"]:
            print(f"Aviso: {problema}")
    return codigo
