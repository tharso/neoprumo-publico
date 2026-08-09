import re
import stat
from pathlib import Path


def motivo(erro):
    return getattr(erro, "strerror", None) or str(erro)


def ler_bytes(caminho):
    return caminho.read_bytes()


def esta_dentro(caminho, workspace):
    try:
        caminho.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def validar_pasta_acervo(acervo, workspace):
    try:
        estado = acervo.lstat()
    except FileNotFoundError:
        return "O Acervo não existe."
    except OSError as erro:
        return f"O Acervo não pôde ser observado ({motivo(erro)})."
    if stat.S_ISLNK(estado.st_mode):
        return "O Acervo é um atalho simbólico e não será seguido."
    if not stat.S_ISDIR(estado.st_mode):
        return "O Acervo deveria ser uma pasta."
    if not esta_dentro(acervo, workspace):
        return "O Acervo aponta para fora do workspace."
    return None


def encontrar_item(acervo, nome):
    exato = acervo / nome
    try:
        if stat.S_ISREG(exato.stat().st_mode):
            return exato, None
    except FileNotFoundError:
        pass
    candidatos = []
    for caminho in acervo.iterdir():
        try:
            regular = stat.S_ISREG(caminho.stat().st_mode)
        except FileNotFoundError:
            continue
        if regular and caminho.stem == nome:
            candidatos.append(caminho)
    if len(candidatos) == 1:
        return candidatos[0], None
    return None, "ambiguo" if len(candidatos) > 1 else "inexistente"


def fotografar_pauta(workspace):
    pauta = workspace / "Pauta.md"
    try:
        estado = pauta.lstat()
    except FileNotFoundError:
        return {"existe": False, "regular": True, "bytes": b""}, None
    except OSError as erro:
        return None, f"Pauta.md: não foi possível conferir o destino ({motivo(erro)})."
    regular = stat.S_ISREG(estado.st_mode)
    dados = b""
    if regular:
        try:
            dados = ler_bytes(pauta)
        except OSError as erro:
            return None, f"Pauta.md: não foi possível ler o destino ({motivo(erro)})."
    return {"existe": True, "regular": regular, "bytes": dados}, None


def marcador_no_acervo(fotografia, identificador):
    if not fotografia or not fotografia["regular"]:
        return False
    id_bytes = re.escape(identificador.encode("utf-8"))
    padrao = re.compile(
        rb"[ \t]*\xe2\x80\x94 acervo " + id_bytes
        + rb", inclu\xc3\xaddo em \d{4}-\d{2}-\d{2}"
    )
    return any(padrao.fullmatch(linha) for linha in fotografia["bytes"].split(b"\n"))


def caminho_sem_colisao(pasta, nome):
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
