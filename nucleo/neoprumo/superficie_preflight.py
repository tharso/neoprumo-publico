import hashlib
import json
import re
import stat
import unicodedata
from pathlib import Path

from .destinos_textuais import fotografar_destinos, marcador_em_destinos
from .superficie_base import campos_aplicar_nulos, codificavel_utf8
from .validacao_despacho import nome_projeto_valido


DECISOES = ("pauta", "acervo", "projeto", "lixo", "depois")
DIGITAL = re.compile(r"^[0-9a-f]{64}$")


def _recusa(workspace, status, problemas, acoes, mensagem):
    return {
        "status": status,
        "problemas": problemas,
        "acoes": acoes,
        "mensagem": mensagem,
        "workspace": str(workspace),
        **campos_aplicar_nulos(),
    }


def _estrutura(workspace, problemas, antiga=False):
    acoes = ["Copie novamente o bloco completo gerado pela superfície."]
    if antiga:
        acoes = ["Esta página é de uma versão antiga; gere a página de novo."]
    return _recusa(
        workspace,
        "recusado",
        problemas,
        acoes,
        "O bloco de respostas tem formato inválido.",
    )


def _tem_controle(valor):
    return any(unicodedata.category(caractere) == "Cc" for caractere in valor)


def _carregar(bloco, workspace):
    if isinstance(bloco, (str, bytes)):
        try:
            bloco = json.loads(bloco)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, _estrutura(
                workspace, ["O bloco não é um documento JSON válido."]
            )
    if not isinstance(bloco, dict):
        motivo = "O bloco precisa ser um objeto JSON."
    elif not codificavel_utf8(bloco.get("superficie")):
        motivo = "O campo superficie precisa ser texto UTF-8 válido."
    elif bloco["superficie"] != "despacho":
        motivo = "O bloco não pertence a uma superfície conhecida."
    elif not codificavel_utf8(bloco.get("pagina")) or not bloco["pagina"].strip():
        motivo = "O campo pagina precisa ser texto não vazio e UTF-8 válido."
    elif not isinstance(bloco.get("respostas"), list):
        motivo = "O campo respostas precisa ser uma lista."
    else:
        return bloco, None
    return None, _estrutura(workspace, [motivo])


def _problemas_da_entrada(entrada, numero):
    prefixo = f"Resposta {numero}: "
    if not isinstance(entrada, dict):
        return [prefixo + "a resposta precisa ser um objeto."]
    problemas = []
    item = entrada.get("item")
    if (
        not codificavel_utf8(item)
        or not item
        or item in (".", "..")
        or _tem_controle(item)
        or Path(item).name != item
    ):
        problemas.append(prefixo + "o campo item precisa ser um nome-base de arquivo válido.")
    decisao = entrada.get("decisao")
    if not codificavel_utf8(decisao) or decisao not in DECISOES:
        problemas.append(prefixo + "o campo decisao precisa ser pauta, acervo, projeto, lixo ou depois.")
    projeto = entrada.get("projeto")
    if decisao == "projeto" and not nome_projeto_valido(projeto):
        problemas.append(prefixo + "o campo projeto precisa ser um nome válido em uma linha.")
    elif "projeto" in entrada and not codificavel_utf8(projeto):
        problemas.append(prefixo + "o campo projeto precisa ser texto UTF-8 válido.")
    observacao = entrada.get("observacao")
    if "observacao" in entrada and not codificavel_utf8(observacao):
        problemas.append(prefixo + "o campo observacao precisa ser texto UTF-8 válido.")
    valor_digital = entrada.get("digital")
    if not isinstance(valor_digital, str) or not DIGITAL.fullmatch(valor_digital):
        problemas.append(prefixo + "o campo digital precisa ter 64 caracteres hexadecimais minúsculos.")
    return problemas


def _normalizar(entrada):
    observacao = entrada.get("observacao")
    return {
        "item": entrada["item"],
        "decisao": entrada["decisao"],
        "projeto": entrada.get("projeto"),
        "observacao": observacao if observacao and observacao.strip() else None,
        "digital": entrada["digital"],
    }


def _encontrar(inbox, nome):
    exato = inbox / nome
    try:
        if stat.S_ISREG(exato.stat().st_mode):
            return exato, None
    except FileNotFoundError:
        pass
    candidatos = []
    for caminho in inbox.iterdir():
        try:
            regular = stat.S_ISREG(caminho.stat().st_mode)
        except FileNotFoundError:
            continue
        if regular and caminho.stem == nome:
            candidatos.append(caminho)
    if len(candidatos) == 1:
        return candidatos[0], None
    return None, "ambiguo" if len(candidatos) > 1 else "inexistente"


def _resolver(respostas, workspace):
    conferencias = []
    caminhos = set()
    duplicatas = []
    inbox = workspace / "Inbox"
    for resposta in respostas:
        try:
            caminho, motivo = _encontrar(inbox, resposta["item"])
            if caminho is not None:
                caminho = caminho.resolve()
                caminho.relative_to(workspace.resolve())
        except ValueError:
            caminho, motivo = None, "inexistente"
        except OSError as erro:
            conferencias.append(
                f"{resposta['item']}: não foi possível localizar o item ({_motivo(erro)})."
            )
            caminho, motivo = None, "falha"
        if caminho is not None and caminho in caminhos:
            duplicatas.append(
                f"Duas respostas para o mesmo item: {resposta['item']}."
            )
        if caminho is not None:
            caminhos.add(caminho)
        conferencias_item = dict(resposta)
        conferencias_item["caminho"] = caminho
        conferencias_item["motivo_resolucao"] = motivo
        conferencias.append(conferencias_item)
    return conferencias, duplicatas


def _motivo(erro):
    return getattr(erro, "strerror", None) or str(erro)


def _falhas_e_fotografia(resolvidas, workspace):
    falhas = [item for item in resolvidas if isinstance(item, str)]
    planos = [item for item in resolvidas if isinstance(item, dict)]
    for item in planos:
        if item["caminho"] is None:
            continue
        try:
            item["bytes"] = item["caminho"].read_bytes()
        except OSError as erro:
            falhas.append(
                f"{item['item']}: não foi possível ler o item ({_motivo(erro)})."
            )
    destinos, problemas = fotografar_destinos(workspace)
    falhas.extend(problemas)
    return planos, destinos, falhas


def _envelhecimento(planos, destinos):
    causas = []
    for item in planos:
        if item["motivo_resolucao"] in ("inexistente", "ambiguo"):
            texto = (
                "não está mais na Inbox"
                if item["motivo_resolucao"] == "inexistente"
                else "não pode mais ser identificado de forma única"
            )
            causas.append((item["item"], texto, False))
            continue
        if item["caminho"] is None or "bytes" not in item:
            continue
        if hashlib.sha256(item["bytes"]).hexdigest() != item["digital"]:
            causas.append((item["item"], "mudou desde que a página foi gerada", False))
        for arquivo in marcador_em_destinos(destinos, item["caminho"].stem):
            causas.append((
                item["item"],
                f"já há registro deste item em {arquivo} — possível sobra de uma aplicação anterior; confira o destino e despache este item na conversa",
                True,
            ))
    return causas


def _recusa_envelhecida(workspace, causas):
    tem_marcador = any(causa[2] for causa in causas)
    tem_fotografia = any(not causa[2] for causa in causas)
    if tem_marcador and tem_fotografia:
        acoes = [
            "Resolva na conversa os itens que já têm registro no destino.",
            "Depois, gere a página de novo para o restante.",
        ]
    elif tem_marcador:
        acoes = ["Confira o destino e despache esse item na conversa."]
    else:
        acoes = ["Gere a página de novo."]
    return _recusa(
        workspace,
        "envelhecida",
        [f"{nome}: {motivo}." for nome, motivo, _ in causas],
        acoes,
        "A página envelheceu: o workspace mudou depois que ela foi gerada.",
    )


def _dominio(planos, destinos, workspace):
    problemas, acoes = [], []
    projetos_conferido = False
    for nome, foto in destinos.items():
        if foto["existe"] and not foto["regular"]:
            problemas.append(f"{nome} precisa ser um arquivo regular.")
            acoes.append("Rode doctor para conferir o workspace.")
    for item in planos:
        if item["caminho"] is None or item["decisao"] not in ("pauta", "projeto"):
            continue
        try:
            texto = item["bytes"].decode("utf-8")
        except UnicodeDecodeError:
            problemas.append(f"{item['item']}: o item não é texto UTF-8.")
            acoes.append("Use acervo ou lixo pra esse item.")
            continue
        if not any(linha.strip() for linha in texto.splitlines()):
            problemas.append(f"{item['item']}: o item não contém texto aproveitável neste destino.")
            acoes.append("Use o destino acervo para preservar o arquivo como está.")
        if (
            item["decisao"] == "projeto"
            and destinos["Projetos.md"]["regular"]
            and not projetos_conferido
        ):
            projetos_conferido = True
            try:
                destinos["Projetos.md"]["bytes"].decode("utf-8")
            except UnicodeDecodeError:
                problemas.append("Projetos.md não é texto UTF-8.")
                acoes.append("Confira Projetos.md e tente novamente.")
    if not problemas:
        return None
    return _recusa(
        workspace, "recusado", problemas, acoes,
        "A página não pode ser aplicada sem resolver estes itens.",
    )


def conferir(bloco, workspace):
    bloco, recusa = _carregar(bloco, workspace)
    if recusa:
        return {"recusa": recusa, "plano": None}
    problemas = []
    for numero, entrada in enumerate(bloco["respostas"], 1):
        problemas.extend(_problemas_da_entrada(entrada, numero))
    if problemas:
        antiga = any(
            isinstance(entrada, dict) and "digital" not in entrada
            for entrada in bloco["respostas"]
        )
        return {"recusa": _estrutura(workspace, problemas, antiga), "plano": None}
    respostas = [_normalizar(entrada) for entrada in bloco["respostas"]]
    if not respostas:
        return {"recusa": None, "plano": []}
    resolvidas, duplicatas = _resolver(respostas, workspace)
    if duplicatas:
        return {"recusa": _estrutura(workspace, duplicatas), "plano": None}
    planos, destinos, falhas = _falhas_e_fotografia(resolvidas, workspace)
    if falhas:
        recusa = _recusa(
            workspace, "recusado", falhas,
            ["Confira as permissões e tente novamente."],
            "Não foi possível conferir a página agora. Confira as permissões e tente novamente.",
        )
        return {"recusa": recusa, "plano": None}
    causas = _envelhecimento(planos, destinos)
    if causas:
        return {"recusa": _recusa_envelhecida(workspace, causas), "plano": None}
    recusa = _dominio(planos, destinos, workspace)
    if recusa:
        return {"recusa": recusa, "plano": None}
    for item in planos:
        item.pop("motivo_resolucao", None)
    return {"recusa": None, "plano": planos}
