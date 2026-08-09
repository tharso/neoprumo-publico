import json


def test_doctor_confirma_workspace_saudavel(tmp_path, executar_cli):
    workspace = tmp_path / "saudavel"
    assert executar_cli("setup", workspace).returncode == 0

    resultado = executar_cli("doctor", workspace)

    assert resultado.returncode == 0
    assert "Tudo certo" in resultado.stdout


def test_doctor_lista_ausencias_e_reparo_preserva_conteudo_do_usuario(
    tmp_path, executar_cli
):
    workspace = tmp_path / "incompleto"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Acervo").rmdir()
    (workspace / "Projetos.md").unlink()
    captura = workspace / "Inbox" / "nome inesperado.txt"
    captura.write_text("conteúdo do usuário", encoding="utf-8")
    (workspace / "Pauta.md").write_text("# Minha pauta\n- preservar\n", encoding="utf-8")

    diagnostico = executar_cli("doctor", workspace)

    assert diagnostico.returncode != 0
    assert "Acervo" in diagnostico.stderr
    assert "Projetos.md" in diagnostico.stderr

    reparo = executar_cli("doctor", workspace, "--reparar")

    assert reparo.returncode == 0
    assert "reparado" in reparo.stdout.lower()
    assert "- Acervo recriado." in reparo.stdout
    assert "- Projetos.md recriado." in reparo.stdout
    assert "Falta " not in reparo.stdout
    assert (workspace / "Acervo").is_dir()
    assert (workspace / "Projetos.md").read_text(encoding="utf-8") == "# Projetos\n"
    assert captura.read_text(encoding="utf-8") == "conteúdo do usuário"
    assert (workspace / "Pauta.md").read_text(encoding="utf-8") == (
        "# Minha pauta\n- preservar\n"
    )


def test_doctor_recusa_caminho_sem_identidade_e_sugere_setup(tmp_path, executar_cli):
    resultado = executar_cli("doctor", tmp_path)

    assert resultado.returncode != 0
    assert "não é um workspace do NeoPrumo" in resultado.stderr
    assert "setup" in resultado.stderr


def test_doctor_trata_caminho_arquivo_como_nao_workspace_sem_traceback(
    tmp_path, executar_modulo
):
    caminho = tmp_path / "arquivo.txt"
    caminho.write_text("preservado", encoding="utf-8")

    resultado = executar_modulo("doctor", caminho)

    assert resultado.returncode != 0
    assert "não é um workspace do NeoPrumo" in resultado.stderr
    assert "aponta para um arquivo" in resultado.stderr
    assert "Traceback" not in resultado.stderr
    assert caminho.read_text(encoding="utf-8") == "preservado"


def test_reparo_nao_substitui_arquivo_do_usuario_que_ocupa_lugar_de_pasta(
    tmp_path, executar_cli
):
    workspace = tmp_path / "conflito"
    executar_cli("setup", workspace)
    (workspace / "Acervo").rmdir()
    conflito = workspace / "Acervo"
    conflito.write_text("isto pertence ao usuário", encoding="utf-8")

    resultado = executar_cli("doctor", workspace, "--reparar")

    assert resultado.returncode != 0
    assert conflito.is_file()
    assert conflito.read_text(encoding="utf-8") == "isto pertence ao usuário"


def test_reparo_recria_identidade_ausente(tmp_path, executar_cli):
    workspace = tmp_path / "sem-identidade"
    executar_cli("setup", workspace)
    identidade = workspace / ".neoprumo" / "workspace.json"
    identidade.unlink()

    resultado = executar_cli("doctor", workspace, "--reparar")

    assert resultado.returncode == 0
    assert json.loads(identidade.read_text(encoding="utf-8"))["layout"] == 1


def test_doctor_sem_caminho_diagnostica_workspace_ativo(tmp_path, executar_cli):
    workspace = tmp_path / "ativo"
    executar_cli("setup", workspace)
    executar_cli("workspace", "usar", workspace)

    resultado = executar_cli("doctor", "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "saudavel"
    assert dados["problemas"] == []
    assert dados["acoes"] == []
    assert dados["mensagem"] == "Tudo certo com o workspace."
    assert dados["workspace"] == str(workspace.resolve())


def test_doctor_sem_caminho_e_sem_ativo_orienta_em_stderr(executar_cli):
    resultado = executar_cli("doctor")

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "workspace ativo" in resultado.stderr.lower()
    assert "setup" in resultado.stderr
    assert "workspace usar" in resultado.stderr


def test_doctor_caminho_explicito_vence_workspace_ativo(tmp_path, executar_cli):
    ativo = tmp_path / "ativo"
    explicito = tmp_path / "explicito"
    executar_cli("setup", ativo)
    executar_cli("setup", explicito)
    executar_cli("workspace", "usar", ativo)
    (explicito / "Acervo").rmdir()

    resultado = executar_cli("doctor", explicito, "--json")

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert dados["problemas"] == ["Falta Acervo (diretorio)."]
    assert dados["workspace"] == str(explicito)


def test_doctor_sem_caminho_trata_configuracao_corrompida_sem_traceback(
    tmp_path, executar_modulo
):
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    configuracao.parent.mkdir(parents=True)
    configuracao.write_text("json quebrado\n", encoding="utf-8")

    resultado = executar_modulo("doctor")

    assert resultado.returncode == 1
    assert "workspace ativo" in resultado.stderr.lower()
    assert "setup" in resultado.stderr
    assert "workspace usar" in resultado.stderr
    assert "Traceback" not in resultado.stderr


def test_doctor_sem_caminho_informa_workspace_ativo_que_sumiu(
    tmp_path, executar_cli
):
    workspace = tmp_path / "removido"
    executar_cli("setup", workspace)
    executar_cli("workspace", "usar", workspace)
    workspace.rename(tmp_path / "movido")

    resultado = executar_cli("doctor", "--json")

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "ativo_invalido"
    assert dados["workspace"] == str(workspace.resolve())
    assert str(workspace.resolve()) in dados["problemas"][0]
    assert "workspace usar" in dados["acoes"][0]
