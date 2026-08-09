import os
from pathlib import Path
from types import SimpleNamespace

import pytest


RAIZ_PROJETO = Path(__file__).parents[2]


@pytest.fixture(autouse=True)
def isolar_configuracao_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "configuracao-xdg"))


@pytest.fixture
def executar_cli(capsys):
    from neoprumo.cli import executar as executar_cli_publica

    def executar_diretamente(*argumentos):
        codigo = executar_cli_publica(list(map(str, argumentos)))
        saida = capsys.readouterr()
        return SimpleNamespace(
            returncode=codigo,
            stdout=saida.out,
            stderr=saida.err,
        )

    return executar_diretamente


@pytest.fixture
def executar_modulo():
    def executar_em_subprocesso(*argumentos, input=None):
        import subprocess
        import sys

        ambiente = os.environ.copy()
        pythonpath_atual = ambiente.get("PYTHONPATH", "")
        caminhos = [str(RAIZ_PROJETO / "nucleo")]
        if pythonpath_atual:
            caminhos.append(pythonpath_atual)
        ambiente["PYTHONPATH"] = os.pathsep.join(caminhos)
        return subprocess.run(
            [sys.executable, "-m", "neoprumo", *map(str, argumentos)],
            cwd=RAIZ_PROJETO,
            env=ambiente,
            input=input,
            capture_output=True,
            text=True,
            check=False,
        )

    return executar_em_subprocesso
