import hashlib
from pathlib import Path


RAIZ = Path(__file__).parents[2]


def test_rota_da_sessao_permanece_byte_a_byte_inalterada():
    conteudo = (RAIZ / "skills" / "sessao" / "SKILL.md").read_bytes()
    assert hashlib.sha256(conteudo).hexdigest() == (
        "f39f3df0344397aca855cd26e4d66f3b9e137d2a8ef7c95a93aa0ea2b8d895f6"
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
