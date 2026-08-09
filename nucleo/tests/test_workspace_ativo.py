import json
import os
from pathlib import Path

import pytest


def test_workspace_usar_define_ativo_e_grava_config(tmp_path, executar_cli):
    workspace = tmp_path / "principal"
    assert executar_cli("setup", workspace).returncode == 0

    resultado = executar_cli("workspace", "usar", workspace)

    assert resultado.returncode == 0
    assert str(workspace.resolve()) in resultado.stdout
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    assert configuracao.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(configuracao.read_text(encoding="utf-8")) == {
        "workspace_ativo": str(workspace.resolve())
    }


def test_workspace_mostra_ativo_valido_em_json(tmp_path, executar_cli):
    workspace = tmp_path / "principal"
    executar_cli("setup", workspace)
    executar_cli("workspace", "usar", workspace)

    resultado = executar_cli("workspace", "--json")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    dados = json.loads(resultado.stdout)
    assert dados == {
        "status": "ativo",
        "problemas": [],
        "acoes": [],
        "mensagem": f"Workspace ativo: {workspace.resolve()}",
        "workspace": str(workspace.resolve()),
    }


def test_workspace_sem_configuracao_orienta_como_criar_ou_apontar(executar_cli):
    resultado = executar_cli("workspace")

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "nenhum workspace ativo" in resultado.stderr.lower()
    assert "setup" in resultado.stderr
    assert "workspace usar" in resultado.stderr


def test_workspace_informa_quando_caminho_ativo_sumiu(tmp_path, executar_cli):
    workspace = tmp_path / "removido"
    executar_cli("setup", workspace)
    executar_cli("workspace", "usar", workspace)
    workspace.rename(tmp_path / "movido")

    resultado = executar_cli("workspace")

    assert resultado.returncode == 1
    assert str(workspace.resolve()) in resultado.stderr
    assert "não existe" in resultado.stderr
    assert "workspace usar" in resultado.stderr


def test_workspace_informa_quando_ativo_deixou_de_ser_workspace(
    tmp_path, executar_cli
):
    workspace = tmp_path / "sem-marca"
    executar_cli("setup", workspace)
    executar_cli("workspace", "usar", workspace)
    (workspace / ".neoprumo").rename(workspace / ".identidade-removida")

    resultado = executar_cli("workspace")

    assert resultado.returncode == 1
    assert str(workspace.resolve()) in resultado.stderr
    assert "não é mais um workspace" in resultado.stderr
    assert "setup --readotar" in resultado.stderr


def test_workspace_trata_configuracao_corrompida_sem_traceback(executar_modulo):
    configuracao = Path(os.environ["XDG_CONFIG_HOME"]) / "neoprumo" / "config.json"
    configuracao.parent.mkdir(parents=True)
    configuracao.write_text("{isto não é json}\n", encoding="utf-8")

    resultado = executar_modulo("workspace")

    assert resultado.returncode == 1
    assert "configuração" in resultado.stderr.lower()
    assert "setup" in resultado.stderr
    assert "workspace usar" in resultado.stderr
    assert "Traceback" not in resultado.stderr


def test_workspace_usar_troca_o_ativo(tmp_path, executar_cli):
    primeiro = tmp_path / "primeiro"
    segundo = tmp_path / "segundo"
    executar_cli("setup", primeiro)
    executar_cli("setup", segundo)
    executar_cli("workspace", "usar", primeiro)

    troca = executar_cli("workspace", "usar", segundo)
    consulta = executar_cli("workspace")

    assert troca.returncode == 0
    assert str(segundo.resolve()) in troca.stdout
    assert str(segundo.resolve()) in consulta.stdout
    assert str(primeiro.resolve()) not in consulta.stdout


def test_workspace_usar_converte_caminho_relativo_em_absoluto(
    tmp_path, monkeypatch, executar_cli
):
    workspace = tmp_path / "relativo"
    executar_cli("setup", workspace)
    monkeypatch.chdir(tmp_path)

    resultado = executar_cli("workspace", "usar", "relativo", "--json")

    assert resultado.returncode == 0
    assert json.loads(resultado.stdout)["workspace"] == str(workspace.resolve())


@pytest.mark.parametrize("posicao", ["antes", "depois"])
def test_workspace_usar_respeita_json_antes_ou_depois_do_subcomando(
    posicao, tmp_path, executar_cli
):
    workspace = tmp_path / posicao
    executar_cli("setup", workspace)
    argumentos = (
        ("workspace", "--json", "usar", workspace)
        if posicao == "antes"
        else ("workspace", "usar", workspace, "--json")
    )

    resultado = executar_cli(*argumentos)

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "definido"
    assert dados["workspace"] == str(workspace.resolve())


@pytest.mark.parametrize("tipo", ["inexistente", "arquivo", "sem_marca"])
def test_workspace_usar_recusa_nao_workspace_e_preserva_configuracao(
    tipo, tmp_path, executar_cli
):
    valido = tmp_path / "valido"
    executar_cli("setup", valido)
    executar_cli("workspace", "usar", valido)
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    conteudo_anterior = configuracao.read_text(encoding="utf-8")
    candidato = tmp_path / tipo
    if tipo == "arquivo":
        candidato.write_text("do usuário", encoding="utf-8")
    elif tipo == "sem_marca":
        candidato.mkdir()

    resultado = executar_cli("workspace", "usar", candidato)

    assert resultado.returncode == 1
    if tipo == "arquivo":
        assert "aponta para um arquivo" in resultado.stderr
    else:
        assert "setup" in resultado.stderr
    assert configuracao.read_text(encoding="utf-8") == conteudo_anterior


def test_workspace_usa_fallback_no_home_quando_xdg_esta_ausente(
    tmp_path, monkeypatch, executar_cli
):
    home_falso = tmp_path / "home-falso"
    workspace = tmp_path / "workspace"
    executar_cli("setup", workspace)
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(home_falso))

    resultado = executar_cli("workspace", "usar", workspace)

    assert resultado.returncode == 0
    configuracao = home_falso / ".config" / "neoprumo" / "config.json"
    assert json.loads(configuracao.read_text(encoding="utf-8"))["workspace_ativo"] == str(
        workspace.resolve()
    )


def test_workspace_usa_fallback_no_home_quando_xdg_esta_vazio(
    tmp_path, monkeypatch, executar_cli
):
    home_falso = tmp_path / "outro-home"
    workspace = tmp_path / "workspace-vazio"
    executar_cli("setup", workspace)
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setenv("HOME", str(home_falso))

    resultado = executar_cli("workspace", "usar", workspace)

    assert resultado.returncode == 0
    assert (home_falso / ".config" / "neoprumo" / "config.json").is_file()


def test_setup_nao_rouba_workspace_ativo_existente(tmp_path, executar_cli):
    ativo = tmp_path / "ativo"
    novo = tmp_path / "novo"
    executar_cli("setup", ativo)

    criacao = executar_cli("setup", novo, "--json")
    consulta = executar_cli("workspace")

    assert criacao.returncode == 0
    assert json.loads(criacao.stdout)["acoes"] == ["Estrutura canônica criada."]
    assert str(ativo.resolve()) in consulta.stdout
    assert str(novo.resolve()) not in consulta.stdout


def test_workspace_trata_configuracao_sem_chave_como_sem_ativo(
    tmp_path, executar_cli
):
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo" / "config.json"
    configuracao.parent.mkdir(parents=True)
    configuracao.write_text('{"outra_chave": true}\n', encoding="utf-8")

    resultado = executar_cli("workspace", "--json")

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "sem_ativo"
    assert dados["workspace"] is None
    assert "configuração" in dados["mensagem"].lower()
