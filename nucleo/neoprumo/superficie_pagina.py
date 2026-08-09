import json
import stat
from pathlib import Path


def _esta_dentro(caminho, workspace):
    try:
        caminho.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def preparar_pasta(workspace):
    pasta = workspace / ".neoprumo" / "superficies"
    try:
        estado = pasta.lstat()
    except FileNotFoundError:
        if not _esta_dentro(pasta, workspace):
            return None, "A pasta de superfícies resolveria para fora do workspace."
        try:
            pasta.mkdir()
        except OSError as erro:
            return None, f"A pasta de superfícies não pôde ser criada ({erro})."
        return pasta, None
    except OSError as erro:
        return None, f"A pasta de superfícies não pôde ser observada ({erro})."
    if stat.S_ISLNK(estado.st_mode):
        return None, "A pasta de superfícies é um atalho simbólico."
    if not pasta.is_dir():
        return None, "O caminho das superfícies deveria ser uma pasta."
    if not _esta_dentro(pasta, workspace):
        return None, "A pasta de superfícies aponta para fora do workspace."
    return pasta, None


def caminho_da_pagina(pasta, referencia):
    base = f"despacho-{referencia.strftime('%Y-%m-%d-%H%M%S')}"
    caminho = pasta / f"{base}.html"
    numero = 2
    while caminho.exists():
        caminho = pasta / f"{base}-{numero}.html"
        numero += 1
    return caminho


def renderizar(itens, identificador):
    dados = json.dumps(
        {"pagina": identificador, "itens": itens}, ensure_ascii=False
    ).replace("<", "\\u003c")
    template = (
        Path(__file__).with_name("dados") / "superficie-despacho.html"
    ).read_text(encoding="utf-8")
    return template.replace("__DADOS_DA_SUPERFICIE__", dados)


def gravar_pagina(pagina, conteudo):
    criada = False
    try:
        with pagina.open("x", encoding="utf-8") as arquivo:
            criada = True
            arquivo.write(conteudo)
    except OSError:
        if criada:
            try:
                pagina.unlink()
            except OSError:
                pass
        raise
