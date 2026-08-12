import json
import re
import stat
from datetime import date, datetime
from pathlib import Path

from .ativo import e_workspace, informar_indisponivel, resolver
from .destinos_textuais import gravar_atomico
from .resultado_retrato import campos_nulos, emitir, envelope, recusar_workspace


NOME_MARCADOR = "retrato.json"
ACAO_REPETICAO = (
    "O carimbo falhou; o retrato pode repetir na próxima sessão. "
    "Confira o marcador e rode neoprumo retrato novamente."
)


def _motivo(erro):
    return getattr(erro, "strerror", None) or str(erro)


def _problema(causa):
    return f"{NOME_MARCADOR} não pôde ser lido: {causa}."


def _ler_dia(marcador):
    try:
        estado = marcador.lstat()
    except FileNotFoundError:
        return None, [], None
    except OSError as erro:
        return None, [_problema(_motivo(erro))], None

    if not stat.S_ISREG(estado.st_mode):
        tipo = "um link simbólico" if stat.S_ISLNK(estado.st_mode) else "um diretório"
        return None, [], f"{NOME_MARCADOR} é {tipo}; nada foi alterado."

    try:
        texto = marcador.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None, [_problema("o conteúdo não é texto UTF-8")], None
    except OSError as erro:
        return None, [_problema(_motivo(erro))], None

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return None, [_problema("o conteúdo não é JSON válido")], None
    if not isinstance(dados, dict) or "dia" not in dados:
        return None, [_problema("falta a chave dia")], None
    dia = dados["dia"]
    if not isinstance(dia, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dia):
        return None, [_problema("dia não é uma data válida em AAAA-MM-DD")], None
    try:
        date.fromisoformat(dia)
    except ValueError:
        return None, [_problema("dia não é uma data válida em AAAA-MM-DD")], None
    return dia, [], None


def _falha_de_carimbo(workspace, hoje, anterior, problemas):
    return envelope(
        "carimbo_falhou",
        "O carimbo falhou; o retrato pode repetir na próxima sessão.",
        workspace,
        hoje,
        anterior,
        True,
        problemas=problemas,
        acoes=[ACAO_REPETICAO],
    )


def carimbar_retrato(workspace, instante=None):
    agora = instante if instante is not None else datetime.now().astimezone()
    hoje = agora.date().isoformat()
    marcador = workspace / ".neoprumo" / NOME_MARCADOR
    anterior, problemas, obstaculo = _ler_dia(marcador)

    if obstaculo:
        return _falha_de_carimbo(workspace, hoje, None, [obstaculo])
    if anterior == hoje:
        return envelope(
            "repetido",
            "O retrato do dia já foi disparado.",
            workspace,
            hoje,
            anterior,
            False,
            problemas=problemas,
        )

    conteudo = json.dumps({"dia": hoje}, ensure_ascii=False).encode("utf-8") + b"\n"
    try:
        gravar_atomico(marcador, conteudo)
    except OSError as erro:
        problemas.append(
            f"{NOME_MARCADOR} não pôde ser gravado ({_motivo(erro)})."
        )
        return _falha_de_carimbo(workspace, hoje, anterior, problemas)
    return envelope(
        "carimbado",
        "Retrato do dia disparado e carimbado.",
        workspace,
        hoje,
        anterior,
        True,
        problemas=problemas,
    )


def executar_retrato(caminho=None, usar_json=False, instante=None):
    explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None:
        return informar_indisponivel(usar_json=usar_json, extras=campos_nulos())
    workspace = Path(workspace).expanduser().resolve()
    if not e_workspace(workspace):
        if explicito:
            resultado = recusar_workspace(workspace)
            emitir(resultado, usar_json, erro=True)
            return 1
        return informar_indisponivel(
            workspace, usar_json=usar_json, extras=campos_nulos()
        )

    resultado = carimbar_retrato(workspace, instante=instante)
    emitir(resultado, usar_json)
    return 0
