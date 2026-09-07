"""Apresentação dos resultados de criação, readoção e diagnóstico do workspace."""

import json
import sys


def _listar(itens, destino):
    for item in itens:
        print(f"- {item}", file=destino)


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    destino = sys.stderr if erro else sys.stdout
    status = resultado["status"]
    acoes = resultado["acoes"]
    problemas = resultado["problemas"]
    parcial = status == "com_problemas" and bool(acoes) and bool(problemas)
    mensagem = resultado["mensagem"]
    if parcial and mensagem == "O workspace tem problemas:":
        mensagem = "O reparo foi parcial."
    print(mensagem, file=destino)
    if parcial:
        print("Feito:", file=destino)
        _listar(acoes, destino)
        print("Continua pendente:", file=destino)
        _listar(problemas, destino)
        return
    if status in {"reparado", "readotado", "ja_existe"}:
        itens = acoes
    elif status == "com_problemas":
        itens = acoes + problemas
    elif status == "recusado":
        itens = problemas + acoes
    else:
        itens = problemas
    _listar(itens, destino)
