from datetime import datetime, timedelta, timezone


REFERENCIA = datetime(2026, 8, 12, 12, tzinfo=timezone.utc)


def _workspace(tmp_path, executar_cli, nome="espera"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def _observar(workspace):
    from neoprumo.ressurgimento import operar_ressurgimento

    codigo, resultado = operar_ressurgimento(workspace, instante=REFERENCIA)
    assert codigo == 0
    return resultado


def test_issue_52_em_espera_so_entrega_candidato_e_breakdown(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "Pauta.md").write_text(
        "# Pauta\n"
        "- [ ] Primeira ideia [em espera]\n"
        "  detalhe\n"
        "  — inbox abc, despachado em 2026-08-05\n"
        "- [ ] Segunda ideia [em espera]\n",
        encoding="utf-8",
    )

    resultado = _observar(workspace)

    assert resultado["elegiveis"] == 2
    assert resultado["elegiveis_acervo"] == 0
    assert resultado["elegiveis_em_espera"] == 2
    assert resultado["candidato"]["origem"] == "em_espera"
    assert resultado["candidato"]["nome"] is None
    assert resultado["candidato"]["manchete"] in {
        "Primeira ideia", "Segunda ideia"
    }
    assert resultado["candidato"]["conteudo"]


def test_issue_52_relogio_prazo_marcador_e_conteudo_exato(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "regras")
    (workspace / "Pauta.md").write_bytes(
        b"texto antes\r\n"
        b"- [ ] Seis [em espera]\r\n"
        b"  \xe2\x80\x94 inbox seis, despachado em 2026-08-06\r\n"
        b"- [ ] Sete [em espera, vence 2026-08-12]\r\n"
        b"  detalhe preservado\r\n"
        b"  \xe2\x80\x94 acervo sete, inclu\xc3\xaddo em 2026-08-05\r\n"
        b"texto entre\r\n"
        b"- [ ] Manual [em espera, vence 2026-02-30]\r\n"
        b"  final sem quebra"
    )

    resultado = _observar(workspace)

    assert resultado["elegiveis_em_espera"] == 2
    candidatos = resultado.pop("_candidatos", None)
    assert candidatos is None
    candidato = resultado["candidato"]
    assert candidato["manchete"] in {"Sete", "Manual"}
    if candidato["manchete"] == "Sete":
        assert candidato["idade"] == 7
        assert candidato["origem_entrada"] == "acervo sete"
        assert candidato["conteudo"] == "Sete\n  detalhe preservado\r\n"
    else:
        assert candidato["idade"] is None
        assert candidato["origem_entrada"] is None
        assert candidato["conteudo"] == "Manual\n  final sem quebra"
    assert not resultado["problemas"]


def test_issue_52_pauta_com_falha_nao_derruba_candidato_do_acervo(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "degradacao")
    (workspace / "Pauta.md").unlink()
    (workspace / "Acervo" / "2020-01-01-000000.md").write_text(
        "ideia antiga", encoding="utf-8"
    )

    resultado = _observar(workspace)

    assert resultado["status"] == "candidato"
    assert resultado["candidato"]["origem"] == "acervo"
    assert resultado["elegiveis_acervo"] == 1
    assert resultado["elegiveis_em_espera"] == 0
    assert any(problema.startswith("Pauta.md:") for problema in resultado["problemas"])


def test_issue_52_manchetes_vazias_geram_um_aviso_agregado(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "vazias")
    (workspace / "Pauta.md").write_text(
        "- [ ] [em espera]\n- [ ] [em espera]\n", encoding="utf-8"
    )

    resultado = _observar(workspace)

    assert resultado["status"] == "sem_candidato"
    assert resultado["problemas"] == [
        "2 entradas em espera sem texto pra apresentar; revise-as na Pauta."
    ]


def test_issue_52_uniao_percorre_cinco_itens_em_cinco_dias(
    tmp_path, executar_cli
):
    from neoprumo.ressurgimento import operar_ressurgimento

    workspace = _workspace(tmp_path, executar_cli, "uniao")
    for numero in range(3):
        (workspace / "Acervo" / f"2020-01-0{numero + 1}-000000.md").write_text(
            f"acervo {numero}", encoding="utf-8"
        )
    (workspace / "Pauta.md").write_text(
        "- [ ] Espera A [em espera]\n- [ ] Espera B [em espera]\n",
        encoding="utf-8",
    )

    vistos = []
    for deslocamento in range(5):
        codigo, resultado = operar_ressurgimento(
            workspace, instante=REFERENCIA + timedelta(days=deslocamento)
        )
        assert codigo == 0
        candidato = resultado["candidato"]
        vistos.append((candidato["origem"], candidato["nome"] or candidato["manchete"]))
        assert resultado["elegiveis"] == 5
        assert resultado["elegiveis_acervo"] == 3
        assert resultado["elegiveis_em_espera"] == 2

    assert len(set(vistos)) == 5


def test_issue_52_prazo_vencido_e_dormindo_ficam_fora(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "prazo-e-sono")
    hoje = REFERENCIA.astimezone().date()
    (workspace / "Pauta.md").write_text(
        f"- [ ] Venceu ontem [em espera, vence {hoje - timedelta(days=1)}]\n"
        f"- [ ] Vence hoje [em espera, vence {hoje}]\n"
        f"- [ ] Vence amanhã [em espera, vence {hoje + timedelta(days=1)}]\n"
        f"- [ ] Sono vencido [dormindo até {hoje - timedelta(days=10)}]\n",
        encoding="utf-8",
    )

    resultado = _observar(workspace)

    assert resultado["elegiveis_em_espera"] == 2
    assert resultado["candidato"]["manchete"] in {"Vence hoje", "Vence amanhã"}
    assert resultado["problemas"] == []


def test_issue_52_marcadores_que_nao_formam_em_espera_ficam_fora_sem_aviso(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "marcadores-fora")
    (workspace / "Pauta.md").write_text(
        "- [ ] Texto do dono [em espera, urgente]\n"
        "- [ ] Regime duplo [em espera, à vista]\n"
        "- [ ] Sono impossível [dormindo até 2026-02-30]\n",
        encoding="utf-8",
    )

    resultado = _observar(workspace)

    assert resultado["status"] == "sem_candidato"
    assert resultado["elegiveis_em_espera"] == 0
    assert resultado["problemas"] == []


def test_issue_52_rodape_com_data_invalida_e_elegivel_sem_idade_e_sem_aviso(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "rodape-invalido")
    (workspace / "Pauta.md").write_text(
        "- [ ] Data quebrada [em espera]\n"
        "  — inbox abc, despachado em 2026-13-40\n",
        encoding="utf-8",
    )

    resultado = _observar(workspace)

    assert resultado["candidato"]["manchete"] == "Data quebrada"
    assert resultado["candidato"]["idade"] is None
    assert resultado["candidato"]["origem_entrada"] == "inbox abc"
    assert resultado["problemas"] == []


def test_issue_52_mensagem_humana_cobre_idade_e_data_desconhecida(
    tmp_path, executar_cli
):
    origem = REFERENCIA.astimezone().date() - timedelta(days=7)
    com_data = _workspace(tmp_path, executar_cli, "mensagem-com-data")
    (com_data / "Pauta.md").write_text(
        "- [ ] Tema datado [em espera]\n"
        f"  — acervo antigo, incluído em {origem}\n",
        encoding="utf-8",
    )
    sem_data = _workspace(tmp_path, executar_cli, "mensagem-sem-data")
    (sem_data / "Pauta.md").write_text(
        "- [ ] Tema manual [em espera]\n", encoding="utf-8"
    )

    resultado_com_data = _observar(com_data)
    resultado_sem_data = _observar(sem_data)

    assert resultado_com_data["mensagem"] == (
        "«Tema datado» está em espera há 7 dias; 1 elegível hoje."
    )
    assert resultado_sem_data["mensagem"] == (
        "«Tema manual» está em espera (sem data conhecida); 1 elegível hoje."
    )
