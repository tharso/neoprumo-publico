import os
import re
import stat
from pathlib import Path


IRMA = re.compile(r"^Configuracao ([2-9]|[1-9]\d+)\.ini$")


def real(caminho, diretorio=False):
    try:
        modo = caminho.lstat().st_mode
    except FileNotFoundError:
        return not diretorio
    esperado = stat.S_ISDIR if diretorio else stat.S_ISREG
    return esperado(modo) and not stat.S_ISLNK(modo)


def participantes(workspace):
    raiz = Path(workspace) / "Configuracao.ini"
    reconhecidas, parecidas = [], []
    try:
        entradas = list(os.scandir(workspace))
    except OSError:
        return raiz, reconhecidas, parecidas
    for entrada in entradas:
        if entrada.name == "Configuracao.ini":
            continue
        if not entrada.name.startswith("Configuracao"):
            continue
        caminho = Path(entrada.path)
        if IRMA.fullmatch(entrada.name) and entrada.is_file(follow_symlinks=False):
            reconhecidas.append(caminho)
        else:
            parecidas.append(entrada.name)
    return raiz, sorted(reconhecidas), sorted(parecidas)
