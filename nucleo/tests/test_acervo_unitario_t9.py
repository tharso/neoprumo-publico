import hashlib
import json

import pytest


def criar_workspace(tmp_path, executar_cli, nome="workspace"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def criar_item(workspace, nome, conteudo=b"abc"):
    item = workspace / "Acervo" / nome
    item.write_bytes(conteudo if isinstance(conteudo, bytes) else conteudo.encode("utf-8"))
    return item


def executar(executar_cli, workspace, item, decisao):
    return executar_cli(
        "acervo", item, decisao, "--workspace", workspace, "--json"
    )


def test_unitario_recusa_decisao_desconhecida_sem_repetir_valor(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "decisao")
    item = criar_item(workspace, "abc.md")

    resultado = executar(executar_cli, workspace, item.name, "\ud800")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert "use pauta ou lixo" in dados["mensagem"].lower()
    assert "\\ud800" not in resultado.stdout.lower() and item.is_file()


@pytest.mark.parametrize("tipo", ["ausente", "arquivo", "symlink"])
def test_unitario_recusa_acervo_invalido(tipo, tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, f"acervo-{tipo}")
    acervo = workspace / "Acervo"
    acervo.rmdir()
    if tipo == "arquivo":
        acervo.write_text("ocupado", encoding="utf-8")
    elif tipo == "symlink":
        alvo = tmp_path / "fora"
        alvo.mkdir()
        acervo.symlink_to(alvo, target_is_directory=True)

    resultado = executar(executar_cli, workspace, "abc.md", "lixo")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert "Inbox" not in resultado.stdout and "inbox" not in resultado.stdout


def test_unitario_recusa_item_ausente_ambiguo_e_fora(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "localizacao")
    criar_item(workspace, "duplo.md")
    criar_item(workspace, "duplo.txt")
    externo = tmp_path / "externo.md"
    externo.write_text("fora", encoding="utf-8")
    (workspace / "Acervo" / "atalho.md").symlink_to(externo)

    for nome in ("ausente.md", "duplo", "atalho.md"):
        resultado = executar(executar_cli, workspace, nome, "lixo")
        assert resultado.returncode == 1
        assert json.loads(resultado.stdout)["status"] == "recusado"
    assert externo.read_text(encoding="utf-8") == "fora"


def test_unitario_nome_exato_vence_radical(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "exato")
    exato = criar_item(workspace, "abc", "exato")
    outro = criar_item(workspace, "abc.md", "outro")

    resultado = executar(executar_cli, workspace, "abc", "lixo")

    assert resultado.returncode == 0 and not exato.exists() and outro.is_file()


@pytest.mark.parametrize("conteudo", [b"\xff", b" \n\t"])
def test_unitario_pauta_recusa_binario_e_vazio_com_orientacao_do_acervo(
    conteudo, tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "pauta-invalida")
    item = criar_item(workspace, "abc.bin", conteudo)

    resultado = executar(executar_cli, workspace, item.name, "pauta")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert "lixo" in " ".join(dados["acoes"])
    assert "Inbox" not in resultado.stdout and "inbox" not in resultado.stdout
    assert item.read_bytes() == conteudo


@pytest.mark.parametrize("conteudo", [b"\xff", b""])
def test_unitario_lixo_aceita_binario_e_vazio(conteudo, tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "lixo-binario")
    item = criar_item(workspace, "abc.bin", conteudo)
    (workspace / ".neoprumo" / "lixo").mkdir()
    (workspace / ".neoprumo" / "lixo" / "abc.bin").write_bytes(b"anterior")

    resultado = executar(executar_cli, workspace, item.name, "lixo")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0 and dados["status"] == "excluido"
    assert (workspace / ".neoprumo" / "lixo" / "abc-2.bin").read_bytes() == conteudo


def test_unitario_e_escape_sem_digital_nem_marcador(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "escape")
    item = criar_item(workspace, "abc.md", "redepósito legítimo")
    (workspace / "Pauta.md").write_text(
        "  — acervo abc, incluído em 2026-08-04\n", encoding="utf-8"
    )

    resultado = executar(executar_cli, workspace, item.name, "pauta")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0 and dados["status"] == "incluido"
    assert (workspace / "Pauta.md").read_text(encoding="utf-8").count("— acervo abc") == 2


def test_unitario_sem_workspace_e_sintaxe(executar_cli, executar_modulo):
    sem_ativo = executar_cli("acervo", "abc.md", "pauta", "--json")
    assert sem_ativo.returncode == 1
    assert json.loads(sem_ativo.stdout)["status"] == "sem_ativo"

    sintaxe = executar_modulo("acervo", "abc.md", "--json")
    assert sintaxe.returncode == 2 and sintaxe.stdout == ""
    assert "usage:" in sintaxe.stderr


@pytest.mark.parametrize("via", ["unitario", "lote"])
@pytest.mark.parametrize("preexistente", [True, False])
def test_falha_ao_remover_do_acervo_compensa_pauta(
    via, preexistente, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import acervo_destinos
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"compensa-{via}-{preexistente}")
    item = criar_item(workspace, "abc.md", "nota")
    pauta = workspace / "Pauta.md"
    anterior = b"# anterior\n"
    if preexistente:
        pauta.write_bytes(anterior)
    else:
        pauta.unlink()
    remover_real = acervo_destinos.remover

    def falhar_origem(caminho):
        if caminho == item:
            raise PermissionError(13, "Permissão negada")
        remover_real(caminho)

    monkeypatch.setattr(acervo_destinos, "remover", falhar_origem)
    if via == "unitario":
        resultado = executar(executar_cli, workspace, item.name, "pauta")
        codigo, dados = resultado.returncode, json.loads(resultado.stdout)
    else:
        entrada = json.dumps({
            "superficie": "acervo", "pagina": "x", "respostas": [{
                "item": item.name, "decisao": "pauta",
                "digital": hashlib.sha256(b"nota").hexdigest(),
            }],
        })
        codigo, agregado, _ = operar_aplicacao(workspace, entrada)
        dados = agregado["resultados"][0]

    assert codigo == 1 and dados["status"] == "recusado"
    assert item.read_text(encoding="utf-8") == "nota"
    assert pauta.read_bytes() == anterior if preexistente else not pauta.exists()


@pytest.mark.parametrize("via", ["unitario", "lote"])
def test_falha_da_compensacao_cita_acervo_e_pauta(
    via, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import acervo_destinos
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"falha-dupla-{via}")
    item = criar_item(workspace, "abc.md", "nota")
    pauta = workspace / "Pauta.md"
    pauta.unlink()
    remover_real = acervo_destinos.remover

    def falhar(caminho):
        if caminho in (item, pauta):
            raise PermissionError(13, "Permissão negada")
        remover_real(caminho)

    monkeypatch.setattr(acervo_destinos, "remover", falhar)
    if via == "unitario":
        resultado = executar(executar_cli, workspace, item.name, "pauta")
        codigo, dados = resultado.returncode, json.loads(resultado.stdout)
    else:
        entrada = json.dumps({
            "superficie": "acervo", "pagina": "x", "respostas": [{
                "item": item.name, "decisao": "pauta",
                "digital": hashlib.sha256(b"nota").hexdigest(),
            }],
        })
        codigo, agregado, _ = operar_aplicacao(workspace, entrada)
        dados = agregado["resultados"][0]

    assert codigo == 1 and dados["status"] == "recusado"
    assert "não saiu do Acervo" in dados["mensagem"]
    assert "Pauta.md" in dados["mensagem"] and "Inbox" not in dados["mensagem"]
