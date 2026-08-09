"""Testes do script de publicação do espelho.

Este arquivo VIAJA no espelho (nucleo/ inteiro está na allowlist), então os
termos e nomes que as barreiras proíbem aparecem aqui só MONTADOS em tempo de
execução — o conteúdo do arquivo não pode disparar a própria barreira que ele
testa. No espelho o script não existe (fica no repo privado) e a suíte inteira
é pulada pelo skipif.

O caminho de publicação real (clone efêmero do remoto + push) depende de rede
e não é exercitado aqui; os testes cobrem o modo --sem-push, que compartilha
composição, barreiras e commit, e as recusas que precedem qualquer rede.
"""

import os
import subprocess
from pathlib import Path

import pytest

from conftest import RAIZ_PROJETO


SCRIPT = RAIZ_PROJETO / "ferramentas" / ("espelho" + ".sh")
TERMO_VIDA = "Daily" + "Life"
NOME_DECISOES = "DECISIONS" + ".md"

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists(),
    reason="script do espelho não acompanha a árvore publicada",
)


def _git(caminho, *argumentos):
    subprocess.run(
        ["git", "-C", str(caminho), *argumentos],
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def origem(tmp_path):
    raiz = tmp_path / "origem"
    for pasta in ("nucleo", "skills", "hooks", "bin", ".claude-plugin",
                  "ferramentas", ".github/workflows"):
        (raiz / pasta).mkdir(parents=True)
    (raiz / "nucleo" / "modulo.py").write_text("VALOR = 1\n", encoding="utf-8")
    (raiz / "skills" / "leia.md").write_text("skill\n", encoding="utf-8")
    (raiz / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
    (raiz / "bin" / "neoprumo").write_text("#!/bin/sh\n", encoding="utf-8")
    (raiz / ".claude-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
    for nome in ("__init__.py", "catraca_skills.py", "orcamento-skills.json"):
        (raiz / "ferramentas" / nome).write_text("\n", encoding="utf-8")
    (raiz / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (raiz / "README.md").write_text("# leia\n", encoding="utf-8")
    (raiz / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (raiz / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    _git(raiz, "init", "-q")
    _git(raiz, "add", "-A")
    _git(raiz, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return raiz


def _rodar(origem, saida, ambiente=None, sem_push=True, cwd=None):
    env = dict(os.environ)
    env["ESPELHO_RAIZ_TESTE"] = str(origem)
    if ambiente:
        env.update(ambiente)
    argumentos = [str(SCRIPT)]
    if saida is not None:
        argumentos.append(str(saida))
    if sem_push:
        argumentos.append("--sem-push")
    return subprocess.run(
        argumentos,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )


def _commit_extra(origem, caminho, conteudo):
    alvo = origem / caminho
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")
    _git(origem, "add", "-A")
    _git(origem, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "extra")


def _arvore(caminho):
    return subprocess.run(
        ["git", "-C", str(caminho), "rev-parse", "HEAD^{tree}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_compoe_allowlist_e_exclui_o_proprio_script(origem, tmp_path):
    saida = tmp_path / "saida"

    resultado = _rodar(origem, saida)

    assert resultado.returncode == 0
    assert (saida / "nucleo" / "modulo.py").is_file()
    assert (saida / "LICENSE").is_file()
    assert not (saida / "ferramentas" / ("espelho" + ".sh")).exists()


def test_saida_existente_e_recusada_intacta(origem, tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()
    (saida / "trabalho.txt").write_text("rascunho\n", encoding="utf-8")

    resultado = _rodar(origem, saida)

    assert resultado.returncode == 1
    assert "não pode existir" in resultado.stderr
    assert (saida / "trabalho.txt").read_text(encoding="utf-8") == "rascunho\n"


def test_saida_vazia_preexistente_tambem_e_recusada(origem, tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()

    resultado = _rodar(origem, saida)

    assert resultado.returncode == 1
    assert "não pode existir" in resultado.stderr


def test_configuracao_global_da_maquina_nao_atravessa(origem, tmp_path):
    lar = tmp_path / "lar"
    lar.mkdir()
    filtro = (
        '[filter "troca"]\n'
        "\tclean = tr a-z A-Z\n"
        '[url "https://alvo.invalido/repo.git"]\n'
        "\tinsteadOf = https://github.com\n"
    )
    (lar / ".gitconfig").write_text(filtro, encoding="utf-8")
    atributos = lar / ".config" / "git"
    atributos.mkdir(parents=True)
    (atributos / "attributes").write_text(
        "* filter=troca\nnucleo export-ignore\n", encoding="utf-8"
    )
    (atributos / "config").write_text(filtro, encoding="utf-8")
    hostil = {
        "HOME": str(lar),
        "XDG_CONFIG_HOME": str(lar / ".config"),
        "GIT_CONFIG_GLOBAL": str(lar / ".gitconfig"),
        "GIT_CONFIG_SYSTEM": str(lar / ".gitconfig"),
    }
    saida = tmp_path / "saida"

    resultado = _rodar(origem, saida, hostil)

    assert resultado.returncode == 0
    conteudo = subprocess.run(
        ["git", "-C", str(saida), "show", "HEAD:README.md"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert conteudo == "# leia\n"
    assert (saida / "nucleo" / "modulo.py").is_file()


def test_termo_de_processo_em_caminho_recusa(origem, tmp_path):
    _commit_extra(origem, f"nucleo/{TERMO_VIDA}/nota.txt", "neutro\n")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "em CAMINHO do espelho" in resultado.stderr


def test_gitignore_versionado_nao_fura_a_allowlist(origem, tmp_path):
    (origem / "nucleo" / ".gitignore").write_text("gerado.txt\n", encoding="utf-8")
    (origem / "nucleo" / "gerado.txt").write_text("faz parte\n", encoding="utf-8")
    _git(origem, "add", "-A", "-f")
    _git(origem, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "ig")
    saida = tmp_path / "saida"

    resultado = _rodar(origem, saida)

    assert resultado.returncode == 0
    arvore = subprocess.run(
        ["git", "-C", str(saida), "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "nucleo/gerado.txt" in arvore


def test_gitattributes_versionado_na_fonte_recusa(origem, tmp_path):
    _commit_extra(origem, ".git" + "attributes", "nucleo export-ignore\n")

    saida = tmp_path / "saida"
    resultado = _rodar(origem, saida)

    assert resultado.returncode == 1
    assert "atributos" in resultado.stderr
    assert not (saida / ".git" / "lista-fonte").exists()


def test_caminho_com_caractere_de_controle_recusa(origem, tmp_path):
    _commit_extra(origem, "nucleo/que\nbra.txt", "neutro\n")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "caractere de controle" in resultado.stderr


def test_gitattributes_em_subpasta_tambem_recusa(origem, tmp_path):
    _commit_extra(origem, "nucleo/sub/" + ".git" + "attributes", "x export-subst\n")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "atributos" in resultado.stderr


def test_info_attributes_local_da_fonte_recusa(origem, tmp_path):
    (origem / ".git" / "info").mkdir(exist_ok=True)
    (origem / ".git" / "info" / "attributes").write_text(
        "* export-ignore\n", encoding="utf-8"
    )

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "info/attributes" in resultado.stderr


def test_saida_que_e_arquivo_e_recusada(origem, tmp_path):
    saida = tmp_path / "arquivo.txt"
    saida.write_text("x\n", encoding="utf-8")

    resultado = _rodar(origem, saida)

    assert resultado.returncode == 1
    assert saida.read_text(encoding="utf-8") == "x\n"


def test_sem_push_exige_diretorio_de_saida(origem, tmp_path):
    resultado = _rodar(origem, None)

    assert resultado.returncode == 1
    assert "exige o diretório de saída" in resultado.stderr


def test_publicacao_real_nao_aceita_diretorio_de_saida(tmp_path):
    saida = tmp_path / "saida"
    resultado = subprocess.run(
        [str(SCRIPT), str(saida)],
        capture_output=True, text=True, env=dict(os.environ),
    )

    assert resultado.returncode == 1
    assert "não aceita diretório de saída" in resultado.stderr
    assert not saida.exists()


def test_override_de_origem_exige_sem_push(origem, tmp_path):
    resultado = _rodar(origem, None, sem_push=False)

    assert resultado.returncode == 1
    assert "só é aceito com --sem-push" in resultado.stderr


def test_composicao_e_deterministica(origem, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"

    assert _rodar(origem, a).returncode == 0
    assert _rodar(origem, b).returncode == 0
    assert _arvore(a) == _arvore(b)


def test_arquivo_nao_versionado_nunca_viaja(origem, tmp_path):
    (origem / "nucleo" / "rascunho-local.txt").write_text("privado\n", encoding="utf-8")
    saida = tmp_path / "saida"

    resultado = _rodar(origem, saida)

    assert resultado.returncode == 0
    assert not (saida / "nucleo" / "rascunho-local.txt").exists()


def test_symlink_commitado_recusa(origem, tmp_path):
    (origem / "nucleo" / "atalho").symlink_to("../../fora")
    _git(origem, "add", "-A")
    _git(origem, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "link")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "symlink no espelho" in resultado.stderr


def test_termo_apos_byte_invalido_ainda_e_encontrado(origem, tmp_path):
    alvo = origem / "nucleo" / "binario.dat"
    alvo.write_bytes(b"\xff" + TERMO_VIDA.encode() + b"\n")
    _git(origem, "add", "-A")
    _git(origem, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "bin")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "termo de artefato de processo" in resultado.stderr


def test_termo_de_processo_commitado_recusa(origem, tmp_path):
    _commit_extra(origem, "nucleo/nota.txt", f"menção ao {TERMO_VIDA}\n")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "termo de artefato de processo" in resultado.stderr


def test_nome_de_processo_commitado_recusa(origem, tmp_path):
    _commit_extra(origem, f"nucleo/interno/{NOME_DECISOES}", "neutro\n")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "caminho proibido" in resultado.stderr


def test_hooks_e_config_do_ambiente_nao_executam(origem, tmp_path):
    modelo = tmp_path / "modelo"
    (modelo / "hooks").mkdir(parents=True)
    gancho = modelo / "hooks" / "pre-commit"
    gancho.write_text(
        '#!/bin/sh\ntouch "$(git rev-parse --show-toplevel)/injetado.txt"\ngit add -A\n',
        encoding="utf-8",
    )
    gancho.chmod(0o755)
    hostil = {
        "GIT_TEMPLATE_DIR": str(modelo),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": str(modelo / "hooks"),
    }
    saida = tmp_path / "saida"

    resultado = _rodar(origem, saida, hostil)

    assert resultado.returncode == 0
    assert not (saida / "injetado.txt").exists()
    arvore = subprocess.run(
        ["git", "-C", str(saida), "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "injetado" not in arvore


def test_grep_options_do_ambiente_nao_cega_a_barreira(origem, tmp_path):
    _commit_extra(origem, "nucleo/nota.txt", f"menção ao {TERMO_VIDA}\n")

    resultado = _rodar(origem, tmp_path / "saida",
                       {"GREP_OPTIONS": "--exclude=*"})

    assert resultado.returncode == 1
    assert "termo de artefato de processo" in resultado.stderr


def test_sentinela_de_limpeza_plantada_no_ambiente_nao_pula_a_limpeza(
    origem, tmp_path
):
    _commit_extra(origem, "nucleo/nota.txt", f"menção ao {TERMO_VIDA}\n")

    resultado = _rodar(origem, tmp_path / "saida", {
        "ESPELHO_AMBIENTE_LIMPO": "1",
        "GREP_OPTIONS": "--exclude=*",
    })

    assert resultado.returncode == 1
    assert "termo de artefato de processo" in resultado.stderr


def test_cdpath_do_ambiente_nao_desvia_a_saida(origem, tmp_path):
    armadilha = tmp_path / "armadilha"
    (armadilha / "saida-relativa").mkdir(parents=True)
    base = tmp_path / "base"
    base.mkdir()

    resultado = _rodar(origem, "saida-relativa",
                       {"CDPATH": str(armadilha)}, cwd=base)

    assert resultado.returncode == 0
    assert (base / "saida-relativa" / "LICENSE").is_file()
    assert not any((armadilha / "saida-relativa").iterdir())


def test_refs_replace_nao_troca_o_conteudo_publicado(origem, tmp_path):
    sha_a = subprocess.run(
        ["git", "-C", str(origem), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    _git(origem, "checkout", "-qb", "alternativa")
    (origem / "README.md").write_text("# ALTERNATIVO\n", encoding="utf-8")
    _git(origem, "add", "-A")
    _git(origem, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b")
    sha_b = subprocess.run(
        ["git", "-C", str(origem), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    _git(origem, "checkout", "-q", "main")
    _git(origem, "update-ref", f"refs/replace/{sha_a}", sha_b)
    saida = tmp_path / "saida"

    resultado = _rodar(origem, saida)

    assert resultado.returncode == 0
    conteudo = subprocess.run(
        ["git", "-C", str(saida), "show", "HEAD:README.md"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert conteudo == "# leia\n"


def test_git_trace_do_ambiente_nao_escreve_em_arquivo_alheio(origem, tmp_path):
    alheio = tmp_path / "trace.log"
    alheio.write_text("", encoding="utf-8")
    saida = tmp_path / "saida"

    resultado = _rodar(origem, saida, {"GIT_TRACE": str(alheio)})

    assert resultado.returncode == 0
    assert alheio.read_text(encoding="utf-8") == ""


def test_gitlink_na_fonte_recusa(origem, tmp_path):
    sha = subprocess.run(
        ["git", "-C", str(origem), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    _git(origem, "update-index", "--add", "--cacheinfo",
         f"160000,{sha},nucleo/submodulo")
    _git(origem, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "sub")

    resultado = _rodar(origem, tmp_path / "saida")

    assert resultado.returncode == 1
    assert "gitlink" in resultado.stderr


def test_identidade_do_commit_independe_do_ambiente(origem, tmp_path):
    saida = tmp_path / "saida"
    hostil = {
        "GIT_AUTHOR_NAME": "Maquina Pessoal",
        "GIT_AUTHOR_EMAIL": "pessoal@exemplo.com",
        "GIT_COMMITTER_NAME": "Maquina Pessoal",
        "GIT_COMMITTER_EMAIL": "pessoal@exemplo.com",
    }

    resultado = _rodar(origem, saida, hostil)

    assert resultado.returncode == 0
    autor = subprocess.run(
        ["git", "-C", str(saida), "log", "-1", "--format=%an <%ae> %cn <%ce>"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert autor == (
        "NeoPrumo Espelho <espelho@users.noreply.github.com> "
        "NeoPrumo Espelho <espelho@users.noreply.github.com>"
    )
