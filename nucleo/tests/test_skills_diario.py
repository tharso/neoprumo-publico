import hashlib
from pathlib import Path


RAIZ = Path(__file__).parents[2]


def ler(relativo):
    return (RAIZ / relativo).read_text(encoding="utf-8")


def test_rota_da_sessao_permanece_byte_a_byte_intacta():
    dados = (RAIZ / "skills/sessao/SKILL.md").read_bytes()
    assert hashlib.sha256(dados).hexdigest() == (
        "062d5c8c2aa8762533c799cb4d1bbb5c1774621ad181db7f37eeeb8e7201a3ff"
    )


def test_extensao_so_oferece_diario_quando_ha_fato():
    texto = ler("skills/sessao/extensoes/fechar-o-dia.md")
    assert "total == 0" in texto and "sem perguntar" in texto
    assert "total > 0" in texto and "oferecer" in texto
    assert "uma vez por sessão" in texto


def test_skill_repete_a_regra_do_dia_sem_fatos():
    # A regra mora na extensão, mas "acabei por hoje" casa a descrição desta
    # skill e dispara sem passar pela rota da sessão: sozinha na extensão, ela
    # nunca chega a ser aplicada (#57, célula (b) do smoke).
    texto = ler("skills/diario/SKILL.md")
    assert "total == 0" in texto
    posicao = texto.index("total == 0")
    assert posicao < texto.index("Mostrar a proposta COMPLETA")
    regra = texto[posicao : texto.index("\n", posicao)]
    assert "não propor texto" in regra
    assert "não perguntar" in regra
    assert "sem passar pela rota da sessão" in regra


def test_skill_confirma_texto_inteiro_antes_de_gravar():
    texto = ler("skills/diario/SKILL.md")
    assert texto.index("Mostrar a proposta COMPLETA") < texto.index("Após o “sim”")
    assert "diario gravar - --dia <dia>" in texto
    assert "compactação" in texto


def test_skill_conduz_segundo_fecho_e_quatro_estados_de_recuperacao():
    texto = ler("skills/diario/SKILL.md")
    assert "diario.existe" in texto and "melhor esforço" in texto
    for estado in ("dia_virou", "gravacao_em_andamento", "parcial", "indeterminado"):
        assert estado in texto
    assert "não repetir antes" in texto
