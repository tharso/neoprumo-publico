import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


FUSO_LOCAL = timezone(timedelta(hours=-3))
DIA_UM = datetime(2026, 8, 12, 23, 59, tzinfo=FUSO_LOCAL)
DIA_DOIS = datetime(2026, 8, 13, 0, 1, tzinfo=FUSO_LOCAL)


def _workspace(tmp_path, executar_cli, nome="retrato"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def _executar(workspace, instante, capsys, usar_json=True):
    from neoprumo.retrato import executar_retrato

    codigo = executar_retrato(workspace, usar_json=usar_json, instante=instante)
    saida = capsys.readouterr()
    return codigo, saida, json.loads(saida.out) if usar_json else None


def _fotografar(raiz, ignorar=()):
    ignorados = {Path(item) for item in ignorar}
    foto = {}
    for caminho in sorted(raiz.rglob("*")):
        relativo = caminho.relative_to(raiz)
        if relativo in ignorados:
            continue
        estado = caminho.lstat()
        foto[str(relativo)] = (
            stat.S_IFMT(estado.st_mode),
            caminho.read_bytes() if stat.S_ISREG(estado.st_mode) else None,
        )
    return foto


def test_primeiro_do_dia_carimba_e_repeticao_nao_regrava(
    tmp_path, executar_cli, capsys
):
    workspace = _workspace(tmp_path, executar_cli)
    marcador = workspace / ".neoprumo" / "retrato.json"

    codigo, _, primeiro = _executar(workspace, DIA_UM, capsys)
    assert codigo == 0
    assert primeiro == {
        "status": "carimbado",
        "problemas": [],
        "acoes": [],
        "mensagem": "Retrato do dia disparado e carimbado.",
        "workspace": str(workspace),
        "hoje": "2026-08-12",
        "anterior": None,
        "primeiro_do_dia": True,
    }
    assert marcador.read_bytes() == b'{"dia": "2026-08-12"}\n'
    estado = (marcador.read_bytes(), marcador.stat().st_mtime_ns)

    codigo, _, repetido = _executar(workspace, DIA_UM, capsys)
    assert codigo == 0
    assert repetido["status"] == "repetido"
    assert repetido["primeiro_do_dia"] is False
    assert repetido["anterior"] == repetido["hoje"] == "2026-08-12"
    assert (marcador.read_bytes(), marcador.stat().st_mtime_ns) == estado


def test_comando_cli_carimba_workspace_explicito(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli, "cli-explicito")

    resposta = executar_cli("retrato", "--workspace", workspace, "--json")

    assert resposta.returncode == 0
    dados = json.loads(resposta.stdout)
    assert dados["status"] == "carimbado"
    assert dados["workspace"] == str(workspace.resolve())
    assert dados["primeiro_do_dia"] is True
    assert (workspace / ".neoprumo/retrato.json").read_text(
        encoding="utf-8"
    ) == json.dumps({"dia": dados["hoje"]}, ensure_ascii=False) + "\n"


def test_virada_real_de_meia_noite_carimba_o_novo_dia(
    tmp_path, executar_cli, capsys
):
    workspace = _workspace(tmp_path, executar_cli, "meia-noite")

    _, _, antes = _executar(workspace, DIA_UM, capsys)
    _, _, depois = _executar(workspace, DIA_DOIS, capsys)

    assert antes["hoje"] == "2026-08-12"
    assert depois["status"] == "carimbado"
    assert depois["hoje"] == "2026-08-13"
    assert depois["anterior"] == "2026-08-12"


@pytest.mark.parametrize(
    "fuso",
    [timezone.utc, timezone(timedelta(hours=14))],
    ids=["utc", "kiritimati"],
)
def test_data_civil_segue_o_fuso_local_sem_hora_absoluta(
    tmp_path, executar_cli, capsys, fuso
):
    workspace = _workspace(tmp_path, executar_cli, f"fuso-{fuso}")
    instante = datetime(2026, 8, 13, 0, 1, tzinfo=fuso)

    _, _, resultado = _executar(workspace, instante, capsys)

    assert resultado["hoje"] == instante.date().isoformat()
    assert resultado["primeiro_do_dia"] is True


def test_data_futura_repete_por_desigualdade_e_regride_o_marcador(
    tmp_path, executar_cli, capsys
):
    workspace = _workspace(tmp_path, executar_cli, "relogio-e-fuso")
    marcador = workspace / ".neoprumo" / "retrato.json"
    marcador.write_text('{"dia": "2030-01-01"}\n', encoding="utf-8")

    _, _, resultado = _executar(workspace, DIA_UM, capsys)

    assert resultado["status"] == "carimbado"
    assert resultado["anterior"] == "2030-01-01"
    assert resultado["problemas"] == []
    assert marcador.read_bytes() == b'{"dia": "2026-08-12"}\n'


@pytest.mark.parametrize(
    ("conteudo", "causa"),
    [
        (b"\xff", "UTF-8"),
        (b"{", "JSON"),
        (b'{"outro": 1}', "chave dia"),
        (b'{"dia": "2026-02-30"}', "data válida"),
    ],
)
def test_marcador_corrompido_e_autocorrigido(
    tmp_path, executar_cli, capsys, conteudo, causa
):
    workspace = _workspace(tmp_path, executar_cli, "corrompido")
    marcador = workspace / ".neoprumo" / "retrato.json"
    marcador.write_bytes(conteudo)

    _, _, resultado = _executar(workspace, DIA_UM, capsys)

    assert resultado["status"] == "carimbado"
    assert resultado["anterior"] is None
    assert len(resultado["problemas"]) == 1
    assert "retrato.json" in resultado["problemas"][0]
    assert causa in resultado["problemas"][0]
    assert marcador.read_bytes() == b'{"dia": "2026-08-12"}\n'
    _, _, limpo = _executar(workspace, DIA_UM, capsys)
    assert limpo["status"] == "repetido"
    assert limpo["problemas"] == []


@pytest.mark.parametrize("tipo", ["symlink", "diretorio"])
def test_obstaculo_no_marcador_nao_e_removido(
    tmp_path, executar_cli, capsys, tipo
):
    workspace = _workspace(tmp_path, executar_cli, tipo)
    marcador = workspace / ".neoprumo" / "retrato.json"
    if tipo == "symlink":
        alvo = tmp_path / "alvo.json"
        alvo.write_bytes(b"intacto")
        marcador.symlink_to(alvo)
        antes = (marcador.lstat().st_mode, alvo.read_bytes())
    else:
        marcador.mkdir()
        (marcador / "intacto").write_bytes(b"sim")
        antes = _fotografar(marcador)

    _, _, resultado = _executar(workspace, DIA_UM, capsys)

    assert resultado["status"] == "carimbo_falhou"
    assert resultado["primeiro_do_dia"] is True
    assert resultado["anterior"] is None
    assert resultado["problemas"] and resultado["acoes"]
    assert "repetir" in resultado["acoes"][0]
    if tipo == "symlink":
        assert (marcador.lstat().st_mode, alvo.read_bytes()) == antes
    else:
        assert _fotografar(marcador) == antes


def test_falha_de_gravacao_mantem_retrato_util_e_avisa_na_saida_humana(
    tmp_path, executar_cli, capsys
):
    workspace = _workspace(tmp_path, executar_cli, "sem-permissao")
    pasta = workspace / ".neoprumo"
    pasta.chmod(0o500)
    try:
        codigo, saida, _ = _executar(workspace, DIA_UM, capsys, usar_json=False)
    finally:
        pasta.chmod(0o700)

    assert codigo == 0
    assert saida.err == ""
    assert "carimbo falhou" in saida.out
    assert "pode repetir na próxima sessão" in saida.out
    assert not (pasta / "retrato.json").exists()


@pytest.mark.parametrize("corrompido", [True, False])
def test_falhas_compostas_preservam_leitura_e_acrescentam_gravacao(
    tmp_path, executar_cli, capsys, corrompido
):
    workspace = _workspace(tmp_path, executar_cli, f"composta-{corrompido}")
    marcador = workspace / ".neoprumo" / "retrato.json"
    marcador.write_bytes(b"{") if corrompido else marcador.write_text(
        '{"dia": "2030-01-01"}\n', encoding="utf-8"
    )
    (workspace / ".neoprumo").chmod(0o500)
    try:
        _, _, resultado = _executar(workspace, DIA_UM, capsys)
    finally:
        (workspace / ".neoprumo").chmod(0o700)

    assert resultado["status"] == "carimbo_falhou"
    assert resultado["anterior"] == (None if corrompido else "2030-01-01")
    assert len(resultado["problemas"]) == (2 if corrompido else 1)
    assert resultado["acoes"] and "repetir" in resultado["acoes"][0]


def test_cli_resolve_ativo_recusa_explicito_e_mantem_campos_nulos(
    tmp_path, executar_cli
):
    sem_ativo = executar_cli("retrato", "--json")
    assert sem_ativo.returncode == 1
    workspace = _workspace(tmp_path, executar_cli, "ativo")
    (workspace / ".neoprumo").rename(workspace / ".identidade-removida")
    ativo_invalido = executar_cli("retrato", "--json")
    recusado = executar_cli(
        "retrato", "--workspace", tmp_path / "nao-workspace", "--json"
    )

    for resposta, status in (
        (sem_ativo, "sem_ativo"),
        (ativo_invalido, "ativo_invalido"),
        (recusado, "recusado"),
    ):
        assert resposta.returncode == 1
        dados = json.loads(resposta.stdout)
        assert dados["status"] == status
        assert dados["hoje"] is None
        assert dados["anterior"] is None
        assert dados["primeiro_do_dia"] is None


def test_cli_rejeita_argumento_desconhecido_pelo_parser(executar_modulo):
    resultado = executar_modulo("retrato", "--desconhecido")

    assert resultado.returncode == 2
    assert "--desconhecido" in resultado.stderr
    assert resultado.stdout == ""


def test_so_marcador_muda_e_configuracao_fica_intacta(
    tmp_path, executar_cli, capsys, monkeypatch
):
    workspace = _workspace(tmp_path, executar_cli, "fotografia")
    xdg = tmp_path / "xdg-fotografado"
    xdg.mkdir()
    (xdg / "intacto").write_bytes("configuração".encode("utf-8"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    antes_workspace = _fotografar(workspace)
    antes_xdg = _fotografar(xdg)

    _executar(workspace, DIA_UM, capsys)

    assert _fotografar(workspace, [Path(".neoprumo/retrato.json")]) == antes_workspace
    assert _fotografar(xdg) == antes_xdg

    marcador = workspace / ".neoprumo/retrato.json"
    marcador.unlink()
    marcador.mkdir()
    (marcador / "intacto").write_bytes(b"falha fotografada")
    antes_da_falha = _fotografar(workspace)
    _executar(workspace, DIA_UM, capsys)
    assert _fotografar(workspace) == antes_da_falha
    assert _fotografar(xdg) == antes_xdg
