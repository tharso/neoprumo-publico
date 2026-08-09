import builtins
import json

from neoprumo import __main__


def test_python_antigo_falha_antes_de_importar_cli(monkeypatch, capsys):
    importar_original = builtins.__import__

    def impedir_cli(nome, *args, **kwargs):
        if nome == "cli":
            raise AssertionError("a CLI não deveria ter sido importada")
        return importar_original(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", impedir_cli)

    codigo = __main__.main((3, 9, 6))

    assert codigo != 0
    assert "Python 3.10" in capsys.readouterr().err


def test_python_antigo_no_hook_entrega_erro_no_envelope(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["neoprumo", "sonda", "--hook"])

    codigo = __main__.main((3, 9, 6))

    captura = capsys.readouterr()
    assert codigo == 0
    assert captura.err == ""
    envelope = json.loads(captura.out)
    saida = envelope["hookSpecificOutput"]
    assert saida["hookEventName"] == "SessionStart"
    assert "Python 3.10" in saida["additionalContext"]
    assert "3.9.6" in saida["additionalContext"]


def test_python_antigo_fora_do_hook_preserva_falha(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["neoprumo", "sonda"])

    codigo = __main__.main((3, 9, 6))

    captura = capsys.readouterr()
    assert codigo != 0
    assert captura.out == ""
    assert "Python 3.10" in captura.err


def test_python_compativel_executa_cli(tmp_path, monkeypatch):
    workspace = tmp_path / "pelo-entrypoint"
    monkeypatch.setattr(
        "sys.argv",
        ["neoprumo", "setup", str(workspace)],
    )

    codigo = __main__.main((3, 10, 0))

    assert codigo == 0
    assert (workspace / ".neoprumo" / "workspace.json").is_file()
