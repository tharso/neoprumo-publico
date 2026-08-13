from . import cli_assunto, cli_diario


NOMES = {"assunto", "diario"}


def adicionar_parsers(comandos):
    cli_assunto.adicionar_parser(comandos)
    cli_diario.adicionar_parser(comandos)


def executar(opcoes):
    modulo = cli_assunto if opcoes.comando == "assunto" else cli_diario
    return modulo.executar(opcoes)
