import sys
from pathlib import Path

from .ativo import e_workspace, informar_indisponivel, resolver
from .diario_colheita import executar_colher, indisponivel_extras
from .diario_gravacao import executar_gravar


def adicionar_parser(comandos):
    diario = comandos.add_parser("diario", help="colhe e grava o diário do dia")
    acoes = diario.add_subparsers(dest="acao_diario", required=True)
    colher = acoes.add_parser("colher", help="colhe os fatos do dia")
    colher.add_argument("--workspace", dest="caminho")
    colher.add_argument("--json", action="store_true", dest="usar_json")
    gravar = acoes.add_parser("gravar", help="grava uma seção confirmada")
    gravar.add_argument("texto")
    gravar.add_argument("--dia", required=True)
    gravar.add_argument("--workspace", dest="caminho")
    gravar.add_argument("--json", action="store_true", dest="usar_json")


def executar(opcoes):
    explicito = opcoes.caminho is not None
    workspace = Path(opcoes.caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None or not e_workspace(workspace):
        return informar_indisponivel(
            workspace, usar_json=opcoes.usar_json, extras=indisponivel_extras()
        )
    if opcoes.acao_diario == "colher":
        return executar_colher(Path(workspace), opcoes.usar_json)
    texto = sys.stdin.read() if opcoes.texto == "-" else opcoes.texto
    return executar_gravar(texto, opcoes.dia, Path(workspace), opcoes.usar_json)
