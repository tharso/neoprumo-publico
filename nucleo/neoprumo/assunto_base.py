import hashlib
import os
import re
import stat
import unicodedata
from datetime import date
from pathlib import Path


PADRAO_ID = re.compile(r"^(?=.{1,64}$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
CHAVES = {
    "Tipo": "tipo",
    "Estado": "estado",
    "Apelidos": "apelidos",
    "Caminho": "caminho",
}


def normalizar(valor):
    return "".join(
        caractere for caractere in unicodedata.normalize("NFD", valor)
        if unicodedata.category(caractere) != "Mn"
    ).casefold()


def derivar_id(nome):
    base = normalizar(nome)
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:64].rstrip("-") or None


def id_valido(valor):
    return bool(
        isinstance(valor, str)
        and PADRAO_ID.fullmatch(valor)
        and "--" not in valor
    )


def tem_controle(valor):
    return any(unicodedata.category(caractere) == "Cc" for caractere in valor)


def texto_de_uma_linha(valor):
    return (
        isinstance(valor, str)
        and bool(valor.strip())
        and "\n" not in valor
        and "\r" not in valor
        and not tem_controle(valor)
    )


def data_valida(valor):
    try:
        date.fromisoformat(valor)
    except (TypeError, ValueError):
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor))


def conferir_prateleira(workspace):
    pasta = Path(workspace) / "Assuntos"
    try:
        modo = pasta.lstat().st_mode
    except OSError as erro:
        return None, f"Assuntos: a prateleira não pôde ser usada ({erro})."
    if stat.S_ISLNK(modo) or not stat.S_ISDIR(modo):
        return None, "Assuntos precisa ser uma pasta real, não um atalho."
    return pasta, None


def nomes_da_prateleira(pasta):
    try:
        return sorted(os.listdir(pasta)), None
    except OSError as erro:
        return None, f"Assuntos: a prateleira não pôde ser lida ({erro})."


def entradas_de_ficha(pasta):
    nomes, falha = nomes_da_prateleira(pasta)
    if falha:
        return [], [], [falha]
    validos, fora = [], []
    for nome in nomes:
        caminho = pasta / nome
        if caminho.suffix == ".md":
            (validos if id_valido(caminho.stem) else fora).append(caminho)
    problemas = []
    if fora:
        problemas.append(
            f"{len(fora)} arquivos na prateleira fora da gramática de ID: "
            + ", ".join(item.name for item in fora) + "."
        )
    return validos, fora, problemas


def digital(dados):
    return hashlib.sha256(dados).hexdigest()
