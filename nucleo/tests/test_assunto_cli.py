import json


def chamar(executar_cli, *args, input=None):
    resultado = executar_cli(*args, "--json", input=input)
    saida = resultado.stdout or resultado.stderr
    return resultado, json.loads(saida)


def workspace_pronto(executar_cli, tmp_path):
    workspace = tmp_path / "casa"
    assert executar_cli("setup", workspace, "--json").returncode == 0
    return workspace


def test_setup_e_doctor_adotam_a_prateleira_sem_interpretar_o_legado(
    executar_cli, tmp_path
):
    workspace = workspace_pronto(executar_cli, tmp_path)
    assert (workspace / "Assuntos").is_dir()
    assert not (workspace / "Projetos.md").exists()

    (workspace / "Assuntos").rmdir()
    (workspace / "Projetos.md").mkdir()
    reparo = executar_cli("doctor", workspace, "--reparar", "--json")

    assert reparo.returncode == 0
    assert (workspace / "Assuntos").is_dir()
    assert (workspace / "Projetos.md").is_dir()


def test_registrar_valida_e_cria_ficha_canônica_relegivel(executar_cli, tmp_path):
    workspace = workspace_pronto(executar_cli, tmp_path)
    resultado, envelope = chamar(
        executar_cli,
        "assunto", "registrar", "Árvore do quintal",
        "--tipo", "área da vida",
        "--apelido", "Quintal",
        "--apelido", "quintal",
        "--caminho", "/Volumes/arquivo ausente",
        "--caminho-relacionado", "/tmp/mapa",
        "--workspace", workspace,
    )

    assert resultado.returncode == 0
    assert envelope["status"] == "registrado"
    assert envelope["id"] == "arvore-do-quintal"
    assert envelope["problemas"]
    ficha = workspace / "Assuntos" / "arvore-do-quintal.md"
    assert ficha.read_text() == (
        "# Árvore do quintal\n\n"
        "Tipo: área da vida\nEstado: ativo\nApelidos: Quintal\n"
        "Caminho: /Volumes/arquivo ausente\n"
        "Caminho relacionado: /tmp/mapa\n\n## Registro\n"
    )

    _, mostrado = chamar(
        executar_cli, "assunto", "mostrar", "arvore-do-quintal",
        "--workspace", workspace,
    )
    assert mostrado["status"] == "assunto"
    assert mostrado["nome"] == "Árvore do quintal"
    assert mostrado["problemas"] == []


def test_colisao_e_referencia_invalida_expoem_contrato(executar_cli, tmp_path):
    workspace = workspace_pronto(executar_cli, tmp_path)
    (workspace / "Assuntos" / "ocupado.md").write_text("sem título\n")

    resultado, colisao = chamar(
        executar_cli, "assunto", "registrar", "Ocupado", "--id", "ocupado",
        "--workspace", workspace,
    )
    assert resultado.returncode == 1
    assert colisao["status"] == "id_em_uso"
    assert colisao["id"] == "ocupado"
    assert colisao["nome"] is None

    resultado, invalida = chamar(
        executar_cli, "assunto", "mostrar", "\u0301", "--workspace", workspace,
    )
    assert resultado.returncode == 1
    assert invalida["status"] == "referencia_invalida"


def test_resolucao_em_camadas_e_listagem_tolerante(executar_cli, tmp_path):
    workspace = workspace_pronto(executar_cli, tmp_path)
    for nome, identificador, apelido in (
        ("Mercúrio retrógrado", "ceu", "planetas"),
        ("Planetas na estante", "estante", "livros"),
    ):
        resultado, _ = chamar(
            executar_cli, "assunto", "registrar", nome, "--id", identificador,
            "--apelido", apelido, "--workspace", workspace,
        )
        assert resultado.returncode == 0

    _, por_apelido = chamar(
        executar_cli, "assunto", "mostrar", "PLANÉTAS", "--workspace", workspace,
    )
    assert por_apelido["id"] == "ceu"
    _, ambiguo = chamar(
        executar_cli, "assunto", "mostrar", "eta", "--workspace", workspace,
    )
    assert ambiguo["status"] == "ambiguo"
    assert [item["id"] for item in ambiguo["candidatas"]] == ["ceu", "estante"]

    (workspace / "Assuntos" / "quebrado.md").write_bytes(b"\xff")
    _, exato = chamar(
        executar_cli, "assunto", "mostrar", "ceu", "--workspace", workspace,
    )
    assert exato["status"] == "assunto"
    _, incerta = chamar(
        executar_cli, "assunto", "mostrar", "livros", "--workspace", workspace,
    )
    assert incerta["status"] == "resolucao_incerta"
    _, lista = chamar(
        executar_cli, "assunto", "listar", "--workspace", workspace,
    )
    assert [item["id"] for item in lista["assuntos"]] == ["ceu", "estante"]
    assert any("quebrado.md" in p for p in lista["problemas"])


def test_parser_tolerante_notas_e_estado_preservam_prosa(executar_cli, tmp_path):
    workspace = workspace_pronto(executar_cli, tmp_path)
    ficha = workspace / "Assuntos" / "casa.md"
    original = (
        "# Casa\nLinha livre\nEstado: estranho\nEstado: arquivado\n"
        "Caminho relacionado: um\nCaminho relacionado: dois\n\n"
        "## Registro\n"
        "- 2026-02-31: data impossível\n"
        "- 2026-08-12 (inbox mapa.md): cabeça\n  corpo\n"
        "tab fora\n## Registro\ntexto do dono\n"
    )
    ficha.write_text(original)

    _, mostrado = chamar(
        executar_cli, "assunto", "mostrar", "casa", "--workspace", workspace,
    )
    assert mostrado["estado"] == "ativo"
    assert mostrado["caminhos_relacionados"] == ["um", "dois"]
    assert mostrado["notas"] == [{
        "data": "2026-08-12", "origem": "inbox mapa.md", "texto": "cabeça\ncorpo"
    }]
    assert any("mais de uma seção Registro" in p for p in mostrado["problemas"])

    _, arquivado = chamar(
        executar_cli, "assunto", "arquivar", "casa", "--workspace", workspace,
    )
    assert arquivado["status"] == "arquivado"
    novo = ficha.read_text()
    assert novo == original.replace("Estado: estranho", "Estado: arquivado", 1)


def test_nota_multilinha_e_recriacao_da_secao(executar_cli, tmp_path):
    workspace = workspace_pronto(executar_cli, tmp_path)
    ficha = workspace / "Assuntos" / "rio.md"
    ficha.write_text("# Rio\n\nProsa final sem newline")

    resultado, anotado = chamar(
        executar_cli, "assunto", "nota", "rio", "-", "--data", "2026-08-11",
        "--origem", "acervo mapa.tar-2.gz", "--workspace", workspace,
        input="\nCabeça\n  já indentado\n\nfinal\r\n",
    )
    assert resultado.returncode == 0
    assert anotado["status"] == "anotado"
    assert ficha.read_text().endswith(
        "\n\n## Registro\n- 2026-08-11 (acervo mapa.tar-2.gz): Cabeça\n"
        "  \n    já indentado\n  \n  final\n"
    )
    _, mostrado = chamar(
        executar_cli, "assunto", "mostrar", "rio", "--workspace", workspace,
    )
    assert mostrado["notas"][0]["texto"] == "Cabeça\n\n  já indentado\n\nfinal"
