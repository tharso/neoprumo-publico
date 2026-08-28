"""Leitura pura do contexto apontado por um assunto.

Esta é a única visita do núcleo fora do workspace: abre somente o arquivo
``.prumo-contexto.md`` convidado pela ficha e mede metadados do primeiro nível
da pasta, sem recursão, cache ou qualquer escrita.
"""

import codecs
import os
import re
import stat
from datetime import date, datetime
from pathlib import Path


LIMITE_LEITURA = 64 * 1024
LIMITE_MANCHETE = 8 * 1024


def _data_local_mtime(valor):
    return datetime.fromtimestamp(valor).astimezone().date()


def _atividade(pasta):
    valores = [pasta.stat().st_mtime]
    with os.scandir(pasta) as entradas:
        valores.extend(
            entrada.stat(follow_symlinks=True).st_mtime for entrada in entradas
        )
    return _data_local_mtime(max(valores))


def _contexto(status, atividade=None, arquivo=None):
    resultado = {
        "status": status,
        "updated": None,
        "manchete": None,
        "manchete_truncada": False,
        "frescor": "indeterminado",
        "atividade": atividade.isoformat() if atividade else None,
    }
    if arquivo is not None:
        resultado["arquivo"] = str(arquivo)
    return resultado


def _medir_atividade(pasta):
    try:
        return _atividade(pasta), None
    except OSError as erro:
        return None, f"{pasta}: a atividade da pasta não pôde ser medida ({erro})."


def _frontmatter(texto):
    linhas = texto.splitlines()
    if not linhas or linhas[0] != "---":
        return False, None, texto
    fim = next(
        (indice for indice, linha in enumerate(linhas[1:], 1) if linha == "---"),
        None,
    )
    if fim is None:
        return False, None, texto
    updated = None
    for linha in linhas[1:fim]:
        casamento = re.fullmatch(r"updated:\s*(.*?)\s*", linha)
        if casamento:
            updated = casamento.group(1) or None
            break
    return True, updated, "\n".join(linhas[fim + 1:]).lstrip("\n")


def _manchete(texto):
    linhas = texto.splitlines()
    try:
        inicio = linhas.index("## Estado atual") + 1
    except ValueError:
        return None
    while inicio < len(linhas) and not linhas[inicio].strip():
        inicio += 1
    fim = inicio
    while fim < len(linhas) and linhas[fim].strip():
        fim += 1
    return "\n".join(linhas[inicio:fim]) or None


def _limitar(texto):
    dados = texto.encode("utf-8")
    if len(dados) <= LIMITE_MANCHETE:
        return texto, False
    trecho = dados[:LIMITE_MANCHETE].decode("utf-8", errors="ignore")
    if "\n" in trecho:
        trecho = trecho.rsplit("\n", 1)[0]
    return trecho.rstrip("\r\n"), True


def _data_updated(valor):
    if valor is None:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            return date.fromisoformat(valor)
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
            r"(?:Z|[+-]\d{2}:\d{2})",
            valor,
        ):
            return None
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if instante.tzinfo is None:
            return None
        return instante.astimezone().date()
    except ValueError:
        return None


def ler_contexto(caminho):
    try:
        pasta = Path(caminho).expanduser()
    except RuntimeError as erro:
        return _contexto("inacessivel"), [
            f"{caminho}: o atalho de pasta pessoal não pôde ser expandido ({erro})."
        ]
    if not pasta.is_absolute():
        return _contexto("inacessivel"), [
            f"{caminho}: Caminho relativo não é uma referência estável."
        ]
    try:
        if not stat.S_ISDIR(pasta.stat().st_mode):
            return _contexto("inacessivel"), [
                f"{pasta}: a pasta do assunto está inacessível."
            ]
    except OSError as erro:
        return _contexto("inacessivel"), [
            f"{pasta}: a pasta do assunto está inacessível ({erro})."
        ]
    arquivo = pasta / ".prumo-contexto.md"
    atividade, problema_atividade = _medir_atividade(pasta)
    try:
        with arquivo.open("rb") as entrada:
            dados = entrada.read(LIMITE_LEITURA)
    except FileNotFoundError:
        if not pasta.is_dir():
            return _contexto("inacessivel"), [
                f"{pasta}: a pasta do assunto ficou inacessível durante a leitura."
            ]
        problemas = [problema_atividade] if problema_atividade else []
        return _contexto("sem_arquivo", atividade), problemas
    except OSError as erro:
        problemas = [
            f"{arquivo}: o arquivo de contexto não pôde ser lido ({erro})."
        ]
        if problema_atividade:
            problemas.append(problema_atividade)
        return _contexto("ilegivel", atividade, arquivo), problemas
    try:
        decodificador = codecs.getincrementaldecoder("utf-8")()
        texto = decodificador.decode(dados, final=len(dados) < LIMITE_LEITURA)
    except UnicodeDecodeError:
        problemas = [f"{arquivo}: o arquivo de contexto não é texto UTF-8."]
        if problema_atividade:
            problemas.append(problema_atividade)
        return _contexto("ilegivel", atividade, arquivo), problemas
    frontmatter_valido, updated, corpo = _frontmatter(texto)
    manchete = _manchete(texto)
    estruturado = frontmatter_valido and manchete is not None
    if estruturado:
        manchete, manchete_truncada = _limitar(manchete)
    elif not corpo.strip():
        manchete, manchete_truncada = None, False
    else:
        manchete, _ = _limitar(corpo)
        manchete_truncada = True
    data_updated = _data_updated(updated)
    problemas = []
    if data_updated is None:
        problemas.append(
            ".prumo-contexto.md: updated ausente ou ilegível; "
            "frescor indeterminado."
        )
    if not estruturado:
        problemas.append(
            ".prumo-contexto.md: arquivo fora do padrão; exibido o primeiro "
            "trecho do corpo."
        )
    if problema_atividade:
        problemas.append(problema_atividade)
    return {
        "status": "lido",
        "arquivo": str(arquivo),
        "updated": updated,
        "manchete": manchete,
        "manchete_truncada": manchete_truncada,
        "frescor": (
            "indeterminado" if data_updated is None or atividade is None
            else "defasado" if atividade > data_updated else "fresco"
        ),
        "atividade": atividade.isoformat() if atividade else None,
    }, problemas
