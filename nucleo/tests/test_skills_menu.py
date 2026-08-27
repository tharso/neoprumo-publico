from pathlib import Path


RAIZ = Path(__file__).parents[2]
MENU = RAIZ / "skills/menu/SKILL.md"
SESSAO = RAIZ / "skills/sessao/SKILL.md"


def test_menu_apresenta_os_oito_gestos():
    texto = MENU.read_text(encoding="utf-8")

    for gesto in (
        "briefing",
        "fim",
        "captura",
        "despacho",
        "pauta",
        "acervo",
        "assunto",
        "sessao",
    ):
        assert f"`{gesto}`" in texto


def test_menu_traz_exemplos_reais_e_abre_conversa():
    texto = MENU.read_text(encoding="utf-8")

    for exemplo in (
        "Me dá o panorama do dia.",
        "Acabei por hoje.",
        "Anota isso pra mim.",
    ):
        assert exemplo in texto

    assert "Quer saber mais sobre algum desses gestos?" in texto
    assert "ficou alguma dúvida" in texto
    assert "bin/neoprumo" not in texto


def test_sessao_delega_ajuda_ao_menu():
    texto = SESSAO.read_text(encoding="utf-8")

    assert "Sob pedido de ajuda, siga a skill `menu`." in texto
