import argparse
import sys

from .ativo import definir, e_workspace, informar_indisponivel, mostrar, resolver
from .acervo import decidir_acervo
from .captura import capturar
from .despacho import despachar
from .ressurgimento import executar_ressurgimento
from .readocao import readotar
from .seed import executar_seed
from .sonda import sondar
from .superficie_aplicar import aplicar_superficie
from .superficie_acervo_builder import gerar_superficie_acervo
from .superficie_builder import gerar_superficie
from .workspace import configurar, diagnosticar


def criar_parser():
    parser = argparse.ArgumentParser(prog="neoprumo")
    comandos = parser.add_subparsers(dest="comando", required=True)
    setup = comandos.add_parser("setup", help="cria um workspace do NeoPrumo")
    setup.add_argument("caminho")
    setup.add_argument("--readotar", action="store_true")
    setup.add_argument("--forcar", action="store_true")
    setup.add_argument("--json", action="store_true", dest="usar_json")
    doctor = comandos.add_parser("doctor", help="verifica um workspace")
    doctor.add_argument("caminho", nargs="?")
    doctor.add_argument("--reparar", action="store_true")
    doctor.add_argument("--json", action="store_true", dest="usar_json")
    sonda = comandos.add_parser("sonda", help="confirma que o NeoPrumo está ativo")
    sonda.add_argument("--hook", action="store_true", dest="usar_hook")
    captura = comandos.add_parser("captura", help="guarda um texto na inbox")
    captura.add_argument("texto")
    captura.add_argument("--workspace", dest="caminho")
    captura.add_argument("--json", action="store_true", dest="usar_json")
    despacho = comandos.add_parser(
        "despacho",
        help="decide o destino de um item da inbox",
    )
    despacho.add_argument("item")
    despacho.add_argument("destino")
    despacho.add_argument("nome_do_projeto", nargs="?")
    despacho.add_argument("--workspace", dest="caminho")
    despacho.add_argument("--json", action="store_true", dest="usar_json")
    acervo = comandos.add_parser(
        "acervo", help="decide o destino de um item do acervo"
    )
    acervo.add_argument("item")
    acervo.add_argument("decisao")
    acervo.add_argument("--workspace", dest="caminho")
    acervo.add_argument("--json", action="store_true", dest="usar_json")
    seed = comandos.add_parser("seed", help="resume o estado do workspace")
    seed.add_argument("--workspace", dest="caminho")
    seed.add_argument("--json", action="store_true", dest="usar_json")
    ressurgimento = comandos.add_parser(
        "ressurgimento", help="reapresenta um item envelhecido do acervo"
    )
    ressurgimento.add_argument("--workspace", dest="caminho")
    ressurgimento.add_argument("--json", action="store_true", dest="usar_json")
    superficie = comandos.add_parser(
        "superficie", help="gera ou aplica uma superfície de trabalho"
    )
    acoes_superficie = superficie.add_subparsers(
        dest="acao_superficie", required=True
    )
    for acao, ajuda in (
        ("despacho", "gera a página de despacho"),
        ("acervo", "gera o navegador do acervo"),
        ("aplicar", "aplica o bloco de respostas"),
    ):
        comando_superficie = acoes_superficie.add_parser(acao, help=ajuda)
        comando_superficie.add_argument("--workspace", dest="caminho")
        comando_superficie.add_argument(
            "--json", action="store_true", dest="usar_json"
        )
    workspace = comandos.add_parser("workspace", help="mostra ou define o workspace ativo")
    workspace.add_argument("--json", action="store_true", dest="usar_json")
    acoes_workspace = workspace.add_subparsers(dest="acao_workspace")
    usar = acoes_workspace.add_parser("usar", help="define o workspace ativo")
    usar.add_argument("caminho")
    usar.add_argument(
        "--json",
        action="store_true",
        dest="usar_json",
        default=argparse.SUPPRESS,
    )
    return parser


def executar(argumentos=None):
    parser = criar_parser()
    opcoes = parser.parse_args(argumentos)
    if opcoes.comando == "setup":
        if opcoes.forcar and not opcoes.readotar:
            parser.error("--forcar só pode ser usado junto com --readotar")
        if opcoes.readotar:
            return readotar(
                opcoes.caminho,
                forcar=opcoes.forcar,
                usar_json=opcoes.usar_json,
            )
        return configurar(opcoes.caminho, usar_json=opcoes.usar_json)
    if opcoes.comando == "doctor":
        caminho = opcoes.caminho if opcoes.caminho is not None else resolver()
        if caminho is None:
            return informar_indisponivel(usar_json=opcoes.usar_json)
        if opcoes.caminho is None and not e_workspace(caminho):
            return informar_indisponivel(caminho, usar_json=opcoes.usar_json)
        return diagnosticar(
            caminho,
            reparar=opcoes.reparar,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "sonda":
        return sondar(usar_hook=opcoes.usar_hook)
    if opcoes.comando == "captura":
        texto = sys.stdin.read() if opcoes.texto == "-" else opcoes.texto
        return capturar(
            texto,
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "despacho":
        return despachar(
            opcoes.item,
            opcoes.destino,
            nome_do_projeto=opcoes.nome_do_projeto,
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "acervo":
        return decidir_acervo(
            opcoes.item,
            opcoes.decisao,
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "seed":
        return executar_seed(
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "ressurgimento":
        return executar_ressurgimento(
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "superficie" and opcoes.acao_superficie == "despacho":
        return gerar_superficie(
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "superficie" and opcoes.acao_superficie == "acervo":
        return gerar_superficie_acervo(
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "superficie" and opcoes.acao_superficie == "aplicar":
        return aplicar_superficie(
            caminho=opcoes.caminho,
            usar_json=opcoes.usar_json,
        )
    if opcoes.comando == "workspace" and opcoes.acao_workspace == "usar":
        return definir(opcoes.caminho, usar_json=opcoes.usar_json)
    if opcoes.comando == "workspace":
        return mostrar(usar_json=opcoes.usar_json)
    return 2
