from datetime import datetime, timedelta, timezone
import json
import pytest


INSTANTE = datetime(2026, 8, 11, 10, tzinfo=timezone(timedelta(hours=-3)))


def _workspace(tmp_path, executar_cli, nome="regimes"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def test_gramatica_reconhece_formas_normalizadas_e_preserva_colchete_invalido():
    from neoprumo.regimes import analisar_linha

    casos = {
        "- [ ] Alfa [A VISTA]": ("Alfa", "a_vista", None, None),
        "- [ ] Beta [vence 2026-08-20, EM ESPERA]": (
            "Beta", "em_espera", None, "2026-08-20"
        ),
        "- [ ] Gama [dormindo ate 2026-09-01]": (
            "Gama", "dormindo", "2026-09-01", None
        ),
        "- [ ] Delta [a vista]": ("Delta", "a_vista", None, None),
    }
    for linha, esperado in casos.items():
        leitura = analisar_linha(linha)
        regime = leitura["regime"]
        obtido = (
            leitura["manchete"],
            regime["nome"] if regime else None,
            regime["ate"] if regime else None,
            leitura["vence"],
        )
        assert obtido == esperado
        assert leitura["problemas"] == []

    for sufixo in ("[]", "[urgente]", "[à vista, urgente]"):
        leitura = analisar_linha(f"- [ ] Texto {sufixo}")
        assert leitura["manchete"] == f"Texto {sufixo}"
        assert leitura["regime"] is None
        assert leitura["problemas"] == []


def test_gramatica_descarta_dimensao_invalida_e_nomeia_a_manchete():
    from neoprumo.regimes import analisar_linha

    data = analisar_linha("- [ ] Data impossível [dormindo até 2026-02-30]")
    regimes = analisar_linha("- [ ] Dois regimes [à vista, em espera]")
    prazos = analisar_linha(
        "- [ ] Dois prazos [vence 2026-08-12, vence 2026-08-13]"
    )

    assert data["regime"] is None
    assert regimes["regime"] is None
    assert prazos["vence"] is None
    assert "Data impossível" in data["problemas"][0]
    assert "Dois regimes" in regimes["problemas"][0]
    assert "Dois prazos" in prazos["problemas"][0]

    combinadas = analisar_linha(
        "- [ ] Tudo errado [dormindo até 2026-02-30, em espera, "
        "vence 2026-02-31, vence 2026-08-12]"
    )
    assert combinadas["regime"] is None and combinadas["vence"] is None
    assert len(combinadas["problemas"]) == 5
    assert all("Tudo errado" in problema for problema in combinadas["problemas"])


def test_seed_calcula_regimes_prazos_e_mantem_contagem_lexical(
    tmp_path, executar_cli
):
    from neoprumo.seed import resumir

    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "Pauta.md").write_text(
        "# Pauta\n"
        "- [ ] Primeiro [à vista, vence 2026-08-13]\n"
        "- [ ] Segundo [A VISTA]\n"
        "- [ ] Dorme atrasado [dormindo até 2026-08-20, vence 2026-08-10]\n"
        "- [ ] Acorda hoje [dormindo até 2026-08-11]\n"
        "- [ ] Acordou antes [dormindo até 2026-08-10]\n"
        "- [ ] Espera [em espera, vence 2026-08-11]\n"
        "- [ ]normal sem espaço [à vista]\n"
        "```\n- [ ] bloco também conta\n```\n"
        "- [x] Feito [à vista]\n",
        encoding="utf-8",
    )

    pauta = resumir(workspace, instante=INSTANTE)["pauta"]

    assert pauta == {
        "abertos": 8,
        "concluidos": 1,
        "regimes": {"a_vista": 2, "dormindo": 1, "em_espera": 1, "normal": 4},
        "a_vista": [
            {"manchete": "Primeiro", "vence_em_dias": 2},
            {"manchete": "Segundo", "vence_em_dias": None},
        ],
        "acordaram_hoje": 1,
        "prazos": {"vencidos": 1, "vence_hoje": 1, "proximo_em_dias": 2},
    }


def test_seed_leva_problema_de_marcador_ao_topo_sem_contaminar_estrutura(
    tmp_path, executar_cli
):
    from neoprumo.seed import resumir

    workspace = _workspace(tmp_path, executar_cli, "problema-marcador")
    (workspace / "Pauta.md").write_text(
        "# Pauta\n- [ ] Data fantasma [vence 2026-02-30]\n",
        encoding="utf-8",
    )

    resultado = resumir(workspace, instante=INSTANTE)

    assert resultado["pauta"]["regimes"]["normal"] == 1
    assert resultado["pauta"]["prazos"]["vencidos"] == 0
    assert any("Data fantasma" in problema for problema in resultado["problemas"])
    assert resultado["estrutura"] == {"status": "saudavel", "problemas": []}


def test_seed_humano_emite_linhas_novas_na_ordem(tmp_path, executar_cli, capsys):
    from neoprumo.seed import executar_seed

    workspace = _workspace(tmp_path, executar_cli, "humano")
    (workspace / "Pauta.md").write_text(
        "# Pauta\n"
        "- [ ] Um [à vista, vence 2026-08-11]\n"
        "- [ ] Dois [à vista, vence 2026-08-12]\n"
        "- [ ] Três [à vista, vence 2026-08-10]\n"
        "- [ ] Acorda [dormindo até 2026-08-11]\n"
        "- [ ] Vencido [vence 2026-08-09]\n",
        encoding="utf-8",
    )

    assert executar_seed(workspace, instante=INSTANTE) == 0
    linhas = capsys.readouterr().out.splitlines()

    assert linhas[1:5] == [
        "Pauta: 5 abertos, 0 concluídos.",
        "À vista: 3 — Um (vence hoje); Dois (vence em 1 dia); Três (venceu há 1 dia).",
        "Acordou hoje: 1.",
        "Prazos: 2 vencidos; 1 vence hoje; próximo vence em 1 dia.",
    ]


def test_saida_humana_de_prazos_cobre_as_quatro_formas_fechadas():
    from neoprumo.resultado_seed import linhas_humanas

    def linha(vencidos=0, hoje=0, proximo=None):
        resultado = {
            "problemas": [],
            "inbox": {"total": 0, "idade_mais_antigo_dias": None,
                      "idade_mais_novo_dias": None},
            "pauta": {
                "abertos": 1, "concluidos": 0,
                "regimes": {"a_vista": 0}, "a_vista": [],
                "acordaram_hoje": 0,
                "prazos": {"vencidos": vencidos, "vence_hoje": hoje,
                            "proximo_em_dias": proximo},
            },
            "acervo": {"total": 0, "idade_mais_antigo_dias": None},
            "estrutura": {"status": "saudavel", "problemas": []},
        }
        return next(item for item in linhas_humanas(resultado) if item.startswith("Prazos:"))

    assert linha(vencidos=1) == "Prazos: 1 vencido."
    assert linha(vencidos=2, hoje=1) == "Prazos: 2 vencidos; 1 vence hoje."
    assert linha(vencidos=1, hoje=2, proximo=3) == (
        "Prazos: 1 vencido; 2 vencem hoje; próximo vence em 3 dias."
    )
    assert linha(proximo=1) == "Prazos: próximo vence em 1 dia."


def test_regime_cli_ajusta_so_a_linha_e_preserva_crlf(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli, "editar")
    pauta = workspace / "Pauta.md"
    pauta.write_bytes(
        b"# Pauta\r\n"
        b"- [ ] Preparar caf\xc3\xa9 [vence 2026-08-20]\r\n"
        b"  detalhe intacto\r\n"
        b"  \xe2\x80\x94 inbox 2026-08-05-101500, despachado em 2026-08-05\r\n"
        b"- [ ] Outra\n"
    )

    resultado = executar_cli(
        "regime", "preparar cafe", "dormindo", "--ate", "2026-08-15",
        "--workspace", workspace, "--json",
    )

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "ajustado"
    assert dados["regime"] == {"nome": "dormindo", "ate": "2026-08-15"}
    assert dados["vence"] == "2026-08-20"
    assert dados["anterior"] == {"regime": None, "vence": "2026-08-20"}
    assert pauta.read_bytes() == (
        b"# Pauta\r\n"
        b"- [ ] Preparar caf\xc3\xa9 [dormindo at\xc3\xa9 2026-08-15, vence 2026-08-20]\r\n"
        b"  detalhe intacto\r\n"
        b"  \xe2\x80\x94 inbox 2026-08-05-101500, despachado em 2026-08-05\r\n"
        b"- [ ] Outra\n"
    )


def test_despacho_pauta_grava_marcador_e_campos_so_no_sucesso(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "despacho-regime")
    item = workspace / "Inbox" / "2026-08-11-101500.md"
    item.write_text("Cobrar retorno", encoding="utf-8")

    resultado = executar_cli(
        "despacho", item.stem, "pauta", "--regime", "dormindo",
        "--ate", "2026-08-20", "--vence", "2026-08-18", "--confirmado",
        "--json",
    )

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["regime"] == {"nome": "dormindo", "ate": "2026-08-20"}
    assert dados["vence"] == "2026-08-18"
    assert dados["acoes"] == [
        "O dono confirmou que o prazo cobra antes de o item acordar."
    ]
    assert "Cobrar retorno [dormindo até 2026-08-20, vence 2026-08-18]" in (
        workspace / "Pauta.md"
    ).read_text(encoding="utf-8")


def test_regime_recusa_ambiguas_desempata_por_origem_e_nao_altera_concluida(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "busca")
    (workspace / "Pauta.md").write_text(
        "# Pauta\n"
        "- [ ] Rever contrato\n  detalhe\n"
        "  — inbox mesmo-id, despachado em 2026-08-10\n"
        "- [ ] Rever contrato antigo\n"
        "  — acervo mesmo-id, incluído em 2026-08-09\n"
        "- [X] Fechar relatório [A VISTA]\n"
        "  — inbox feito-id, despachado em 2026-08-08\n",
        encoding="utf-8",
    )

    ambigua = executar_cli(
        "regime", "rever contrato", "a-vista", "--workspace", workspace, "--json"
    )
    assert ambigua.returncode == 1
    assert json.loads(ambigua.stdout)["candidatas"] == [
        {"manchete": "Rever contrato", "origem": "inbox mesmo-id"},
        {"manchete": "Rever contrato antigo", "origem": "acervo mesmo-id"},
    ]

    escolhida = executar_cli(
        "regime", "rever contrato", "em-espera", "--origem", "acervo mesmo-id",
        "--workspace", workspace, "--json",
    )
    assert escolhida.returncode == 0
    assert json.loads(escolhida.stdout)["origem"] == "acervo mesmo-id"

    concluida = executar_cli(
        "regime", "fechar relatorio", "normal", "--workspace", workspace, "--json"
    )
    dados = json.loads(concluida.stdout)
    assert concluida.returncode == 1
    assert dados["manchete"] == "Fechar relatório"
    assert dados["origem"] == "inbox feito-id"
    assert "concluída" in dados["mensagem"]


def test_regime_nao_escolhe_candidatas_indistinguiveis(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli, "indistinguiveis")
    (workspace / "Pauta.md").write_text(
        "# Pauta\n- [ ] Igual\n- [ ] Igual\n", encoding="utf-8"
    )

    resultado = executar_cli(
        "regime", "igual", "a-vista", "--workspace", workspace, "--json"
    )

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert "diferencie o texto à mão" in dados["mensagem"]
    assert len(dados["candidatas"]) == 2


def test_regime_semantica_de_dormir_prazo_e_confirmacao(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli, "validacoes")
    pauta = workspace / "Pauta.md"
    pauta.write_text("# Pauta\n- [ ] Escolher escola [vence 2026-08-12]\n", encoding="utf-8")

    casos = [
        (("regime", "escola"), "Nada a mudar"),
        (("regime", "escola", "dormindo"), "data de acordar"),
        (("regime", "escola", "a-vista", "--ate", "2026-08-20"), "--ate"),
        (("regime", "escola", "--vence", "2026-02-30"), "prazo"),
        (("regime", "escola", "--vence", "2026-08-20", "--sem-prazo"), "juntos"),
        (("regime", "escola", "a-vista", "--confirmado"), "Não há o que confirmar"),
    ]
    for argumentos, mensagem in casos:
        resultado = executar_cli(*argumentos, "--workspace", workspace, "--json")
        assert resultado.returncode == 1
        assert mensagem.casefold() in json.loads(resultado.stdout)["mensagem"].casefold()

    contradicao = executar_cli(
        "regime", "escola", "dormindo", "--ate", "2026-08-20",
        "--workspace", workspace, "--json",
    )
    assert contradicao.returncode == 1
    assert "antes de acordar" in json.loads(contradicao.stdout)["mensagem"]
    assert "dormindo" not in pauta.read_text(encoding="utf-8")

    confirmado = executar_cli(
        "regime", "escola", "dormindo", "--ate", "2026-08-20", "--confirmado",
        "--workspace", workspace, "--json",
    )
    assert confirmado.returncode == 0
    assert json.loads(confirmado.stdout)["acoes"]

    preserva = executar_cli(
        "regime", "escola", "dormindo", "--vence", "2026-08-21",
        "--workspace", workspace, "--json",
    )
    assert preserva.returncode == 0
    assert json.loads(preserva.stdout)["regime"]["ate"] == "2026-08-20"


def test_regime_detecta_corrida_sem_gravar(tmp_path, executar_cli):
    from neoprumo.comando_regime import operar_regime

    workspace = _workspace(tmp_path, executar_cli, "corrida")
    pauta = workspace / "Pauta.md"
    pauta.write_text("# Pauta\n- [ ] Alvo\n", encoding="utf-8")

    def concorrente():
        pauta.write_text("# Pauta\n- [ ] Alvo\n- [ ] Concorrente\n", encoding="utf-8")

    codigo, resultado = operar_regime(
        "alvo", regime="a-vista", caminho=workspace,
        antes_de_reconferir=concorrente,
    )

    assert codigo == 1
    assert "mudou desde a leitura" in resultado["mensagem"]
    assert pauta.read_text(encoding="utf-8").endswith("- [ ] Concorrente\n")


def test_regime_indisponivel_usa_status_real_e_campos_nulos(executar_cli):
    resultado = executar_cli("regime", "algo", "a-vista", "--json")

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "sem_ativo"
    assert all(
        dados[chave] is None
        for chave in ("manchete", "origem", "regime", "vence", "anterior")
    )
    assert dados["candidatas"] == []


def test_regime_ativo_invalido_usa_status_real(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli, "ativo-invalido")
    (workspace / ".neoprumo").rename(workspace / ".marca-removida")

    resultado = executar_cli("regime", "algo", "a-vista", "--json")

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "ativo_invalido"
    assert dados["regime"] is None and dados["anterior"] is None


def test_despacho_campos_novos_seguem_matriz_e_recusa_antes_do_efeito(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "matriz-despacho")
    inbox = workspace / "Inbox"
    (inbox / "normal.md").write_text("Normal", encoding="utf-8")
    (inbox / "recusa.md").write_text("Recusa", encoding="utf-8")
    (inbox / "acervo.md").write_text("Acervo", encoding="utf-8")

    normal = executar_cli(
        "despacho", "normal", "pauta", "--workspace", workspace, "--json"
    )
    assert {"regime": None, "vence": None}.items() <= json.loads(normal.stdout).items()

    recusa = executar_cli(
        "despacho", "recusa", "pauta", "--regime", "dormindo",
        "--ate", "2026-08-20", "--vence", "2026-08-18",
        "--workspace", workspace, "--json",
    )
    assert recusa.returncode == 1 and (inbox / "recusa.md").exists()
    assert "regime" not in json.loads(recusa.stdout)
    assert "vence" not in json.loads(recusa.stdout)

    outro = executar_cli(
        "despacho", "acervo", "acervo", "--regime", "a-vista",
        "--workspace", workspace, "--json",
    )
    assert outro.returncode == 1 and (inbox / "acervo.md").exists()
    assert "regime" not in json.loads(outro.stdout)

    sem_caso = executar_cli(
        "despacho", "acervo", "acervo", "--confirmado",
        "--workspace", workspace, "--json",
    )
    assert sem_caso.returncode == 1
    assert "não há o que confirmar" in json.loads(sem_caso.stdout)["mensagem"].casefold()


@pytest.mark.parametrize(
    ("argumentos", "esperado"),
    [
        ((), None),
        (("--regime", "a-vista"), {"nome": "a_vista", "ate": None}),
        (("--regime", "em-espera"), {"nome": "em_espera", "ate": None}),
        (("--regime", "dormindo", "--ate", "2026-09-01"),
         {"nome": "dormindo", "ate": "2026-09-01"}),
    ],
)
def test_despacho_fotografa_as_quatro_formas_do_regime(
    argumentos, esperado, tmp_path, executar_cli
):
    nome = "forma-" + (esperado["nome"] if esperado else "normal")
    workspace = _workspace(tmp_path, executar_cli, nome)
    (workspace / "Inbox" / "item.md").write_text("Item", encoding="utf-8")

    resultado = executar_cli(
        "despacho", "item", "pauta", *argumentos,
        "--workspace", workspace, "--json",
    )

    assert resultado.returncode == 0
    assert json.loads(resultado.stdout)["regime"] == esperado
