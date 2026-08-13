from .assunto_base import conferir_prateleira, entradas_de_ficha
from .assunto_ficha import ler_ficha


def fotografar_marcadores(workspace):
    pasta, falha = conferir_prateleira(workspace)
    if falha:
        return [], [falha]
    caminhos, _, problemas = entradas_de_ficha(pasta)
    origens = {}
    for caminho in caminhos:
        ficha, falha = ler_ficha(caminho)
        if falha:
            problemas.append(f"{caminho.name}: ilegível na conferência de marcadores.")
            continue
        for nota in ficha["notas"]:
            origem = nota["origem"]
            if origem and origem.startswith("inbox "):
                origens.setdefault(origem[6:], []).append(f"Assuntos/{caminho.name}")
    return origens, problemas


def conferir_marcador(workspace, nome_completo):
    origens, problemas = fotografar_marcadores(workspace)
    return origens.get(nome_completo, []), problemas
