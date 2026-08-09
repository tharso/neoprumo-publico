import hashlib
import json
from pathlib import Path

import pytest


def criar_workspace(tmp_path, executar_cli, nome):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def criar_item(workspace, nome, conteudo=b"abc"):
    item = workspace / "Inbox" / nome
    item.write_bytes(conteudo)
    return item


def bloco(respostas):
    return json.dumps(
        {
            "superficie": "despacho",
            "pagina": "despacho-2026-08-05-101500",
            "respostas": respostas,
        }
    )


def resposta(nome, decisao, conteudo=b"abc", **extras):
    return {
        "item": nome,
        "decisao": decisao,
        "digital": hashlib.sha256(conteudo).hexdigest(),
        **extras,
    }


@pytest.mark.parametrize("destino", ["pauta", "projeto"])
@pytest.mark.parametrize("preexistente", [True, False])
@pytest.mark.parametrize("via", ["unitario", "lote"])
def test_falha_ao_remover_origem_compensa_destino_textual(
    destino, preexistente, via, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import destinos_textuais
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"compensa-{via}-{destino}-{preexistente}")
    item = criar_item(workspace, "abc.md")
    arquivo = workspace / ("Pauta.md" if destino == "pauta" else "Projetos.md")
    anterior = b"# anterior\n"
    if preexistente:
        arquivo.write_bytes(anterior)
    else:
        arquivo.unlink()
    unlink_real = destinos_textuais.Path.unlink

    def falhar_origem(caminho, *args, **kwargs):
        if caminho == item:
            raise PermissionError(13, "Permissão negada")
        return unlink_real(caminho, *args, **kwargs)

    monkeypatch.setattr(destinos_textuais.Path, "unlink", falhar_origem)
    if via == "unitario":
        argumentos = ["despacho", item.name, destino]
        if destino == "projeto":
            argumentos.append("Museu")
        resultado = executar_cli(*argumentos, "--workspace", workspace, "--json")
        codigo, dados = resultado.returncode, json.loads(resultado.stdout)
    else:
        extras = {"projeto": "Museu"} if destino == "projeto" else {}
        codigo, dados, _ = operar_aplicacao(
            workspace,
            bloco([resposta(item.name, destino, **extras)]),
        )

    assert codigo == 1
    assert dados["status"] in ("recusado", "aplicado_com_recusas")
    assert item.read_bytes() == b"abc"
    if preexistente:
        assert arquivo.read_bytes() == anterior
    else:
        assert not arquivo.exists()


@pytest.mark.parametrize("destino", ["pauta", "projeto"])
@pytest.mark.parametrize("via", ["unitario", "lote"])
def test_falha_da_compensacao_avisa_sobra_em_mensagem_autocontida(
    destino, via, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import destinos_textuais
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"falha-dupla-{via}-{destino}")
    item = criar_item(workspace, "abc.md")
    arquivo = workspace / ("Pauta.md" if destino == "pauta" else "Projetos.md")
    arquivo.unlink()
    unlink_real = destinos_textuais.Path.unlink

    def falhar(caminho, *args, **kwargs):
        if caminho in (item, arquivo):
            raise PermissionError(13, "Permissão negada")
        return unlink_real(caminho, *args, **kwargs)

    monkeypatch.setattr(destinos_textuais.Path, "unlink", falhar)
    if via == "unitario":
        argumentos = ["despacho", item.name, destino]
        if destino == "projeto":
            argumentos.append("Museu")
        resultado = executar_cli(*argumentos, "--workspace", workspace, "--json")
        codigo, dados = resultado.returncode, json.loads(resultado.stdout)
    else:
        extras = {"projeto": "Museu"} if destino == "projeto" else {}
        codigo, agregado, _ = operar_aplicacao(
            workspace,
            bloco([resposta(item.name, destino, **extras)]),
        )
        dados = agregado["resultados"][0]

    assert codigo == 1
    assert item.is_file() and arquivo.is_file()
    assert "não saiu da Inbox" in dados["mensagem"]
    assert arquivo.name in dados["mensagem"]
    assert "confira antes de aplicar de novo" in dados["mensagem"]


def test_marcador_de_sobra_bloqueia_recolagem_do_lote(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import destinos_textuais
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "sobra-recolagem")
    item = criar_item(workspace, "abc.md")
    pauta = workspace / "Pauta.md"
    pauta.unlink()
    unlink_real = destinos_textuais.Path.unlink

    def falhar(caminho, *args, **kwargs):
        if caminho in (item, pauta):
            raise PermissionError(13, "Permissão negada")
        return unlink_real(caminho, *args, **kwargs)

    monkeypatch.setattr(destinos_textuais.Path, "unlink", falhar)
    texto = bloco([resposta(item.name, "pauta")])
    primeira, _, _ = operar_aplicacao(workspace, texto)
    monkeypatch.setattr(destinos_textuais.Path, "unlink", unlink_real)
    segunda, dados, _ = operar_aplicacao(workspace, texto)

    assert primeira == segunda == 1
    assert dados["status"] == "envelhecida"
    assert dados["acoes"] == ["Confira o destino e despache esse item na conversa."]


def test_corrida_de_digital_recusa_item_isolado_e_lote_segue(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "corrida-digital")
    primeiro = criar_item(workspace, "primeiro.md")
    criar_item(workspace, "segundo.md", b"segundo")
    leitura_real = Path.read_bytes
    leituras = 0

    def mudar_na_reconferencia(caminho):
        nonlocal leituras
        if caminho == primeiro:
            leituras += 1
            if leituras == 2:
                primeiro.write_bytes(b"mudou na corrida")
        return leitura_real(caminho)

    monkeypatch.setattr(Path, "read_bytes", mudar_na_reconferencia)
    codigo, dados, _ = operar_aplicacao(
        workspace,
        bloco([
            resposta("primeiro.md", "acervo"),
            resposta("segundo.md", "acervo", b"segundo"),
        ]),
    )

    assert codigo == 1 and dados["status"] == "aplicado_com_recusas"
    assert [item["status"] for item in dados["resultados"]] == ["recusado", "despachado"]
    assert primeiro.read_bytes() == b"mudou na corrida"
    assert (workspace / "Acervo" / "segundo.md").is_file()


@pytest.mark.parametrize("decisao", ["pauta", "acervo"])
def test_corrida_de_marcador_recusa_item_sem_duplicar(
    decisao, tmp_path, executar_cli, monkeypatch
):
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"corrida-marcador-{decisao}")
    item = criar_item(workspace, "abc.md")
    pauta = workspace / "Pauta.md"
    leitura_real = Path.read_bytes
    leituras_pauta = 0

    def inserir_na_reconferencia(caminho):
        nonlocal leituras_pauta
        if caminho == pauta:
            leituras_pauta += 1
            if leituras_pauta == 2:
                pauta.write_text(
                    "  — inbox abc, despachado em 2026-08-05\n", encoding="utf-8"
                )
        return leitura_real(caminho)

    monkeypatch.setattr(Path, "read_bytes", inserir_na_reconferencia)
    codigo, dados, _ = operar_aplicacao(
        workspace,
        bloco([resposta("abc.md", decisao)]),
    )

    assert codigo == 1 and dados["status"] == "aplicado_com_recusas"
    assert item.is_file()
    assert pauta.read_text(encoding="utf-8").count("inbox abc") == 1
    assert "conversa" in dados["resultados"][0]["mensagem"]


def test_oserror_na_reconferencia_recusa_item_isolado_sem_efeito(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "corrida-oserror")
    item = criar_item(workspace, "abc.md")
    leitura_real = Path.read_bytes
    leituras = 0

    def negar_segunda(caminho):
        nonlocal leituras
        if caminho == item:
            leituras += 1
            if leituras == 2:
                raise PermissionError(13, "Permissão negada")
        return leitura_real(caminho)

    monkeypatch.setattr(Path, "read_bytes", negar_segunda)
    codigo, dados, _ = operar_aplicacao(
        workspace,
        bloco([resposta("abc.md", "lixo")]),
    )

    assert codigo == 1 and dados["status"] == "aplicado_com_recusas"
    assert item.read_bytes() == b"abc"


def test_falha_imprevisivel_no_meio_nao_interrompe_demais_e_recolagem_envelhece(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import despacho as modulo_despacho
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "falha-meio")
    for nome in ("um.md", "dois.md", "tres.md"):
        criar_item(workspace, nome)
    replace_real = modulo_despacho.Path.replace

    def falhar_no_meio(caminho, destino):
        if caminho.name == "dois.md":
            raise PermissionError(13, "Permissão negada")
        return replace_real(caminho, destino)

    monkeypatch.setattr(modulo_despacho.Path, "replace", falhar_no_meio)
    texto = bloco([resposta(nome, "acervo") for nome in ("um.md", "dois.md", "tres.md")])
    codigo, dados, _ = operar_aplicacao(workspace, texto)
    codigo_recolagem, recolagem, _ = operar_aplicacao(workspace, texto)

    assert codigo == 1 and dados["status"] == "aplicado_com_recusas"
    assert [item["status"] for item in dados["resultados"]] == ["despachado", "recusado", "despachado"]
    assert codigo_recolagem == 1 and recolagem["status"] == "envelhecida"
