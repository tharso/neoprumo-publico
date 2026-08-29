from pathlib import Path


RAIZ = Path(__file__).parents[2]

# Os freios da captura de tarefas de reunião moram nos DOIS lugares que
# casam o gesto: a extensão cobre a oferta espontânea do briefing, e a skill
# cobre o pedido direto. Se um deles perder a regra, uma das entradas pode
# gravar sem filtro, agrupar tarefas ou duplicar eventos da agenda.
LUGARES_DAS_TAREFAS_DE_REUNIAO = (
    "skills/captura/SKILL.md",
    "skills/sessao/extensoes/primeira-sessao-do-dia.md",
)


def ler(relativo):
    return (RAIZ / relativo).read_text(encoding="utf-8")


def test_os_freios_da_captura_moram_nos_dois_lugares():
    frases_guarda = (
        "Nunca gravar sem o sim do dono.",
        "Capturar um item por tarefa.",
        "— da reunião",
        "Evento de hora marcada não vira item: fica na agenda.",
    )

    for relativo in LUGARES_DAS_TAREFAS_DE_REUNIAO:
        texto = ler(relativo)
        for frase in frases_guarda:
            assert frase in texto, f"{relativo}: {frase}"


def test_a_oferta_do_briefing_usa_a_janela_do_retrato_e_degrada_so_a_parte():
    texto = ler("skills/sessao/extensoes/primeira-sessao-do-dia.md")
    assert "anterior" in texto
    assert "reuniões: sem conexão neste host" in texto
    assert "Se o dono recusar, não deixar rastro nem reoferecer nesta sessão." in texto
