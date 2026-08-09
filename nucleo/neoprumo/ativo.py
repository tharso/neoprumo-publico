import json
import os
import sys
from pathlib import Path

from .estrutura_workspace import tem_marca_real
from .orientacao import orientar, orientar_sem_ativo


def _caminho_da_configuracao():
    raiz_xdg = os.environ.get("XDG_CONFIG_HOME")
    raiz = Path(raiz_xdg) if raiz_xdg else Path.home() / ".config"
    return raiz / "neoprumo" / "config.json"


def _emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    destino = sys.stderr if erro else sys.stdout
    print(resultado["mensagem"], file=destino)


def e_workspace(caminho):
    workspace = Path(caminho)
    return workspace.is_dir() and tem_marca_real(workspace)


def adotar_se_primeiro(caminho):
    configuracao = _caminho_da_configuracao()
    workspace = Path(caminho).expanduser().resolve()
    configuracao.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(configuracao, "x", encoding="utf-8", newline="") as arquivo:
            arquivo.write(
                json.dumps({"workspace_ativo": str(workspace)}, ensure_ascii=False)
                + "\n"
            )
    except FileExistsError:
        return False
    return True


def definir(caminho, usar_json=False):
    workspace = Path(caminho).expanduser().resolve()
    if not e_workspace(workspace):
        guia = orientar(workspace, "caminho_explicito")
        resultado = {
            "status": "recusado",
            "problemas": ["O caminho não é um workspace do NeoPrumo."],
            "acoes": guia["acoes"],
            "mensagem": (
                "O caminho não é um workspace do NeoPrumo. " + guia["mensagem"]
            ),
            "workspace": str(workspace),
        }
        _emitir(resultado, usar_json, erro=True)
        return 1

    configuracao = _caminho_da_configuracao()
    configuracao.parent.mkdir(parents=True, exist_ok=True)
    configuracao.write_text(
        json.dumps({"workspace_ativo": str(workspace)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    resultado = {
        "status": "definido",
        "problemas": [],
        "acoes": [],
        "mensagem": f"Workspace ativo definido: {workspace}",
        "workspace": str(workspace),
    }
    _emitir(resultado, usar_json)
    return 0


def resolver():
    try:
        dados = json.loads(_caminho_da_configuracao().read_text(encoding="utf-8"))
        return Path(dados["workspace_ativo"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def informar_indisponivel(
    workspace=None,
    usar_json=False,
    incluir_item=False,
    extras=None,
):
    caminho = str(workspace) if workspace is not None else None
    guia = (
        orientar(workspace, "ponteiro_ativo")
        if workspace is not None
        else orientar_sem_ativo()
    )
    resultado = {
        "status": "ativo_invalido" if caminho else "sem_ativo",
        "problemas": [
            f"O caminho configurado não é um workspace válido: {caminho}"
            if caminho
            else "Não há um workspace ativo resolvível."
        ],
        "acoes": guia["acoes"],
        "mensagem": (
            f"O workspace ativo {caminho} não pôde ser usado. {guia['mensagem']}"
            if caminho
            else guia["mensagem"]
        ),
        "workspace": caminho,
    }
    if incluir_item:
        resultado.update({"item": None, "id": None})
    if extras is not None:
        resultado.update(extras)
    _emitir(resultado, usar_json, erro=True)
    return 1


def mostrar(usar_json=False):
    configuracao = _caminho_da_configuracao()
    if not configuracao.is_file():
        guia = orientar_sem_ativo()
        resultado = {
            "status": "sem_ativo",
            "problemas": ["Nenhum workspace ativo foi configurado."],
            "acoes": guia["acoes"],
            "mensagem": (
                "Nenhum workspace ativo. " + guia["mensagem"]
            ),
            "workspace": None,
        }
        _emitir(resultado, usar_json, erro=True)
        return 1
    try:
        dados = json.loads(configuracao.read_text(encoding="utf-8"))
        workspace = Path(dados["workspace_ativo"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        guia = orientar_sem_ativo()
        resultado = {
            "status": "sem_ativo",
            "problemas": ["A configuração não contém um workspace ativo válido."],
            "acoes": guia["acoes"],
            "mensagem": (
                "A configuração do NeoPrumo está inválida; " + guia["mensagem"]
            ),
            "workspace": None,
        }
        _emitir(resultado, usar_json, erro=True)
        return 1
    if not workspace.exists():
        guia = orientar(workspace, "ponteiro_ativo")
        resultado = {
            "status": "ativo_invalido",
            "problemas": [f"O caminho configurado não existe: {workspace}"],
            "acoes": guia["acoes"],
            "mensagem": (
                f"O workspace ativo {workspace} não existe. " + guia["mensagem"]
            ),
            "workspace": str(workspace),
        }
        _emitir(resultado, usar_json, erro=True)
        return 1
    if not e_workspace(workspace):
        guia = orientar(workspace, "ponteiro_ativo")
        resultado = {
            "status": "ativo_invalido",
            "problemas": [f"O caminho deixou de ser um workspace: {workspace}"],
            "acoes": guia["acoes"],
            "mensagem": (
                f"O caminho ativo {workspace} não é mais um workspace. "
                + guia["mensagem"]
            ),
            "workspace": str(workspace),
        }
        _emitir(resultado, usar_json, erro=True)
        return 1
    resultado = {
        "status": "ativo",
        "problemas": [],
        "acoes": [],
        "mensagem": f"Workspace ativo: {workspace}",
        "workspace": str(workspace),
    }
    _emitir(resultado, usar_json)
    return 0
