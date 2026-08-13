import json
import os
import stat
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


RAIZ = Path(__file__).parents[2]
BASE = {
    "status",
    "problemas",
    "acoes",
    "mensagem",
    "workspace",
    "candidato",
    "elegiveis",
    "elegiveis_acervo",
    "elegiveis_em_espera",
}


def criar_workspace(tmp_path, executar_cli, nome="workspace"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def criar_item(workspace, nome, conteudo="ideia", mtime=None):
    item = workspace / "Acervo" / nome
    if isinstance(conteudo, bytes):
        item.write_bytes(conteudo)
    else:
        item.write_text(conteudo, encoding="utf-8")
    if mtime is not None:
        marca = mtime.timestamp()
        os.utime(item, (marca, marca))
    return item


def observar(workspace, instante):
    from neoprumo.ressurgimento import operar_ressurgimento

    codigo, resultado = operar_ressurgimento(workspace, instante=instante)
    assert codigo == 0
    return resultado


def test_rotacao_deterministica_descansa_cobre_o_ciclo_e_remove_resolvido(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "rotacao")
    nomes = [
        "2026-07-20-090000.md",
        "2026-07-21-090000.md",
        "2026-07-22-090000.md",
    ]
    for nome in nomes:
        criar_item(workspace, nome, nome)
    primeiro_dia = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)

    candidatos = [
        observar(workspace, primeiro_dia + timedelta(days=dia))["candidato"]["nome"]
        for dia in range(3)
    ]

    assert observar(workspace, primeiro_dia)["candidato"]["nome"] == candidatos[0]
    assert candidatos[0] != candidatos[1]
    assert set(candidatos) == set(nomes)
    (workspace / "Acervo" / candidatos[0]).unlink()
    seguinte = observar(workspace, primeiro_dia)
    assert seguinte["candidato"]["nome"] != candidatos[0]
    assert seguinte["elegiveis"] == 2


def test_ordem_espelha_builder_com_mais_antigo_e_desempate_code_point(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "ordem")
    referencia = datetime(2026, 8, 20, 9, tzinfo=timezone.utc)
    for nome in ("b.md", "A.md", "a.md"):
        criar_item(
            workspace,
            nome,
            nome,
            mtime=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        )
    criar_item(workspace, "mais-antigo.md", "antigo", mtime=datetime(
        2026, 7, 31, 9, tzinfo=timezone.utc
    ))

    resultado = observar(workspace, referencia)
    ordem = ["mais-antigo.md", "A.md", "a.md", "b.md"]

    assert resultado["candidato"]["nome"] == ordem[referencia.date().toordinal() % 4]


def test_limiar_exato_exclui_seis_dias_e_inclui_sete_com_conteudo_integral(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "limiar")
    instante = datetime(2026, 8, 10, 9, tzinfo=timezone.utc)
    criar_item(workspace, "2026-08-04-000000.md", "novo")
    conteudo = "linha inicial\n\nlinha final\n"
    criar_item(workspace, "2026-08-03-235959-12.md", conteudo)

    resultado = observar(workspace, instante)

    assert resultado["elegiveis"] == 1
    assert resultado["candidato"] == {
        "origem": "acervo",
        "nome": "2026-08-03-235959-12.md",
        "manchete": None,
        "idade": 7,
        "conteudo": conteudo,
        "origem_entrada": None,
    }
    assert resultado["candidato"]["conteudo"].strip()


def test_so_itens_novos_retorna_sem_candidato(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "novos")
    criar_item(workspace, "2026-08-04-120000.md")

    resultado = observar(
        workspace, datetime(2026, 8, 10, 9, tzinfo=timezone.utc)
    )

    assert resultado == {
        "status": "sem_candidato",
        "problemas": [],
        "acoes": [],
        "mensagem": "Nada a ressurgir por enquanto.",
        "workspace": str(workspace),
        "candidato": None,
        "elegiveis": 0,
        "elegiveis_acervo": 0,
        "elegiveis_em_espera": 0,
    }


def test_enumeracao_ignora_observaveis_e_avisa_nomes_stat_e_idade(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import ressurgimento as modulo

    workspace = criar_workspace(tmp_path, executar_cli, "enumeracao")
    acervo = workspace / "Acervo"
    criar_item(workspace, ".oculto.md", "oculto")
    criar_item(workspace, "controle\n.md", "controle")
    (acervo / "pasta").mkdir()
    alvo = tmp_path / "fora.md"
    alvo.write_text("fora", encoding="utf-8")
    (acervo / "atalho.md").symlink_to(alvo)
    criar_item(
        workspace,
        "por-mtime.md",
        "válido",
        mtime=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    scandir_real = modulo.os.scandir

    class Entrada:
        def __init__(self, nome, erro=None, estado=None):
            self.name = nome
            self.path = str(acervo / nome)
            self.erro = erro
            self.estado = estado

        def stat(self, follow_symlinks=False):
            if self.erro:
                raise self.erro
            return self.estado

    class Entradas:
        def __init__(self, itens):
            self.itens = itens

        def __enter__(self):
            return iter(self.itens)

        def __exit__(self, tipo, valor, traceback):
            return False

    with scandir_real(acervo) as entradas:
        reais = list(entradas)
    extras = [
        Entrada("nome-\udcff.md"),
        Entrada("sem-stat.md", PermissionError(13, "Permissão negada")),
        Entrada(
            "sem-data.md",
            estado=SimpleNamespace(st_mode=stat.S_IFREG, st_mtime=12345),
        ),
    ]
    datetime_real = modulo.datetime

    class DataComFalha(datetime):
        @classmethod
        def fromtimestamp(cls, valor, tz=None):
            if valor == 12345:
                raise OverflowError("fora do calendário")
            return datetime_real.fromtimestamp(valor, tz=tz)

    monkeypatch.setattr(modulo, "datetime", DataComFalha)
    monkeypatch.setattr(
        modulo.os,
        "scandir",
        lambda caminho: Entradas(reais + extras) if caminho == acervo else scandir_real(caminho),
    )

    resultado = observar(
        workspace, datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    )

    assert resultado["elegiveis"] == 1
    assert resultado["candidato"]["nome"] == "por-mtime.md"
    assert len(resultado["problemas"]) == 4
    assert any("incompatível com UTF-8" in item for item in resultado["problemas"])
    assert any("caracteres de controle" in item for item in resultado["problemas"])
    assert any("sem-stat.md" in item and "não foi incluído" in item for item in resultado["problemas"])
    assert any("sem-data.md" in item and "ler a data" in item for item in resultado["problemas"])


def test_apresentabilidade_so_e_lida_depois_da_idade_e_agrega_um_aviso(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import ressurgimento as modulo

    workspace = criar_workspace(tmp_path, executar_cli, "conteudo")
    caminhos = {
        "ilegivel": criar_item(workspace, "2026-08-01-000000.md", "x"),
        "binario": criar_item(workspace, "2026-08-01-000001.md", b"\xff"),
        "vazio": criar_item(workspace, "2026-08-01-000002.md", b""),
        "branco": criar_item(workspace, "2026-08-01-000003.md", " \n\t"),
        "novo": criar_item(workspace, "2026-08-09-000000.md", "não leia"),
    }
    ler_real = modulo.ler_bytes
    lidos = []

    def ler(caminho):
        lidos.append(caminho)
        if caminho == caminhos["ilegivel"]:
            raise PermissionError(13, "Permissão negada")
        if caminho == caminhos["novo"]:
            raise AssertionError("item novo não pode ter o conteúdo lido")
        return ler_real(caminho)

    monkeypatch.setattr(modulo, "ler_bytes", ler)

    resultado = observar(
        workspace, datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    )

    assert resultado["status"] == "sem_candidato"
    assert resultado["candidato"] is None and resultado["elegiveis"] == 0
    assert caminhos["novo"] not in lidos
    assert resultado["problemas"] == [
        "4 itens do acervo sem conteúdo legível pra apresentar; "
        "revise-os pelo garimpo ou na conversa."
    ]


@pytest.mark.parametrize("tipo", ["ausente", "arquivo", "symlink", "ilegivel"])
def test_acervo_invalido_ou_ilegivel_e_recusa_global(
    tipo, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import ressurgimento as modulo

    workspace = criar_workspace(tmp_path, executar_cli, f"acervo-{tipo}")
    acervo = workspace / "Acervo"
    if tipo != "ilegivel":
        acervo.rmdir()
        if tipo == "arquivo":
            acervo.write_text("ocupado", encoding="utf-8")
        elif tipo == "symlink":
            alvo = tmp_path / "acervo-fora"
            alvo.mkdir()
            acervo.symlink_to(alvo, target_is_directory=True)
    else:
        scandir_real = modulo.os.scandir

        def negar(caminho):
            if caminho == acervo:
                raise PermissionError(13, "Permissão negada")
            return scandir_real(caminho)

        monkeypatch.setattr(modulo.os, "scandir", negar)

    codigo, resultado = modulo.operar_ressurgimento(
        workspace, instante=datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    )

    assert codigo == 1 and resultado["status"] == "recusado"
    assert set(resultado) == BASE
    assert resultado["candidato"] is None and resultado["elegiveis"] is None
    assert resultado["problemas"] and resultado["acoes"]


def test_cinco_envelopes_tem_forma_unica_e_streams_json(
    tmp_path, executar_cli
):
    sem_ativo = executar_cli("ressurgimento", "--json")
    workspace = criar_workspace(tmp_path, executar_cli, "ativo")
    sem_candidato = executar_cli(
        "ressurgimento", "--workspace", workspace, "--json"
    )
    criar_item(workspace, "2020-01-01-000000.md", "conteúdo")
    candidato = executar_cli("ressurgimento", "--json")
    (workspace / ".neoprumo").rename(workspace / ".identidade-removida")
    ativo_invalido = executar_cli("ressurgimento", "--json")
    nao_workspace = tmp_path / "nao-workspace"
    nao_workspace.mkdir()
    recusado = executar_cli(
        "ressurgimento", "--workspace", nao_workspace, "--json"
    )

    casos = [
        (sem_ativo, "sem_ativo", 1, None),
        (sem_candidato, "sem_candidato", 0, 0),
        (candidato, "candidato", 0, 1),
        (ativo_invalido, "ativo_invalido", 1, None),
        (recusado, "recusado", 1, None),
    ]
    for saida, status_esperado, codigo, elegiveis in casos:
        dados = json.loads(saida.stdout)
        assert saida.returncode == codigo and saida.stderr == ""
        assert saida.stdout.count("\n") == 1
        assert set(dados) == BASE and dados["status"] == status_esperado
        assert dados["elegiveis"] == elegiveis
        if codigo:
            assert dados["candidato"] is None


def test_modo_humano_mostra_resumo_conteudo_avisos_e_recusa_no_stderr(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "humano")
    criar_item(workspace, "2020-01-01-000000.md", "substância integral\nsegunda linha")
    criar_item(workspace, "2019-01-01-000000.md", b"\xff")

    sucesso = executar_cli("ressurgimento", "--workspace", workspace)
    recusa = executar_cli(
        "ressurgimento", "--workspace", tmp_path / "inexistente"
    )

    assert sucesso.returncode == 0 and sucesso.stderr == ""
    assert "2020-01-01-000000.md" in sucesso.stdout
    assert "há " in sucesso.stdout and "1 elegível" in sucesso.stdout
    assert "substância integral\nsegunda linha" in sucesso.stdout
    assert "Aviso:" in sucesso.stdout
    assert recusa.returncode == 1 and recusa.stdout == ""
    assert "workspace" in recusa.stderr.lower()


def test_os_dois_wrappers_entregam_o_mesmo_documento_json(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "wrappers")
    criar_item(workspace, "2020-01-01-000000.md", "uma ideia")
    modulo = executar_modulo(
        "ressurgimento", "--workspace", workspace, "--json"
    )
    binario = subprocess.run(
        [
            str(RAIZ / "bin" / "neoprumo"),
            "ressurgimento",
            "--workspace",
            str(workspace),
            "--json",
        ],
        cwd=RAIZ,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert modulo.returncode == binario.returncode == 0
    assert modulo.stderr == binario.stderr == ""
    assert json.loads(modulo.stdout) == json.loads(binario.stdout)


@pytest.mark.parametrize("wrapper", ["modulo", "binario"])
def test_sintaxe_invalida_sai_com_codigo_2(wrapper, executar_modulo):
    if wrapper == "modulo":
        resultado = executar_modulo("ressurgimento", "extra")
    else:
        resultado = subprocess.run(
            [str(RAIZ / "bin" / "neoprumo"), "ressurgimento", "extra"],
            cwd=RAIZ,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )

    assert resultado.returncode == 2
    assert "usage:" in resultado.stderr and "Traceback" not in resultado.stderr


def test_virada_ocorre_na_meia_noite_civil_local_em_dois_fusos(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "fusos")
    criar_item(workspace, "2020-01-01-000000.md", "a")
    criar_item(workspace, "2020-01-01-000001.md", "b")
    anterior = os.environ.get("TZ")
    casos = [
        (
            "UTC",
            datetime(2026, 8, 5, 23, 59, tzinfo=timezone.utc),
            datetime(2026, 8, 6, 0, 1, tzinfo=timezone.utc),
        ),
        (
            "Pacific/Kiritimati",
            datetime(2026, 8, 5, 9, 59, tzinfo=timezone.utc),
            datetime(2026, 8, 5, 10, 1, tzinfo=timezone.utc),
        ),
    ]
    try:
        for fuso, antes, depois in casos:
            os.environ["TZ"] = fuso
            time.tzset()
            candidato_antes = observar(workspace, antes)["candidato"]["nome"]
            candidato_depois = observar(workspace, depois)["candidato"]["nome"]
            assert candidato_antes != candidato_depois
    finally:
        if anterior is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = anterior
        time.tzset()


def test_ressurgimento_e_somente_leitura_inclusive_configuracao_xdg(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "fotografia")
    criar_item(workspace, "2020-01-01-000000.md", "conteúdo")
    (workspace / "Pauta.md").write_text(
        "- [ ] Espera datada [em espera]\n"
        "  detalhe preservado\n"
        "  — inbox datada, despachado em 2020-01-01\n"
        "- [ ] Espera manual [em espera]\n",
        encoding="utf-8",
    )
    configuracao = tmp_path / "configuracao-xdg"
    antes = fotografar(workspace, configuracao)

    resultado = executar_cli("ressurgimento", "--json")

    assert resultado.returncode == 0
    assert fotografar(workspace, configuracao) == antes


def fotografar(*raizes):
    foto = {}
    for raiz in raizes:
        caminhos = [raiz]
        for pasta, diretorios, arquivos in os.walk(raiz, followlinks=False):
            caminhos.extend(Path(pasta) / nome for nome in diretorios + arquivos)
        for caminho in map(Path, caminhos):
            estado = caminho.lstat()
            foto[str(caminho)] = (
                stat.S_IFMT(estado.st_mode),
                caminho.read_bytes() if stat.S_ISREG(estado.st_mode) else None,
                estado.st_mtime_ns,
            )
    return foto
