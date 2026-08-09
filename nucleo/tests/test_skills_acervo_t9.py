import json
from pathlib import Path


RAIZ = Path(__file__).parents[2]


def test_skill_acervo_condiciona_atacar_e_delega_toda_escrita_ao_nucleo():
    conteudo = (RAIZ / "skills" / "acervo" / "SKILL.md").read_text(encoding="utf-8")
    assert 'decisao: "atacar"' in conteudo
    assert 'status: "incluido"' in conteudo
    assert "Nunca abrir trabalho" in conteudo
    assert "superficie acervo" in conteudo and "superficie aplicar" in conteudo
    assert "bloco colado INTACTO" in conteudo
    assert "nunca gerar sozinho" in conteudo


def test_skill_acervo_tem_entrada_no_orcamento_congelado():
    orcamento = json.loads(
        (RAIZ / "ferramentas" / "orcamento-skills.json").read_text(encoding="utf-8")
    )["skills"]
    assert "acervo" in orcamento
