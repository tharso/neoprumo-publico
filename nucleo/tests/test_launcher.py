import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import RAIZ_PROJETO


INICIALIZADOR = RAIZ_PROJETO / "bin" / "neoprumo"
PYTHON_DO_SISTEMA = Path("/usr/bin/python3")


def executar_inicializador(interprete, diretorio, *argumentos):
    return subprocess.run(
        [str(interprete), str(INICIALIZADOR), *argumentos],
        cwd=diretorio,
        capture_output=True,
        text=True,
        check=False,
    )


def python_do_sistema_e_antigo():
    if not PYTHON_DO_SISTEMA.exists():
        return False
    resultado = subprocess.run(
        [
            str(PYTHON_DO_SISTEMA),
            "-c",
            "import sys; print('%d %d' % sys.version_info[:2])",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        return False
    return tuple(map(int, resultado.stdout.split())) < (3, 10)


def test_launcher_funciona_fora_da_raiz_do_plugin(tmp_path):
    assert os.access(INICIALIZADOR, os.X_OK)
    resultado = executar_inicializador(sys.executable, tmp_path, "sonda")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.startswith("NeoPrumo 0.1.0 ativo — Python ")


def test_launcher_hook_funciona_fora_da_raiz_do_plugin(tmp_path):
    resultado = executar_inicializador(sys.executable, tmp_path, "sonda", "--hook")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    envelope = json.loads(resultado.stdout)
    assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "NeoPrumo 0.1.0 ativo" in envelope["hookSpecificOutput"]["additionalContext"]


@pytest.mark.skipif(
    not python_do_sistema_e_antigo(),
    reason="o Python do sistema não existe ou já atende ao piso 3.10",
)
def test_launcher_hook_explica_piso_em_python_antigo(tmp_path):
    resultado = executar_inicializador(
        PYTHON_DO_SISTEMA, tmp_path, "sonda", "--hook"
    )

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    envelope = json.loads(resultado.stdout)
    mensagem = envelope["hookSpecificOutput"]["additionalContext"]
    assert "Python 3.10" in mensagem
    assert "3.9" in mensagem
