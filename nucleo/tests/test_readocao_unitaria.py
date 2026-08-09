import json
import os
from pathlib import Path

import pytest


def _estrutura_saudavel(raiz):
    from neoprumo.estrutura_workspace import ESTRUTURA, criar_item_ausente, criar_marca

    raiz.mkdir()
    for nome, tipo in ESTRUTURA.items():
        if nome == ".neoprumo/workspace.json":
            criar_marca(raiz)
        criar_item_ausente(raiz, nome, tipo)


@pytest.mark.parametrize(
    ("preparar", "estado"),
    [
        (lambda raiz: None, "inexistente"),
        (lambda raiz: raiz.write_text("arquivo", encoding="utf-8"), "arquivo"),
        (lambda raiz: raiz.mkdir(), "vazio"),
        (lambda raiz: (raiz.mkdir(), (raiz / "Inbox").mkdir()), "sem_marca_sem_sinal"),
        (
            lambda raiz: (
                raiz.mkdir(),
                (raiz / "Inbox").mkdir(),
                (raiz / "Acervo").mkdir(),
            ),
            "sem_marca_com_sinal",
        ),
        (
            lambda raiz: (raiz.mkdir(), (raiz / ".neoprumo").write_text("marca")),
            "sem_marca_com_sinal",
        ),
    ],
)
def test_classificador_distingue_estados_sem_marca(tmp_path, preparar, estado):
    from neoprumo.orientacao import classificar

    raiz = tmp_path / "workspace"
    preparar(raiz)

    assert classificar(raiz) == estado


def test_classificador_distingue_marca_simbolica_incompleta_e_saudavel(tmp_path):
    from neoprumo.orientacao import classificar

    alvo = tmp_path / "alvo"
    alvo.mkdir()
    simbolico = tmp_path / "simbolico"
    simbolico.mkdir()
    (simbolico / ".neoprumo").symlink_to(alvo, target_is_directory=True)
    incompleto = tmp_path / "incompleto"
    incompleto.mkdir()
    (incompleto / ".neoprumo").mkdir()
    saudavel = tmp_path / "saudavel"
    _estrutura_saudavel(saudavel)

    assert classificar(simbolico) == "marca_simbolica"
    assert classificar(incompleto) == "marcado_incompleto"
    assert classificar(saudavel) == "saudavel"


def test_classificador_nao_vaza_falha_de_observacao(tmp_path, monkeypatch):
    from neoprumo.orientacao import classificar

    raiz = tmp_path / "ilegivel"
    raiz.mkdir()
    original = Path.iterdir

    def falhar(caminho):
        if caminho == raiz:
            raise PermissionError("system text")
        return original(caminho)

    monkeypatch.setattr(Path, "iterdir", falhar)

    assert classificar(raiz) == "ilegivel"


def test_classificador_trata_raiz_que_some_ao_listar_como_inexistente(
    tmp_path, monkeypatch
):
    from neoprumo.orientacao import classificar

    raiz = tmp_path / "sumiu"
    raiz.mkdir()
    original = Path.iterdir

    def sumir(caminho):
        if caminho == raiz:
            raise FileNotFoundError
        return original(caminho)

    monkeypatch.setattr(Path, "iterdir", sumir)

    assert classificar(raiz) == "inexistente"


@pytest.mark.parametrize(
    ("estado", "contexto", "trecho"),
    [
        ("inexistente", "caminho_explicito", "setup "),
        ("inexistente", "ponteiro_ativo", "workspace usar"),
        ("vazio", "caminho_explicito", "setup "),
        ("sem_marca_com_sinal", "ponteiro_ativo", "setup --readotar "),
        ("sem_marca_sem_sinal", "caminho_explicito", "setup --readotar --forcar "),
        ("marcado_incompleto", "ponteiro_ativo", "doctor --reparar "),
    ],
)
def test_orientacao_escolhe_acao_aplicavel(tmp_path, monkeypatch, estado, contexto, trecho):
    import neoprumo.orientacao as modulo

    caminho = tmp_path / "destino"
    monkeypatch.setattr(modulo, "classificar", lambda _caminho: estado)

    assert trecho in modulo.orientar(caminho, contexto)["acoes"][0]


@pytest.mark.parametrize("estado", ["saudavel", "arquivo", "ilegivel", "marca_simbolica"])
def test_orientacao_explicita_nao_sugere_comando_inaplicavel(
    tmp_path, monkeypatch, estado
):
    import neoprumo.orientacao as modulo

    monkeypatch.setattr(modulo, "classificar", lambda _caminho: estado)

    assert modulo.orientar(tmp_path / "destino", "caminho_explicito")["acoes"] == []


def test_classificar_e_puro_inclusive_para_configuracao_xdg(tmp_path):
    from neoprumo.orientacao import classificar

    raiz = tmp_path / "workspace"
    raiz.mkdir()
    sentinela = raiz / "rascunho.txt"
    sentinela.write_bytes(b"intacto\x00")
    antes = [(item.name, item.read_bytes()) for item in raiz.iterdir()]

    assert classificar(raiz) == "sem_marca_sem_sinal"
    assert [(item.name, item.read_bytes()) for item in raiz.iterdir()] == antes
    assert not (tmp_path / "configuracao-xdg").exists()


def test_criacao_exclusiva_preserva_arquivo_que_apareceu(tmp_path, monkeypatch):
    import builtins
    from neoprumo.estrutura_workspace import criar_item_ausente

    raiz = tmp_path / "workspace"
    raiz.mkdir()
    item = raiz / "Pauta.md"
    original = builtins.open

    def concorrente(caminho, modo="r", *args, **kwargs):
        if Path(caminho) == item and modo == "x":
            item.write_bytes(b"chegou da nuvem\x00")
        return original(caminho, modo, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", concorrente)

    assert criar_item_ausente(raiz, "Pauta.md", "arquivo") is None
    assert item.read_bytes() == b"chegou da nuvem\x00"


def test_criar_marca_aceita_pasta_concorrente_e_recusa_symlink(tmp_path, monkeypatch):
    from neoprumo.estrutura_workspace import criar_marca

    raiz = tmp_path / "workspace"
    raiz.mkdir()
    marca = raiz / ".neoprumo"
    original = Path.mkdir

    def pasta_concorrente(caminho, *args, **kwargs):
        if caminho == marca:
            original(caminho)
        return original(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", pasta_concorrente)
    assert criar_marca(raiz) is None

    marca.rmdir()
    alvo = tmp_path / "alvo"
    alvo.mkdir()

    def atalho_concorrente(caminho, *args, **kwargs):
        if caminho == marca:
            caminho.symlink_to(alvo, target_is_directory=True)
        return original(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", atalho_concorrente)
    with pytest.raises(OSError, match="atalho"):
        criar_marca(raiz)


def test_problemas_da_estrutura_traduz_falha_de_observacao(tmp_path, monkeypatch):
    from neoprumo.estrutura_workspace import problemas_da_estrutura

    raiz = tmp_path / "workspace"
    raiz.mkdir()
    original = Path.is_dir

    def falhar(caminho):
        if caminho == raiz / "Inbox":
            raise PermissionError("system text")
        return original(caminho)

    monkeypatch.setattr(Path, "is_dir", falhar)

    problemas = problemas_da_estrutura(raiz)
    assert any("Inbox" in problema and "Não foi possível" in problema for problema in problemas)


@pytest.mark.parametrize(
    ("preparar", "esperado"),
    [
        (lambda marca: None, False),
        (lambda marca: marca.write_text("arquivo"), False),
        (lambda marca: marca.mkdir(), True),
        (lambda marca: marca.symlink_to(marca.parent, target_is_directory=True), False),
    ],
)
def test_tem_marca_real_distingue_tipo_sem_vazar_excecao(
    tmp_path, preparar, esperado
):
    from neoprumo.estrutura_workspace import tem_marca_real

    raiz = tmp_path / "workspace"
    raiz.mkdir()
    preparar(raiz / ".neoprumo")

    assert tem_marca_real(raiz) is esperado


def test_tem_marca_real_converte_outro_erro_de_observacao_em_falso(
    tmp_path, monkeypatch
):
    from neoprumo.estrutura_workspace import tem_marca_real

    raiz = tmp_path / "workspace"
    raiz.mkdir()
    original = Path.lstat

    def falhar(caminho):
        if caminho == raiz / ".neoprumo":
            raise PermissionError("system text")
        return original(caminho)

    monkeypatch.setattr(Path, "lstat", falhar)

    assert tem_marca_real(raiz) is False


def test_caminhos_de_estrutura_nao_removem_item_canonico(tmp_path, monkeypatch):
    from neoprumo.estrutura_workspace import criar_item_ausente, criar_marca

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def remocao_proibida(*_args, **_kwargs):
        raise AssertionError("caminho de estrutura tentou remover conteúdo")

    monkeypatch.setattr(Path, "unlink", remocao_proibida)
    monkeypatch.setattr(Path, "rmdir", remocao_proibida)

    assert criar_item_ausente(workspace, "Pauta.md", "arquivo")
    assert criar_marca(workspace)


def test_adotar_se_primeiro_preserva_configuracao_que_aparece_na_corrida(
    tmp_path, monkeypatch
):
    import builtins
    from neoprumo.ativo import adotar_se_primeiro

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    configuracao = Path(os.environ["XDG_CONFIG_HOME"]) / "neoprumo" / "config.json"
    original = builtins.open

    def concorrente(caminho, modo="r", *args, **kwargs):
        if Path(caminho) == configuracao and modo == "x":
            configuracao.write_bytes(b'{"workspace_ativo":"concorrente"}\n')
        return original(caminho, modo, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", concorrente)

    assert adotar_se_primeiro(workspace) is False
    assert json.loads(configuracao.read_text(encoding="utf-8"))["workspace_ativo"] == "concorrente"


def test_adotar_se_primeiro_propaga_outro_erro_de_gravacao(tmp_path, monkeypatch):
    import builtins
    from neoprumo.ativo import adotar_se_primeiro

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    original = builtins.open

    def falhar(caminho, modo="r", *args, **kwargs):
        if modo == "x" and Path(caminho).name == "config.json":
            raise PermissionError("system text")
        return original(caminho, modo, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", falhar)

    with pytest.raises(PermissionError):
        adotar_se_primeiro(workspace)
