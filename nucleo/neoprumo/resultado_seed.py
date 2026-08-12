import json
import sys

from .orientacao import orientar


def campos_nulos():
    return {
        "gerado_em": None,
        "inbox": None,
        "pauta": None,
        "acervo": None,
        "estrutura": None,
        "configuracao": None,
    }


def recusar_workspace(workspace, usar_json, extras=None):
    guia = orientar(workspace, "caminho_explicito")
    resultado = {
        "status": "recusado",
        "problemas": ["O caminho não é um workspace do NeoPrumo."],
        "acoes": guia["acoes"],
        "mensagem": "O caminho não é um workspace do NeoPrumo. " + guia["mensagem"],
        "workspace": str(workspace),
        **(campos_nulos() if extras is None else extras),
    }
    _emitir_recusa(resultado, usar_json)
    return 1


def _emitir_recusa(resultado, usar_json):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        print(resultado["mensagem"], file=sys.stderr)


def _quantidade(valor, singular, plural):
    return f"{valor} {singular if valor == 1 else plural}"


def _motivo_da_area(resultado, nome):
    motivo = next(
        (problema for problema in resultado["problemas"] if problema.startswith(nome)),
        "falha de leitura",
    )
    return motivo.rstrip(".")


def _idade(dias):
    return f"{dias} {'dia' if dias == 1 else 'dias'}"


def _prazo_item(dias):
    if dias is None:
        return ""
    if dias == 0:
        return " (vence hoje)"
    if dias > 0:
        return f" (vence em {dias} {'dia' if dias == 1 else 'dias'})"
    atraso = abs(dias)
    return f" (venceu há {atraso} {'dia' if atraso == 1 else 'dias'})"


def _linhas_da_pauta(pauta):
    linhas = []
    if pauta["regimes"]["a_vista"]:
        itens = "; ".join(
            item["manchete"] + _prazo_item(item["vence_em_dias"])
            for item in pauta["a_vista"]
        )
        linhas.append(f"À vista: {pauta['regimes']['a_vista']} — {itens}.")
    acordaram = pauta["acordaram_hoje"]
    if acordaram:
        verbo = "Acordou hoje" if acordaram == 1 else "Acordaram hoje"
        linhas.append(f"{verbo}: {acordaram}.")
    prazos = pauta["prazos"]
    partes = []
    if prazos["vencidos"]:
        partes.append(_quantidade(prazos["vencidos"], "vencido", "vencidos"))
    if prazos["vence_hoje"]:
        n = prazos["vence_hoje"]
        partes.append(f"{n} {'vence' if n == 1 else 'vencem'} hoje")
    if prazos["proximo_em_dias"] is not None:
        dias = prazos["proximo_em_dias"]
        partes.append(f"próximo vence em {dias} {'dia' if dias == 1 else 'dias'}")
    if partes:
        linhas.append("Prazos: " + "; ".join(partes) + ".")
    return linhas


def linhas_humanas(resultado):
    inbox = resultado["inbox"]
    if inbox is None:
        linha_inbox = f"Inbox: não deu pra ver ({_motivo_da_area(resultado, 'Inbox')})."
    elif inbox["total"] == 0:
        linha_inbox = "Inbox: vazia."
    else:
        linha_inbox = (
            f"Inbox: {_quantidade(inbox['total'], 'item', 'itens')}; "
            f"mais antigo há {_idade(inbox['idade_mais_antigo_dias'])}; "
            f"mais novo há {_idade(inbox['idade_mais_novo_dias'])}."
        )

    pauta = resultado["pauta"]
    if pauta is None:
        linha_pauta = f"Pauta: não deu pra ver ({_motivo_da_area(resultado, 'Pauta')})."
    elif pauta["abertos"] == pauta["concluidos"] == 0:
        linha_pauta = "Pauta: vazia."
    else:
        linha_pauta = (
            f"Pauta: {_quantidade(pauta['abertos'], 'aberto', 'abertos')}, "
            f"{_quantidade(pauta['concluidos'], 'concluído', 'concluídos')}."
        )

    acervo = resultado["acervo"]
    if acervo is None:
        linha_acervo = f"Acervo: não deu pra ver ({_motivo_da_area(resultado, 'Acervo')})."
    elif acervo["total"] == 0:
        linha_acervo = "Acervo: vazio."
    else:
        linha_acervo = (
            f"Acervo: {_quantidade(acervo['total'], 'item', 'itens')}; "
            f"mais antigo há {_idade(acervo['idade_mais_antigo_dias'])}."
        )

    estrutura = resultado["estrutura"]
    if estrutura["status"] == "saudavel":
        linha_estrutura = "Estrutura: saudável."
    else:
        linha_estrutura = (
            "Estrutura: com "
            f"{_quantidade(len(estrutura['problemas']), 'problema', 'problemas')}."
        )
    linhas = [linha_inbox, linha_pauta]
    if pauta is not None:
        linhas.extend(_linhas_da_pauta(pauta))
    linhas.extend([linha_acervo, linha_estrutura])
    linhas.extend(f"Aviso: {problema}" for problema in resultado["problemas"])
    return linhas


def emitir_resumo(resultado, usar_json):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    for linha in linhas_humanas(resultado):
        print(linha)
