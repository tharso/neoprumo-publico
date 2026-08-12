from pathlib import Path


RAIZ = Path(__file__).parents[2]


def test_extensao_do_momento_existe_e_declara_condicoes_independentes():
    rota = (RAIZ / "skills/sessao/SKILL.md").read_text(encoding="utf-8")
    relativo = "extensoes/primeira-sessao-do-dia.md"
    extensao = RAIZ / "skills/sessao" / relativo

    assert relativo in rota
    assert extensao.is_file()
    texto = extensao.read_text(encoding="utf-8")
    assert "## Regimes na abertura" in texto
    assert "## Composição" in texto
    assert "pauta.regimes.a_vista > 0" in texto
    assert "pauta.regimes.a_vista > 5" in texto
    assert "pauta.acordaram_hoje > 0" in texto
    assert "pauta.prazos.vencidos > 0" in texto
    assert "mesmo quando `pauta.regimes.a_vista == 0`" in texto
    assert "não repetir o pódio" in texto


def test_skills_de_despacho_e_pauta_exigem_confirmacao_de_datas():
    despacho = (RAIZ / "skills/despacho/SKILL.md").read_text(encoding="utf-8")
    pauta = (RAIZ / "skills/pauta/SKILL.md").read_text(encoding="utf-8")

    for texto in (despacho, pauta):
        assert "AAAA-MM-DD" in texto
        assert "--confirmado" in texto
        assert "confirma" in texto.casefold()
    assert "bin/neoprumo regime" in pauta
