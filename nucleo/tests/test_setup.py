import json


def test_primeiro_setup_define_workspace_ativo(tmp_path, executar_cli):
    workspace = tmp_path / "primeiro"

    criacao = executar_cli("setup", workspace, "--json")
    consulta = executar_cli("workspace")
    diagnostico = executar_cli("doctor")

    assert criacao.returncode == 0
    dados = json.loads(criacao.stdout)
    assert dados["acoes"] == [
        "Estrutura canônica criada.",
        "Definido como workspace ativo.",
    ]
    assert "Definido como workspace ativo" in dados["mensagem"]
    assert "workspace" not in dados
    assert str(workspace.resolve()) in consulta.stdout
    assert diagnostico.returncode == 0
    assert "Tudo certo" in diagnostico.stdout


def test_setup_cria_workspace_canonico_em_diretorio_inexistente(
    tmp_path, executar_modulo
):
    workspace = tmp_path / "meu-workspace"

    resultado = executar_modulo("setup", workspace)

    assert resultado.returncode == 0
    assert "Workspace criado" in resultado.stdout
    assert (workspace / "Inbox").is_dir()
    assert (workspace / "Acervo").is_dir()
    assert (workspace / "Diario").is_dir()
    assert (workspace / "Pauta.md").read_text(encoding="utf-8") == "# Pauta\n"
    assert (workspace / "Projetos.md").read_text(encoding="utf-8") == "# Projetos\n"
    identidade = json.loads(
        (workspace / ".neoprumo" / "workspace.json").read_text(encoding="utf-8")
    )
    assert identidade["layout"] == 1
    assert identidade["criado_em"].endswith(("Z", "+00:00"))


def test_setup_recusa_diretorio_nao_vazio_sem_tocar_no_conteudo(
    tmp_path, executar_cli
):
    workspace = tmp_path / "ocupado"
    workspace.mkdir()
    arquivo = workspace / "rascunho.txt"
    arquivo.write_text("não mexa", encoding="utf-8")

    resultado = executar_cli("setup", workspace)

    assert resultado.returncode != 0
    assert "não está vazio" in resultado.stderr
    assert list(workspace.iterdir()) == [arquivo]
    assert arquivo.read_text(encoding="utf-8") == "não mexa"
    assert not (tmp_path / "configuracao-xdg" / "neoprumo" / "config.json").exists()


def test_setup_existente_informa_e_nao_altera_nada(tmp_path, executar_cli):
    workspace = tmp_path / "existente"
    metadados = workspace / ".neoprumo"
    metadados.mkdir(parents=True)
    sentinela = metadados / "do-usuario.txt"
    sentinela.write_text("preservado", encoding="utf-8")

    resultado = executar_cli("setup", workspace)

    assert resultado.returncode == 0
    assert "já existe" in resultado.stdout
    assert list(workspace.rglob("*")) == [metadados, sentinela]
    assert sentinela.read_text(encoding="utf-8") == "preservado"


def test_setup_aceita_diretorio_que_ja_existe_mas_esta_vazio(
    tmp_path, executar_cli
):
    workspace = tmp_path / "vazio"
    workspace.mkdir()

    resultado = executar_cli("setup", workspace)

    assert resultado.returncode == 0
    assert (workspace / ".neoprumo" / "workspace.json").is_file()


def test_setup_recusa_caminho_que_aponta_para_arquivo_sem_traceback(
    tmp_path, executar_modulo
):
    caminho = tmp_path / "arquivo.txt"
    caminho.write_text("conteúdo preservado", encoding="utf-8")

    resultado = executar_modulo("setup", caminho)

    assert resultado.returncode != 0
    assert "aponta para um arquivo, não para uma pasta" in resultado.stderr
    assert "Traceback" not in resultado.stderr
    assert caminho.read_text(encoding="utf-8") == "conteúdo preservado"
    assert not (tmp_path / "configuracao-xdg" / "neoprumo" / "config.json").exists()


def test_setup_recusa_arquivo_tambem_pela_cli_em_processo(tmp_path, executar_cli):
    caminho = tmp_path / "arquivo-local.txt"
    caminho.write_text("preservado", encoding="utf-8")

    resultado = executar_cli("setup", caminho, "--json")

    assert resultado.returncode == 1
    assert json.loads(resultado.stdout)["status"] == "recusado"
    assert caminho.read_text(encoding="utf-8") == "preservado"


def test_setup_nao_substitui_ponteiro_quebrado(tmp_path, executar_cli):
    workspace_antigo = tmp_path / "antigo"
    workspace_novo = tmp_path / "novo"
    executar_cli("setup", workspace_antigo)
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    conteudo_anterior = configuracao.read_bytes()
    workspace_antigo.rename(tmp_path / "antigo-fora-do-ar")

    resultado = executar_cli("setup", workspace_novo)

    assert resultado.returncode == 0
    assert configuracao.read_bytes() == conteudo_anterior
    assert "Definido como workspace ativo" not in resultado.stdout


def test_setup_preserva_configuracao_corrompida_sem_traceback(
    tmp_path, executar_modulo
):
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    configuracao.parent.mkdir(parents=True)
    conteudo_anterior = b"{json quebrado}\n"
    configuracao.write_bytes(conteudo_anterior)
    workspace = tmp_path / "criado"

    resultado = executar_modulo("setup", workspace)

    assert resultado.returncode == 0
    assert "Workspace criado" in resultado.stdout
    assert "Definido como workspace ativo" not in resultado.stdout
    assert "Traceback" not in resultado.stderr
    assert configuracao.read_bytes() == conteudo_anterior


def test_setup_ja_existente_nao_ativa_sem_configuracao(tmp_path, executar_cli):
    workspace = tmp_path / "existente-sem-config"
    (workspace / ".neoprumo").mkdir(parents=True)
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"

    resultado = executar_cli("setup", workspace)

    assert resultado.returncode == 0
    assert "já existe" in resultado.stdout
    assert not configuracao.exists()


def test_primeiro_setup_relativo_grava_ativo_absoluto(
    tmp_path, monkeypatch, executar_cli
):
    monkeypatch.chdir(tmp_path)

    resultado = executar_cli("setup", "relativo")

    assert resultado.returncode == 0
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    dados = json.loads(configuracao.read_text(encoding="utf-8"))
    assert dados["workspace_ativo"] == str((tmp_path / "relativo").resolve())


def test_primeiro_setup_expande_home_antes_de_criar_e_ativar(
    tmp_path, monkeypatch, executar_cli
):
    home_falso = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_falso))
    monkeypatch.chdir(tmp_path)

    resultado = executar_cli("setup", "~/com-tilde")

    assert resultado.returncode == 0
    workspace = home_falso / "com-tilde"
    assert (workspace / ".neoprumo").is_dir()
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    dados = json.loads(configuracao.read_text(encoding="utf-8"))
    assert dados["workspace_ativo"] == str(workspace.resolve())
    assert not (tmp_path / "~").exists()
