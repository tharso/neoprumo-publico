from pathlib import Path


RAIZ = Path(__file__).parents[2]


def test_skill_assunto_conduz_batismo_estado_e_migracao_assistida():
    texto = (RAIZ / "skills" / "assunto" / "SKILL.md").read_text().lower()
    for trecho in (
        "esperar o dono confirmar o batismo",
        "não trouxer `id_sugerido`",
        "o núcleo valida",
        "pedir um “sim” explícito",
        "uma seção por vez",
        "origem antiga em `--origem`",
        "origem legada",
        "fonte permanece intacto",
    ):
        assert trecho in texto


def test_skill_despacho_conduz_associacao_nascimento_e_reparo():
    texto = (RAIZ / "skills" / "despacho" / "SKILL.md").read_text().lower()
    for trecho in (
        "acervo --assunto",
        "tipo_sugerido",
        "sem `id_sugerido`",
        "escolher o destino não confirma",
        "nota_perdida",
        "assunto nota --data",
        "recusa isolada de domínio",
    ):
        assert trecho in texto
