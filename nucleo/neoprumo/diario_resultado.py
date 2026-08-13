import json
import sys


LIMITACOES = [
    "A data em que uma entrada da Pauta foi concluída não é registrada; só o estado de conclusão é visível.",
    "Entrada criada à mão na Pauta, sem rodapé de origem, não tem data comprovável.",
    "Item movido pro Acervo cuja captura é de outro dia não aparece como acontecimento de hoje.",
    "Item mandado pro lixo não deixa carimbo disponível para o diário.",
    "Mudança de regime ou prazo da Pauta não deixa carimbo disponível para o diário.",
    "Assunto registrado, arquivado ou reativado não deixa carimbo disponível para o diário.",
    "Item cujo nome saiu do RG canônico não tem data comprovável pela captura.",
    "A data de uma nota de assunto é declarada pelo dono e não prova quando ela foi realmente escrita.",
]


def envelope(status, mensagem, workspace, problemas=None, acoes=None, **campos):
    resultado = {
        "status": status,
        "problemas": problemas or [],
        "acoes": acoes or [],
        "mensagem": mensagem,
        "workspace": str(workspace) if workspace is not None else None,
    }
    resultado.update(campos)
    return resultado


def campos_vazios(dia=None):
    return {
        "dia": dia,
        "pauta": [],
        "assuntos": [],
        "capturas": [],
        "total": 0,
        "limitacoes": LIMITACOES,
        "diario": {"existe": False, "secoes": 0},
    }


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    destino = sys.stderr if erro else sys.stdout
    print(resultado["mensagem"], file=destino)
    for problema in resultado["problemas"]:
        print(f"Aviso: {problema}", file=destino)
