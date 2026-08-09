import hashlib
import json
from pathlib import Path

import pytest


def criar_workspace(tmp_path, executar_cli, nome="workspace"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def criar_item(workspace, nome, conteudo=b"abc"):
    item = workspace / "Acervo" / nome
    item.write_bytes(conteudo if isinstance(conteudo, bytes) else conteudo.encode("utf-8"))
    return item


def digital(conteudo=b"abc"):
    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")
    return hashlib.sha256(conteudo).hexdigest()


def resposta(nome, decisao="deixar", conteudo=b"abc", **extras):
    return {"item": nome, "decisao": decisao, "digital": digital(conteudo), **extras}


def bloco(respostas, pagina="acervo-2026-08-05-101500"):
    return json.dumps(
        {"superficie": "acervo", "pagina": pagina, "respostas": respostas},
        ensure_ascii=True,
    )


def aplicar(executar_modulo, workspace, respostas, usar_json=True):
    argumentos = ["superficie", "aplicar", "--workspace", workspace]
    if usar_json:
        argumentos.append("--json")
    return executar_modulo(*argumentos, input=bloco(respostas))


def test_bloco_vazio_nao_fotografa_pauta_e_usa_contadores_do_acervo(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "vazio")
    pauta = workspace / "Pauta.md"
    pauta.unlink()
    alvo = tmp_path / "pauta-fora.md"
    alvo.write_text("fora", encoding="utf-8")
    pauta.symlink_to(alvo)

    resultado = aplicar(executar_modulo, workspace, [])

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0 and dados["status"] == "aplicado"
    assert (dados["incluidos"], dados["excluidos"], dados["deixados"], dados["recusados"]) == (0, 0, 0, 0)
    assert dados["resultados"] == []
    assert "despachados" not in dados and "adiados" not in dados


def test_preflight_recusa_acervo_ausente_sem_traceback(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "acervo-ausente")
    (workspace / "Acervo").rmdir()

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.md")])

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert dados["resultados"] is None and "Traceback" not in resultado.stdout


@pytest.mark.parametrize("campo", ["pagina", "item", "decisao", "observacao", "digital"])
def test_preflight_recusa_surrogate_sem_vazar_valor(
    campo, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"surrogate-{campo}")
    criar_item(workspace, "abc.md")
    dados = {
        "superficie": "acervo",
        "pagina": "pagina",
        "respostas": [resposta("abc.md", observacao="nota")],
    }
    if campo == "pagina":
        dados[campo] = "\ud800"
    else:
        dados["respostas"][0][campo] = "\ud800"

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json",
        input=json.dumps(dados, ensure_ascii=True),
    )

    saida = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and saida["status"] == "recusado"
    assert "\\ud800" not in resultado.stdout.lower()
    assert saida["resultados"] is None


def test_preflight_do_acervo_e_puro(tmp_path, executar_cli, capsys):
    from neoprumo.superficie_acervo_preflight import conferir_acervo

    workspace = criar_workspace(tmp_path, executar_cli, "puro")
    criar_item(workspace, "abc.md")
    capsys.readouterr()

    resultado = conferir_acervo(json.loads(bloco([resposta("abc.md")])), workspace)

    captura = capsys.readouterr()
    assert captura.out == captura.err == ""
    assert resultado["recusa"] is None and resultado["plano"][0]["bytes"] == b"abc"


def test_same_radical_com_pauta_recusa_so_o_segundo(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "radical-pauta")
    criar_item(workspace, "foo.md", "primeiro")
    criar_item(workspace, "foo.txt", "segundo")

    resultado = aplicar(executar_modulo, workspace, [
        resposta("foo.md", "pauta", "primeiro"),
        resposta("foo.txt", "pauta", "segundo"),
    ])

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "aplicado_com_recusas"
    assert [item["status"] for item in dados["resultados"]] == ["incluido", "recusado"]
    assert not (workspace / "Acervo" / "foo.md").exists()
    assert (workspace / "Acervo" / "foo.txt").is_file()
    assert "conversa" in dados["resultados"][1]["mensagem"]


def test_same_radical_com_lixo_executa_os_dois(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "radical-lixo")
    criar_item(workspace, "foo.md")
    criar_item(workspace, "foo.txt")

    resultado = aplicar(executar_modulo, workspace, [
        resposta("foo.md", "lixo"), resposta("foo.txt", "lixo")
    ])

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert [item["status"] for item in dados["resultados"]] == ["excluido", "excluido"]


def test_same_radical_com_deixar_nao_cria_colisao(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "radical-deixar")
    criar_item(workspace, "foo.md")
    criar_item(workspace, "foo.txt")

    resultado = aplicar(executar_modulo, workspace, [
        resposta("foo.md", "deixar", observacao="um"),
        resposta("foo.txt", "deixar", observacao="dois"),
    ])

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert [item["status"] for item in dados["resultados"]] == ["deixado", "deixado"]


def test_same_radical_com_marcador_preexistente_envelhece_globalmente(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "radical-marcado")
    criar_item(workspace, "foo.md")
    criar_item(workspace, "foo.txt")
    (workspace / "Pauta.md").write_text(
        "  — acervo foo, incluído em 2026-08-05\n", encoding="utf-8"
    )

    resultado = aplicar(executar_modulo, workspace, [
        resposta("foo.md", "lixo"), resposta("foo.txt", "lixo")
    ])

    assert json.loads(resultado.stdout)["status"] == "envelhecida"
    assert (workspace / "Acervo" / "foo.md").is_file()
    assert (workspace / "Acervo" / "foo.txt").is_file()


@pytest.mark.parametrize(
    ("linha", "envelhece"),
    [
        ("texto com acervo abc no meio\n", False),
        ("  — acervo abc-2, incluído em 2026-08-05\n", False),
        ("  — inbox abc, despachado em 2026-08-05\n", False),
        ("  — acervo abc, incluído em 2026-08-05\n", True),
    ],
)
def test_marcador_do_acervo_exige_linha_canonica_inteira(
    linha, envelhece, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "forma-marcador")
    criar_item(workspace, "abc.md")
    (workspace / "Pauta.md").write_text(linha, encoding="utf-8")

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.md")])

    assert json.loads(resultado.stdout)["status"] == (
        "envelhecida" if envelhece else "aplicado"
    )


@pytest.mark.parametrize("tipo", ["ausente", "binario", "pasta", "symlink"])
def test_aplicar_acervo_ignora_projetos(tipo, tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, f"projetos-{tipo}")
    criar_item(workspace, "abc.md")
    projetos = workspace / "Projetos.md"
    projetos.unlink()
    if tipo == "binario":
        projetos.write_bytes(b"\xff")
    elif tipo == "pasta":
        projetos.mkdir()
    elif tipo == "symlink":
        alvo = tmp_path / "projetos-fora"
        alvo.write_bytes(b"\xff")
        projetos.symlink_to(alvo)

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.md")])

    assert resultado.returncode == 0


@pytest.mark.parametrize("decisao", ["pauta", "atacar"])
@pytest.mark.parametrize("conteudo", [b"\xff", b" \n\t"])
def test_pauta_e_atacar_exigem_texto_aproveitavel(
    decisao, conteudo, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"dominio-{decisao}")
    criar_item(workspace, "abc.md", conteudo)

    resultado = aplicar(
        executar_modulo, workspace, [resposta("abc.md", decisao, conteudo)]
    )

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado" and dados["resultados"] is None
    assert "excluir" in " ".join(dados["acoes"])


@pytest.mark.parametrize("decisao", ["lixo", "deixar"])
@pytest.mark.parametrize("conteudo", [b"\xff", b" \n\t"])
def test_lixo_e_deixar_aceitam_binario_e_vazio(
    decisao, conteudo, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"aceita-{decisao}")
    item = criar_item(workspace, "abc.bin", conteudo)

    resultado = aplicar(
        executar_modulo, workspace,
        [resposta("abc.bin", decisao, conteudo, observacao="fica")],
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert dados["resultados"][0]["status"] == (
        "excluido" if decisao == "lixo" else "deixado"
    )
    assert item.exists() is (decisao == "deixar")


def test_deixar_com_observacao_e_reaplicavel_sem_efeito(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "deixar-reaplicavel")
    item = criar_item(workspace, "abc.md", "fica")
    respostas = [resposta("abc.md", "deixar", "fica", observacao="lembrar")]
    antes = item.read_bytes()

    primeira = aplicar(executar_modulo, workspace, respostas)
    segunda = aplicar(executar_modulo, workspace, respostas)

    assert primeira.returncode == segunda.returncode == 0
    assert json.loads(segunda.stdout)["resultados"][0]["observacao"] == "lembrar"
    assert item.read_bytes() == antes


def test_reaplicar_bloco_com_efeito_envelhece_sem_duplicar(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "reaplicar")
    criar_item(workspace, "abc.md", "nota")
    respostas = [resposta("abc.md", "pauta", "nota")]

    primeira = aplicar(executar_modulo, workspace, respostas)
    pauta_apos_primeira = (workspace / "Pauta.md").read_bytes()
    segunda = aplicar(executar_modulo, workspace, respostas)

    assert primeira.returncode == 0
    assert segunda.returncode == 1
    assert json.loads(segunda.stdout)["status"] == "envelhecida"
    assert (workspace / "Pauta.md").read_bytes() == pauta_apos_primeira


@pytest.mark.parametrize("tipo", ["pasta", "symlink"])
def test_preflight_recusa_pauta_nao_regular(tipo, tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, f"pauta-{tipo}")
    criar_item(workspace, "abc.md")
    pauta = workspace / "Pauta.md"
    pauta.unlink()
    if tipo == "pasta":
        pauta.mkdir()
    else:
        alvo = tmp_path / "pauta-fora"
        alvo.write_text("fora", encoding="utf-8")
        pauta.symlink_to(alvo)

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.md", "lixo")])

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado" and dados["resultados"] is None
    assert (workspace / "Acervo" / "abc.md").is_file()


@pytest.mark.parametrize("decisao", ["pauta", "atacar", "lixo", "deixar"])
def test_corrida_de_digital_recusa_as_quatro_decisoes(
    decisao, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import acervo as modulo_acervo
    from neoprumo import superficie_acervo_preflight as modulo_preflight
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"corrida-digital-{decisao}")
    item = criar_item(workspace, "abc.md")
    leitura_real = Path.read_bytes
    leituras = 0

    def mudar(caminho):
        nonlocal leituras
        if caminho == item:
            leituras += 1
            if leituras == 2:
                item.write_bytes(b"mudou")
        return leitura_real(caminho)

    monkeypatch.setattr(modulo_preflight, "ler_bytes", mudar)
    monkeypatch.setattr(modulo_acervo, "ler_bytes", mudar)
    codigo, dados, _ = operar_aplicacao(
        workspace, bloco([resposta("abc.md", decisao, observacao="fica")])
    )

    assert codigo == 1 and dados["status"] == "aplicado_com_recusas"
    assert dados["resultados"][0]["status"] == "recusado"
    esperado = "pauta" if decisao in ("pauta", "atacar") else (
        "lixo" if decisao == "lixo" else None
    )
    assert dados["resultados"][0]["destino"] == esperado
    assert item.read_bytes() == b"mudou"


def test_oserror_na_releitura_recusa_item_isolado(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import acervo as modulo_acervo
    from neoprumo import superficie_acervo_preflight as modulo_preflight
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "releitura")
    item = criar_item(workspace, "abc.md")
    leitura_real = Path.read_bytes
    monkeypatch.setattr(modulo_preflight, "ler_bytes", leitura_real)

    def negar(caminho):
        if caminho == item:
            raise PermissionError(13, "Permissão negada")
        return leitura_real(caminho)

    monkeypatch.setattr(modulo_acervo, "ler_bytes", negar)
    codigo, dados, _ = operar_aplicacao(
        workspace, bloco([resposta("abc.md", "lixo")])
    )

    assert codigo == 1 and dados["resultados"][0]["status"] == "recusado"
    assert item.is_file()


@pytest.mark.parametrize("decisao", ["pauta", "atacar", "lixo", "deixar"])
def test_corrida_de_marcador_recusa_as_quatro_decisoes(
    decisao, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import acervo_base
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"corrida-marcador-{decisao}")
    item = criar_item(workspace, "abc.md")
    pauta = workspace / "Pauta.md"
    ler_real = acervo_base.ler_bytes
    leituras = 0

    def inserir(caminho):
        nonlocal leituras
        if caminho == pauta:
            leituras += 1
            if leituras == 2:
                pauta.write_text(
                    "  — acervo abc, incluído em 2026-08-05\n", encoding="utf-8"
                )
        return ler_real(caminho)

    monkeypatch.setattr(acervo_base, "ler_bytes", inserir)
    codigo, dados, _ = operar_aplicacao(
        workspace, bloco([resposta("abc.md", decisao, observacao="fica")])
    )

    assert codigo == 1 and dados["resultados"][0]["status"] == "recusado"
    assert item.is_file() and "conversa" in dados["resultados"][0]["mensagem"]


@pytest.mark.parametrize("decisao", ["pauta", "atacar", "lixo", "deixar"])
@pytest.mark.parametrize("tipo", ["pasta", "symlink"])
def test_pauta_mudando_de_tipo_na_corrida_fecha_as_quatro_decisoes(
    decisao, tipo, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import acervo as modulo_acervo
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, f"tipo-{tipo}-{decisao}")
    item = criar_item(workspace, "abc.md")
    pauta = workspace / "Pauta.md"
    foto_real = modulo_acervo.fotografar_pauta

    def trocar(_):
        pauta.unlink()
        if tipo == "pasta":
            pauta.mkdir()
        else:
            alvo = tmp_path / f"fora-{decisao}"
            alvo.write_text("fora", encoding="utf-8")
            pauta.symlink_to(alvo)
        return foto_real(workspace)

    monkeypatch.setattr(modulo_acervo, "fotografar_pauta", trocar)
    codigo, dados, _ = operar_aplicacao(
        workspace, bloco([resposta("abc.md", decisao, observacao="fica")])
    )

    assert codigo == 1 and dados["resultados"][0]["status"] == "recusado"
    assert item.is_file()


def test_lote_misto_tem_envelopes_contadores_e_destinos_exatos(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "misto")
    criar_item(workspace, "incluir.md", "incluir")
    criar_item(workspace, "atacar.md", "atacar")
    criar_item(workspace, "excluir.md", "excluir")
    criar_item(workspace, "deixar.md", "deixar")
    respostas = [
        resposta("incluir.md", "pauta", "incluir"),
        resposta("atacar.md", "atacar", "atacar", observacao="agora"),
        resposta("excluir.md", "lixo", "excluir"),
        resposta("deixar.md", "deixar", "deixar", observacao="talvez"),
    ]

    resultado = aplicar(executar_modulo, workspace, respostas)

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert (dados["incluidos"], dados["excluidos"], dados["deixados"], dados["recusados"]) == (2, 1, 1, 0)
    assert [item["destino"] for item in dados["resultados"]] == ["pauta", "pauta", "lixo", None]
    assert [item["status"] for item in dados["resultados"]] == ["incluido", "incluido", "excluido", "deixado"]
    chaves = {"status", "problemas", "acoes", "mensagem", "workspace", "item", "id", "destino", "entrada", "decisao", "observacao"}
    assert all(set(item) == chaves for item in dados["resultados"])


def test_relatorio_humano_do_acervo_e_recusa_global_visivel(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "humano")
    criar_item(workspace, "abc.md")
    sucesso = aplicar(
        executar_modulo, workspace,
        [resposta("abc.md", observacao="lembrar")], usar_json=False,
    )
    linha = json.loads(sucesso.stdout.splitlines()[0])
    assert set(linha) == {"entrada", "status", "mensagem", "decisao", "observacao"}
    assert sucesso.stderr == ""

    recusa = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace,
        input=bloco([{"item": "x", "decisao": "gaveta"}]),
    )
    assert recusa.returncode == 1 and recusa.stdout == ""
    assert len(recusa.stderr.splitlines()) >= 3


def test_precedencia_workspace_e_json_preserva_envelope_legado(executar_modulo):
    resultado = executar_modulo("superficie", "aplicar", "--json", input="{quebrado")
    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "sem_ativo"
    assert set(("resultados", "despachados", "recusados", "adiados")) <= set(dados)
    assert "incluidos" not in dados


def test_bloco_legado_de_despacho_continua_pedindo_pagina_nova(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "legado")
    entrada = json.dumps({
        "superficie": "despacho", "pagina": "antiga",
        "respostas": [{"item": "x.md", "decisao": "pauta"}],
    })

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json", input=entrada
    )

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado"
    assert dados["acoes"] == ["Esta página é de uma versão antiga; gere a página de novo."]
