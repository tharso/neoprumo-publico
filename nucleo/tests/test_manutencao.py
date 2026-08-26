import json
from datetime import date
from typing import get_type_hints

import pytest

from conftest import RAIZ_PROJETO
from neoprumo.manutencao import aviso_de_manutencao


def test_interface_declara_retorno_str_ou_none():
    assert get_type_hints(aviso_de_manutencao)["return"] == str | None


@pytest.mark.parametrize(
    ("hoje", "esperado"),
    [
        (date(2026, 8, 30), None),
        (date(2026, 8, 31), "7 dias"),
        (date(2026, 9, 1), "8 dias"),
    ],
)
def test_lembrete_comeca_no_setimo_dia(hoje, esperado):
    aviso = aviso_de_manutencao(
        hoje=hoje, data_versao="2026-08-24", ambiente={}
    )

    if esperado is None:
        assert aviso is None
    else:
        assert esperado in aviso


def test_data_ilegivel_cala_sem_sinal_de_falha():
    assert aviso_de_manutencao(
        hoje=date(2026, 9, 1), data_versao="ontem", ambiente={}
    ) is None


def test_data_futura_cala_sem_sinal_de_falha():
    assert aviso_de_manutencao(
        hoje=date(2026, 8, 23), data_versao="2026-08-24", ambiente={}
    ) is None


def test_limiar_invalido_cala_sem_sinal_de_falha():
    assert aviso_de_manutencao(
        hoje=date(2026, 9, 1), ambiente={}, limiar="sete"
    ) is None


def test_variavel_nao_vazia_silencia_e_vazia_mantem_ativo(monkeypatch):
    from neoprumo import manutencao

    nome = "NEOPRUMO_SEM_AVISO_DE_IDADE"
    # Data fixa no módulo, argumento omitido: o caminho default segue
    # exercitado sem depender da idade real do pacote.
    monkeypatch.setattr(manutencao, "__data_versao__", "2026-08-24")

    assert aviso_de_manutencao(
        hoje=date(2026, 9, 1), ambiente={nome: "1"}
    ) is None
    assert aviso_de_manutencao(
        hoje=date(2026, 9, 1), ambiente={nome: ""}
    ) is not None


def test_texto_declara_so_manutencao_e_repete_os_comandos_do_onboarding():
    # Data fixa como nos irmãos: o texto é o contrato, não a idade do pacote.
    aviso = aviso_de_manutencao(
        hoje=date(2026, 9, 1), data_versao="2026-08-24", ambiente={}
    )
    readme = (RAIZ_PROJETO / "README.md").read_text(encoding="utf-8")
    comandos = (
        "claude plugin update neoprumo@neoprumo",
        "codex plugin marketplace upgrade neoprumo",
        "codex plugin add neoprumo@neoprumo",
    )

    assert "8 dias" in aviso
    assert "vale conferir se saiu uma nova" in aviso
    assert "há uma versão nova" not in aviso.lower()
    for comando in comandos:
        assert comando in aviso
        assert comando in readme


@pytest.mark.parametrize(
    "etapa",
    ["_esta_silenciado", "_hoje_utc", "_ler_data", "_montar_mensagem"],
)
def test_falha_em_cada_etapa_preserva_envelope_byte_a_byte(
    etapa, monkeypatch, capsys
):
    from neoprumo import manutencao, sonda

    monkeypatch.setattr(manutencao, "__data_versao__", "2000-01-01")
    monkeypatch.setenv("NEOPRUMO_SEM_AVISO_DE_IDADE", "1")
    sonda.sondar(usar_hook=True)
    anterior = capsys.readouterr().out

    def falhar(*_argumentos, **_opcoes):
        raise RuntimeError("falha injetada")

    monkeypatch.setenv("NEOPRUMO_SEM_AVISO_DE_IDADE", "")
    monkeypatch.setattr(manutencao, etapa, falhar)
    sonda.sondar(usar_hook=True)
    depois = capsys.readouterr().out

    envelope = json.loads(depois)
    assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert depois == anterior
