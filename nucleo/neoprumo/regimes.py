import re
import unicodedata
from datetime import date


PREFIXO_ABERTO = "- [ ] "
PREFIXOS_CONCLUIDOS = ("- [x] ", "- [X] ")
PADRAO_DATA = r"\d{4}-\d{2}-\d{2}"
ORIGEM = re.compile(r"^\s+— (inbox|acervo) ([^,]+),")


def normalizar(texto):
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(
        caractere
        for caractere in decomposto
        if unicodedata.category(caractere) != "Mn"
    ).casefold()


def data_valida(texto):
    if not re.fullmatch(PADRAO_DATA, texto):
        return False
    try:
        date.fromisoformat(texto)
    except ValueError:
        return False
    return True


def _forma(peca):
    texto = normalizar(peca)
    if texto == "a vista":
        return "regime", "a_vista", None
    if texto == "em espera":
        return "regime", "em_espera", None
    dormindo = re.fullmatch(rf"dormindo ate ({PADRAO_DATA})", texto)
    if dormindo:
        return "regime", "dormindo", dormindo.group(1)
    prazo = re.fullmatch(rf"vence ({PADRAO_DATA})", texto)
    if prazo:
        return "vence", prazo.group(1), None
    return None


def _prefixo(linha, concluida):
    candidatos = PREFIXOS_CONCLUIDOS if concluida else (PREFIXO_ABERTO,)
    return next((prefixo for prefixo in candidatos if linha.startswith(prefixo)), None)


def analisar_linha(linha, concluida=False):
    prefixo = _prefixo(linha, concluida)
    if prefixo is None:
        return {
            "manchete": linha[len("- [ ]") :].lstrip().rstrip(),
            "regime": None,
            "vence": None,
            "problemas": [],
            "marcador": False,
        }
    corpo = linha[len(prefixo) :].rstrip()
    if not corpo.endswith("]") or "[" not in corpo:
        return _resultado(corpo, None, None, [], False)
    inicio = corpo.rfind("[")
    pecas = [peca.strip() for peca in corpo[inicio + 1 : -1].split(",")]
    formas = [_forma(peca) for peca in pecas]
    if not pecas or any(forma is None for forma in formas):
        return _resultado(corpo, None, None, [], False)

    manchete = corpo[:inicio].rstrip()
    regimes = [forma for forma in formas if forma[0] == "regime"]
    prazos = [forma for forma in formas if forma[0] == "vence"]
    problemas = []
    regime = None
    vence = None
    datas_de_sono_invalidas = [
        forma[2] for forma in regimes
        if forma[2] is not None and not data_valida(forma[2])
    ]
    for data_invalida in datas_de_sono_invalidas:
        problemas.append(
            f"{manchete}: a data de acordar {data_invalida} não existe."
        )
    if len(regimes) > 1:
        problemas.append(f"{manchete}: o marcador tem mais de um regime.")
        if any(forma[1] == "dormindo" for forma in regimes):
            problemas.append(
                f"{manchete}: dormindo até não combina com outro regime."
            )
    elif regimes:
        _, nome, ate = regimes[0]
        if not datas_de_sono_invalidas:
            regime = {"nome": nome, "ate": ate}
    datas_de_prazo_invalidas = [
        forma[1] for forma in prazos if not data_valida(forma[1])
    ]
    for data_invalida in datas_de_prazo_invalidas:
        problemas.append(
            f"{manchete}: a data de prazo {data_invalida} não existe."
        )
    if len(prazos) > 1:
        problemas.append(f"{manchete}: o marcador tem mais de um prazo.")
    elif prazos:
        vence_candidato = prazos[0][1]
        if not datas_de_prazo_invalidas:
            vence = vence_candidato
    return _resultado(manchete, regime, vence, problemas, True)


def _resultado(manchete, regime, vence, problemas, marcador):
    return {
        "manchete": manchete,
        "regime": regime,
        "vence": vence,
        "problemas": problemas,
        "marcador": marcador,
    }


def formatar_marcador(regime, vence):
    pecas = []
    if regime:
        nomes = {
            "a_vista": "à vista",
            "dormindo": f"dormindo até {regime['ate']}",
            "em_espera": "em espera",
        }
        pecas.append(nomes[regime["nome"]])
    if vence:
        pecas.append(f"vence {vence}")
    return f" [{', '.join(pecas)}]" if pecas else ""


def origem_da_linha(linha):
    correspondencia = ORIGEM.match(linha)
    if correspondencia is None:
        return None
    return f"{correspondencia.group(1)} {correspondencia.group(2)}"
