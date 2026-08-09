import json
import re

import pytest

from conftest import RAIZ_PROJETO
from neoprumo import __version__


PASTA_SKILLS = RAIZ_PROJETO / "skills"


def skills_empacotadas():
    return sorted(caminho for caminho in PASTA_SKILLS.iterdir() if caminho.is_dir())


def test_manifesto_declara_identidade_e_versao_do_nucleo():
    manifesto = json.loads(
        (RAIZ_PROJETO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert manifesto["name"] == "neoprumo"
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifesto["version"])
    assert manifesto["version"] == __version__


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
