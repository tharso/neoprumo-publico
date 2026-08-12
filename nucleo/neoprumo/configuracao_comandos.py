import json
import sys

from .ativo import resolver as resolver_ativo
from .configuracao_avaliar import avaliar
from .configuracao_base import emitir, envelope, recusar, workspace_resolvido
from .configuracao_estado import observar
from .configuracao_lock import LockOcupado, lock_configuracao
from .configuracao_operacoes import DEFAULTS, conferir_commit, escolher_base, preparar
from .configuracao_rito import promover_stagings, publicar


def mostrar_configuracao(caminho=None, usar_json=False):
    workspace, resolução = workspace_resolvido(caminho, usar_json)
    if workspace is None:
        return 1
    estado = observar(workspace)
    ativo = resolver_ativo()
    configuração = {"estado": estado["estado"],
                    "chaves": {"versao": {"valor": "1", "origem": "workspace" if estado["ini"].exists() else "default"},
                               "workspace_ativo": {"valor": str(ativo) if ativo else None, "origem": "maquina"}},
                    "regras": estado["regras"], "dominancias": estado["dominancias"],
                    "avisos": estado["avisos"], "linhagem": estado["linhagem"]}
    resultado = envelope(workspace, "mostrada", f"Configuração: {estado['estado']}.",
                         acoes=estado["acoes"], resolucao_workspace=resolução,
                         configuracao=configuração)
    return emitir(resultado, usar_json)


def avaliar_configuracao(caminho=None, usar_json=False):
    workspace, _ = workspace_resolvido(caminho, usar_json)
    if workspace is None:
        return 1
    estado = observar(workspace)
    try:
        entrada = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return emitir(envelope(workspace, "recusado", "A entrada não é JSON válido.", ["JSON inválido."]), usar_json, 1)
    _, problemas = avaliar(entrada, [])
    if problemas:
        return emitir(envelope(workspace, "recusado", "A entrada do avaliador foi recusada.", problemas), usar_json, 1)
    if estado["estado"] not in ("vigente", "vigente com aviso", "vigente por autorização observada"):
        return emitir(envelope(workspace, "sem_regras", "A configuração atual não governa regras.", estado=estado["estado"], alvos=[], semanticas_ativas=[], suspensas_semanticas=[]), usar_json)
    resposta, _ = avaliar(entrada, estado["regras"])
    return emitir(envelope(workspace, "avaliado", "Alvos avaliados.", **resposta), usar_json)


def _resultado_preview(workspace, preparo):
    return envelope(workspace, "canonizada", "Configuração canonizada; confirme com o recibo.",
                    decisao=preparo["decisao"], token=preparo["token"], canonico=preparo["canonico"])


def _publicar_confirmado(workspace, gesto, preparo, texto, status, anexos=None,
                        destino=None, origem=None, extras=None):
    _, problema = conferir_commit(texto, preparo)
    if problema:
        return recusar(workspace, problema)
    try:
        with lock_configuracao(workspace):
            atual = observar(workspace)
            if atual["irmas"] and gesto != "resolver":
                return recusar(workspace, "Há conflito pendente; resolva primeiro.")
            base_atual, falha_base = escolher_base(
                atual, preparo.get("_cabeca_argumento"),
                preparo.get("_sob_pendencia", False),
            )
            if falha_base or base_atual != preparo["decisao"]["cabeca"]:
                return recusar(workspace, "O componente cabeca mudou desde o preview.")
            _, problema = conferir_commit(texto, preparo)
            if problema:
                return recusar(workspace, problema)
            promover_stagings(workspace)
            _, ok = publicar(workspace, gesto, preparo["canonico"], preparo["decisao"]["cabeca"],
                             preparo["mapa"], anexos=anexos, destino=destino,
                             origem_restauracao=origem, extras=extras)
            if not ok:
                return recusar(workspace, "Configuracao.ini mudou durante a publicação; a gravação ficou incompleta para recuperação.")
    except (LockOcupado, OSError) as erro:
        return recusar(workspace, str(erro))
    return envelope(workspace, status, "Configuração publicada com confirmação.")


def gravar(caminho=None, usar_json=False, confirmada=False, cabeca=None):
    workspace, _ = workspace_resolvido(caminho, usar_json)
    if workspace is None:
        return 1
    texto = sys.stdin.read()
    candidato = texto
    if confirmada:
        try:
            candidato = json.loads(texto)["candidato"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return emitir(recusar(workspace, "O commit de gravar precisa trazer candidato, recibo e token."), usar_json, 1)
    estado = observar(workspace)
    if estado["irmas"]:
        return emitir(recusar(workspace, "Há conflito pendente; resolva primeiro."), usar_json, 1)
    if estado["estado"] in ("proposta pendente", "proposta inválida"):
        return emitir(recusar(workspace, "Há uma edição manual pendente — adote ou rejeite primeiro."), usar_json, 1)
    preparo, _, problema = preparar(workspace, "gravar", candidato, cabeca)
    if problema:
        return emitir(recusar(workspace, problema), usar_json, 1)
    if not confirmada:
        return emitir(_resultado_preview(workspace, preparo), usar_json)
    resultado = _publicar_confirmado(workspace, "gravar", preparo, texto, "gravada")
    return emitir(resultado, usar_json, 0 if resultado["status"] == "gravada" else 1)


def defaults(caminho=None, usar_json=False, confirmada=False, cabeca=None):
    return _gesto_raiz("defaults", DEFAULTS, "gravada", caminho, usar_json, confirmada, cabeca)


def adotar(caminho=None, usar_json=False, confirmada=False, cabeca=None):
    workspace, _ = workspace_resolvido(caminho, usar_json)
    if workspace is None: return 1
    estado = observar(workspace)
    if estado["estado"] not in ("proposta pendente", "proposta inválida"):
        return emitir(recusar(workspace, "Não há proposta pendente para adotar."), usar_json, 1)
    bruto = estado["ini"].read_bytes()
    preparo, _, problema = preparar(workspace, "adotar", bruto, cabeca, True,
                                    riscos=["Regra permanente exige confirmação consciente."] if b"confirmacao = permanente" in bruto else [])
    if problema: return emitir(recusar(workspace, problema), usar_json, 1)
    if not confirmada: return emitir(_resultado_preview(workspace, preparo), usar_json)
    texto = sys.stdin.read()
    resultado = _publicar_confirmado(workspace, "adotar", preparo, texto, "adotada",
                                     [("proposta-original.ini", "proposta-original", bruto)])
    return emitir(resultado, usar_json, 0 if resultado["status"] == "adotada" else 1)


def _gesto_raiz(gesto, candidato, sucesso, caminho, usar_json, confirmada, cabeca):
    workspace, _ = workspace_resolvido(caminho, usar_json)
    if workspace is None: return 1
    estado = observar(workspace)
    if estado["irmas"]: return emitir(recusar(workspace, "Há conflito pendente; resolva primeiro."), usar_json, 1)
    if estado["estado"] in ("proposta pendente", "proposta inválida"):
        return emitir(recusar(workspace, "Há uma edição manual pendente — adote ou rejeite primeiro."), usar_json, 1)
    preparo, _, problema = preparar(workspace, gesto, candidato, cabeca)
    if problema: return emitir(recusar(workspace, problema), usar_json, 1)
    if not confirmada: return emitir(_resultado_preview(workspace, preparo), usar_json)
    resultado = _publicar_confirmado(workspace, gesto, preparo, sys.stdin.read(), sucesso)
    return emitir(resultado, usar_json, 0 if resultado["status"] == sucesso else 1)
