import stat
from pathlib import Path

from .estrutura_workspace import problemas_da_estrutura, tem_marca_real


SINAIS_FORTES = {".neoprumo", "Pauta.md", "Projetos.md"}
SINAIS_FRACOS = {"Inbox", "Acervo", "Diario"}
CONTEXTOS = {"caminho_explicito", "ponteiro_ativo"}


def _observar_raiz(caminho):
    try:
        estado = caminho.lstat()
    except FileNotFoundError:
        return "inexistente"
    except OSError:
        return "ilegivel"
    if not stat.S_ISDIR(estado.st_mode):
        return "arquivo"
    return None


def _listar(caminho):
    try:
        return list(caminho.iterdir()), None
    except FileNotFoundError:
        return None, "inexistente"
    except OSError:
        return None, "ilegivel"


def _observar_marca(caminho):
    try:
        modo = (caminho / ".neoprumo").lstat().st_mode
    except FileNotFoundError:
        return None, None
    except OSError:
        return None, "ilegivel"
    if stat.S_ISLNK(modo):
        return "simbolica", None
    if stat.S_ISDIR(modo):
        return "real", None
    return "outro", None


def _sinais(caminho):
    presentes = set()
    for nome in SINAIS_FORTES | SINAIS_FRACOS:
        try:
            (caminho / nome).lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return None, "ilegivel"
        presentes.add(nome)
    return presentes, None


def classificar(caminho):
    caminho = Path(caminho).expanduser()
    estado = _observar_raiz(caminho)
    if estado:
        return estado
    entradas, falha = _listar(caminho)
    if falha:
        return falha
    marca, falha = _observar_marca(caminho)
    if falha:
        return falha
    if marca == "simbolica":
        return "marca_simbolica"
    if marca == "real" and tem_marca_real(caminho):
        return (
            "marcado_incompleto"
            if problemas_da_estrutura(caminho)
            else "saudavel"
        )
    if not entradas:
        return "vazio"
    sinais, falha = _sinais(caminho)
    if falha:
        return falha
    suficiente = bool(sinais & SINAIS_FORTES) or len(sinais) >= 2
    return "sem_marca_com_sinal" if suficiente else "sem_marca_sem_sinal"


def _acao(estado, caminho, contexto):
    if estado == "inexistente":
        return (
            f"Execute setup {caminho} para criar um workspace."
            if contexto == "caminho_explicito"
            else "Execute workspace usar <outro caminho>."
        )
    if estado in {"arquivo", "ilegivel", "marca_simbolica"}:
        return (
            None
            if contexto == "caminho_explicito"
            else "Execute workspace usar <outro caminho>."
        )
    if estado == "vazio":
        return f"Execute setup {caminho}."
    if estado == "sem_marca_com_sinal":
        return f"Execute setup --readotar {caminho}."
    if estado == "sem_marca_sem_sinal":
        return f"Execute setup --readotar --forcar {caminho}."
    if estado == "marcado_incompleto":
        return f"Execute doctor --reparar {caminho}."
    return None


def _textos(estado, caminho):
    if estado == "inexistente":
        return "O caminho não existe.", f"O caminho {caminho} não existe."
    if estado == "arquivo":
        return (
            "O caminho aponta para um arquivo.",
            "O caminho aponta para um arquivo, não para uma pasta.",
        )
    if estado == "ilegivel":
        return (
            "Não foi possível ler o caminho.",
            f"Não foi possível ler {caminho}; verifique as permissões.",
        )
    if estado == "marca_simbolica":
        return (
            "A pasta .neoprumo é um atalho.",
            "A pasta .neoprumo é um atalho; aponte para a pasta real.",
        )
    if estado == "marcado_incompleto":
        return "O workspace tem problemas.", "O workspace precisa de reparo."
    if estado == "saudavel":
        return "", "Tudo certo com o workspace."
    return (
        "O caminho não é um workspace do NeoPrumo.",
        "O caminho ainda não é um workspace utilizável.",
    )


def orientar(caminho, contexto):
    if contexto not in CONTEXTOS:
        raise ValueError("Contexto de orientação desconhecido.")
    caminho = Path(caminho).expanduser()
    estado = classificar(caminho)
    problema, mensagem = _textos(estado, caminho)
    acao = _acao(estado, caminho, contexto)
    return {
        "problema": problema,
        "acoes": [acao] if acao else [],
        "mensagem": mensagem + (f" {acao}" if acao else ""),
    }


def orientar_sem_ativo():
    acao = (
        "Execute setup para criar um workspace ou workspace usar para apontar "
        "um existente."
    )
    return {
        "problema": "Não há um workspace ativo resolvível.",
        "acoes": [acao],
        "mensagem": (
            "Nenhum workspace ativo pôde ser resolvido. "
            "Execute setup ou workspace usar para corrigir."
        ),
    }


def orientar_recuperacao(
    caminho,
    forcar=False,
    setup_puro_se_inexistente=False,
    falha_do_ponteiro=False,
):
    caminho = Path(caminho).expanduser()
    if falha_do_ponteiro:
        return f"Execute workspace usar {caminho}."
    if setup_puro_se_inexistente:
        try:
            caminho.lstat()
        except FileNotFoundError:
            return f"Resolva o obstáculo e repita setup {caminho}."
        except OSError:
            pass
    if tem_marca_real(caminho):
        return f"Execute doctor --reparar {caminho}."
    bandeira = " --forcar" if forcar else ""
    return f"Repita setup --readotar{bandeira} {caminho}."
