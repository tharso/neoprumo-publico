import hashlib
import json
from datetime import date

import pytest

from neoprumo.configuracao_modelo import canonizar, digital_reautorizacao, ler_ini


REGRA = """[regra Z]
dominio = email
execucao = hibrida
predicado = remetente-dominio: café.com
politica = arquivar
origem = conversa
"""


@pytest.mark.parametrize("versao", ["0", "2", "abc"])
def test_schema_futuro_recusa_integral(versao):
    resultado = ler_ini(f"[configuracao]\nversao = {versao}\n")
    assert resultado["integral"] is False
    assert versao in resultado["recusa"]


def test_default_e_secao_duplicada_nao_autorizam_regra():
    defaults = ler_ini("[DEFAULT]\nconfirmacao = permanente\n" + REGRA)
    duplicada = ler_ini(REGRA + REGRA)
    assert defaults["integral"] is False
    assert "DEFAULT" in defaults["recusa"]
    assert duplicada["parseia"] is False


def test_canonico_tem_ordem_data_derivada_e_newline_unica():
    resultado = canonizar(REGRA, hoje=date(2026, 8, 11))
    assert resultado["canonico"].startswith("[configuracao]\nversao = 1\n\n[regra Z]")
    assert "autorizada_em = 2026-08-11\n" in resultado["canonico"]
    assert resultado["canonico"].endswith("\n")
    assert not resultado["canonico"].endswith("\n\n")


def test_digital_permanente_reproduz_serializacao_declarada():
    regra = ler_ini(REGRA)["validas"][0]
    esperado = hashlib.sha256(json.dumps(
        ["email", "hibrida", "remetente-dominio: café.com", "arquivar", "por-alvo", None],
        ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()
    assert digital_reautorizacao(regra) == esperado


def test_origem_e_nota_nao_mudam_data_da_base():
    primeiro = canonizar(REGRA, hoje=date(2026, 8, 10))
    alterado = REGRA.replace("conversa", "importação") + "nota = lembrete\n"
    segundo = canonizar(alterado, primeiro["mapa"], hoje=date(2026, 8, 11))
    assert segundo["mapa"][0]["autorizada_em"] == "2026-08-10"


@pytest.mark.parametrize("valor", ["Nome <a@b>", "@x.com", ".x.com", "x .com", "<x.com>"])
def test_predicados_invalidos_recusam_so_a_unidade(valor):
    texto = REGRA.replace("remetente-dominio: café.com", f"remetente-dominio: {valor}")
    leitura = ler_ini(texto + REGRA.replace("Z", "válida"))
    assert len(leitura["validas"]) == 1
    assert leitura["regras"][0]["estado"] == "recusada"
