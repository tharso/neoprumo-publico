import json
import sys
from datetime import datetime
from pathlib import Path

from .ativo import e_workspace, informar_indisponivel, resolver
from .orientacao import orientar


AVISO_INBOX_RECRIADA = (
    "A pasta Inbox estava faltando e foi recriada. "
    "Rode doctor para conferir o workspace."
)


def _emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    destino = sys.stderr if erro else sys.stdout
    print(resultado["mensagem"], file=destino)


def _recusar_workspace(workspace, usar_json):
    guia = orientar(workspace, "caminho_explicito")
    resultado = {
        "status": "recusado",
        "problemas": ["O caminho não é um workspace do NeoPrumo."],
        "acoes": guia["acoes"],
        "mensagem": "O caminho não é um workspace do NeoPrumo. " + guia["mensagem"],
        "workspace": str(workspace),
        "item": None,
        "id": None,
    }
    _emitir(resultado, usar_json, erro=True)
    return 1


def _recusar_texto_vazio(workspace, usar_json):
    resultado = {
        "status": "recusado",
        "problemas": ["O texto está vazio ou contém apenas espaços."],
        "acoes": ["Envie algum texto para guardar na inbox."],
        "mensagem": "Capturar nada não é captura. Envie algum texto para guardar.",
        "workspace": str(workspace),
        "item": None,
        "id": None,
    }
    _emitir(resultado, usar_json, erro=True)
    return 1


def _gravar(inbox, texto):
    base = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    numero = 1
    conteudo = texto.rstrip("\r\n") + "\n"
    while True:
        identificador = base if numero == 1 else f"{base}-{numero}"
        item = inbox / f"{identificador}.md"
        try:
            with item.open("x", encoding="utf-8", newline="") as arquivo:
                arquivo.write(conteudo)
            return identificador, item
        except FileExistsError:
            numero += 1


def capturar(texto, caminho=None, usar_json=False):
    workspace_explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if caminho is not None else resolver()
    if workspace is None:
        return informar_indisponivel(usar_json=usar_json, incluir_item=True)
    if not e_workspace(workspace):
        if workspace_explicito:
            return _recusar_workspace(workspace, usar_json)
        return informar_indisponivel(
            workspace,
            usar_json=usar_json,
            incluir_item=True,
        )
    if not texto.strip():
        return _recusar_texto_vazio(workspace, usar_json)

    inbox = workspace / "Inbox"
    acoes = []
    if not inbox.exists():
        inbox.mkdir(parents=True, exist_ok=True)
        acoes.append(AVISO_INBOX_RECRIADA)
    identificador, item = _gravar(inbox, texto)
    mensagem = f"Guardei na inbox: {identificador}. Workspace: {workspace}."
    if acoes:
        mensagem += " A pasta Inbox estava faltando e foi recriada — rode doctor."
    resultado = {
        "status": "capturado",
        "problemas": [],
        "acoes": acoes,
        "mensagem": mensagem,
        "workspace": str(workspace),
        "item": str(item),
        "id": identificador,
    }
    _emitir(resultado, usar_json)
    return 0
