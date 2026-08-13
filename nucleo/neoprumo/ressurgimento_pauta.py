import re
from datetime import date

from .pauta_entradas import entradas, ler_pauta
from .regimes import data_valida, origem_da_linha


LIMIAR_DIAS = 7
DATA_FINAL = re.compile(r"(\d{4}-\d{2}-\d{2})$")
AVISO_SEM_TEXTO = (
    "{total} {entradas} em espera sem texto pra apresentar; revise-{pronome} na Pauta."
)


def _data_de_origem(corpo):
    for linha in reversed(corpo):
        texto = linha.rstrip("\r\n")
        if origem_da_linha(texto) is None:
            continue
        encontrada = DATA_FINAL.search(texto)
        if encontrada and data_valida(encontrada.group(1)):
            return date.fromisoformat(encontrada.group(1))
        return None
    return None


def _conteudo(entrada):
    restantes = [
        linha for linha in entrada["corpo"]
        if origem_da_linha(linha.rstrip("\r\n")) is None
    ]
    if not restantes:
        return entrada["manchete"]
    return entrada["manchete"] + "\n" + "".join(restantes)


def enumerar_em_espera(workspace, referencia):
    _, leitura, erro = ler_pauta(workspace, mensagens_seed=True)
    if erro:
        return [], [erro]
    _, texto = leitura
    _, todas = entradas(texto)
    candidatas = []
    sem_texto = 0
    hoje = referencia.date()
    for entrada in todas:
        regime = entrada["regime"]
        if not regime or regime["nome"] != "em_espera":
            continue
        if entrada["vence"] and date.fromisoformat(entrada["vence"]) < hoje:
            continue
        if not entrada["manchete"]:
            sem_texto += 1
            continue
        origem = _data_de_origem(entrada["corpo"])
        idade = None if origem is None else max(0, (hoje - origem).days)
        if idade is not None and idade < LIMIAR_DIAS:
            continue
        candidatas.append({
            "origem": "em_espera",
            "nome": None,
            "manchete": entrada["manchete"],
            "idade": idade,
            "conteudo": _conteudo(entrada),
            "origem_entrada": entrada["origem"],
        })
    problemas = []
    if sem_texto:
        problemas.append(AVISO_SEM_TEXTO.format(
            total=sem_texto,
            entradas="entrada" if sem_texto == 1 else "entradas",
            pronome="a" if sem_texto == 1 else "as",
        ))
    return candidatas, problemas
