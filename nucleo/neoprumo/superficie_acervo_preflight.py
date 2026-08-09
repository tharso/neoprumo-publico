import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .acervo_base import (
    encontrar_item,
    esta_dentro,
    fotografar_pauta,
    marcador_no_acervo,
    ler_bytes,
    motivo,
    validar_pasta_acervo,
)
from .superficie_base import campos_aplicar_acervo_nulos, codificavel_utf8


DECISOES = ("pauta", "atacar", "lixo", "deixar")
DIGITAL = re.compile(r"^[0-9a-f]{64}$")


def _recusa(workspace, status, problemas, acoes, mensagem):
    return {
        "status": status,
        "problemas": problemas,
        "acoes": acoes,
        "mensagem": mensagem,
        "workspace": str(workspace),
        **campos_aplicar_acervo_nulos(),
    }


def _estrutura(workspace, problemas):
    return _recusa(
        workspace,
        "recusado",
        problemas,
        ["Copie novamente o bloco completo gerado pela superfície."],
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
        motivo_recusa = "O bloco precisa ser um objeto JSON."
    elif not codificavel_utf8(bloco.get("superficie")):
        motivo_recusa = "O campo superficie precisa ser texto UTF-8 válido."
    elif bloco["superficie"] != "acervo":
        motivo_recusa = "O bloco não pertence à superfície do acervo."
    elif not codificavel_utf8(bloco.get("pagina")) or not bloco["pagina"].strip():
        motivo_recusa = "O campo pagina precisa ser texto não vazio e UTF-8 válido."
    elif not isinstance(bloco.get("respostas"), list):
        motivo_recusa = "O campo respostas precisa ser uma lista."
    else:
        return bloco, None
    return None, _estrutura(workspace, [motivo_recusa])


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
        problemas.append(
            prefixo + "o campo item precisa ser um nome-base de arquivo válido."
        )
    decisao = entrada.get("decisao")
    if not codificavel_utf8(decisao) or decisao not in DECISOES:
        problemas.append(
            prefixo + "o campo decisao precisa ser pauta, atacar, lixo ou deixar."
        )
    observacao = entrada.get("observacao")
    if "observacao" in entrada and not codificavel_utf8(observacao):
        problemas.append(
            prefixo + "o campo observacao precisa ser texto UTF-8 válido."
        )
    digital = entrada.get("digital")
    if not isinstance(digital, str) or not DIGITAL.fullmatch(digital):
        problemas.append(
            prefixo
            + "o campo digital precisa ter 64 caracteres hexadecimais minúsculos."
        )
    return problemas


def _normalizar(entrada):
    observacao = entrada.get("observacao")
    return {
        "item": entrada["item"],
        "decisao": entrada["decisao"],
        "observacao": observacao if observacao and observacao.strip() else None,
        "digital": entrada["digital"],
    }


def _resolver(respostas, workspace):
    acervo = workspace / "Acervo"
    problema = validar_pasta_acervo(acervo, workspace)
    if problema:
        return [], [], [problema]
    planos, caminhos, duplicatas, falhas = [], set(), [], []
    for resposta in respostas:
        try:
            caminho, causa = encontrar_item(acervo, resposta["item"])
            if caminho is not None:
                caminho = caminho.resolve()
                if not esta_dentro(caminho, workspace):
                    caminho, causa = None, "inexistente"
        except OSError as erro:
            falhas.append(
                f"{resposta['item']}: não foi possível localizar o item ({motivo(erro)})."
            )
            caminho, causa = None, "falha"
        if caminho is not None and caminho in caminhos:
            duplicatas.append(
                f"Duas respostas para o mesmo item: {resposta['item']}."
            )
        if caminho is not None:
            caminhos.add(caminho)
        plano = dict(resposta)
        plano.update({"caminho": caminho, "motivo_resolucao": causa})
        planos.append(plano)
    return planos, duplicatas, falhas


def _fotografar(planos, workspace):
    falhas = []
    for item in planos:
        if item["caminho"] is None:
            continue
        try:
            item["bytes"] = ler_bytes(item["caminho"])
        except OSError as erro:
            falhas.append(
                f"{item['item']}: não foi possível ler o item ({motivo(erro)})."
            )
    pauta, problema = fotografar_pauta(workspace)
    if problema:
        falhas.append(problema)
    return pauta, falhas


def _envelhecimento(planos, pauta):
    causas = []
    for item in planos:
        resolucao = item["motivo_resolucao"]
        if resolucao in ("inexistente", "ambiguo"):
            texto = (
                "não está mais no Acervo"
                if resolucao == "inexistente"
                else "não pode mais ser identificado de forma única"
            )
            causas.append((item["item"], texto, False))
            continue
        if item["caminho"] is None or "bytes" not in item:
            continue
        if hashlib.sha256(item["bytes"]).hexdigest() != item["digital"]:
            causas.append(
                (item["item"], "mudou desde que a página foi gerada", False)
            )
        if marcador_no_acervo(pauta, item["caminho"].stem):
            causas.append((
                item["item"],
                "já há registro deste item em Pauta.md — possível sobra de uma "
                "aplicação anterior; confira o destino e resolva este item na conversa",
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
        [f"{nome}: {causa}." for nome, causa, _ in causas],
        acoes,
        "A página envelheceu: o workspace mudou depois que ela foi gerada.",
    )


def _dominio(planos, pauta, workspace):
    problemas, acoes = [], []
    if pauta["existe"] and not pauta["regular"]:
        problemas.append("Pauta.md precisa ser um arquivo regular.")
        acoes.append("Rode doctor para conferir o workspace.")
    for item in planos:
        if item["caminho"] is None or item["decisao"] not in ("pauta", "atacar"):
            continue
        try:
            texto = item["bytes"].decode("utf-8")
        except UnicodeDecodeError:
            problemas.append(f"{item['item']}: o item não é texto UTF-8.")
            acoes.append("Use excluir ou deixe o item no acervo.")
            continue
        if not any(linha.strip() for linha in texto.splitlines()):
            problemas.append(
                f"{item['item']}: o item não contém texto aproveitável neste destino."
            )
            acoes.append("Use excluir ou deixe o item no acervo.")
    if not problemas:
        return None
    return _recusa(
        workspace,
        "recusado",
        problemas,
        acoes,
        "A página não pode ser aplicada sem resolver estes itens.",
    )


def conferir_acervo(bloco, workspace):
    bloco, recusa = _carregar(bloco, workspace)
    if recusa:
        return {"recusa": recusa, "plano": None}
    problemas = []
    for numero, entrada in enumerate(bloco["respostas"], 1):
        problemas.extend(_problemas_da_entrada(entrada, numero))
    if problemas:
        return {"recusa": _estrutura(workspace, problemas), "plano": None}
    respostas = [_normalizar(entrada) for entrada in bloco["respostas"]]
    if not respostas:
        return {"recusa": None, "plano": []}
    planos, duplicatas, falhas = _resolver(respostas, workspace)
    if duplicatas:
        return {"recusa": _estrutura(workspace, duplicatas), "plano": None}
    pauta, falhas_foto = _fotografar(planos, workspace)
    falhas.extend(falhas_foto)
    if falhas:
        return {"recusa": _recusa(
            workspace,
            "recusado",
            falhas,
            ["Confira as permissões e tente novamente."],
            "Não foi possível conferir a página agora. Confira as permissões e tente novamente.",
        ), "plano": None}
    causas = _envelhecimento(planos, pauta)
    if causas:
        return {"recusa": _recusa_envelhecida(workspace, causas), "plano": None}
    recusa = _dominio(planos, pauta, workspace)
    if recusa:
        return {"recusa": recusa, "plano": None}
    for item in planos:
        item.pop("motivo_resolucao", None)
    return {"recusa": None, "plano": planos}
