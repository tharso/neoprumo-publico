import hashlib
import json


CANDIDATO = """[regra loja]
dominio = email
execucao = hibrida
predicado = remetente-dominio: x.com
politica = arquivar
origem = conversa
"""


def _commit(preview, candidato=None):
    dados = json.loads(preview.stdout)
    envelope = {"recibo": dados["decisao"], "token": dados["token"]}
    if candidato is not None:
        envelope["candidato"] = candidato
    return json.dumps(envelope)


def test_preview_nao_escreve_e_commit_publica_exatamente_o_canonico(tmp_path, executar_cli, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado"))
    workspace = tmp_path / "ws"; executar_cli("setup", workspace)
    preview = executar_cli("configuracao", "gravar", "-", "--workspace", workspace, "--json", input=CANDIDATO)
    dados = json.loads(preview.stdout)
    assert dados["status"] == "canonizada"
    assert not (workspace / "Configuracao.ini").exists()
    commit = executar_cli("configuracao", "gravar", "-", "--confirmada", "--workspace", workspace, "--json", input=_commit(preview, CANDIDATO))
    assert json.loads(commit.stdout)["status"] == "gravada"
    assert (workspace / "Configuracao.ini").read_text() == dados["canonico"]


def test_token_adulterado_e_recibo_de_outro_workspace_recusam(tmp_path, executar_cli):
    a, b = tmp_path / "a", tmp_path / "b"; executar_cli("setup", a); executar_cli("setup", b)
    preview = executar_cli("configuracao", "defaults", "--workspace", a, "--json")
    envelope = json.loads(_commit(preview)); envelope["token"] = "0" * 64
    recusa = executar_cli("configuracao", "defaults", "--confirmada", "--workspace", a, "--json", input=json.dumps(envelope))
    assert recusa.returncode == 1 and "token" in json.loads(recusa.stdout)["mensagem"]
    outro = executar_cli("configuracao", "defaults", "--confirmada", "--workspace", b, "--json", input=_commit(preview))
    assert outro.returncode == 1 and "workspace" in json.loads(outro.stdout)["mensagem"]


def test_default_proibido_e_proposta_bloqueia_gravar_e_defaults(tmp_path, executar_cli):
    workspace = tmp_path / "ws"; executar_cli("setup", workspace)
    ruim = executar_cli("configuracao", "gravar", "-", "--workspace", workspace, "--json", input="[DEFAULT]\nconfirmacao = permanente\n")
    assert ruim.returncode == 1
    preview = executar_cli("configuracao", "defaults", "--workspace", workspace, "--json")
    executar_cli("configuracao", "defaults", "--confirmada", "--workspace", workspace, "--json", input=_commit(preview))
    (workspace / "Configuracao.ini").write_text(CANDIDATO)
    for args in (("defaults",), ("gravar", "-")):
        resultado = executar_cli("configuracao", *args, "--workspace", workspace, "--json", input=CANDIDATO if "-" in args else None)
        assert resultado.returncode == 1
        assert "adote ou rejeite" in json.loads(resultado.stdout)["mensagem"]


def test_mostrar_e_seed_trazem_configuracao_aditiva(tmp_path, executar_cli):
    workspace = tmp_path / "ws"; executar_cli("setup", workspace)
    mostrar = json.loads(executar_cli("configuracao", "--workspace", workspace, "--json").stdout)
    assert mostrar["resolucao_workspace"] == "argumento"
    assert mostrar["configuracao"]["chaves"]["workspace_ativo"]["origem"] == "maquina"
    seed = json.loads(executar_cli("seed", "--workspace", workspace, "--json").stdout)
    assert seed["configuracao"] == {"estado": "nunca configurada", "avisos": []}
