import os
import re
import stat
import tempfile
from datetime import datetime
from pathlib import Path

from .resultado_despacho import envelope, recusa_falha, recusa_item_vazio
from .regimes import formatar_marcador


AVISOS_RECRIACAO = {
    "Pauta.md": (
        "O arquivo Pauta.md estava faltando e foi recriado. "
        "Rode doctor para conferir o workspace."
    ),
    "Projetos.md": (
        "O arquivo Projetos.md estava faltando e foi recriado. "
        "Rode doctor para conferir o workspace."
    ),
}


def _motivo(erro):
    return getattr(erro, "strerror", None) or str(erro)


def fotografar_destinos(workspace):
    fotografias = {}
    problemas = []
    for nome in ("Pauta.md", "Projetos.md"):
        caminho = workspace / nome
        try:
            estado = caminho.lstat()
        except FileNotFoundError:
            fotografias[nome] = {"existe": False, "regular": True, "bytes": b""}
            continue
        except OSError as erro:
            problemas.append(
                f"{nome}: não foi possível conferir o destino ({_motivo(erro)})."
            )
            continue
        regular = stat.S_ISREG(estado.st_mode)
        dados = b""
        if regular:
            try:
                dados = caminho.read_bytes()
            except OSError as erro:
                problemas.append(
                    f"{nome}: não foi possível ler o destino ({_motivo(erro)})."
                )
                continue
        fotografias[nome] = {"existe": True, "regular": regular, "bytes": dados}
    return fotografias, problemas


def marcador_em_destinos(destinos, identificador):
    id_bytes = re.escape(identificador.encode("utf-8"))
    pauta = re.compile(
        rb"[ \t]*\xe2\x80\x94 inbox " + id_bytes
        + rb", despachado em \d{4}-\d{2}-\d{2}"
    )
    projetos = re.compile(
        rb"- \d{4}-\d{2}-\d{2} \(inbox " + id_bytes + rb"\): "
    )
    encontrados = []
    foto_pauta = destinos.get("Pauta.md")
    if foto_pauta and foto_pauta["regular"]:
        if any(pauta.fullmatch(linha) for linha in foto_pauta["bytes"].split(b"\n")):
            encontrados.append("Pauta.md")
    foto_projetos = destinos.get("Projetos.md")
    if foto_projetos and foto_projetos["regular"]:
        if any(projetos.match(linha) for linha in foto_projetos["bytes"].split(b"\n")):
            encontrados.append("Projetos.md")
    return encontrados


def _separar_conteudo(conteudo):
    linhas = conteudo.splitlines()
    for indice, linha in enumerate(linhas):
        if linha.strip():
            return linha, linhas[:indice] + linhas[indice + 1 :]
    return None, []


def _formatar_pauta(conteudo, identificador, data, regime=None, vence=None):
    primeira, restantes = _separar_conteudo(conteudo)
    if primeira is None:
        return None
    linhas = [f"- [ ] {primeira}{formatar_marcador(regime, vence)}\n"]
    linhas.extend(f"  {linha}\n" for linha in restantes)
    linhas.append(f"  — inbox {identificador}, despachado em {data}\n")
    return "".join(linhas)


def _formatar_nota_projeto(conteudo, identificador, data):
    primeira, restantes = _separar_conteudo(conteudo)
    if primeira is None:
        return None
    linhas = [f"- {data} (inbox {identificador}): {primeira}\n"]
    linhas.extend(f"  {linha}\n" for linha in restantes)
    return "".join(linhas)


def gravar_atomico(caminho, conteudo):
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=caminho.parent, prefix=".neoprumo-", delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        temporario = None
    finally:
        if temporario is not None:
            try:
                temporario.unlink()
            except OSError:
                pass


def _conteudo_com_apenso(conteudo, apenso):
    separador = b"" if not conteudo or conteudo.endswith(b"\n") else b"\n"
    return conteudo + separador + apenso.encode("utf-8")


def _inserir_no_projeto(conteudo, nome, nota):
    titulo = f"## {nome}"
    linhas = conteudo.splitlines(keepends=True)
    inicio = None
    fim = len(conteudo)
    posicao = 0
    for linha in linhas:
        texto = linha.rstrip("\r\n")
        if inicio is None and texto == titulo:
            inicio = posicao
        elif inicio is not None and texto.startswith("## "):
            fim = posicao
            break
        posicao += len(linha)
    if inicio is None:
        if not conteudo or conteudo.endswith("\n\n"):
            separador = ""
        elif conteudo.endswith("\n"):
            separador = "\n"
        else:
            separador = "\n\n"
        return conteudo + separador + titulo + "\n" + nota
    antes, depois = conteudo[:fim], conteudo[fim:]
    separador_antes = "" if antes.endswith("\n") else "\n"
    separador_depois = "\n" if depois else ""
    return antes + separador_antes + nota + separador_depois + depois


def _preparar_arquivo_textual(caminho, cabecalho):
    try:
        return caminho.read_bytes(), [], True
    except FileNotFoundError:
        return cabecalho.encode("utf-8"), [AVISOS_RECRIACAO[caminho.name]], False


def _recusa_compensacao(item, arquivo, workspace, destino):
    resultado = recusa_falha(
        item,
        workspace,
        destino,
        OSError(
            f"O item não saiu da Inbox e pode ter sobrado o registro no destino "
            f"{arquivo.name}; confira antes de aplicar de novo."
        ),
    )
    resultado["mensagem"] = (
        f"O item não saiu da Inbox e pode ter sobrado o registro no destino "
        f"{arquivo.name}; confira antes de aplicar de novo."
    )
    return resultado


def _concluir(
    item, arquivo, conteudo, anterior, existia, acoes, mensagem, workspace, destino
):
    gravar_atomico(arquivo, conteudo)
    try:
        item.unlink()
    except OSError as erro:
        try:
            if existia:
                gravar_atomico(arquivo, anterior)
            else:
                arquivo.unlink()
        except OSError:
            return 1, _recusa_compensacao(item, arquivo, workspace, destino)
        return 1, recusa_falha(item, workspace, destino, erro)
    if acoes:
        mensagem += f" {acoes[0]}"
    return envelope(
        "despachado",
        mensagem,
        workspace,
        destino,
        item=arquivo,
        identificador=item.stem,
        acoes=acoes,
    )


def despachar_pauta(item, conteudo, workspace, regime=None, vence=None,
                    acoes_regime=None, incluir_campos=False):
    registro = _formatar_pauta(
        conteudo, item.stem, datetime.now().astimezone().strftime("%Y-%m-%d"), regime, vence
    )
    if registro is None:
        return 1, recusa_item_vazio(item, workspace, "pauta")
    pauta = workspace / "Pauta.md"
    try:
        anterior, acoes, existia = _preparar_arquivo_textual(pauta, "# Pauta\n")
        acoes.extend(acoes_regime or [])
        resultado = _concluir(
            item,
            pauta,
            _conteudo_com_apenso(anterior, registro),
            anterior,
            existia,
            acoes,
            f"Despachado pra pauta: {item.stem}.",
            workspace,
            "pauta",
        )
    except OSError as erro:
        return 1, recusa_falha(item, workspace, "pauta", erro)
    if isinstance(resultado, tuple):
        return resultado
    if incluir_campos:
        resultado["regime"] = regime
        resultado["vence"] = vence
    return 0, resultado


def despachar_projeto(item, conteudo, nome, workspace):
    nota = _formatar_nota_projeto(
        conteudo, item.stem, datetime.now().strftime("%Y-%m-%d")
    )
    if nota is None:
        return 1, recusa_item_vazio(item, workspace, "projeto")
    projetos = workspace / "Projetos.md"
    try:
        anterior, acoes, existia = _preparar_arquivo_textual(projetos, "# Projetos\n")
        novo_conteudo = _inserir_no_projeto(
            anterior.decode("utf-8"), nome, nota
        ).encode("utf-8")
        resultado = _concluir(
            item,
            projetos,
            novo_conteudo,
            anterior,
            existia,
            acoes,
            f"Anotado no projeto {nome}: {item.stem}.",
            workspace,
            "projeto",
        )
    except (OSError, UnicodeDecodeError) as erro:
        return 1, recusa_falha(item, workspace, "projeto", erro)
    return resultado if isinstance(resultado, tuple) else (0, resultado)
