from pathlib import Path


RAIZ = Path(__file__).parents[2]

# Todo lugar que conduz um gesto capaz de apagar item do dono. O smoke cruzado
# de 13/08 mediu a diferença: "exige confirmação explícita" sozinho falhou 2/2
# nos dois hosts, que trataram a escolha do verbo como a confirmação; com
# "escolher o verbo não é confirmação" o gate segurou 2/2. A frase é o gate.
GESTOS_QUE_APAGAM = (
    "skills/acervo/SKILL.md",
    "skills/pauta/SKILL.md",
    "skills/assunto/SKILL.md",
    "skills/sessao/extensoes/ressurgimento.md",
)


def ler(relativo):
    return (RAIZ / relativo).read_text(encoding="utf-8")


def test_todo_gesto_que_apaga_diz_que_escolher_o_verbo_nao_confirma():
    for relativo in GESTOS_QUE_APAGAM:
        assert "escolher o verbo não é confirmação" in ler(relativo), relativo


def test_acervo_repete_o_que_sai_antes_de_excluir():
    # O mesmo `acervo <item> lixo` chega por dois caminhos: pela extensão
    # `ressurgimento`, que traz o gate forte, e pelo garimpo conduzido por esta
    # skill. Sem a regra aqui, o segundo caminho apaga sem "sim" próprio.
    texto = ler("skills/acervo/SKILL.md")
    assert "repetir o que sairá do Acervo" in texto
    assert "o clique já confirmou" in texto
