import json
import sys

from .despacho import operar_adiamento, operar_despacho
from .superficie_acervo_aplicar import operar_aplicacao_acervo
from .superficie_base import (
    campos_aplicar_nulos,
    codificavel_utf8,
    emitir,
    resolver_workspace,
)
from .superficie_preflight import conferir


def _executar(resposta, workspace):
    if resposta["decisao"] == "depois":
        _, resultado = operar_adiamento(
            resposta["item"],
            workspace,
            item_resolvido=resposta["caminho"],
            digital_esperada=resposta["digital"],
        )
    else:
        _, resultado = operar_despacho(
            resposta["item"],
            resposta["decisao"],
            resposta["projeto"],
            workspace,
            item_resolvido=resposta["caminho"],
            bytes_validados=resposta["bytes"],
            digital_esperada=resposta["digital"],
        )
    resultado.update(
        {"entrada": resposta["item"], "observacao": resposta["observacao"]}
    )
    estados_de_dominio = {
        "assunto_inexistente", "ambiguo", "referencia_invalida",
        "resolucao_incerta",
    }
    if resultado["status"] in estados_de_dominio:
        dominio = resultado["status"]
        resultado["status"] = "recusado"
        resultado["problemas"].append(f"Estado do assunto: {dominio}.")
    return resultado


def _quantidade(valor, singular, plural):
    return f"{valor} {singular if valor == 1 else plural}"


def _resumo(despachados, recusados, adiados):
    return ", ".join(
        (
            _quantidade(despachados, "despachado", "despachados"),
            _quantidade(recusados, "recusado", "recusados"),
            _quantidade(adiados, "adiado", "adiados"),
        )
    ) + "."


def _agregar(workspace, resultados, problemas=None):
    despachados = sum(item["status"] == "despachado" for item in resultados)
    recusados = sum(item["status"] == "recusado" for item in resultados)
    adiados = sum(item["status"] == "adiado" for item in resultados)
    return {
        "status": "aplicado_com_recusas" if recusados else "aplicado",
        "problemas": (problemas or []) + [
            problema for item in resultados for problema in item["problemas"]
        ],
        "acoes": [acao for item in resultados for acao in item["acoes"]],
        "mensagem": (
            "Nenhuma resposta para aplicar."
            if not resultados
            else _resumo(despachados, recusados, adiados)
        ),
        "workspace": str(workspace),
        "resultados": resultados,
        "despachados": despachados,
        "recusados": recusados,
        "adiados": adiados,
    }


def _relatorio(resultado, resposta):
    return {
        "entrada": resultado["entrada"],
        "status": resultado["status"],
        "mensagem": resultado["mensagem"],
        "projeto": resposta["projeto"],
        "observacao": resultado["observacao"],
    }


def _recusa_superficie(workspace):
    return {
        "status": "recusado",
        "problemas": ["O bloco não pertence a uma superfície conhecida."],
        "acoes": ["Copie novamente o bloco completo gerado pela superfície."],
        "mensagem": "O bloco de respostas tem formato inválido.",
        "workspace": str(workspace),
        **campos_aplicar_nulos(),
    }


def _rotear(entrada, workspace):
    bloco = entrada
    if isinstance(bloco, (str, bytes)):
        try:
            bloco = json.loads(bloco)
        except (json.JSONDecodeError, UnicodeDecodeError):
            preflight = conferir(entrada, workspace)
            return None, None, preflight["recusa"]
    if not isinstance(bloco, dict) or not codificavel_utf8(bloco.get("superficie")):
        preflight = conferir(bloco, workspace)
        return None, None, preflight["recusa"]
    superficie = bloco["superficie"]
    if superficie not in ("despacho", "acervo"):
        return None, None, _recusa_superficie(workspace)
    return superficie, bloco, None


def operar_aplicacao(caminho=None, texto=None):
    workspace, falha = resolver_workspace(caminho, campos_aplicar_nulos())
    if falha:
        return 1, falha, []
    entrada = sys.stdin.read() if texto is None else texto
    superficie, bloco, recusa = _rotear(entrada, workspace)
    if recusa:
        return 1, recusa, []
    if superficie == "acervo":
        return operar_aplicacao_acervo(bloco, workspace)
    preflight = conferir(bloco, workspace)
    if preflight["recusa"]:
        return 1, preflight["recusa"], []
    resultados = []
    relatorios = []
    for resposta in preflight["plano"]:
        resultado = _executar(resposta, workspace)
        resultados.append(resultado)
        relatorios.append(_relatorio(resultado, resposta))
    agregado = _agregar(workspace, resultados, preflight.get("problemas"))
    return (1 if agregado["recusados"] else 0), agregado, relatorios


def _emitir_recusa_humana(resultado):
    print(resultado["mensagem"], file=sys.stderr)
    for problema in resultado["problemas"]:
        print(problema, file=sys.stderr)
    for acao in resultado["acoes"]:
        print(acao, file=sys.stderr)


def aplicar_superficie(caminho=None, usar_json=False):
    codigo, resultado, relatorios = operar_aplicacao(caminho)
    if usar_json:
        emitir(resultado, True, erro=codigo != 0)
        return codigo
    if resultado["resultados"] is None:
        _emitir_recusa_humana(resultado)
        return codigo
    for relatorio in relatorios:
        print(json.dumps(relatorio, ensure_ascii=False))
    print(resultado["mensagem"])
    for problema in resultado["problemas"]:
        print(f"Aviso: {problema}")
    return codigo
