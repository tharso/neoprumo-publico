import sys

from .configuracao_base import emitir, recusar, workspace_resolvido
from .configuracao_comandos import _publicar_confirmado, _resultado_preview
from .configuracao_estado import observar
from .configuracao_linhagem import candidato
from .configuracao_modelo import digital_bytes
from .configuracao_operacoes import DEFAULTS, artefato_da_gravacao, escolher_base, preparar


def rejeitar(caminho=None, usar_json=False, confirmada=False, cabeca=None,
             usar_defaults=False, gravacao=None, artefato=None):
    workspace, _ = workspace_resolvido(caminho, usar_json)
    if workspace is None: return 1
    estado = observar(workspace)
    if estado["estado"] not in ("proposta pendente", "proposta inválida"):
        return emitir(recusar(workspace, "Não há proposta pendente para rejeitar."), usar_json, 1)
    proposta = estado["ini"].read_bytes()
    base, problema = escolher_base(estado, cabeca, True)
    if problema: return emitir(recusar(workspace, problema), usar_json, 1)
    origem = None
    if base is not None and candidato(estado["grafo"]["mapa"][base]) and not usar_defaults and gravacao is None:
        alvo = candidato(estado["grafo"]["mapa"][base]).read_bytes()
        destino = {"tipo": "base"}
    elif usar_defaults:
        alvo, destino = DEFAULTS.encode(), {"tipo": "defaults"}
    elif gravacao:
        fonte, selecionado, problema = artefato_da_gravacao(estado, gravacao, artefato or "candidato")
        if problema: return emitir(recusar(workspace, problema), usar_json, 1)
        item, alvo = selecionado
        destino = {"tipo": "artefato", "gravacao": fonte["id"],
                   "artefato": {"tipo": item["tipo"], "arquivo": item["arquivo"]},
                   "digital": item["digital"]}
        origem = {"gravacao": fonte["id"], "artefato": destino["artefato"], "digital": item["digital"]}
    elif base is None:
        alvo, destino = DEFAULTS.encode(), {"tipo": "defaults"}
    else:
        return emitir(recusar(workspace, "A base foi identificada, mas seu payload não existe. Escolha --defaults ou --gravacao/--artefato."), usar_json, 1)
    preparo, _, problema = preparar(workspace, "rejeitar", alvo, cabeca, True, campos={"destino": destino})
    if problema: return emitir(recusar(workspace, problema), usar_json, 1)
    if not confirmada: return emitir(_resultado_preview(workspace, preparo), usar_json)
    resultado = _publicar_confirmado(workspace, "rejeitar", preparo, sys.stdin.read(), "rejeitada",
                                     [("rejeitada.ini", "rejeitada", proposta)],
                                     destino={"tipo": destino["tipo"]}, origem=origem)
    return emitir(resultado, usar_json, 0 if resultado["status"] == "rejeitada" else 1)


def restaurar(caminho=None, usar_json=False, confirmada=False, cabeca=None,
              gravacao=None, artefato="candidato"):
    workspace, _ = workspace_resolvido(caminho, usar_json)
    if workspace is None: return 1
    estado = observar(workspace)
    if estado["estado"] in ("proposta pendente", "proposta inválida"):
        return emitir(recusar(workspace, "Há uma edição manual pendente — adote ou rejeite primeiro."), usar_json, 1)
    fonte, selecionado, problema = artefato_da_gravacao(estado, gravacao, artefato)
    if problema: return emitir(recusar(workspace, problema), usar_json, 1)
    item, conteudo = selecionado
    origem = {"gravacao": fonte["id"], "artefato": {"tipo": item["tipo"], "arquivo": item["arquivo"]}, "digital": item["digital"]}
    campos = {"gravacao_origem": fonte["id"], "artefato": origem["artefato"],
              "digital_payload_historico": item["digital"]}
    preparo, _, problema = preparar(workspace, "restaurar", conteudo, cabeca, campos=campos)
    if problema: return emitir(recusar(workspace, problema), usar_json, 1)
    if not confirmada: return emitir(_resultado_preview(workspace, preparo), usar_json)
    resultado = _publicar_confirmado(workspace, "restaurar", preparo, sys.stdin.read(), "restaurada",
                                     origem=origem)
    return emitir(resultado, usar_json, 0 if resultado["status"] == "restaurada" else 1)
