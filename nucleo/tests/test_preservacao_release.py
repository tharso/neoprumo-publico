import os
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import RAIZ_PROJETO


def executar(copia, xdg, *argumentos):
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(copia / "nucleo")
    ambiente["XDG_CONFIG_HOME"] = str(xdg)
    return subprocess.run(
        [sys.executable, "-m", "neoprumo", *map(str, argumentos)],
        capture_output=True,
        text=True,
        env=ambiente,
    )


def fotografar(raiz):
    return {
        caminho.relative_to(raiz): caminho.read_bytes()
        for caminho in raiz.rglob("*")
        if caminho.is_file()
    }


def test_nucleo_relocado_le_workspace_e_preserva_ponteiro(tmp_path):
    # Esta prova cobre a relocação do núcleo entre duas pastas de versão; não
    # simula install nem upgrade do host, que pertence ao smoke real do release.
    copias = []
    for nome in ("pacote-0.1.0", "pacote-0.2.0"):
        copia = tmp_path / nome
        (copia / "nucleo").mkdir(parents=True)
        shutil.copytree(
            RAIZ_PROJETO / "nucleo" / "neoprumo",
            copia / "nucleo" / "neoprumo",
        )
        copias.append(copia)
    workspace = tmp_path / "vida"
    xdg = tmp_path / "configuracao"

    assert executar(copias[0], xdg, "setup", workspace).returncode == 0
    (workspace / "arquivo-desconhecido.txt").write_bytes(b"fica comigo\n")
    ponteiro = xdg / "neoprumo" / "config.json"
    ponteiro_antes = ponteiro.read_bytes()
    workspace_antes = fotografar(workspace)

    leitura = executar(copias[1], xdg, "seed", "--json")

    assert leitura.returncode == 0
    assert ponteiro.read_bytes() == ponteiro_antes
    assert fotografar(workspace) == workspace_antes
