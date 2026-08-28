import json
import os
from datetime import datetime, timezone


def _mostrar(executar_cli, workspace, referencia="horta"):
    resultado = executar_cli(
        "assunto", "mostrar", referencia, "--workspace", workspace, "--json"
    )
    saida = resultado.stdout or resultado.stderr
    return resultado, json.loads(saida)


def _workspace_com_assunto(executar_cli, tmp_path, caminho=None):
    workspace = tmp_path / "workspace"
    assert executar_cli("setup", workspace, "--json").returncode == 0
    linhas = ["# Horta\n", "\n", "Tipo: projeto\n", "Estado: ativo\n"]
    if caminho is not None:
        linhas.append(f"Caminho: {caminho}\n")
    linhas.extend(["\n", "## Registro\n"])
    (workspace / "Assuntos" / "horta.md").write_text(
        "".join(linhas), encoding="utf-8"
    )
    return workspace


def test_mostrar_le_contexto_estruturado_e_marca_fresco(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-horta"
    projeto.mkdir()
    contexto = projeto / ".prumo-contexto.md"
    contexto.write_text(
        "---\nupdated: 2026-08-20\n---\n\n"
        "# Horta\n\n## Estado atual\n"
        "Os canteiros estão desenhados.\nA irrigação será manual.\n\n"
        "## Decisões\nSem automação nesta etapa.\n",
        encoding="utf-8",
    )
    instante = datetime(2026, 8, 20, 12, 0).timestamp()
    os.utime(contexto, (instante, instante))
    os.utime(projeto, (instante, instante))
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    resultado, mostrado = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert mostrado["contexto"] == {
        "status": "lido",
        "arquivo": str(contexto),
        "updated": "2026-08-20",
        "manchete": "Os canteiros estão desenhados.\nA irrigação será manual.",
        "manchete_truncada": False,
        "frescor": "fresco",
        "atividade": "2026-08-20",
    }
    assert mostrado["problemas"] == []


def test_contexto_sem_updated_tem_frescor_indeterminado(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-telhado"
    projeto.mkdir()
    (projeto / ".prumo-contexto.md").write_text(
        "---\ntitulo: Reforma do telhado\n---\n\n"
        "## Estado atual\nAs telhas foram encomendadas.\n",
        encoding="utf-8",
    )
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    resultado, mostrado = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert mostrado["contexto"]["status"] == "lido"
    assert mostrado["contexto"]["updated"] is None
    assert mostrado["contexto"]["frescor"] == "indeterminado"
    assert any("updated" in problema for problema in mostrado["problemas"])


def test_arquivo_fora_do_padrao_usa_rede_de_oito_kb(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-oficina"
    projeto.mkdir()
    texto = "Plano ainda sem frontmatter.\n" + ("linha de trabalho\n" * 700)
    (projeto / ".prumo-contexto.md").write_text(texto, encoding="utf-8")
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    resultado, mostrado = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    contexto = mostrado["contexto"]
    assert contexto["status"] == "lido"
    assert contexto["manchete"].startswith("Plano ainda sem frontmatter.")
    assert len(contexto["manchete"].encode("utf-8")) <= 8 * 1024
    assert contexto["manchete"].endswith("linha de trabalho")
    assert contexto["manchete_truncada"] is True
    assert any("fora do padrão" in problema for problema in mostrado["problemas"])


def test_rede_sem_corpo_devolve_manchete_nula_sem_truncamento(
    executar_cli, tmp_path
):
    projeto = tmp_path / "projeto-cisterna"
    projeto.mkdir()
    (projeto / ".prumo-contexto.md").write_text(
        "---\nupdated: 2026-08-20\n---\n", encoding="utf-8"
    )
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    resultado, mostrado = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    contexto = mostrado["contexto"]
    assert contexto["status"] == "lido"
    assert contexto["manchete"] is None
    assert contexto["manchete_truncada"] is False
    assert any("fora do padrão" in problema for problema in mostrado["problemas"])


def test_falhas_do_contexto_preservam_a_ficha_e_saida_zero(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-casa"
    projeto.mkdir()
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)
    ficha = workspace / "Assuntos" / "horta.md"

    resultado, sem_arquivo = _mostrar(executar_cli, workspace)
    assert resultado.returncode == 0
    assert sem_arquivo["contexto"]["status"] == "sem_arquivo"
    assert sem_arquivo["nome"] == "Horta"

    inexistente = tmp_path / "projeto-ausente"
    ficha.write_text(ficha.read_text().replace(str(projeto), str(inexistente)))
    resultado, inacessivel = _mostrar(executar_cli, workspace)
    assert resultado.returncode == 0
    assert inacessivel["contexto"]["status"] == "inacessivel"
    assert inacessivel["contexto"]["frescor"] == "indeterminado"
    assert inacessivel["contexto"]["atividade"] is None
    assert inacessivel["nome"] == "Horta"

    ficha.write_text(ficha.read_text().replace(str(inexistente), str(projeto)))
    arquivo = projeto / ".prumo-contexto.md"
    arquivo.write_bytes(b"\xff\xfe")
    resultado, ilegivel = _mostrar(executar_cli, workspace)
    assert resultado.returncode == 0
    assert ilegivel["contexto"]["status"] == "ilegivel"
    assert ilegivel["contexto"]["arquivo"] == str(arquivo)
    assert ilegivel["contexto"]["manchete"] is None
    assert ilegivel["nome"] == "Horta"
    assert all(item["problemas"] for item in (inacessivel, ilegivel))


def test_atividade_posterior_marca_defasado_sem_recursao(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-estufa"
    projeto.mkdir()
    arquivo = projeto / ".prumo-contexto.md"
    arquivo.write_text(
        "---\nupdated: 2026-08-20\n---\n\n## Estado atual\nEstrutura montada.\n",
        encoding="utf-8",
    )
    primeiro_nivel = projeto / "medidas.txt"
    primeiro_nivel.write_text("medidas", encoding="utf-8")
    subpasta = projeto / "arquivo"
    subpasta.mkdir()
    profundo = subpasta / "rascunho.txt"
    profundo.write_text("rascunho", encoding="utf-8")
    dia_20 = datetime(2026, 8, 20, 12).timestamp()
    dia_21 = datetime(2026, 8, 21, 12).timestamp()
    dia_22 = datetime(2026, 8, 22, 12).timestamp()
    for caminho, instante in (
        (arquivo, dia_20), (projeto, dia_20), (subpasta, dia_20),
        (primeiro_nivel, dia_21), (profundo, dia_22),
    ):
        os.utime(caminho, (instante, instante))
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    _, mostrado = _mostrar(executar_cli, workspace)

    assert mostrado["contexto"]["atividade"] == "2026-08-21"
    assert mostrado["contexto"]["frescor"] == "defasado"


def test_updated_rfc3339_vira_data_civil_no_fuso_local(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-varanda"
    projeto.mkdir()
    arquivo = projeto / ".prumo-contexto.md"
    arquivo.write_text(
        "---\nupdated: 2026-08-20T23:30:00-03:00\n---\n\n"
        "## Estado atual\nPiso escolhido.\n",
        encoding="utf-8",
    )
    instante = datetime(2026, 8, 21, 2, 30, tzinfo=timezone.utc).timestamp()
    os.utime(arquivo, (instante, instante))
    os.utime(projeto, (instante, instante))
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    _, mostrado = _mostrar(executar_cli, workspace)

    assert mostrado["contexto"]["updated"] == "2026-08-20T23:30:00-03:00"
    assert mostrado["contexto"]["frescor"] == "fresco"


def test_caminho_relativo_e_inacessivel_sem_virar_defasado(executar_cli, tmp_path):
    workspace = _workspace_com_assunto(executar_cli, tmp_path, "projeto-relativo")

    resultado, mostrado = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert mostrado["contexto"]["status"] == "inacessivel"
    assert mostrado["contexto"]["frescor"] == "indeterminado"
    assert any("relativo" in problema.casefold() for problema in mostrado["problemas"])


def test_home_de_usuario_desconhecido_degrada_sem_traceback(executar_cli, tmp_path):
    workspace = _workspace_com_assunto(
        executar_cli, tmp_path, "~usuario-ficticio-inexistente/projeto"
    )

    resultado, mostrado = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert mostrado["contexto"]["status"] == "inacessivel"
    assert mostrado["contexto"]["frescor"] == "indeterminado"
    assert mostrado["problemas"]


def test_mostrar_sem_caminho_preserva_envelope_anterior(executar_cli, tmp_path):
    workspace = _workspace_com_assunto(executar_cli, tmp_path)
    resultado, mostrado = _mostrar(executar_cli, workspace)
    esperado = {
        "status": "assunto",
        "problemas": [],
        "acoes": [],
        "mensagem": "Assunto: Horta (horta).",
        "workspace": str(workspace),
        "id": "horta",
        "nome": "Horta",
        "tipo": "projeto",
        "estado": "ativo",
        "apelidos": [],
        "caminho": None,
        "caminhos_relacionados": [],
        "notas": [],
    }

    assert mostrado == esperado
    assert resultado.stdout == json.dumps(esperado, ensure_ascii=False) + "\n"


def test_leitura_nao_altera_arquivos_nem_metadados_de_escrita(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-bancada"
    projeto.mkdir()
    arquivo = projeto / ".prumo-contexto.md"
    arquivo.write_text(
        "---\nupdated: 2026-08-20\n---\n\n## Estado atual\nBancada pronta.\n",
        encoding="utf-8",
    )
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)
    antes = {
        caminho.name: (caminho.read_bytes(), caminho.stat().st_mtime_ns)
        for caminho in projeto.iterdir()
    }
    mtime_pasta = projeto.stat().st_mtime_ns

    resultado, _ = _mostrar(executar_cli, workspace)

    depois = {
        caminho.name: (caminho.read_bytes(), caminho.stat().st_mtime_ns)
        for caminho in projeto.iterdir()
    }
    assert resultado.returncode == 0
    assert depois == antes
    assert projeto.stat().st_mtime_ns == mtime_pasta


def test_manchete_estruturada_respeita_teto_duro(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-lago"
    projeto.mkdir()
    (projeto / ".prumo-contexto.md").write_text(
        "---\nupdated: 2026-08-20\n---\n\n## Estado atual\n"
        + ("observação do lago\n" * 700)
        + "\n## Próximos passos\nMedir a margem.\n",
        encoding="utf-8",
    )
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    _, mostrado = _mostrar(executar_cli, workspace)

    contexto = mostrado["contexto"]
    assert len(contexto["manchete"].encode("utf-8")) <= 8 * 1024
    assert contexto["manchete_truncada"] is True


def test_expande_home_e_recusa_timestamp_fora_de_rfc3339(
    executar_cli, tmp_path, monkeypatch
):
    casa = tmp_path / "casa-do-host"
    projeto = casa / "projetos" / "jardim"
    projeto.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(casa))
    (projeto / ".prumo-contexto.md").write_text(
        "---\nupdated: 2026-08-20 12:00:00+00:00\n---\n\n"
        "## Estado atual\nSementes separadas.\n",
        encoding="utf-8",
    )
    workspace = _workspace_com_assunto(
        executar_cli, tmp_path, "~/projetos/jardim"
    )

    _, mostrado = _mostrar(executar_cli, workspace)

    contexto = mostrado["contexto"]
    assert contexto["status"] == "lido"
    assert contexto["arquivo"] == str(projeto / ".prumo-contexto.md")
    assert contexto["updated"] == "2026-08-20 12:00:00+00:00"
    assert contexto["frescor"] == "indeterminado"
    assert any("updated" in problema for problema in mostrado["problemas"])


def test_falha_de_leitura_e_de_atividade_sao_nomeadas(executar_cli, tmp_path):
    projeto = tmp_path / "projeto-pomar"
    projeto.mkdir()
    arquivo = projeto / ".prumo-contexto.md"
    arquivo.mkdir()
    workspace = _workspace_com_assunto(executar_cli, tmp_path, projeto)

    resultado, ilegivel = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert ilegivel["contexto"]["status"] == "ilegivel"
    assert any("não pôde ser lido" in item for item in ilegivel["problemas"])

    arquivo.rmdir()
    arquivo.write_text(
        "---\nupdated: 2026-08-20\n---\n\n## Estado atual\nÁrvores medidas.\n",
        encoding="utf-8",
    )
    (projeto / "atalho-quebrado").symlink_to(projeto / "alvo-ausente")
    resultado, indeterminado = _mostrar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert indeterminado["contexto"]["status"] == "lido"
    assert indeterminado["contexto"]["atividade"] is None
    assert indeterminado["contexto"]["frescor"] == "indeterminado"
    assert any("atividade" in item for item in indeterminado["problemas"])
