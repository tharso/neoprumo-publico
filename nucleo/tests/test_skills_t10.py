import hashlib
from pathlib import Path


RAIZ = Path(__file__).parents[2]


def test_arquivos_intocaveis_permanecem_byte_a_byte_inalterados():
    esperados = {
        # Lacre de escopo, não proibição: abre só por revisão consciente, com o
        # hash recongelado no merge e a razão no log de decisões do projeto.
        # Última abertura: 24/08, o lembrete diário de manutenção (#18).
        "skills/sessao/SKILL.md": "029ac34f443aebed262b4e332505736dce0e78205ac3ba342cd1fb27abb15260",
        "skills/sessao/extensoes/pilha-grande.md": "47bc5cacdd597f01f6af82f726fb376e70680fcc3aa7e7a9734950c06a541529",
        "skills/acervo/SKILL.md": "b96f37af9c0656e3a0fde832bdbb97fee4ce0946e041010f009cc974e0e0b996",
        # Última abertura: 28/08, tarefas de reunião a pedido (#77).
        "skills/captura/SKILL.md": "0e63d806a1831e7feb8d09971bdd7251c462d06f664db4d07005a3d1d75374d5",
        "hooks/hooks.json": "d3a40b1747afd393f38f6db4714702cd16d0e9301beffdbd8adf69e4639a3ed3",
    }
    for relativo, esperado in esperados.items():
        assert hashlib.sha256((RAIZ / relativo).read_bytes()).hexdigest() == esperado


def test_extensao_define_momento_condicao_apresentacao_e_contencao():
    texto = extensao().lower()
    for trecho in (
        "apresentar o estado da abertura conta como cobrança feita",
        "inbox vazia",
        "nível leve",
        "fora da abertura",
        "mensagem própria",
        "uma vez por sessão",
        "mesmo dia",
        "intenção explícita",
    ):
        assert trecho in texto


def test_extensao_nao_deixa_falhas_mudas_e_so_silencia_saida_limpa():
    texto = extensao().lower()
    for trecho in (
        "mensagem",
        "problemas",
        "acoes",
        "aviso de saúde",
        "qualquer saída",
        "sem_candidato",
    ):
        assert trecho in texto
    assert "`problemas` vazio" in texto or "problemas está vazio" in texto


def test_extensao_descreve_sem_prescrever_e_oferece_mao_de_obra():
    texto = extensao().lower()
    assert "sugestão descritiva" in texto
    assert "nunca prescritiva" in texto
    assert "oferecer" in texto and "trabalho" in texto
    assert "recomendar o veredito" in texto
    assert "prioridade" in texto


def test_extensao_usa_unitario_com_vazio_aceito_e_execucao_condicionada():
    texto = extensao().lower()
    for trecho in (
        "bin/neoprumo ressurgimento",
        "${claude_plugin_root}/bin/neoprumo ressurgimento",
        "bin/neoprumo acervo <item> pauta",
        "bin/neoprumo acervo <item> lixo",
        "confirmação explícita",
        "atacar agora",
        "status `incluido`",
        "deixa",
        "vislumbre e o gesto",
        "mudou ou sumiu",
    ):
        assert trecho in texto


def test_extensao_oferece_garimpo_no_limiar_sem_gerar_sozinha():
    texto = extensao().lower()
    assert "elegiveis_acervo >= 5" in texto or "elegiveis_acervo ≥ 5" in texto
    assert "bin/neoprumo superficie acervo" in texto
    assert "mesma mensagem" in texto
    assert "só com o sim" in texto


def extensao():
    return (
        RAIZ / "skills" / "sessao" / "extensoes" / "ressurgimento.md"
    ).read_text(encoding="utf-8")
