import json
import re
from datetime import datetime
from pathlib import Path


def test_captura_grava_na_inbox_do_workspace_ativo(tmp_path, executar_cli):
    workspace = tmp_path / "ativo"
    executar_cli("setup", workspace)
    texto = "Comprar um sino para a bicicleta"

    resultado = executar_cli("captura", texto)

    assert resultado.returncode == 0
    itens = list((workspace / "Inbox").iterdir())
    assert len(itens) == 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{6}\.md", itens[0].name)
    assert itens[0].read_text(encoding="utf-8") == texto + "\n"
    assert itens[0].stem in resultado.stdout
    assert str(workspace.resolve()) in resultado.stdout
    assert resultado.stdout.count("\n") == 1


def test_captura_preserva_multilinha_e_acentos_byte_a_byte(tmp_path, executar_cli):
    workspace = tmp_path / "fiel"
    executar_cli("setup", workspace)
    texto = "Ideia: café no terraço\nNão esquecer o pão de queijo 🧀\n"

    resultado = executar_cli("captura", texto)

    assert resultado.returncode == 0
    item = next((workspace / "Inbox").iterdir())
    assert item.read_bytes() == texto.encode("utf-8")


def test_captura_normaliza_varias_quebras_finais_para_uma(tmp_path, executar_cli):
    workspace = tmp_path / "quebras-finais"
    executar_cli("setup", workspace)

    resultado = executar_cli("captura", "texto preservado\n\n")

    assert resultado.returncode == 0
    item = next((workspace / "Inbox").iterdir())
    assert item.read_bytes() == b"texto preservado\n"


def test_captura_hifen_le_todo_o_stdin(tmp_path, executar_cli, executar_modulo):
    workspace = tmp_path / "stdin"
    executar_cli("setup", workspace)
    texto = "primeira linha\nsegunda linha com ação"

    resultado = executar_modulo("captura", "-", input=texto)

    assert resultado.returncode == 0
    item = next((workspace / "Inbox").iterdir())
    assert item.read_text(encoding="utf-8") == texto + "\n"


def test_capturas_no_mesmo_segundo_recebem_sufixo_incremental(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import captura as modulo_captura

    class DataHoraFixa(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 4, 21, 30, 45)

    monkeypatch.setattr(modulo_captura, "datetime", DataHoraFixa)
    workspace = tmp_path / "colisao"
    executar_cli("setup", workspace)

    for texto in ("um", "dois", "três"):
        assert executar_cli("captura", texto).returncode == 0

    assert sorted(item.name for item in (workspace / "Inbox").iterdir()) == [
        "2026-08-04-213045-2.md",
        "2026-08-04-213045-3.md",
        "2026-08-04-213045.md",
    ]


def test_workspace_explicito_vence_o_configurado(tmp_path, executar_cli):
    ativo = tmp_path / "ativo"
    explicito = tmp_path / "explicito"
    executar_cli("setup", ativo)
    executar_cli("setup", explicito)

    resultado = executar_cli("captura", "vai para o outro", "--workspace", explicito)

    assert resultado.returncode == 0
    assert list((ativo / "Inbox").iterdir()) == []
    assert len(list((explicito / "Inbox").iterdir())) == 1
    assert str(explicito.resolve()) in resultado.stdout


def test_workspace_explicito_invalido_e_recusado_sem_gravar(tmp_path, executar_cli):
    caminho = tmp_path / "nao-workspace"
    caminho.mkdir()

    resultado = executar_cli("captura", "não grave", "--workspace", caminho)

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "não é um workspace" in resultado.stderr
    assert "setup" in resultado.stderr
    assert list(caminho.iterdir()) == []


def test_captura_sem_configuracao_sugere_setup(executar_cli):
    resultado = executar_cli("captura", "guarde isto")

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "workspace ativo" in resultado.stderr.lower()
    assert "setup" in resultado.stderr


def test_configuracao_apontando_para_nao_workspace_informa_caminho(
    tmp_path, executar_cli
):
    workspace = tmp_path / "deixou-de-ser"
    executar_cli("setup", workspace)
    (workspace / ".neoprumo").rename(workspace / ".marca-removida")

    resultado = executar_cli("captura", "não grave")

    assert resultado.returncode == 1
    assert str(workspace.resolve()) in resultado.stderr
    assert "workspace" in resultado.stderr.lower()
    assert list((workspace / "Inbox").iterdir()) == []


def test_captura_recusa_texto_vazio_sem_gravar(tmp_path, executar_cli):
    workspace = tmp_path / "vazio"
    executar_cli("setup", workspace)

    resultado = executar_cli("captura", " \n\t ")

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "capturar nada" in resultado.stderr.lower()
    assert list((workspace / "Inbox").iterdir()) == []


def test_captura_recria_inbox_ausente_e_avisa(tmp_path, executar_cli):
    workspace = tmp_path / "sem-inbox"
    executar_cli("setup", workspace)
    (workspace / "Inbox").rmdir()

    resultado = executar_cli("captura", "resgate", "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "capturado"
    assert dados["acoes"] == [
        "A pasta Inbox estava faltando e foi recriada. Rode doctor para conferir o workspace."
    ]
    assert (workspace / "Inbox" / f"{dados['id']}.md").is_file()


def test_captura_avisa_inbox_recriada_na_saida_humana_em_uma_linha(
    tmp_path, executar_cli
):
    workspace = tmp_path / "aviso-humano"
    executar_cli("setup", workspace)
    (workspace / "Inbox").rmdir()

    resultado = executar_cli("captura", "resgate humano")

    assert resultado.returncode == 0
    assert "Inbox estava faltando e foi recriada" in resultado.stdout
    assert "doctor" in resultado.stdout
    assert resultado.stdout.count("\n") == 1


def test_captura_json_entrega_envelope_e_identidade_do_item(tmp_path, executar_cli):
    workspace = tmp_path / "json"
    executar_cli("setup", workspace)

    resultado = executar_cli("captura", "em formato máquina", "--json")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "capturado"
    assert dados["problemas"] == []
    assert dados["acoes"] == []
    assert dados["workspace"] == str(workspace.resolve())
    assert dados["id"] == data_do_item(dados["item"])
    assert dados["item"] == str(workspace / "Inbox" / f"{dados['id']}.md")


def test_recusa_em_json_tambem_tem_envelope_valido(tmp_path, executar_cli):
    workspace = tmp_path / "recusa-json"
    executar_cli("setup", workspace)

    resultado = executar_cli("captura", "   ", "--json")

    assert resultado.returncode == 1
    assert resultado.stderr == ""
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado"
    assert dados["problemas"]
    assert dados["acoes"]
    assert dados["workspace"] == str(workspace.resolve())
    assert dados["item"] is None
    assert dados["id"] is None


def test_python_m_neoprumo_executa_captura(tmp_path, executar_cli, executar_modulo):
    workspace = tmp_path / "entrypoint"
    executar_cli("setup", workspace)

    resultado = executar_modulo("captura", "pelo módulo", "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "capturado"
    assert (workspace / "Inbox" / f"{dados['id']}.md").is_file()


def data_do_item(caminho):
    return Path(caminho).stem
