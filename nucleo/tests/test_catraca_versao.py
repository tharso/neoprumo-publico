import json
import io
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import RAIZ_PROJETO


CATRACA = RAIZ_PROJETO / "ferramentas" / "catraca_versao.py"
CONTROLE = Path("ferramentas") / ("espelho" + ".sh")
DATA_COMMIT = "2026-08-24T12:00:00+00:00"
ALLOWLIST = (
    "nucleo",
    "skills",
    "hooks",
    "bin",
    ".claude-plugin",
    "ferramentas/__init__.py",
    "ferramentas/catraca_skills.py",
    "ferramentas/catraca_versao.py",
    "ferramentas/orcamento-skills.json",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    ".github/workflows/ci.yml",
)


def git(raiz, *argumentos, ambiente=None):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_DATE": DATA_COMMIT,
            "GIT_COMMITTER_DATE": DATA_COMMIT,
        }
    )
    if ambiente:
        env.update(ambiente)
    return subprocess.run(
        ["git", "-C", str(raiz), *argumentos],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def gravar_versao(
    raiz,
    versao,
    data="2026-08-24",
    com_data=True,
    versao_no_marketplace=True,
):
    pacote = raiz / "nucleo" / "neoprumo"
    pacote.mkdir(parents=True, exist_ok=True)
    linha_data = f'__data_versao__ = "{data}"\n' if com_data else ""
    (pacote / "__init__.py").write_text(
        f'__version__ = "{versao}"\n{linha_data}', encoding="utf-8"
    )
    manifests = raiz / ".claude-plugin"
    manifests.mkdir(exist_ok=True)
    (manifests / "plugin.json").write_text(
        json.dumps({"name": "neoprumo", "version": versao}), encoding="utf-8"
    )
    entrada_marketplace = {"name": "neoprumo"}
    if versao_no_marketplace:
        entrada_marketplace["version"] = versao
    (manifests / "marketplace.json").write_text(
        json.dumps({"plugins": [entrada_marketplace]}), encoding="utf-8"
    )
    (raiz / "pyproject.toml").write_text(
        f'[project]\nname = "neoprumo"\nversion = "{versao}"\n',
        encoding="utf-8",
    )


def gravar_controle(raiz, extras=()):
    caminho = raiz / CONTROLE
    caminho.parent.mkdir(parents=True, exist_ok=True)
    membros = "\n".join(f"    {item}" for item in (*ALLOWLIST, *extras))
    caminho.write_text(f"ALLOWLIST=(\n{membros}\n)\n", encoding="utf-8")


def commit(raiz, mensagem):
    git(raiz, "add", "-A")
    git(
        raiz,
        "-c",
        "user.name=Teste",
        "-c",
        "user.email=teste@example.invalid",
        "commit",
        "-qm",
        mensagem,
    )


@pytest.fixture()
def repositorio(tmp_path):
    raiz = tmp_path / "repo"
    raiz.mkdir()
    git(raiz, "init", "-q")
    gravar_versao(raiz, "0.1.0")
    gravar_controle(raiz)
    (raiz / "README.md").write_text("# Produto\n", encoding="utf-8")
    commit(raiz, "base")
    git(raiz, "update-ref", "refs/remotes/origin/main", "HEAD")
    return raiz


def rodar(raiz, *argumentos, ambiente=None):
    if ambiente is None:
        from ferramentas import catraca_versao

        saida = io.StringIO()
        erro = io.StringIO()
        pasta_anterior = Path.cwd()
        try:
            os.chdir(raiz)
            with redirect_stdout(saida), redirect_stderr(erro):
                codigo = catraca_versao.main(list(argumentos))
        finally:
            os.chdir(pasta_anterior)
        return SimpleNamespace(
            returncode=codigo, stdout=saida.getvalue(), stderr=erro.getvalue()
        )
    env = dict(os.environ)
    if ambiente:
        env.update(ambiente)
    return subprocess.run(
        [sys.executable, str(CATRACA), *argumentos],
        cwd=raiz,
        capture_output=True,
        text=True,
        env=env,
    )


def alterar_pacote(raiz, versao="0.1.0", data="2026-08-24"):
    (raiz / "README.md").write_text("# Produto pronto\n", encoding="utf-8")
    gravar_versao(raiz, versao, data)
    commit(raiz, "pacote")


def test_recusa_mudanca_de_pacote_sem_bump(repositorio):
    alterar_pacote(repositorio)

    resultado = rodar(repositorio)

    assert resultado.returncode == 1
    assert "não subiu" in resultado.stderr


def test_recusa_bump_inferior_ao_piso_da_ponta(repositorio):
    gravar_versao(repositorio, "0.2.0")
    commit(repositorio, "base nova")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    gravar_versao(repositorio, "0.1.1")
    commit(repositorio, "regressão")

    resultado = rodar(repositorio)

    assert resultado.returncode == 1
    assert "0.2.0" in resultado.stderr


def test_branch_antiga_respeita_piso_da_ponta_de_origin_main(repositorio):
    base = git(repositorio, "rev-parse", "HEAD").stdout.strip()
    git(repositorio, "checkout", "-qb", "principal")
    gravar_versao(repositorio, "0.3.0")
    commit(repositorio, "ponta avançou")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repositorio, "checkout", "-q", "--detach", base)
    alterar_pacote(repositorio, "0.2.0")

    resultado = rodar(repositorio)

    assert resultado.returncode == 1
    assert "0.3.0" in resultado.stderr


def test_composicao_da_allowlist_alterada_exige_bump(repositorio):
    gravar_controle(repositorio, extras=("novo.txt",))
    (repositorio / "novo.txt").write_text("novo\n", encoding="utf-8")
    commit(repositorio, "composição")

    resultado = rodar(repositorio)

    assert resultado.returncode == 1
    assert "composição" in resultado.stderr


def test_controle_sujo_e_falha_operacional(repositorio):
    with (repositorio / CONTROLE).open("a", encoding="utf-8") as arquivo:
        arquivo.write("# sujeira\n")

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "controle" in resultado.stderr


def test_controle_commitado_exige_bump(repositorio):
    with (repositorio / CONTROLE).open("a", encoding="utf-8") as arquivo:
        arquivo.write("# alteração\n")
    commit(repositorio, "controle")

    resultado = rodar(repositorio)

    assert resultado.returncode == 1
    assert "controle" in resultado.stderr


def test_arvore_suja_no_pacote_e_recusada_nomeando_arquivo(repositorio):
    (repositorio / "README.md").write_text("rascunho\n", encoding="utf-8")

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "README.md" in resultado.stderr


def test_base_ausente_fecha_com_falha_operacional(repositorio):
    git(repositorio, "update-ref", "-d", "refs/remotes/origin/main")

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "origin/main" in resultado.stderr


def test_git_ausente_fecha_com_falha_operacional(repositorio, tmp_path):
    resultado = rodar(repositorio, ambiente={"PATH": str(tmp_path)})

    assert resultado.returncode == 2
    assert "Git" in resultado.stderr


def test_manifesto_com_forma_inesperada_fecha_com_falha_operacional(repositorio):
    (repositorio / ".claude-plugin" / "marketplace.json").write_text(
        '{"plugins": null}\n', encoding="utf-8"
    )
    commit(repositorio, "manifesto quebrado")

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "Traceback" not in resultado.stderr


def test_data_desancorada_do_commit_e_falha_operacional(repositorio):
    gravar_versao(repositorio, "0.1.0", "2026-08-19")
    commit(repositorio, "base mais antiga")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    alterar_pacote(repositorio, "0.2.0", "2026-08-20")

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "ancorada" in resultado.stderr


def test_data_futura_e_falha_operacional(repositorio):
    alterar_pacote(repositorio, "0.2.0", "2999-01-01")

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "futura" in resultado.stderr


def test_data_anterior_a_base_e_violacao(repositorio):
    gravar_versao(repositorio, "0.1.0", "2026-08-23")
    commit(repositorio, "base datada")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    alterar_pacote(repositorio, "0.2.0", "2026-08-22")

    resultado = rodar(repositorio)

    assert resultado.returncode == 1
    assert "anterior" in resultado.stderr


def test_datas_iguais_passam(repositorio):
    alterar_pacote(repositorio, "0.2.0", "2026-08-24")

    resultado = rodar(repositorio)

    assert resultado.returncode == 0
    assert git(repositorio, "rev-parse", "HEAD").stdout.strip() in resultado.stdout


def test_bootstrap_aceita_base_sem_data_com_versao_maior(repositorio):
    gravar_versao(repositorio, "0.1.0", com_data=False)
    commit(repositorio, "base sem data")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    alterar_pacote(repositorio, "0.2.0")

    resultado = rodar(repositorio)

    assert resultado.returncode == 0


def test_bootstrap_recusa_base_sem_data_sem_versao_maior(repositorio):
    gravar_versao(repositorio, "0.1.0", com_data=False)
    commit(repositorio, "base sem data")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    (repositorio / "README.md").write_text("mudou\n", encoding="utf-8")
    gravar_versao(repositorio, "0.1.0")
    commit(repositorio, "data sem bump")

    resultado = rodar(repositorio)

    assert resultado.returncode == 1


def test_bootstrap_sem_versao_no_marketplace_recusa_pacote_sem_bump(
    repositorio,
):
    gravar_versao(
        repositorio, "0.1.0", versao_no_marketplace=False
    )
    commit(repositorio, "base sem versão no marketplace")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    alterar_pacote(repositorio)

    resultado = rodar(repositorio)

    assert resultado.returncode == 1
    assert "não subiu" in resultado.stderr


def test_bootstrap_sem_versao_no_marketplace_aceita_bump(repositorio):
    gravar_versao(
        repositorio, "0.1.0", versao_no_marketplace=False
    )
    commit(repositorio, "base sem versão no marketplace")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    alterar_pacote(repositorio, "0.2.0")

    resultado = rodar(repositorio)

    assert resultado.returncode == 0


def test_versao_atual_sem_data_e_falha_operacional(repositorio):
    gravar_versao(repositorio, "0.2.0", com_data=False)
    commit(repositorio, "versão sem data")

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "__data_versao__" in resultado.stderr


def test_tolerancia_de_um_dia_antes_do_commit_passa(repositorio):
    gravar_versao(repositorio, "0.1.0", "2026-08-22")
    commit(repositorio, "base anterior")
    git(repositorio, "update-ref", "refs/remotes/origin/main", "HEAD")
    alterar_pacote(repositorio, "0.2.0", "2026-08-23")

    resultado = rodar(repositorio)

    assert resultado.returncode == 0


def test_gate_de_primeiro_pai_recusa_merge_sem_bump(repositorio):
    (repositorio / "README.md").write_text("mudança direta\n", encoding="utf-8")
    commit(repositorio, "main ruim")

    resultado = rodar(repositorio, "--primeiro-pai")

    assert resultado.returncode == 1
    assert "não subiu" in resultado.stderr


def test_historico_ambiguo_da_versao_e_falha_operacional(repositorio):
    base = git(repositorio, "rev-parse", "HEAD").stdout.strip()
    git(repositorio, "checkout", "-qb", "lado-a")
    gravar_versao(repositorio, "0.2.0")
    (repositorio / "README.md").write_text("lado a\n", encoding="utf-8")
    commit(repositorio, "introduz no lado a")
    git(repositorio, "checkout", "-qb", "lado-b", base)
    gravar_versao(repositorio, "0.2.0")
    (repositorio / "LICENSE").write_text("lado b\n", encoding="utf-8")
    commit(repositorio, "introduz no lado b")
    git(repositorio, "checkout", "-q", "lado-a")
    git(
        repositorio,
        "-c",
        "user.name=Teste",
        "-c",
        "user.email=teste@example.invalid",
        "merge",
        "--no-ff",
        "-qm",
        "une histórias",
        "lado-b",
    )

    resultado = rodar(repositorio)

    assert resultado.returncode == 2
    assert "ambíguo" in resultado.stderr


def test_lista_da_catraca_e_igual_ao_array_de_publicacao():
    script = RAIZ_PROJETO / CONTROLE
    if not script.exists():
        pytest.skip("arquivo de publicação não acompanha esta árvore")
    from ferramentas.catraca_versao import ARQUIVOS_DO_PACOTE

    linhas = script.read_text(encoding="utf-8").splitlines()
    inicio = linhas.index("ALLOWLIST=(") + 1
    fim = linhas.index(")", inicio)
    publicados = tuple(linha.strip() for linha in linhas[inicio:fim])

    assert publicados == ARQUIVOS_DO_PACOTE


def test_entrada_publica_confere_sha_e_retorna_zero(
    repositorio, monkeypatch, capsys
):
    from ferramentas import catraca_versao

    alterar_pacote(repositorio, "0.2.0")
    monkeypatch.chdir(repositorio)

    codigo = catraca_versao.main([])

    saida = capsys.readouterr()
    assert codigo == 0
    assert git(repositorio, "rev-parse", "HEAD").stdout.strip() in saida.out
    assert saida.err == ""
