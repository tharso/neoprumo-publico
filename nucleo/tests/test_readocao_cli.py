import json
import os
from pathlib import Path
import builtins

import pytest


def _configuracao():
    return Path(os.environ["XDG_CONFIG_HOME"]) / "neoprumo" / "config.json"


def _fotografia(raiz):
    return {
        str(item.relative_to(raiz)): (
            item.stat().st_mtime_ns,
            item.read_bytes() if item.is_file() else None,
        )
        for item in raiz.rglob("*")
    }


def test_readocao_reconstroi_identidade_preserva_conteudo_e_ativa(
    tmp_path, executar_cli
):
    workspace = tmp_path / "recuperado"
    (workspace / "Inbox").mkdir(parents=True)
    (workspace / "Acervo").mkdir()
    (workspace / "Diario").mkdir()
    (workspace / "Pauta.md").write_bytes(b"# pauta do dono\n- [ ] intacta\x00")
    (workspace / "Projetos.md").write_bytes(b"# projetos do dono\n")
    (workspace / "Inbox" / "ideia.md").write_bytes(b"ideia\xff")
    (workspace / "Acervo" / "lembranca.md").write_bytes(b"lembran\xe7a")
    antes = _fotografia(workspace)

    resultado = executar_cli("setup", "--readotar", workspace, "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "readotado"
    assert dados["problemas"] == []
    assert "workspace" not in dados
    assert ".neoprumo/ criada." in dados["acoes"]
    assert ".neoprumo/workspace.json recriado." in dados["acoes"]
    assert "Definido como workspace ativo." in dados["acoes"]
    assert resultado.stderr == ""
    assert _fotografia(workspace).items() >= antes.items()
    for nome, estado in antes.items():
        assert _fotografia(workspace)[nome] == estado
    assert json.loads(_configuracao().read_text(encoding="utf-8"))["workspace_ativo"] == str(
        workspace.resolve()
    )


@pytest.mark.parametrize(
    ("sinais", "forcar", "status"),
    [
        (("Pauta.md",), False, "readotado"),
        (("Inbox", "Acervo"), False, "readotado"),
        (("Inbox",), False, "recusado"),
        (("Inbox",), True, "readotado"),
    ],
)
def test_readocao_aplica_regua_de_sinal(tmp_path, executar_cli, sinais, forcar, status):
    workspace = tmp_path / "sinais"
    workspace.mkdir()
    for nome in sinais:
        item = workspace / nome
        item.mkdir() if "." not in nome else item.write_text("do dono", encoding="utf-8")
    argumentos = ["setup", "--readotar"]
    if forcar:
        argumentos.append("--forcar")
    argumentos.extend([workspace, "--json"])

    resultado = executar_cli(*argumentos)
    dados = json.loads(resultado.stdout)

    assert dados["status"] == status
    assert resultado.returncode == (0 if status == "readotado" else 1)
    if status == "recusado":
        assert "--forcar" in dados["acoes"][0]
        assert "seriam criados" in dados["mensagem"]
        assert not (workspace / ".neoprumo").exists()


def test_readocao_de_pasta_vazia_usa_status_criado(tmp_path, executar_cli):
    workspace = tmp_path / "vazio"
    workspace.mkdir()

    resultado = executar_cli("setup", "--readotar", workspace, "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "criado"
    assert dados["acoes"][0] == "Estrutura canônica criada."


@pytest.mark.parametrize("tipo", ["saudavel", "incompleto", "simbolico"])
def test_readocao_estados_reconhecidos_nao_sofrem_mutacao(
    tipo, tmp_path, executar_cli
):
    workspace = tmp_path / tipo
    if tipo in {"saudavel", "incompleto"}:
        executar_cli("setup", workspace)
        if tipo == "incompleto":
            (workspace / "Acervo").rmdir()
    else:
        workspace.mkdir()
        alvo = tmp_path / "alvo"
        alvo.mkdir()
        (workspace / ".neoprumo").symlink_to(alvo, target_is_directory=True)
    antes = _fotografia(workspace)

    resultado = executar_cli("setup", "--readotar", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert dados["status"] == ("ja_existe" if tipo == "saudavel" else "recusado")
    assert resultado.returncode == (0 if tipo == "saudavel" else 1)
    assert _fotografia(workspace) == antes
    if tipo == "incompleto":
        assert "doctor --reparar" in dados["acoes"][0]


@pytest.mark.parametrize("tipo", ["arquivo", "inexistente"])
def test_readocao_recusa_caminho_inaplicavel_em_portugues(
    tipo, tmp_path, executar_modulo
):
    caminho = tmp_path / tipo
    if tipo == "arquivo":
        caminho.write_text("intacto", encoding="utf-8")

    resultado = executar_modulo("setup", "--readotar", caminho)

    assert resultado.returncode == 1
    assert "Traceback" not in resultado.stderr
    assert ("arquivo" if tipo == "arquivo" else "não existe") in resultado.stderr


def test_forcar_sem_readotar_e_erro_legivel_do_parser(tmp_path, executar_modulo):
    resultado = executar_modulo("setup", "--forcar", tmp_path / "destino")

    assert resultado.returncode == 2
    assert "--forcar" in resultado.stderr
    assert "Traceback" not in resultado.stderr


def test_falha_em_conteudo_deixa_marca_por_ultimo_e_orienta_repetir(
    tmp_path, executar_cli, monkeypatch
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "parcial"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")
    original = modulo.criar_item_ausente

    def falhar(raiz, nome, tipo):
        if nome == "Assuntos":
            raise PermissionError("system text")
        return original(raiz, nome, tipo)

    monkeypatch.setattr(modulo, "criar_item_ausente", falhar)

    resultado = executar_cli("setup", "--readotar", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    assert dados["status"] == "com_problemas"
    assert len(dados["acoes"]) == len(set(dados["acoes"]))
    assert any("Assuntos" in problema for problema in dados["problemas"])
    assert "setup --readotar" in dados["mensagem"]
    assert not (workspace / ".neoprumo").exists()
    assert not _configuracao().exists()
    seed = executar_cli("seed", "--workspace", workspace)
    assert seed.returncode == 1


def test_falha_em_conteudo_forcado_preserva_forcar_na_rota(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import estrutura_workspace

    workspace = tmp_path / "forcado"
    workspace.mkdir()
    (workspace / "Inbox").mkdir()
    original = estrutura_workspace._conteudo_inicial

    def falhar(nome):
        if nome == "Pauta.md":
            raise OSError("system text")
        return original(nome)

    monkeypatch.setattr(estrutura_workspace, "_conteudo_inicial", falhar)

    resultado = executar_cli(
        "setup", "--readotar", "--forcar", workspace, "--json"
    )

    assert resultado.returncode == 1
    assert "setup --readotar --forcar" in json.loads(resultado.stdout)["mensagem"]


def test_marca_que_aparece_durante_falha_muda_rota_para_doctor(
    tmp_path, executar_cli, monkeypatch
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "marca-cruzada"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")
    original = modulo.criar_item_ausente

    def falhar_depois_da_marca(raiz, nome, tipo):
        if nome == "Assuntos":
            (Path(raiz) / ".neoprumo").mkdir()
            raise PermissionError("system text")
        return original(raiz, nome, tipo)

    monkeypatch.setattr(modulo, "criar_item_ausente", falhar_depois_da_marca)

    resultado = executar_cli("setup", "--readotar", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    assert "doctor --reparar" in dados["mensagem"]
    assert "setup --readotar" not in dados["mensagem"]


def test_troca_da_marca_por_symlink_depois_da_checagem_e_reportada(
    tmp_path, executar_cli, monkeypatch
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "troca"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")
    fora = tmp_path / "fora"
    fora.mkdir()
    original = modulo.tem_marca_real
    chamadas = 0

    def trocar_depois_de_observar(raiz):
        nonlocal chamadas
        chamadas += 1
        real = original(raiz)
        if chamadas == 1 and real:
            (Path(raiz) / ".neoprumo").rmdir()
            (Path(raiz) / ".neoprumo").symlink_to(fora, target_is_directory=True)
        return real

    monkeypatch.setattr(modulo, "tem_marca_real", trocar_depois_de_observar)

    resultado = executar_cli("setup", "--readotar", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    assert dados["status"] == "com_problemas"
    assert any("pasta real" in problema for problema in dados["problemas"])
    assert not _configuracao().exists()


def test_falha_na_identidade_orienta_doctor_e_reparo_fecha_layout(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import estrutura_workspace

    workspace = tmp_path / "identidade"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")
    original = estrutura_workspace._conteudo_inicial

    def falhar(nome):
        if nome == ".neoprumo/workspace.json":
            raise OSError("system text")
        return original(nome)

    monkeypatch.setattr(estrutura_workspace, "_conteudo_inicial", falhar)
    resultado = executar_cli("setup", "--readotar", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    assert "doctor --reparar" in dados["mensagem"]
    identidade = workspace / ".neoprumo" / "workspace.json"
    assert identidade.exists()
    identidade.unlink()
    monkeypatch.setattr(estrutura_workspace, "_conteudo_inicial", original)
    reparo = executar_cli("doctor", "--reparar", workspace)
    assert reparo.returncode == 0
    assert json.loads(identidade.read_text(encoding="utf-8"))["layout"] == 1


def test_marca_arquivo_produz_falha_parcial_com_acoes_e_problemas(
    tmp_path, executar_cli
):
    workspace = tmp_path / "marca-arquivo"
    workspace.mkdir()
    marca = workspace / ".neoprumo"
    marca.write_bytes(b"do dono\x00")

    resultado = executar_cli("setup", "--readotar", workspace)

    assert resultado.returncode == 1
    assert "recriado" in resultado.stderr
    assert ".neoprumo" in resultado.stderr
    assert marca.read_bytes() == b"do dono\x00"


def test_readocao_nao_rouba_ponteiro_existente(tmp_path, executar_cli):
    antigo = tmp_path / "antigo"
    executar_cli("setup", antigo)
    configuracao = _configuracao()
    antes = configuracao.read_bytes()
    workspace = tmp_path / "recuperado"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")

    resultado = executar_cli("setup", "--readotar", workspace, "--json")

    assert resultado.returncode == 0
    assert configuracao.read_bytes() == antes
    assert "Definido como workspace ativo." not in json.loads(resultado.stdout)["acoes"]


@pytest.mark.parametrize("estado", ["quebrado", "corrompido"])
def test_readocao_preserva_ponteiro_preexistente_mesmo_invalido(
    estado, tmp_path, executar_cli
):
    configuracao = _configuracao()
    configuracao.parent.mkdir(parents=True)
    conteudo = (
        json.dumps({"workspace_ativo": str(tmp_path / "sumiu")}) + "\n"
        if estado == "quebrado"
        else "{json quebrado}\n"
    )
    configuracao.write_text(conteudo, encoding="utf-8")
    workspace = tmp_path / estado
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")

    resultado = executar_cli("setup", "--readotar", workspace, "--json")

    assert resultado.returncode == 0
    assert configuracao.read_text(encoding="utf-8") == conteudo
    assert "Definido como workspace ativo." not in json.loads(resultado.stdout)["acoes"]


def test_setup_comum_trata_configuracao_que_aparece_na_corrida_como_preexistente(
    tmp_path, executar_cli, monkeypatch
):
    import builtins

    workspace = tmp_path / "setup-concorrente"
    configuracao = _configuracao()
    original = builtins.open
    concorrente = b'{"workspace_ativo":"da-nuvem"}\n'

    def aparecer(caminho, modo="r", *args, **kwargs):
        if Path(caminho) == configuracao and modo == "x":
            configuracao.write_bytes(concorrente)
        return original(caminho, modo, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", aparecer)

    resultado = executar_cli("setup", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 0
    assert dados["acoes"] == ["Estrutura canônica criada."]
    assert "Definido como workspace ativo" not in dados["mensagem"]
    assert configuracao.read_bytes() == concorrente


def test_falha_do_ponteiro_nao_vira_acao_e_orienta_workspace_usar(
    tmp_path, executar_cli, monkeypatch
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "ponteiro"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")

    def falhar(_workspace):
        raise PermissionError("system text")

    monkeypatch.setattr(modulo, "adotar_se_primeiro", falhar)
    resultado = executar_cli("setup", "--readotar", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    assert dados["status"] == "com_problemas"
    assert "workspace usar" in dados["mensagem"]
    assert all("workspace usar" not in acao for acao in dados["acoes"])
    assert not dados["problemas"] == []


def test_erro_do_ponteiro_com_configuracao_final_correta_reconstroi_acao(
    tmp_path, executar_cli, monkeypatch
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "releitura"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")

    def gravar_e_falhar(caminho):
        configuracao = _configuracao()
        configuracao.parent.mkdir(parents=True)
        configuracao.write_text(
            json.dumps({"workspace_ativo": str(Path(caminho).resolve())}) + "\n",
            encoding="utf-8",
        )
        raise PermissionError("system text")

    monkeypatch.setattr(modulo, "adotar_se_primeiro", gravar_e_falhar)
    resultado = executar_cli("setup", "--readotar", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 0
    assert dados["problemas"] == []
    assert "Definido como workspace ativo." in dados["acoes"]


def test_setup_comum_recusa_nao_vazio_com_acao_do_estado(tmp_path, executar_cli):
    workspace = tmp_path / "ocupado"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")

    resultado = executar_cli("setup", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    assert dados["status"] == "recusado"
    assert "setup --readotar" in dados["acoes"][0]


def test_setup_comum_captura_falha_estrutural_sem_traceback(
    tmp_path, monkeypatch, capsys
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "falha"
    original = modulo.criar_item_ausente

    def falhar(raiz, nome, tipo):
        if nome == "Pauta.md":
            raise PermissionError("system text")
        return original(raiz, nome, tipo)

    monkeypatch.setattr(modulo, "criar_item_ausente", falhar)
    resultado = modulo.configurar(workspace, usar_json=True)
    dados = json.loads(capsys.readouterr().out)

    assert resultado == 1
    assert dados["status"] == "com_problemas"
    assert "setup --readotar" in dados["mensagem"]
    assert workspace.exists()
    assert not (workspace / ".neoprumo").exists()


def test_setup_comum_orienta_setup_puro_quando_mkdir_da_raiz_falha(
    tmp_path, monkeypatch, capsys
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "raiz-bloqueada"
    original = Path.mkdir

    def falhar(caminho, *args, **kwargs):
        if caminho == workspace:
            raise PermissionError("system text")
        return original(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", falhar)

    codigo = modulo.configurar(workspace, usar_json=True)
    dados = json.loads(capsys.readouterr().out)

    assert codigo == 1
    assert "repita setup" in dados["mensagem"].lower()
    assert "--readotar" not in dados["mensagem"]


def test_setup_comum_orienta_doctor_quando_marca_aparece_na_falha(
    tmp_path, monkeypatch, capsys
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "marca-na-falha"
    original = modulo.criar_item_ausente

    def falhar(raiz, nome, tipo):
        if nome == "Pauta.md":
            (Path(raiz) / ".neoprumo").mkdir()
            raise PermissionError("system text")
        return original(raiz, nome, tipo)

    monkeypatch.setattr(modulo, "criar_item_ausente", falhar)

    codigo = modulo.configurar(workspace, usar_json=True)
    dados = json.loads(capsys.readouterr().out)

    assert codigo == 1
    assert "doctor --reparar" in dados["mensagem"]


@pytest.mark.parametrize("modo", ["setup", "readocao"])
@pytest.mark.parametrize("item", ["Inbox", "Pauta.md"])
def test_falha_antes_da_criacao_guarda_causa_sem_duplicar_falta(
    modo, item, tmp_path, executar_cli, monkeypatch
):
    workspace = tmp_path / f"{modo}-{item}"
    if modo == "readocao":
        workspace.mkdir()
        sinal = "Pauta.md" if item == "Inbox" else "Projetos.md"
        (workspace / sinal).write_text("sinal do dono", encoding="utf-8")

    if item == "Inbox":
        original_mkdir = Path.mkdir

        def negar_pasta(caminho, *args, **kwargs):
            if caminho == workspace / "Inbox":
                raise PermissionError("acesso negado pelo teste")
            return original_mkdir(caminho, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", negar_pasta)
    else:
        original_open = builtins.open

        def negar_arquivo(caminho, modo_abertura="r", *args, **kwargs):
            if Path(caminho) == workspace / "Pauta.md" and modo_abertura == "x":
                raise PermissionError("acesso negado pelo teste")
            return original_open(caminho, modo_abertura, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", negar_arquivo)

    argumentos = ["setup"]
    if modo == "readocao":
        argumentos.append("--readotar")
    resultado = executar_cli(*argumentos, workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    problemas_do_item = [problema for problema in dados["problemas"] if item in problema]
    assert len(problemas_do_item) == 1
    assert "Não foi possível criar" in problemas_do_item[0]
    assert "acesso negado pelo teste" in problemas_do_item[0]
    assert all(not problema.startswith(f"Falta {item} ") for problema in dados["problemas"])


def test_setup_comum_reconstroi_ativacao_confirmada_apos_erro(
    tmp_path, executar_cli, monkeypatch
):
    import neoprumo.workspace as modulo

    workspace = tmp_path / "setup-releitura"

    def gravar_e_falhar(caminho):
        configuracao = _configuracao()
        configuracao.parent.mkdir(parents=True)
        configuracao.write_text(
            json.dumps({"workspace_ativo": str(Path(caminho).resolve())}) + "\n",
            encoding="utf-8",
        )
        raise PermissionError("acesso negado pelo teste")

    monkeypatch.setattr(modulo, "adotar_se_primeiro", gravar_e_falhar)

    resultado = executar_cli("setup", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 0
    assert dados["status"] == "criado"
    assert dados["problemas"] == []
    assert "Definido como workspace ativo." in dados["acoes"]


def test_setup_comum_nao_chama_pasta_ilegivel_de_nao_vazia(
    tmp_path, executar_cli, monkeypatch
):
    workspace = tmp_path / "ilegivel"
    workspace.mkdir()
    original = Path.iterdir

    def negar_listagem(caminho):
        if caminho == workspace:
            raise PermissionError("acesso negado pelo teste")
        return original(caminho)

    monkeypatch.setattr(Path, "iterdir", negar_listagem)

    resultado = executar_cli("setup", workspace, "--json")
    dados = json.loads(resultado.stdout)

    assert resultado.returncode == 1
    assert dados["problemas"] == ["Não foi possível ler o caminho."]
    assert "Não foi possível ler" in dados["mensagem"]
    assert "não está vazio" not in dados["mensagem"]


@pytest.mark.parametrize(
    ("argumentos", "status"),
    [
        (("setup", "--readotar"), "readotado"),
        (("setup", "--readotar", "--forcar"), "criado"),
    ],
)
def test_json_da_readocao_e_documento_unico_sem_workspace(
    argumentos, status, tmp_path, executar_modulo
):
    workspace = tmp_path / "ação"
    workspace.mkdir()
    if "--forcar" not in argumentos:
        (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")

    resultado = executar_modulo(*argumentos, workspace, "--json")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.endswith("\n") and resultado.stdout.count("\n") == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == status
    assert "workspace" not in dados
    assert "ação" in resultado.stdout
