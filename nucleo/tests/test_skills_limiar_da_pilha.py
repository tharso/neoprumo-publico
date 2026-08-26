from pathlib import Path


RAIZ = Path(__file__).parents[2]

# O limiar que troca a conversa pela página mora nos DOIS lugares que casam o
# gesto de despachar: a extensão cobre quem chega pela rota da sessão, e a
# skill cobre quem pede o despacho direto. A auditoria de 13/08 mostrou que
# regra escrita só na extensão é contornada quando a skill pega o gatilho —
# com 12 itens na Inbox, a página nunca era oferecida.
LUGARES_DO_LIMIAR = (
    "skills/despacho/SKILL.md",
    "skills/sessao/extensoes/pilha-grande.md",
)


def ler(relativo):
    return (RAIZ / relativo).read_text(encoding="utf-8")


def test_o_limiar_da_pilha_mora_nos_dois_lugares():
    for relativo in LUGARES_DO_LIMIAR:
        assert "quero gerar a página de despacho?" in ler(relativo), relativo


def test_a_skill_despacho_aplica_o_limiar_antes_do_primeiro_item():
    texto = ler("skills/despacho/SKILL.md")
    assert "5 ou mais itens" in texto
    assert "antes do primeiro item" in texto


def test_a_oferta_da_skill_nao_sequestra_intencao_explicita():
    # Regra 6 da rota da sessão: nenhuma oferta bloqueia ou posterga a
    # intenção explícita. Pedido que já traz a forma não vê a pergunta.
    texto = ler("skills/despacho/SKILL.md")
    assert "atendido direto, sem a oferta" in texto


def test_a_escolha_nao_vira_preferencia():
    # O contrato tem quatro partes: a escolha dura o atendimento em curso
    # (os mesmos marcos do fecho da skill), a oferta não se repete no meio,
    # trocar é gesto exclusivo do dono, e o pedido seguinte reabre a oferta.
    texto = ler("skills/despacho/SKILL.md")
    assert "vale até a Inbox acabar ou o dono parar" in texto
    assert "sem repetir a oferta no meio" in texto
    assert "trocar de forma só se o dono pedir" in texto
    assert "No pedido de despacho seguinte, a oferta volta." in texto
