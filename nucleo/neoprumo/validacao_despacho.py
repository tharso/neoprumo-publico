import unicodedata

from .regimes import data_valida
from .superficie_base import codificavel_utf8


CIENCIA_CONTRADICAO = "O dono confirmou que o prazo cobra antes de o item acordar."
MENSAGEM_CONTRADICAO = (
    "Este item vence em {vence}, antes de acordar em {ate} — ele vai cobrar na "
    "abertura mesmo dormindo. Confirme com o dono e repita com --confirmado."
)


def nome_projeto_valido(nome):
    return (
        codificavel_utf8(nome)
        and bool(nome.strip())
        and len(nome.splitlines()) == 1
        and not any(
            unicodedata.category(caractere) in ("Cc", "Cs", "Zl", "Zp")
            for caractere in nome
        )
    )


def validar_regime_despacho(
    destino, regime, ate, vence, confirmado, aceita_confirmacao=False
):
    usou_campos = any((regime, ate, vence, confirmado))
    contraditorio = regime == "dormindo" and ate and vence and vence < ate
    if destino != "pauta" and usou_campos:
        if confirmado and aceita_confirmacao and not any((regime, ate, vence)):
            return None, None, None, []
        mensagem = (
            "Não há o que confirmar."
            if confirmado and not contraditorio
            else "Regime e prazo só podem ser usados no destino pauta."
        )
        return mensagem, None, None, []
    if ate and regime != "dormindo":
        return "--ate só pode ser usado com o regime dormindo.", None, None, []
    if regime == "dormindo" and not ate:
        return "Dormir exige a data de acordar: use --ate.", None, None, []
    if ate and not data_valida(ate):
        return "A data de acordar precisa existir e usar AAAA-MM-DD.", None, None, []
    if vence and not data_valida(vence):
        return "A data de prazo precisa existir e usar AAAA-MM-DD.", None, None, []
    nomes = {"a-vista": "a_vista", "em-espera": "em_espera"}
    objeto = None
    if regime == "dormindo":
        objeto = {"nome": "dormindo", "ate": ate}
    elif regime:
        objeto = {"nome": nomes[regime], "ate": None}
    if contraditorio and not confirmado:
        return MENSAGEM_CONTRADICAO.format(vence=vence, ate=ate), None, None, []
    if confirmado and not contraditorio and not aceita_confirmacao:
        return "Não há o que confirmar.", None, None, []
    acoes = [CIENCIA_CONTRADICAO] if contraditorio else []
    return None, objeto, vence, acoes
