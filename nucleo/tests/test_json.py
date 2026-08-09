import json


def test_setup_json_entrega_estado_problemas_e_acoes(tmp_path, executar_cli):
    resultado = executar_cli("setup", tmp_path / "workspace", "--json")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "criado"
    assert dados["problemas"] == []
    assert dados["acoes"] == [
        "Estrutura canônica criada.",
        "Definido como workspace ativo.",
    ]
    assert "workspace" not in dados


def test_doctor_json_descreve_problemas_e_reparo(tmp_path, executar_cli):
    workspace = tmp_path / "workspace"
    executar_cli("setup", workspace)
    (workspace / "Diario").rmdir()

    diagnostico = executar_cli("doctor", workspace, "--json")

    assert diagnostico.returncode != 0
    dados = json.loads(diagnostico.stdout)
    assert dados["status"] == "com_problemas"
    assert dados["problemas"] == ["Falta Diario (diretorio)."]
    assert dados["acoes"] == []
    assert dados["workspace"] == str(workspace)

    reparo = executar_cli("doctor", workspace, "--reparar", "--json")

    assert reparo.returncode == 0
    dados_reparo = json.loads(reparo.stdout)
    assert dados_reparo["status"] == "reparado"
    assert dados_reparo["acoes"] == ["Diario recriado."]
    assert dados_reparo["workspace"] == str(workspace)
