import os
import re
import stat
from datetime import datetime
from pathlib import Path

from .ativo import e_workspace, informar_indisponivel, resolver
from .resultado_seed import campos_nulos, emitir_resumo, recusar_workspace
from .workspace import inspecionar_estrutura


PADRAO_NOME = re.compile(
    r"^(?P<data>\d{4}-\d{2}-\d{2}-\d{6})(?:-(?:[2-9]\d*|1\d+))?$"
)


def _motivo(erro):
    return erro.strerror or str(erro)


def _validar_area(caminho, tipo):
    nome = caminho.name
    try:
        estado = caminho.lstat()
    except FileNotFoundError:
        return f"{nome}: não existe."
    except OSError as erro:
        return f"{nome}: não pôde ser observada ({_motivo(erro)})."
    if stat.S_ISLNK(estado.st_mode):
        return f"{nome}: é um atalho simbólico e não será seguido."
    modo_esperado = stat.S_ISDIR if tipo == "pasta" else stat.S_ISREG
    if not modo_esperado(estado.st_mode):
        artigo = "uma" if tipo == "pasta" else "um"
        return f"{nome}: deveria ser {artigo} {tipo}."
    return None


def _data_pelo_nome(nome):
    radical = Path(nome).stem
    correspondencia = PADRAO_NOME.fullmatch(radical)
    if correspondencia is None:
        return None
    try:
        return datetime.strptime(
            correspondencia.group("data"), "%Y-%m-%d-%H%M%S"
        ).date()
    except ValueError:
        return None


def _observar_itens(pasta, referencia, incluir_mais_novo):
    problema = _validar_area(pasta, "pasta")
    if problema:
        return None, [problema]
    idades = []
    problemas = []
    try:
        with os.scandir(pasta) as entradas:
            for entrada in entradas:
                if entrada.name.startswith("."):
                    continue
                try:
                    estado = entrada.stat(follow_symlinks=False)
                except OSError as erro:
                    problemas.append(
                        f"{pasta.name}: não foi possível observar {entrada.name} "
                        f"({_motivo(erro)}); o item não foi contado."
                    )
                    continue
                if not stat.S_ISREG(estado.st_mode):
                    continue
                data = _data_pelo_nome(entrada.name)
                if data is None:
                    try:
                        data = datetime.fromtimestamp(
                            estado.st_mtime, tz=referencia.tzinfo
                        ).date()
                    except (OSError, OverflowError, ValueError) as erro:
                        problemas.append(
                            f"{pasta.name}: não foi possível ler a data de "
                            f"{entrada.name} ({erro}); o item não foi contado."
                        )
                        continue
                idades.append(max(0, (referencia.date() - data).days))
    except OSError as erro:
        return None, [
            f"{pasta.name}: não pôde ser lida ({_motivo(erro)})."
        ]
    resultado = {
        "total": len(idades),
        "idade_mais_antigo_dias": max(idades) if idades else None,
    }
    if incluir_mais_novo:
        resultado["idade_mais_novo_dias"] = min(idades) if idades else None
    return resultado, problemas


def _observar_pauta(caminho):
    problema = _validar_area(caminho, "arquivo")
    if problema:
        return None, [problema]
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return None, ["Pauta.md: o conteúdo não é texto UTF-8."]
    except OSError as erro:
        return None, [f"Pauta.md: não pôde ser lida ({_motivo(erro)})."]
    return {
        "abertos": sum(linha.startswith("- [ ]") for linha in linhas),
        "concluidos": sum(
            linha.startswith(("- [x]", "- [X]")) for linha in linhas
        ),
    }, []


def resumir(caminho, instante=None):
    workspace = Path(caminho)
    referencia = instante or datetime.now().astimezone()
    if referencia.tzinfo is None:
        referencia = referencia.astimezone()
    referencia = referencia.replace(microsecond=0)
    inbox, problemas_inbox = _observar_itens(
        workspace / "Inbox", referencia, incluir_mais_novo=True
    )
    acervo, problemas_acervo = _observar_itens(
        workspace / "Acervo", referencia, incluir_mais_novo=False
    )
    pauta, problemas_pauta = _observar_pauta(workspace / "Pauta.md")
    return {
        "status": "resumido",
        "problemas": problemas_inbox + problemas_pauta + problemas_acervo,
        "acoes": [],
        "mensagem": "Resumo do workspace pronto.",
        "workspace": str(workspace),
        "gerado_em": referencia.isoformat(),
        "inbox": inbox,
        "pauta": pauta,
        "acervo": acervo,
        "estrutura": inspecionar_estrutura(workspace),
    }


def executar_seed(caminho=None, usar_json=False, instante=None):
    workspace_explicito = caminho is not None
    workspace = (
        Path(caminho).expanduser().resolve() if workspace_explicito else resolver()
    )
    if workspace is None:
        return informar_indisponivel(
            usar_json=usar_json,
            extras=campos_nulos(),
        )
    workspace = Path(workspace).expanduser().resolve()
    if not e_workspace(workspace):
        if workspace_explicito:
            return recusar_workspace(workspace, usar_json)
        return informar_indisponivel(
            workspace,
            usar_json=usar_json,
            extras=campos_nulos(),
        )
    resultado = resumir(workspace, instante=instante)
    emitir_resumo(resultado, usar_json)
    return 0
