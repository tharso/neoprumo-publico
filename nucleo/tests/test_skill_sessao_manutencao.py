from conftest import RAIZ_PROJETO


def test_skill_apresenta_lembrete_so_com_status_carimbado():
    texto = (RAIZ_PROJETO / "skills/sessao/SKILL.md").read_text(encoding="utf-8")

    assert 'status == "carimbado"' in texto
    for estado in ("repetido", "carimbo_falhou", "ausente", "inválido"):
        assert estado in texto
    assert "calam sem sinal" in texto


def test_skill_torna_apresentacao_eventual_obrigatoria_e_de_menor_prioridade():
    texto = (RAIZ_PROJETO / "skills/sessao/SKILL.md").read_text(encoding="utf-8")

    for trecho in (
        "obrigatório",
        "prioridade mais baixa",
        "fim da primeira resposta",
        "depois de atender",
        "nunca vira uma terceira frase",
        "toda abertura válida",
    ):
        assert trecho in texto
