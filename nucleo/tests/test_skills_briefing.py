import hashlib
from pathlib import Path


RAIZ = Path(__file__).parents[2]
EXTENSAO = RAIZ / "skills/sessao/extensoes/primeira-sessao-do-dia.md"
SKILL = RAIZ / "skills/briefing/SKILL.md"


def test_rota_e_skill_da_sessao_seguem_byte_a_byte():
    esperados = {
        # A spec da issue 52 amplia somente a condição do ressurgimento.
        "skills/sessao/SKILL.md": (
            "029ac34f443aebed262b4e332505736dce0e78205ac3ba342cd1fb27abb15260"
        ),
    }
    for relativo, esperado in esperados.items():
        assert hashlib.sha256((RAIZ / relativo).read_bytes()).hexdigest() == esperado


def test_extensao_executa_briefing_e_declara_os_dois_modos():
    texto = EXTENSAO.read_text(encoding="utf-8")

    for trecho in (
        "## Briefing",
        "neoprumo retrato --json",
        "`primeiro_do_dia` verdadeiro",
        "Modo automático",
        "Modo explícito",
        "seed fresco",
        "total + idades",
        "não reexecuta",
    ):
        assert trecho in texto


def test_extensao_ordena_corpo_e_absorve_regimes_sem_perder_cobrancas():
    texto = EXTENSAO.read_text(encoding="utf-8")
    posicoes = [
        texto.index("### À vista"),
        texto.index("### Pauta"),
        texto.index("### Agenda de hoje"),
        texto.index("### Email"),
    ]

    assert posicoes == sorted(posicoes)
    for trecho in (
        'Se a seção "Briefing" apresentou o panorama NESTA abertura',
        "não repetir o pódio",
        "o anúncio de acordou",
        "nem re-apresentar os prazos",
        "cobrança acionável dos vencidos",
        "A condição 2",
        "Sem briefing nesta abertura, as quatro condições valem integrais",
    ):
        assert trecho in texto


def test_extensao_fecha_protocolo_de_email_e_degradacao():
    texto = EXTENSAO.read_text(encoding="utf-8")

    for trecho in (
        '"dominio": "email"',
        '"alvos"',
        '"id"',
        '"remetente"',
        '"assunto"',
        "configuracao avaliar",
        "efetiva",
        "conflito",
        "suspensas_que_casariam",
        "semanticas_ativas",
        "suspensas_semanticas",
        "sem_regras",
        "agenda: sem conexão neste host",
        "email: sem conexão neste host",
        "aviso agregado",
        "timeout",
        "julgamento padrão",
    ):
        assert trecho in texto


def test_skill_explicita_usa_estado_fresco_e_repetido_nao_bloqueia():
    texto = SKILL.read_text(encoding="utf-8")

    assert "briefing" in texto.casefold()
    assert "panorama do dia" in texto.casefold()
    assert "neoprumo seed --json" in texto
    assert "neoprumo retrato --json" in texto
    assert "seed fresco" in texto.casefold()
    assert "modo explícito" in texto.casefold()
    assert "total e idades" in texto.casefold()
    assert "`repetido` nunca bloqueia" in texto
    assert "primeira-sessao-do-dia.md" in texto
