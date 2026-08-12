from datetime import date

from neoprumo.configuracao_avaliar import avaliar


def regra(identificador, predicado, politica="arquivar", condicao=None):
    return {"id": identificador, "dominio": "email", "execucao": "hibrida",
            "predicado": predicado, "politica": politica, "confirmacao": "por-alvo",
            "origem": "teste", "autorizada_em": "2026-08-01", "condicao": condicao}


def test_maximas_mistas_consolidam_ou_conflitam_e_casefolda():
    regras = [regra("domínio", "remetente-dominio: CAFÉ.com"),
              regra("direto", "remetente: LOJA@café.COM"),
              regra("assunto", "assunto-contem: PROMOÇÃO")]
    entrada = {"dominio": "email", "alvos": [{"id": "1", "remetente": "loja@CAFÉ.com", "assunto": "Grande promoção"}]}
    resposta, problemas = avaliar(entrada, regras)
    assert problemas == []
    alvo = resposta["alvos"][0]
    assert alvo["efetiva"]["regras"] == ["direto", "assunto"]
    regras[-1]["politica"] = "manter"
    resposta, _ = avaliar(entrada, regras)
    assert {r["id"] for r in resposta["alvos"][0]["conflito"]} == {"direto", "assunto"}


def test_suspensa_que_dominaria_e_semanticas_sao_entregues():
    suspensa = regra("direta", "remetente: a@x.com", condicao="revisao 2026-08-11")
    semantica = {**regra("semântica", "prosa"), "execucao": "semantica"}
    entrada = {"dominio": "email", "alvos": [{"id": "a", "remetente": "a@x.com", "assunto": ""}]}
    resposta, _ = avaliar(entrada, [regra("domínio", "remetente-dominio: x.com"), suspensa, semantica], hoje=date(2026, 8, 11))
    assert resposta["alvos"][0]["suspensas_que_casariam"][0]["dominaria"] is True
    assert resposta["semanticas_ativas"][0]["id"] == "semântica"


def test_entrada_estrita_nomeia_multiplos_defeitos_e_zero_alvos_e_valido():
    ruim = {"dominio": "outro", "extra": 1, "alvos": [{"id": "", "remetente": "Nome <a@b>", "assunto": None}]}
    _, problemas = avaliar(ruim, [])
    assert any("dominio" in p for p in problemas)
    assert any("extra" in p for p in problemas)
    assert any("remetente" in p for p in problemas)
    resposta, problemas = avaliar({"dominio": "email", "alvos": []}, [])
    assert problemas == [] and resposta["alvos"] == []
