import sys

from .assunto_comandos import (
    executar_estado, executar_listar, executar_mostrar, executar_nota,
    executar_registrar,
)


def adicionar_parser(comandos):
    assunto = comandos.add_parser("assunto", help="cuida da prateleira de assuntos")
    acoes = assunto.add_subparsers(dest="acao_assunto", required=True)
    registrar = acoes.add_parser("registrar")
    registrar.add_argument("nome")
    registrar.add_argument("--id", dest="identificador")
    registrar.add_argument("--tipo")
    registrar.add_argument("--caminho", dest="caminho_principal")
    registrar.add_argument("--caminho-relacionado", action="append", dest="relacionados")
    registrar.add_argument("--apelido", action="append", dest="apelidos")
    nota = acoes.add_parser("nota")
    nota.add_argument("referencia")
    nota.add_argument("texto")
    nota.add_argument("--data")
    nota.add_argument("--origem")
    mostrar = acoes.add_parser("mostrar")
    mostrar.add_argument("referencia")
    listar = acoes.add_parser("listar")
    listar.add_argument("--todos", action="store_true")
    estados = []
    for nome in ("arquivar", "reativar"):
        estado = acoes.add_parser(nome)
        estado.add_argument("referencia")
        estados.append(estado)
    for comando in (registrar, nota, mostrar, listar, *estados):
        comando.add_argument("--workspace", dest="caminho")
        comando.add_argument("--json", action="store_true", dest="usar_json")


def executar(opcoes):
    if opcoes.acao_assunto == "registrar":
        return executar_registrar(
            opcoes.nome, caminho=opcoes.caminho,
            identificador=opcoes.identificador, tipo=opcoes.tipo,
            caminho_principal=opcoes.caminho_principal,
            relacionados=opcoes.relacionados, apelidos=opcoes.apelidos,
            usar_json=opcoes.usar_json,
        )
    if opcoes.acao_assunto == "nota":
        texto = sys.stdin.read() if opcoes.texto == "-" else opcoes.texto
        return executar_nota(
            opcoes.referencia, texto, opcoes.caminho, opcoes.usar_json,
            opcoes.data, opcoes.origem,
        )
    if opcoes.acao_assunto == "mostrar":
        return executar_mostrar(opcoes.referencia, opcoes.caminho, opcoes.usar_json)
    if opcoes.acao_assunto == "listar":
        return executar_listar(opcoes.caminho, opcoes.usar_json, opcoes.todos)
    pedido = "arquivado" if opcoes.acao_assunto == "arquivar" else "ativo"
    return executar_estado(opcoes.referencia, pedido, opcoes.caminho, opcoes.usar_json)
