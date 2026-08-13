import hashlib
import json


def criar_workspace(executar_cli, tmp_path):
    workspace = tmp_path / "casa"
    assert executar_cli("setup", workspace, "--json").returncode == 0
    assert executar_cli(
        "assunto", "registrar", "Museu submerso", "--id", "museu",
        "--tipo", "projeto", "--workspace", workspace, "--json",
    ).returncode == 0
    return workspace


def resposta(nome, conteudo, projeto="museu"):
    return {
        "item": nome, "decisao": "projeto", "projeto": projeto,
        "digital": hashlib.sha256(conteudo).hexdigest(),
    }


def aplicar(executar_modulo, workspace, respostas):
    bloco = {"superficie": "despacho", "pagina": "teste", "respostas": respostas}
    return executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json",
        input=json.dumps(bloco),
    )


def test_marcador_na_primeira_secao_bloqueia_nome_completo_sem_falso_positivo(
    executar_cli, executar_modulo, tmp_path
):
    workspace = criar_workspace(executar_cli, tmp_path)
    ficha = workspace / "Assuntos" / "museu.md"
    ficha.write_text(
        "# Museu submerso\nEstado: ativo\n\n## Registro\n"
        "- 2026-08-12 (inbox mapa.md): já foi\n"
        "## Registro\n- 2026-08-12 (inbox outro.txt): texto do dono\n"
    )
    item_md = workspace / "Inbox" / "mapa.md"
    item_txt = workspace / "Inbox" / "mapa.txt"
    item_md.write_bytes(b"um")
    item_txt.write_bytes(b"dois")

    bloqueado = aplicar(executar_modulo, workspace, [resposta("mapa.md", b"um")])
    assert bloqueado.returncode == 1
    assert json.loads(bloqueado.stdout)["status"] == "envelhecida"

    livre = aplicar(executar_modulo, workspace, [resposta("mapa.txt", b"dois")])
    assert livre.returncode == 0
    assert not item_txt.exists()
    assert item_md.exists()


def test_ficha_ilegivel_avisa_sem_bloquear_builder(executar_cli, tmp_path):
    workspace = criar_workspace(executar_cli, tmp_path)
    (workspace / "Assuntos" / "quebrado.md").write_bytes(b"\xff")
    (workspace / "Inbox" / "novo.md").write_text("novo")

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )
    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert dados["status"] == "gerado"
    assert any("ilegível na conferência de marcadores" in p for p in dados["problemas"])


def test_lote_isola_assunto_inexistente_e_aplica_outro_item(
    executar_cli, executar_modulo, tmp_path
):
    workspace = criar_workspace(executar_cli, tmp_path)
    ruim = workspace / "Inbox" / "ruim.md"
    bom = workspace / "Inbox" / "bom.md"
    ruim.write_bytes(b"ruim")
    bom.write_bytes(b"bom")

    resultado = aplicar(executar_modulo, workspace, [
        resposta("ruim.md", b"ruim", "fantasma"),
        resposta("bom.md", b"bom"),
    ])
    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1
    assert dados["status"] == "aplicado_com_recusas"
    assert [item["status"] for item in dados["resultados"]] == ["recusado", "despachado"]
    assert ruim.exists() and not bom.exists()


def test_projetos_de_qualquer_tipo_nao_bloqueia_builder_e_aplicar(
    executar_cli, executar_modulo, tmp_path
):
    workspace = criar_workspace(executar_cli, tmp_path)
    (workspace / "Projetos.md").mkdir()
    item = workspace / "Inbox" / "nota.md"
    item.write_bytes(b"nota")
    gerado = executar_cli("superficie", "despacho", "--workspace", workspace, "--json")
    assert gerado.returncode == 0
    aplicado = aplicar(executar_modulo, workspace, [resposta("nota.md", b"nota")])
    assert aplicado.returncode == 0

