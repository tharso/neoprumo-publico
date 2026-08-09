import json
import sys

from . import __version__
from .__main__ import envelope_do_hook
from .ativo import e_workspace, resolver
from .orientacao import orientar, orientar_sem_ativo
from .resultado_seed import linhas_humanas
from .seed import resumir


def linha_de_estado():
    versao_python = ".".join(map(str, sys.version_info[:3]))
    return f"NeoPrumo {__version__} ativo — Python {versao_python}."


def sondar(usar_hook=False):
    linha = linha_de_estado()
    if usar_hook:
        try:
            workspace = resolver()
            if workspace is None:
                linha += "\n" + orientar_sem_ativo()["mensagem"]
            elif not e_workspace(workspace):
                guia = orientar(workspace, "ponteiro_ativo")
                linha += (
                    f"\nO workspace ativo {workspace} não pôde ser usado. "
                    + guia["mensagem"]
                )
            else:
                resumo = resumir(workspace)
                linha = "\n".join([linha, *linhas_humanas(resumo)])
        except Exception:
            linha += (
                "\nO estado do workspace não pôde ser preparado nesta abertura. "
                "A sessão pode continuar."
            )
        print(json.dumps(envelope_do_hook(linha), ensure_ascii=False))
    else:
        print(linha)
    return 0
