import json
import re

import pytest

from conftest import RAIZ_PROJETO
from neoprumo import __data_versao__, __version__


PASTA_SKILLS = RAIZ_PROJETO / "skills"


def skills_empacotadas():
    return sorted(caminho for caminho in PASTA_SKILLS.iterdir() if caminho.is_dir())


def test_quatro_lugares_declaram_a_mesma_versao_semver_estrita():
    plugin = json.loads(
        (RAIZ_PROJETO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace = json.loads(
        (RAIZ_PROJETO / ".claude-plugin" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    projeto = (RAIZ_PROJETO / "pyproject.toml").read_text(encoding="utf-8")
    versao_projeto = re.search(
        r'^version = "([^"]+)"$', projeto, flags=re.MULTILINE
    ).group(1)
    versoes = {
        __version__,
        plugin["version"],
        marketplace["plugins"][0]["version"],
        versao_projeto,
    }

    assert plugin["name"] == "neoprumo"
    assert len(versoes) == 1
    assert re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", __version__
    )
    assert __version__ == "0.7.0"


def test_pacote_declara_data_da_versao_em_formato_iso():
    from datetime import date

    assert date.fromisoformat(__data_versao__).isoformat() == __data_versao__
    assert __data_versao__ == "2026-09-01"


def test_manifestos_declaram_identidade_publica_e_licenca():
    plugin = json.loads(
        (RAIZ_PROJETO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace = json.loads(
        (RAIZ_PROJETO / ".claude-plugin" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    entrada = marketplace["plugins"][0]

    assert marketplace["name"] == "neoprumo"
    assert entrada["name"] == "neoprumo"
    assert "nada se perde" in entrada["description"]
    assert entrada["author"] == {"name": "Tharso Vieira"}
    assert entrada["license"] == "MIT"
    assert plugin["author"] == entrada["author"]
    assert plugin["license"] == entrada["license"]


def test_hook_usa_raiz_portatil_e_modo_hook():
    configuracao = json.loads(
        (RAIZ_PROJETO / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )
    comando = configuracao["hooks"]["SessionStart"][0]["hooks"][0]["command"]

    assert "${CLAUDE_PLUGIN_ROOT}" in comando
    assert "sonda --hook" in comando


@pytest.mark.parametrize(
    "pasta",
    skills_empacotadas(),
    ids=lambda caminho: caminho.name,
)
def test_toda_skill_tem_frontmatter_compativel_com_padrao_aberto(pasta):
    caminho = pasta / "SKILL.md"
    partes = caminho.read_text(encoding="utf-8").split("---")
    campos = dict(
        linha.split(":", 1) for linha in partes[1].strip().splitlines()
    )

    assert campos["name"].strip() == pasta.name
    assert 1 <= len(campos["description"].strip()) <= 1024


def test_sessao_substitui_sonda_no_pacote():
    nomes = {caminho.name for caminho in skills_empacotadas()}

    assert "sessao" in nomes
    assert "sonda" not in nomes


def test_template_da_superficie_viaja_com_o_nucleo():
    template = (
        RAIZ_PROJETO
        / "nucleo"
        / "neoprumo"
        / "dados"
        / "superficie-despacho.html"
    )

    assert template.is_file()
    assert "__DADOS_DA_SUPERFICIE__" in template.read_text(encoding="utf-8")


def test_ci_busca_base_explicita_e_confere_versao_so_no_repo_privado():
    fluxo = (RAIZ_PROJETO / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    refspec = "git fetch --no-tags origin main:refs/remotes/origin/main"
    catraca = "python3 ferramentas/catraca_versao.py"
    condicao = "github.repository == 'tharso/NeoPrumo'"
    assert refspec in fluxo
    assert catraca in fluxo
    assert fluxo.index(refspec) < fluxo.index(catraca)
    assert fluxo.count(condicao) >= 2
