import json
import sys


def campos_nulos():
    return {
        "candidato": None,
        "elegiveis": None,
        "elegiveis_acervo": None,
        "elegiveis_em_espera": None,
    }


def envelope(
    status,
    mensagem,
    workspace,
    candidato=None,
    elegiveis=None,
    elegiveis_acervo=None,
    elegiveis_em_espera=None,
    problemas=None,
    acoes=None,
):
    return {
        "status": status,
        "problemas": problemas or [],
        "acoes": acoes or [],
        "mensagem": mensagem,
        "workspace": str(workspace) if workspace is not None else None,
        "candidato": candidato,
        "elegiveis": elegiveis,
        "elegiveis_acervo": elegiveis_acervo,
        "elegiveis_em_espera": elegiveis_em_espera,
    }


def recusa(workspace, problema, acao, mensagem):
    return envelope(
        "recusado",
        mensagem,
        workspace,
        problemas=[problema],
        acoes=[acao],
    )


def mensagem_do_candidato(candidato, elegiveis):
    dias = candidato["idade"]
    total = f"{elegiveis} {'elegível' if elegiveis == 1 else 'elegíveis'}"
    if candidato["origem"] == "em_espera":
        if dias is None:
            idade = "(sem data conhecida)"
        else:
            idade = f"há {dias} {'dia' if dias == 1 else 'dias'}"
        return (
            f"«{candidato['manchete']}» está em espera {idade}; {total} hoje."
        )
    idade = f"{dias} {'dia' if dias == 1 else 'dias'}"
    return f"{candidato['nome']} está no acervo há {idade}; {total} hoje."


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    destino = sys.stderr if erro else sys.stdout
    print(resultado["mensagem"], file=destino)
    if erro:
        return
    candidato = resultado["candidato"]
    if candidato is not None:
        print(candidato["conteudo"], file=destino)
    for problema in resultado["problemas"]:
        print(f"Aviso: {problema}", file=destino)
