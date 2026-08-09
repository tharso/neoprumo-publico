import os
import tempfile
from datetime import datetime
from pathlib import Path

from .acervo_base import caminho_sem_colisao, esta_dentro
from .resultado_acervo import recusa, recusa_falha
from .resultado_despacho import envelope


AVISO_PAUTA_RECRIADA = (
    "O arquivo Pauta.md estava faltando e foi recriado. "
    "Rode doctor para conferir o workspace."
)


def remover(caminho):
    caminho.unlink()


def mover(caminho, destino):
    caminho.replace(destino)


def _separar_conteudo(conteudo):
    linhas = conteudo.splitlines()
    for indice, linha in enumerate(linhas):
        if linha.strip():
            return linha, linhas[:indice] + linhas[indice + 1 :]
    return None, []


def _formatar_pauta(conteudo, identificador, data):
    primeira, restantes = _separar_conteudo(conteudo)
    if primeira is None:
        return None
    linhas = [f"- [ ] {primeira}\n"]
    linhas.extend(f"  {linha}\n" for linha in restantes)
    linhas.append(f"  — acervo {identificador}, incluído em {data}\n")
    return "".join(linhas)


def _gravar_atomico(caminho, conteudo):
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


def _restaurar(pauta, anterior, existia):
    if existia:
        _gravar_atomico(pauta, anterior)
    else:
        remover(pauta)


def _recusa_compensacao(item, pauta, workspace):
    return recusa(
        "O item não saiu do Acervo e pode ter sobrado o registro no destino "
        "Pauta.md; confira antes de aplicar de novo.",
        "A compensação do destino Pauta.md também falhou.",
        "Confira o Acervo e Pauta.md antes de aplicar de novo.",
        workspace,
        "pauta",
        item,
    )


def incluir_na_pauta(item, conteudo, workspace):
    registro = _formatar_pauta(
        conteudo, item.stem, datetime.now().strftime("%Y-%m-%d")
    )
    pauta = workspace / "Pauta.md"
    try:
        try:
            anterior, acoes, existia = pauta.read_bytes(), [], True
        except FileNotFoundError:
            anterior, acoes, existia = b"# Pauta\n", [AVISO_PAUTA_RECRIADA], False
        _gravar_atomico(pauta, _conteudo_com_apenso(anterior, registro))
        try:
            remover(item)
        except OSError as erro:
            try:
                _restaurar(pauta, anterior, existia)
            except OSError:
                return 1, _recusa_compensacao(item, pauta, workspace)
            return 1, recusa_falha(item, workspace, "pauta", erro)
    except OSError as erro:
        return 1, recusa_falha(item, workspace, "pauta", erro)
    mensagem = f"Incluído na pauta: {item.stem}."
    if acoes:
        mensagem += f" {acoes[0]}"
    return 0, envelope(
        "incluido",
        mensagem,
        workspace,
        "pauta",
        item=pauta,
        identificador=item.stem,
        acoes=acoes,
    )


def mover_pro_lixo(item, workspace):
    pasta = workspace / ".neoprumo" / "lixo"
    try:
        if not esta_dentro(pasta, workspace):
            raise OSError("o destino aponta para fora do workspace")
        pasta.mkdir(parents=True, exist_ok=True)
        destino = caminho_sem_colisao(pasta, item.name)
        mover(item, destino)
    except OSError as erro:
        return 1, recusa_falha(item, workspace, "lixo", erro)
    return 0, envelope(
        "excluido",
        f"Movido pro lixo (recuperável): {destino.name}.",
        workspace,
        "lixo",
        item=destino,
        identificador=item.stem,
    )
