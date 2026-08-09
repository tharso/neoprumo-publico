import json
import os
import stat
import sys
from pathlib import Path

from neoprumo import __version__
from neoprumo import __main__


def linha_esperada():
    versao_python = ".".join(map(str, sys.version_info[:3]))
    return f"NeoPrumo {__version__} ativo — Python {versao_python}."


def assert_envelope_portatil(resultado):
    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.count("\n") == 1
    assert "Traceback" not in resultado.stdout
    envelope = json.loads(resultado.stdout)
    assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    contexto = envelope["hookSpecificOutput"]["additionalContext"]
    assert contexto.startswith(linha_esperada())
    return contexto


def test_sonda_informa_versoes_sem_tocar_em_workspace(executar_cli):
    resultado = executar_cli("sonda")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout == linha_esperada() + "\n"


def test_sonda_hook_resume_workspace_com_paridade_e_sem_escrever(
    tmp_path, executar_cli
):
    workspace = tmp_path / "ativo"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Pauta.md").write_bytes(b"\xff")
    seed = executar_cli("seed")
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo"
    antes = fotografar(workspace, configuracao)

    resultado = executar_cli("sonda", "--hook")

    contexto = assert_envelope_portatil(resultado)
    assert contexto.split("\n", 1)[1] == seed.stdout.rstrip("\n")
    assert fotografar(workspace, configuracao) == antes


def test_sonda_hook_orienta_quando_nao_ha_workspace_utilizavel(executar_cli):
    resultado = executar_cli("sonda", "--hook")

    contexto = assert_envelope_portatil(resultado)
    assert contexto.splitlines() == [
        linha_esperada(),
        "Nenhum workspace ativo pôde ser resolvido. "
        "Execute setup ou workspace usar para corrigir.",
    ]


def test_sonda_hook_orienta_quando_workspace_ativo_deixa_de_ser_valido(
    tmp_path, executar_cli
):
    workspace = tmp_path / "invalido"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / ".neoprumo").rename(workspace / ".identidade-removida")

    resultado = executar_cli("sonda", "--hook")

    contexto = assert_envelope_portatil(resultado)
    assert contexto.splitlines() == [
        linha_esperada(),
        f"O workspace ativo {workspace} não pôde ser usado. "
        "O caminho ainda não é um workspace utilizável. "
        f"Execute setup --readotar {workspace}.",
    ]


def test_sonda_hook_esconde_falha_inesperada_do_pipeline(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import seed as modulo_seed

    workspace = tmp_path / "falha"
    assert executar_cli("setup", workspace).returncode == 0

    def falhar_ao_ler(_caminho):
        raise RuntimeError("segredo interno")

    monkeypatch.setattr(modulo_seed.os, "scandir", falhar_ao_ler)

    resultado = executar_cli("sonda", "--hook")

    contexto = assert_envelope_portatil(resultado)
    assert contexto.splitlines() == [
        linha_esperada(),
        "O estado do workspace não pôde ser preparado nesta abertura. "
        "A sessão pode continuar.",
    ]
    assert "segredo interno" not in resultado.stdout


def test_sonda_hook_preserva_envelope_no_piso_de_python(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["neoprumo", "sonda", "--hook"])

    codigo = __main__.main((3, 9, 6))

    captura = capsys.readouterr()
    assert codigo == 0
    assert captura.err == ""
    assert captura.out.count("\n") == 1
    assert "Traceback" not in captura.out
    envelope = json.loads(captura.out)
    saida = envelope["hookSpecificOutput"]
    assert saida["hookEventName"] == "SessionStart"
    assert saida["additionalContext"] == __main__.mensagem_de_versao((3, 9, 6))


def fotografar(*raizes):
    foto = {}
    for raiz in raizes:
        caminhos = [raiz]
        for pasta, diretorios, arquivos in os.walk(raiz, followlinks=False):
            caminhos.extend(Path(pasta) / nome for nome in diretorios + arquivos)
        for caminho_bruto in caminhos:
            caminho = Path(caminho_bruto)
            estado = caminho.lstat()
            conteudo = caminho.read_bytes() if stat.S_ISREG(estado.st_mode) else None
            foto[str(caminho)] = (
                stat.S_IFMT(estado.st_mode),
                conteudo,
                estado.st_mtime_ns,
            )
    return foto
