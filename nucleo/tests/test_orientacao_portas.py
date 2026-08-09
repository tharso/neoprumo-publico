import json
import os
from pathlib import Path

import pytest

from neoprumo.orientacao import orientar


def _apontar(workspace):
    configuracao = Path(os.environ["XDG_CONFIG_HOME"]) / "neoprumo" / "config.json"
    configuracao.parent.mkdir(parents=True, exist_ok=True)
    configuracao.write_text(
        json.dumps({"workspace_ativo": str(workspace)}) + "\n",
        encoding="utf-8",
    )


def _dados(resultado):
    return json.loads(resultado.stdout)


def test_doctor_e_workspace_usar_repetem_acao_do_classificador(
    tmp_path, executar_cli
):
    workspace = tmp_path / "perdeu-marca"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")
    esperada = orientar(workspace, "caminho_explicito")["acoes"]

    doctor = executar_cli("doctor", workspace, "--json")
    definir = executar_cli("workspace", "usar", workspace, "--json")

    assert _dados(doctor)["acoes"] == esperada
    assert _dados(definir)["acoes"] == esperada


def test_portas_de_workspace_ativo_repetem_acao_do_classificador(
    tmp_path, executar_cli
):
    workspace = tmp_path / "ativo-sem-marca"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")
    _apontar(workspace)
    esperada = orientar(workspace, "ponteiro_ativo")["acoes"]

    resultados = [
        executar_cli("workspace", "--json"),
        executar_cli("captura", "texto", "--json"),
        executar_cli("despacho", "item", "lixo", "--json"),
        executar_cli("superficie", "despacho", "--json"),
    ]

    assert all(_dados(resultado)["acoes"] == esperada for resultado in resultados)


def test_mostrar_ativo_inexistente_usa_contexto_de_ponteiro(
    tmp_path, executar_cli
):
    workspace = tmp_path / "sumiu"
    _apontar(workspace)

    resultado = executar_cli("workspace", "--json")

    assert _dados(resultado)["acoes"] == orientar(
        workspace, "ponteiro_ativo"
    )["acoes"]


def test_portas_de_caminho_explicito_repetem_acao_do_classificador(
    tmp_path, executar_cli
):
    workspace = tmp_path / "explicito"
    workspace.mkdir()
    (workspace / "Inbox").mkdir()
    esperada = orientar(workspace.resolve(), "caminho_explicito")["acoes"]

    resultados = [
        executar_cli("captura", "texto", "--workspace", workspace, "--json"),
        executar_cli("seed", "--workspace", workspace, "--json"),
        executar_cli(
            "despacho", "item", "lixo", "--workspace", workspace, "--json"
        ),
        executar_cli(
            "superficie", "despacho", "--workspace", workspace, "--json"
        ),
    ]

    assert all(_dados(resultado)["acoes"] == esperada for resultado in resultados)


def test_hook_injeta_acao_verdadeira_do_classificador(tmp_path, executar_cli):
    workspace = tmp_path / "hook"
    workspace.mkdir()
    (workspace / "Pauta.md").write_text("sinal", encoding="utf-8")
    _apontar(workspace)

    resultado = executar_cli("sonda", "--hook")
    contexto = _dados(resultado)["hookSpecificOutput"]["additionalContext"]

    assert orientar(workspace, "ponteiro_ativo")["acoes"][0] in contexto


@pytest.mark.parametrize("comando", ["workspace", "doctor", "seed"])
def test_marca_simbolica_e_recusada_em_todo_nucleo(
    comando, tmp_path, executar_cli
):
    workspace = tmp_path / comando
    workspace.mkdir()
    alvo = tmp_path / f"alvo-{comando}"
    alvo.mkdir()
    (workspace / ".neoprumo").symlink_to(alvo, target_is_directory=True)
    esperada = orientar(
        workspace.resolve(),
        "ponteiro_ativo" if comando == "workspace" else "caminho_explicito",
    )["acoes"]
    if comando == "workspace":
        _apontar(workspace.resolve())
        resultado = executar_cli("workspace", "--json")
    elif comando == "doctor":
        resultado = executar_cli("doctor", workspace, "--json")
    else:
        resultado = executar_cli("seed", "--workspace", workspace, "--json")

    assert resultado.returncode == 1
    assert _dados(resultado)["acoes"] == esperada
    assert "atalho" in _dados(resultado)["mensagem"]


def test_reproducao_da_issue_fecha_encadeamento(tmp_path, executar_cli):
    workspace = tmp_path / "issue-42"
    executar_cli("setup", workspace)
    (workspace / "Pauta.md").write_text("# pauta real\n", encoding="utf-8")
    identidade = workspace / ".neoprumo" / "workspace.json"
    identidade.unlink()
    (workspace / ".neoprumo").rmdir()

    esperada = orientar(workspace, "caminho_explicito")["acoes"][0]
    primeiro = executar_cli("doctor", workspace, "--json")
    acao = _dados(primeiro)["acoes"][0]
    readocao = executar_cli("setup", "--readotar", workspace)
    segundo = executar_cli("doctor", workspace)

    assert acao == esperada
    assert readocao.returncode == 0
    assert segundo.returncode == 0
    assert "Tudo certo" in segundo.stdout


def test_orientacao_de_raiz_nao_e_copiada_fora_do_modulo():
    raiz = Path(__file__).parents[1] / "neoprumo"
    frase_antiga = "Execute setup para criar um workspace."
    ocorrencias = []
    for arquivo in raiz.glob("*.py"):
        if arquivo.name == "orientacao.py":
            continue
        if frase_antiga in arquivo.read_text(encoding="utf-8"):
            ocorrencias.append(arquivo.name)

    assert ocorrencias == []
