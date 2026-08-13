import hashlib
from pathlib import Path


RAIZ = Path(__file__).parents[2]


def test_rota_da_sessao_permanece_byte_a_byte_inalterada():
    conteudo = (RAIZ / "skills" / "sessao" / "SKILL.md").read_bytes()
    # A spec da issue 52 amplia somente a condição do ressurgimento.
    assert hashlib.sha256(conteudo).hexdigest() == (
        "062d5c8c2aa8762533c799cb4d1bbb5c1774621ad181db7f37eeeb8e7201a3ff"
    )


def test_extensao_pilha_grande_oferece_superficie_a_partir_de_cinco_itens():
    caminho = RAIZ / "skills" / "sessao" / "extensoes" / "pilha-grande.md"
    texto = caminho.read_text(encoding="utf-8")
    assert "inbox.total" in texto
    assert ">= 5" in texto or "≥ 5" in texto
    assert "superfície" in texto.lower()
    assert "quero gerar a página de despacho?" in texto.lower()
    assert "bin/neoprumo superficie despacho" in texto
    assert "${CLAUDE_PLUGIN_ROOT}" in texto
    assert "conversa" in texto.lower()


def test_skill_despacho_distingue_todas_as_causas_do_aplicar():
    texto = (RAIZ / "skills" / "despacho" / "SKILL.md").read_text(encoding="utf-8").lower()
    for trecho in (
        "envelhecida",
        "digital",
        "não está mais na inbox",
        "já há registro",
        "misto",
        "estrutural",
        "conferência",
        "domínio",
    ):
        assert trecho in texto
