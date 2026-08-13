import json
import multiprocessing
import os
import re
import stat
from datetime import datetime
from pathlib import Path

import pytest


DIA = "2026-08-13"


def _escritor_concorrente(
    workspace, texto, observado, iniciar, antes_do_write, liberar, resultados
):
    from neoprumo.diario_colheita import colher
    import neoprumo.diario_gravacao as modulo

    colher(Path(workspace), instante=datetime(2026, 8, 13, 15, 20).astimezone())
    observado.set()
    iniciar.wait(10)
    if antes_do_write is not None:
        original = modulo.escrever_tudo

        def bloquear(descritor, dados):
            antes_do_write.set()
            if not liberar.wait(10):
                raise OSError("o teste não liberou a escrita")
            return original(descritor, dados)

        modulo.escrever_tudo = bloquear
    resultados.put(modulo.operar_gravar(texto, DIA, Path(workspace)))


def chamar(executar_cli, workspace, texto="feito", dia=DIA, input=None):
    resultado = executar_cli(
        "diario", "gravar", texto, "--dia", dia,
        "--workspace", workspace, "--json", input=input,
    )
    return resultado, json.loads(resultado.stdout or resultado.stderr)


@pytest.fixture
def workspace(executar_cli, tmp_path):
    caminho = tmp_path / "casa"
    assert executar_cli("setup", caminho, "--json").returncode == 0
    return caminho


@pytest.fixture(autouse=True)
def relogio_fixo(monkeypatch):
    import neoprumo.diario_gravacao as modulo
    import neoprumo.diario_colheita as modulo_colheita

    class Relogio(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 13, 15, 20).astimezone()

    monkeypatch.setattr(
        modulo, "agora_local",
        lambda: datetime(2026, 8, 13, 15, 20).astimezone(),
    )
    monkeypatch.setattr(modulo_colheita, "datetime", Relogio)


def test_primeiro_fecho_publica_arquivo_completo(executar_cli, workspace):
    resultado, envelope = chamar(executar_cli, workspace, "um feito")

    arquivo = workspace / "Diario" / f"{DIA}.md"
    assert resultado.returncode == 0
    assert envelope["status"] == "gravado"
    assert envelope["dia"] == DIA
    assert envelope["arquivo"] == str(arquivo.resolve())
    assert re.fullmatch(r"## Sessão \d{2}:\d{2}", envelope["secao"])
    assert arquivo.read_bytes() == (
        b"# 2026-08-13\n\n" + envelope["secao"].encode() + b"\n\num feito\n"
    )
    assert not list((workspace / "Diario").glob(".diario-*.tmp"))


def test_segundo_fecho_apensa_sem_mudar_inode_metadados_ou_prefixo(executar_cli, workspace):
    arquivo = workspace / "Diario" / f"{DIA}.md"
    original = b"# 2026-08-13\n\n## Sess\xc3\xa3o 09:00\n\nprosa editada \xf0\x9f\x8c\xb5\n"
    arquivo.write_bytes(original)
    os.chmod(arquivo, 0o640)
    antes = arquivo.stat()

    resultado, envelope = chamar(executar_cli, workspace, "novo")

    depois = arquivo.stat()
    assert resultado.returncode == 0
    assert envelope["status"] == "gravado"
    assert arquivo.read_bytes() == (
        original + b"\n" + envelope["secao"].encode() + b"\n\nnovo\n"
    )
    assert depois.st_ino == antes.st_ino
    assert stat.S_IMODE(depois.st_mode) == stat.S_IMODE(antes.st_mode)
    assert (depois.st_uid, depois.st_gid) == (antes.st_uid, antes.st_gid)


@pytest.mark.parametrize(
    ("cauda", "separador"), [(b"texto", b"\n\n"), (b"texto\n", b"\n"), (b"texto\n\n\n", b"")]
)
def test_separador_preserva_quebras_e_garante_linha_em_branco(
    executar_cli, workspace, cauda, separador
):
    arquivo = workspace / "Diario" / f"{DIA}.md"
    prefixo = b"# 2026-08-13\n" + cauda
    arquivo.write_bytes(prefixo)

    resultado, envelope = chamar(executar_cli, workspace, "fim")

    assert resultado.returncode == 0
    assert arquivo.read_bytes() == (
        prefixo + separador + envelope["secao"].encode() + b"\n\nfim\n"
    )


def test_round_trip_normaliza_como_ficha_sem_indentar(executar_cli, workspace):
    texto = "\r\nCabeça\r\n\r\n  já indentado\r\nfinal\r\n\r\n"

    resultado, envelope = chamar(executar_cli, workspace, "-", input=texto)

    assert resultado.returncode == 0
    conteudo = (workspace / "Diario" / f"{DIA}.md").read_text()
    assert conteudo.endswith(
        envelope["secao"] + "\n\nCabeça\n\n\n  já indentado\nfinal\n\n"
    )


@pytest.mark.parametrize("texto", ["", " \n\t\n"])
def test_texto_vazio_recusa_antes_de_criar_trinco(executar_cli, workspace, texto):
    resultado, envelope = chamar(executar_cli, workspace, texto)

    assert resultado.returncode == 1
    assert envelope["status"] == "texto_vazio"
    assert not (workspace / "Diario" / f"{DIA}.md").exists()


def test_texto_com_utf8_invalido_e_recusado_sem_efeito(executar_cli, workspace):
    resultado, envelope = chamar(executar_cli, workspace, "\udcff")

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    assert any("UTF-8" in item for item in envelope["problemas"])
    assert not (workspace / "Diario" / f"{DIA}.md").exists()


def test_guarda_nao_aceita_dia_passado(executar_cli, workspace):
    resultado, envelope = chamar(executar_cli, workspace, dia="2026-08-12")

    assert resultado.returncode == 1
    assert envelope["status"] == "dia_virou"
    assert not list((workspace / "Diario").iterdir())


@pytest.mark.parametrize("tipo", ["symlink", "arquivo"])
def test_diario_precisa_ser_pasta_real(executar_cli, workspace, tipo):
    pasta = workspace / "Diario"
    pasta.rmdir()
    if tipo == "symlink":
        alvo = workspace / "fora"
        alvo.mkdir()
        os.symlink(alvo, pasta)
    else:
        pasta.write_text("não é pasta")

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    assert any("Diario" in item for item in envelope["problemas"])


@pytest.mark.parametrize("tipo", ["symlink", "diretorio", "sem_titulo", "outro_dia", "utf8_fim"])
def test_arquivo_hostil_e_recusado_sem_append(executar_cli, workspace, tipo):
    arquivo = workspace / "Diario" / f"{DIA}.md"
    if tipo == "symlink":
        alvo = workspace / "alvo"
        alvo.write_text(f"# {DIA}\n")
        os.symlink(alvo, arquivo)
    elif tipo == "diretorio":
        arquivo.mkdir()
    elif tipo == "sem_titulo":
        arquivo.write_text("prosa\n")
    elif tipo == "outro_dia":
        arquivo.write_text("# 2026-08-12\n")
    else:
        arquivo.write_bytes(f"# {DIA}\n".encode() + b"a" * 9000 + b"\xff")
    antes = arquivo.lstat()
    dados = arquivo.read_bytes() if arquivo.is_file() and not arquivo.is_symlink() else None

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    if dados is not None:
        assert arquivo.read_bytes() == dados
    assert arquivo.lstat().st_ino == antes.st_ino


def test_escrita_curta_e_retomada_no_append_e_temporario(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_descritores as modulo

    original = modulo.os.write

    def curta(fd, dados):
        return original(fd, dados[:3])

    monkeypatch.setattr(modulo.os, "write", curta)
    primeiro, _ = chamar(executar_cli, workspace, "primeiro longo")
    segundo, _ = chamar(executar_cli, workspace, "segundo longo")

    assert primeiro.returncode == segundo.returncode == 0
    texto = (workspace / "Diario" / f"{DIA}.md").read_text()
    assert "primeiro longo" in texto and "segundo longo" in texto


def test_falha_depois_de_bytes_no_append_e_parcial(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_descritores as modulo

    arquivo = workspace / "Diario" / f"{DIA}.md"
    arquivo.write_text(f"# {DIA}\n")
    original = modulo.os.write
    chamadas = 0

    def falhar(fd, dados):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return original(fd, dados[:4])
        raise OSError("falha simulada")

    monkeypatch.setattr(modulo.os, "write", falhar)
    resultado, envelope = chamar(executar_cli, workspace, "longo")

    assert resultado.returncode == 1
    assert envelope["status"] == "parcial"
    assert any("4 bytes" in item for item in envelope["problemas"])


def test_falha_na_escrita_do_temporario_recusa_e_remove_sobra(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_descritores as modulo

    original = modulo.os.write
    chamadas = 0

    def falhar(fd, dados):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return original(fd, dados[:4])
        raise OSError("falha simulada")

    monkeypatch.setattr(modulo.os, "write", falhar)
    resultado, envelope = chamar(executar_cli, workspace, "longo")

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    assert not (workspace / "Diario" / f"{DIA}.md").exists()
    assert not list((workspace / "Diario").glob(".diario-*.tmp"))


def test_dia_vira_antes_do_append_sem_escrever(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_gravacao as modulo

    arquivo = workspace / "Diario" / f"{DIA}.md"
    arquivo.write_text(f"# {DIA}\n")
    instantes = iter([
        datetime(2026, 8, 13, 23, 59).astimezone(),
        datetime(2026, 8, 14, 0, 0).astimezone(),
    ])
    monkeypatch.setattr(modulo, "agora_local", lambda: next(instantes))

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "dia_virou"
    assert arquivo.read_text() == f"# {DIA}\n"


def test_dia_vira_antes_do_link_remove_temporario(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_gravacao as modulo

    instantes = iter([
        datetime(2026, 8, 13, 23, 59).astimezone(),
        datetime(2026, 8, 14, 0, 0).astimezone(),
    ])
    monkeypatch.setattr(modulo, "agora_local", lambda: next(instantes))

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "dia_virou"
    assert not list((workspace / "Diario").iterdir())


def test_fsync_do_temporario_falha_antes_de_publicar(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_gravacao as modulo

    monkeypatch.setattr(modulo.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("sem sync")))

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    assert not list((workspace / "Diario").iterdir())


def test_fsync_depois_do_append_e_ambiguo_mas_gravado(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_gravacao as modulo

    arquivo = workspace / "Diario" / f"{DIA}.md"
    arquivo.write_text(f"# {DIA}\n")
    monkeypatch.setattr(modulo.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("sem sync")))

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert envelope["status"] == "gravado"
    assert envelope["problemas"] and envelope["acoes"]
    assert "feito" in arquivo.read_text()


def test_fsync_da_pasta_falha_depois_do_link_com_mensagem_propria(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    original = modulo.os.fsync

    def falhar_so_na_pasta(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("pasta sem sync")
        return original(fd)

    monkeypatch.setattr(modulo.os, "fsync", falhar_so_na_pasta)
    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert envelope["status"] == "gravado"
    assert any("nome do diário" in item for item in envelope["problemas"])


def test_nome_do_append_diverge_e_resultado_indeterminado(executar_cli, workspace, monkeypatch):
    import neoprumo.diario_gravacao as modulo

    arquivo = workspace / "Diario" / f"{DIA}.md"
    arquivo.write_text(f"# {DIA}\n")
    monkeypatch.setattr(modulo, "nome_aponta_para", lambda *args: False)

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "indeterminado"
    assert len(envelope["acoes"]) == 1
    assert "não repita" in envelope["acoes"][0]


def test_nome_final_diverge_do_temporario_e_resultado_indeterminado(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    original = modulo.mesma_identidade
    chamadas = 0

    def divergir_na_segunda(primeiro, segundo):
        nonlocal chamadas
        chamadas += 1
        return original(primeiro, segundo) if chamadas == 1 else False

    monkeypatch.setattr(modulo, "mesma_identidade", divergir_na_segunda)
    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "indeterminado"
    assert len(envelope["acoes"]) == 1


def test_pasta_substituida_antes_do_efeito_recusa_sem_escrita(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    arquivo = workspace / "Diario" / f"{DIA}.md"
    arquivo.write_text(f"# {DIA}\n")
    monkeypatch.setattr(modulo, "identidade_dir_canonico", lambda *args: False)

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    assert arquivo.read_text() == f"# {DIA}\n"


def test_pasta_substituida_depois_do_efeito_e_indeterminada(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    arquivo = workspace / "Diario" / f"{DIA}.md"
    arquivo.write_text(f"# {DIA}\n")
    respostas = iter([True, False])
    monkeypatch.setattr(modulo, "identidade_dir_canonico", lambda *args: next(respostas))

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "indeterminado"
    assert "feito" in arquivo.read_text()


def test_trinco_ocupado_recusa_sem_gravar(executar_cli, workspace):
    from neoprumo.diario_lock import trinco_diario

    with trinco_diario(workspace):
        resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "gravacao_em_andamento"
    assert not (workspace / "Diario" / f"{DIA}.md").exists()


def test_dois_escritores_com_mesma_leitura_nao_perdem_secao_em_silencio(workspace):
    arquivo = workspace / "Diario" / f"{DIA}.md"
    arquivo.write_text(f"# {DIA}\n\n## Sessão 08:00\n\nexistente\n")
    contexto = multiprocessing.get_context("fork")
    observado_um, observado_dois = contexto.Event(), contexto.Event()
    iniciar_um, iniciar_dois = contexto.Event(), contexto.Event()
    antes_do_write, liberar = contexto.Event(), contexto.Event()
    resultados = contexto.Queue()
    primeiro = contexto.Process(
        target=_escritor_concorrente,
        args=(workspace, "primeiro", observado_um, iniciar_um, antes_do_write, liberar, resultados),
    )
    segundo = contexto.Process(
        target=_escritor_concorrente,
        args=(workspace, "segundo", observado_dois, iniciar_dois, None, liberar, resultados),
    )
    primeiro.start()
    segundo.start()
    assert observado_um.wait(10) and observado_dois.wait(10)
    iniciar_um.set()
    assert antes_do_write.wait(10)
    iniciar_dois.set()
    segundo.join(10)
    liberar.set()
    primeiro.join(10)

    assert primeiro.exitcode == segundo.exitcode == 0
    envelopes = [resultados.get(timeout=2)[1] for _ in range(2)]
    assert sorted(item["status"] for item in envelopes) == [
        "gravacao_em_andamento", "gravado",
    ]
    texto = arquivo.read_text()
    assert texto.count("## Sessão ") == 2
    assert ("primeiro" in texto) != ("segundo" in texto)


def test_falha_ao_criar_trinco_recusa_sem_gravar(
    executar_cli, workspace, tmp_path, monkeypatch
):
    bloqueio = tmp_path / "estado-como-arquivo"
    bloqueio.write_text("ocupado")
    monkeypatch.setenv("XDG_STATE_HOME", str(bloqueio))

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    assert "trinco" in envelope["mensagem"]


def test_normalizacao_devolve_status_sem_depender_da_mensagem():
    from neoprumo.diario_gravacao import normalizar_texto

    texto, status, mensagem = normalizar_texto("  \n")

    assert texto is None
    assert status == "texto_vazio"
    assert mensagem == "O texto do diário está vazio."


def test_falha_de_unlink_deixa_sobra_declarada_e_nao_bloqueia_proximo_fecho(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    original = modulo.os.unlink
    falhou = False

    def falhar_primeiro(nome, *args, **kwargs):
        nonlocal falhou
        if str(nome).startswith(".diario-") and not falhou:
            falhou = True
            raise OSError("não removeu")
        return original(nome, *args, **kwargs)

    monkeypatch.setattr(modulo.os, "unlink", falhar_primeiro)
    primeiro, envelope = chamar(executar_cli, workspace, "primeiro")
    segundo, _ = chamar(executar_cli, workspace, "segundo")

    assert primeiro.returncode == segundo.returncode == 0
    assert envelope["status"] == "gravado"
    assert any(".diario-" in item for item in envelope["problemas"])
    assert len(list((workspace / "Diario").glob(".diario-*.tmp"))) == 1


def test_temporario_preexistente_sorteia_outro_nome_sem_apagar_sobra(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    sobra = workspace / "Diario" / f".diario-{DIA}-ocupado.tmp"
    sobra.write_text("do dono")
    antes = executar_cli("diario", "colher", "--workspace", workspace, "--json")
    colheita_antes = json.loads(antes.stdout)
    assert colheita_antes["total"] == 0
    assert colheita_antes["diario"] == {"existe": False, "secoes": 0}
    assert colheita_antes["problemas"] == []
    nomes = iter(["ocupado", "novo"])
    monkeypatch.setattr(modulo.secrets, "token_hex", lambda _: next(nomes))

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert envelope["status"] == "gravado"
    assert sobra.read_text() == "do dono"
    depois = executar_cli("diario", "colher", "--workspace", workspace, "--json")
    colheita_depois = json.loads(depois.stdout)
    assert colheita_depois["total"] == 0
    assert colheita_depois["diario"] == {"existe": True, "secoes": 1}
    assert colheita_depois["problemas"] == []


def test_publicacao_ordena_link_unlink_e_fsync_da_pasta(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    original_link = modulo.os.link
    original_unlink = modulo.os.unlink
    original_fsync = modulo.os.fsync
    ordem = []

    def link(*args, **kwargs):
        ordem.append("link")
        return original_link(*args, **kwargs)

    def unlink(nome, *args, **kwargs):
        if str(nome).startswith(".diario-"):
            ordem.append("unlink")
        return original_unlink(nome, *args, **kwargs)

    def fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            ordem.append("fsync_dir")
        return original_fsync(fd)

    monkeypatch.setattr(modulo.os, "link", link)
    monkeypatch.setattr(modulo.os, "unlink", unlink)
    monkeypatch.setattr(modulo.os, "fsync", fsync)

    resultado, _ = chamar(executar_cli, workspace)

    assert resultado.returncode == 0
    assert ordem == ["link", "unlink", "fsync_dir"]


def test_falha_entre_temporario_e_link_nao_deixa_diario(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_gravacao as modulo

    monkeypatch.setattr(
        modulo.os, "link", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("sem link"))
    )

    resultado, envelope = chamar(executar_cli, workspace)

    assert resultado.returncode == 1
    assert envelope["status"] == "recusado"
    assert not list((workspace / "Diario").iterdir())
