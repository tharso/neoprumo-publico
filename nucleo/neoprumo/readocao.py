from pathlib import Path

from .estrutura_workspace import problemas_da_estrutura
from .orientacao import classificar, orientar, orientar_recuperacao
from .workspace import (
    _ativar_workspace,
    _criar_conteudo,
    _criar_identidade,
    _emitir,
    _resultado,
    configurar,
)


def _recusar(workspace, estado, usar_json):
    guia = orientar(workspace, "caminho_explicito")
    problema = guia["problema"] or "O workspace não pode ser readotado neste estado."
    resultado = _resultado("recusado", [problema], guia["acoes"], guia["mensagem"])
    _emitir(resultado, usar_json, erro=True)
    return 1


def _recusar_sem_sinal(workspace, usar_json):
    acao = orientar_recuperacao(workspace, forcar=True)
    mensagem = (
        "Não há sinal suficiente de um workspace anterior. Com --forcar, seriam "
        "criados Inbox, Pauta.md, Acervo, Assuntos, Diario e .neoprumo."
    )
    resultado = _resultado(
        "recusado",
        ["Não há sinal suficiente de vida anterior do workspace."],
        [acao],
        mensagem,
    )
    _emitir(resultado, usar_json, erro=True)
    return 1


def _problemas_presentes(workspace, incompletos):
    problemas = problemas_da_estrutura(workspace)
    problemas.extend(incompletos)
    return problemas


def _parcial(workspace, problemas, acoes, forcar, usar_json, ponteiro=False):
    rota = (
        orientar_recuperacao(workspace, falha_do_ponteiro=True)
        if ponteiro
        else orientar_recuperacao(workspace, forcar=forcar)
    )
    resultado = _resultado(
        "com_problemas",
        problemas,
        acoes,
        f"A readoção ficou incompleta. {rota}",
    )
    _emitir(resultado, usar_json, erro=True)
    return 1


def readotar(caminho, forcar=False, usar_json=False):
    workspace = Path(caminho).expanduser()
    estado = classificar(workspace)
    if estado in {"arquivo", "inexistente", "ilegivel", "marca_simbolica"}:
        return _recusar(workspace, estado, usar_json)
    if estado == "saudavel":
        resultado = _resultado(
            "ja_existe", [], [], f"O workspace já existe em {workspace}; nada foi alterado."
        )
        _emitir(resultado, usar_json)
        return 0
    if estado == "marcado_incompleto":
        return _recusar(workspace, estado, usar_json)
    if estado == "vazio":
        return configurar(workspace, usar_json=usar_json)
    if estado == "sem_marca_sem_sinal" and not forcar:
        return _recusar_sem_sinal(workspace, usar_json)

    acoes, problemas = _criar_conteudo(workspace)
    if problemas:
        return _parcial(workspace, problemas, acoes, forcar, usar_json)
    incompletos = _criar_identidade(workspace, acoes)
    problemas = _problemas_presentes(workspace, incompletos)
    if problemas:
        return _parcial(workspace, problemas, acoes, forcar, usar_json)
    problemas = _ativar_workspace(workspace, acoes, "readotado")
    if problemas:
        return _parcial(
            workspace, problemas, acoes, forcar, usar_json, ponteiro=True
        )
    resultado = _resultado(
        "readotado",
        [],
        acoes,
        f"Workspace readotado em {workspace}.",
    )
    _emitir(resultado, usar_json)
    return 0
