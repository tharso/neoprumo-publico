from .acervo import operar_acervo
from .superficie_acervo_preflight import conferir_acervo


def _executar(resposta, workspace):
    _, resultado = operar_acervo(
        resposta["item"],
        resposta["decisao"],
        workspace,
        item_resolvido=resposta["caminho"],
        bytes_validados=resposta["bytes"],
        digital_esperada=resposta["digital"],
    )
    resultado.update({
        "entrada": resposta["item"],
        "decisao": resposta["decisao"],
        "observacao": resposta["observacao"],
    })
    return resultado


def _quantidade(valor, singular, plural):
    return f"{valor} {singular if valor == 1 else plural}"


def _resumo(incluidos, excluidos, deixados, recusados):
    return ", ".join((
        _quantidade(incluidos, "incluído", "incluídos"),
        _quantidade(excluidos, "excluído", "excluídos"),
        _quantidade(deixados, "deixado", "deixados"),
        _quantidade(recusados, "recusado", "recusados"),
    )) + "."


def _agregar(workspace, resultados):
    incluidos = sum(item["status"] == "incluido" for item in resultados)
    excluidos = sum(item["status"] == "excluido" for item in resultados)
    deixados = sum(item["status"] == "deixado" for item in resultados)
    recusados = sum(item["status"] == "recusado" for item in resultados)
    return {
        "status": "aplicado_com_recusas" if recusados else "aplicado",
        "problemas": [
            problema for item in resultados for problema in item["problemas"]
        ],
        "acoes": [acao for item in resultados for acao in item["acoes"]],
        "mensagem": (
            "Nenhuma resposta para aplicar."
            if not resultados
            else _resumo(incluidos, excluidos, deixados, recusados)
        ),
        "workspace": str(workspace),
        "resultados": resultados,
        "incluidos": incluidos,
        "excluidos": excluidos,
        "deixados": deixados,
        "recusados": recusados,
    }


def _relatorio(resultado):
    return {
        "entrada": resultado["entrada"],
        "status": resultado["status"],
        "mensagem": resultado["mensagem"],
        "decisao": resultado["decisao"],
        "observacao": resultado["observacao"],
    }


def operar_aplicacao_acervo(bloco, workspace):
    preflight = conferir_acervo(bloco, workspace)
    if preflight["recusa"]:
        return 1, preflight["recusa"], []
    resultados = [
        _executar(resposta, workspace) for resposta in preflight["plano"]
    ]
    agregado = _agregar(workspace, resultados)
    relatorios = [_relatorio(resultado) for resultado in resultados]
    return (1 if agregado["recusados"] else 0), agregado, relatorios
