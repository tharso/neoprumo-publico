import hashlib
import json
import os
import stat
from pathlib import Path

import pytest


DIGITAL_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def criar_workspace(tmp_path, executar_cli, nome="workspace"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def criar_item(workspace, nome, conteudo=b"abc"):
    item = workspace / "Inbox" / nome
    item.write_bytes(conteudo if isinstance(conteudo, bytes) else conteudo.encode())
    return item


def digital(conteudo):
    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")
    return hashlib.sha256(conteudo).hexdigest()


def resposta(nome, decisao="acervo", conteudo=b"abc", **extras):
    return {
        "item": nome,
        "decisao": decisao,
        "digital": digital(conteudo),
        **extras,
    }


def bloco(respostas, pagina="despacho-2026-08-05-101500", superficie="despacho"):
    return json.dumps(
        {"superficie": superficie, "pagina": pagina, "respostas": respostas},
        ensure_ascii=True,
    )


def aplicar(executar_modulo, workspace, respostas, usar_json=True):
    argumentos = ["superficie", "aplicar", "--workspace", workspace]
    if usar_json:
        argumentos.append("--json")
    return executar_modulo(*argumentos, input=bloco(respostas))


def fotografar(raiz):
    foto = {}
    for pasta, diretorios, arquivos in os.walk(raiz, followlinks=False):
        for nome in diretorios + arquivos:
            caminho = Path(pasta) / nome
            estado = caminho.lstat()
            foto[str(caminho.relative_to(raiz))] = (
                stat.S_IFMT(estado.st_mode),
                caminho.read_bytes() if stat.S_ISREG(estado.st_mode) else None,
                estado.st_mtime_ns if stat.S_ISREG(estado.st_mode) else None,
            )
    return foto


CASOS_ENTRADA_INVALIDA = [
    pytest.param(None, "objeto", id="entrada-nao-objeto"),
    pytest.param({"item": 7, "decisao": "pauta", "digital": DIGITAL_ABC}, "item", id="item-nao-string"),
    pytest.param({"item": "", "decisao": "pauta", "digital": DIGITAL_ABC}, "item", id="item-vazio"),
    pytest.param({"item": "../abc.md", "decisao": "pauta", "digital": DIGITAL_ABC}, "item", id="item-caminho"),
    pytest.param({"item": "abc\u0000.md", "decisao": "pauta", "digital": DIGITAL_ABC}, "item", id="item-controle"),
    pytest.param({"item": "abc.md", "decisao": "gaveta", "digital": DIGITAL_ABC}, "decisao", id="decisao-desconhecida"),
    pytest.param({"item": "abc.md", "decisao": "projeto", "digital": DIGITAL_ABC}, "projeto", id="projeto-ausente"),
    pytest.param({"item": "abc.md", "decisao": "projeto", "projeto": 9, "digital": DIGITAL_ABC}, "projeto", id="projeto-nao-string"),
    pytest.param({"item": "abc.md", "decisao": "projeto", "projeto": "  ", "digital": DIGITAL_ABC}, "projeto", id="projeto-vazio"),
    pytest.param({"item": "abc.md", "decisao": "projeto", "projeto": "Casa\nMuseu", "digital": DIGITAL_ABC}, "projeto", id="projeto-multilinha"),
    pytest.param({"item": "abc.md", "decisao": "projeto", "projeto": "Casa\u0007", "digital": DIGITAL_ABC}, "projeto", id="projeto-controle"),
    pytest.param({"item": "abc.md", "decisao": "pauta", "observacao": 9, "digital": DIGITAL_ABC}, "observacao", id="observacao-nao-string"),
    pytest.param({"item": "abc.md", "decisao": "pauta"}, "digital", id="digital-ausente"),
    pytest.param({"item": "abc.md", "decisao": "pauta", "digital": 7}, "digital", id="digital-nao-string"),
    pytest.param({"item": "abc.md", "decisao": "pauta", "digital": "a" * 63}, "digital", id="digital-tamanho"),
    pytest.param({"item": "abc.md", "decisao": "pauta", "digital": "A" * 64}, "digital", id="digital-maiuscula"),
]


@pytest.mark.parametrize(("invalida", "campo"), CASOS_ENTRADA_INVALIDA)
def test_preflight_recusa_global_toda_entrada_invalida_sem_efeito(
    invalida, campo, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"estrutura-{campo}")
    criar_item(workspace, "valido.md")
    antes = fotografar(workspace)

    resultado = aplicar(
        executar_modulo,
        workspace,
        [invalida, resposta("valido.md")],
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert dados["resultados"] is None
    assert any("Resposta 1:" in problema and campo in problema for problema in dados["problemas"])
    assert fotografar(workspace) == antes


@pytest.mark.parametrize(
    "campo",
    ["superficie", "pagina", "item", "decisao", "projeto", "observacao", "digital"],
)
def test_preflight_recusa_surrogate_nos_sete_campos_sem_vazar_valor(
    campo, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"surrogate-{campo}")
    criar_item(workspace, "abc.md")
    dados = {
        "superficie": "despacho",
        "pagina": "pagina",
        "respostas": [
            {
                "item": "abc.md",
                "decisao": "projeto",
                "projeto": "Museu",
                "observacao": "nota",
                "digital": DIGITAL_ABC,
            }
        ],
    }
    if campo in ("superficie", "pagina"):
        dados[campo] = "\ud800"
    else:
        dados["respostas"][0][campo] = "\ud800"

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json",
        input=json.dumps(dados, ensure_ascii=True),
    )

    saida = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and saida["status"] == "recusado"
    assert saida["resultados"] is None
    assert "\\ud800" not in resultado.stdout.lower()


def test_preflight_lista_todas_as_violacoes_na_ordem_fixa(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "todas-violacoes")
    criar_item(workspace, "intacto.md")
    antes = fotografar(workspace)
    ruins = [
        {"item": "../x", "decisao": "gaveta", "projeto": 8, "observacao": 9, "digital": "A"},
        None,
    ]

    resultado = aplicar(executar_modulo, workspace, ruins)

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado"
    assert len(dados["problemas"]) == 6
    assert [problema.split(":", 1)[0] for problema in dados["problemas"]] == [
        "Resposta 1", "Resposta 1", "Resposta 1", "Resposta 1", "Resposta 1", "Resposta 2"
    ]
    assert [campo in dados["problemas"][indice] for indice, campo in enumerate(
        ("item", "decisao", "projeto", "observacao", "digital")
    )] == [True] * 5
    assert fotografar(workspace) == antes


def test_preflight_recusa_duas_respostas_para_mesmo_item(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "duplicata")
    criar_item(workspace, "foo.md")
    antes = fotografar(workspace)

    resultado = aplicar(
        executar_modulo,
        workspace,
        [resposta("foo"), resposta("foo.md")],
    )

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado"
    assert any("duas respostas para o mesmo item" in p.lower() for p in dados["problemas"])
    assert fotografar(workspace) == antes


def test_reaplicar_bloco_com_efeito_recusa_como_envelhecida_sem_novo_efeito(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "reaplicar")
    criar_item(workspace, "abc.md")
    respostas = [resposta("abc.md", "pauta")]

    primeira = aplicar(executar_modulo, workspace, respostas)
    depois_da_primeira = fotografar(workspace)
    segunda = aplicar(executar_modulo, workspace, respostas)

    dados = json.loads(segunda.stdout)
    assert primeira.returncode == 0
    assert segunda.returncode == 1 and dados["status"] == "envelhecida"
    assert fotografar(workspace) == depois_da_primeira


@pytest.mark.parametrize("causa", ["ausente", "digital"])
def test_pagina_envelhecida_por_ausencia_ou_digital_recusa_lote_inteiro(
    causa, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"velha-{causa}")
    item = criar_item(workspace, "abc.md")
    outro = criar_item(workspace, "outro.md", b"outro")
    respostas = [resposta("abc.md"), resposta("outro.md", conteudo=b"outro")]
    if causa == "ausente":
        item.unlink()
    else:
        item.write_bytes(b"mudou")
    antes = fotografar(workspace)

    resultado = aplicar(executar_modulo, workspace, respostas)

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "envelhecida"
    assert dados["acoes"] == ["Gere a página de novo."]
    assert "abc.md" in " ".join(dados["problemas"])
    assert outro.is_file() and fotografar(workspace) == antes


def test_item_novo_depois_da_pagina_nao_envelhece(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "item-novo")
    criar_item(workspace, "abc.md")
    novo = criar_item(workspace, "novo.md", b"novo")

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.md")])

    assert resultado.returncode == 0
    assert json.loads(resultado.stdout)["status"] == "aplicado"
    assert novo.read_bytes() == b"novo"


@pytest.mark.parametrize(
    ("arquivo", "linha", "decisao"),
    [
        ("Pauta.md", "  — inbox abc, despachado em 2026-08-05\n", "acervo"),
        ("Projetos.md", "- 2026-08-05 (inbox abc): já foi\n", "pauta"),
    ],
)
def test_marcador_em_qualquer_destino_envelhece_mesmo_com_decisao_trocada(
    arquivo, linha, decisao, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"marcador-{arquivo}")
    criar_item(workspace, "abc.md")
    (workspace / arquivo).write_text(linha, encoding="utf-8")
    antes = fotografar(workspace)

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.md", decisao)])

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "envelhecida"
    assert dados["acoes"] == ["Confira o destino e despache esse item na conversa."]
    assert "já há registro" in " ".join(dados["problemas"])
    assert fotografar(workspace) == antes


@pytest.mark.parametrize(
    ("pauta", "projetos", "envelhece"),
    [
        ("texto com inbox abc no meio\n", "", False),
        ("  — inbox abc-2, despachado em 2026-08-05\n", "", False),
        ("  — inbox abc, despachado em 2026-08-05\n", "", True),
        ("", "  - 2026-08-05 (inbox abc): continuação\n", False),
    ],
)
def test_marcador_usa_linha_canonica_e_coluna_correta(
    pauta, projetos, envelhece, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "forma-marcador")
    criar_item(workspace, "abc.md")
    (workspace / "Pauta.md").write_text(pauta, encoding="utf-8")
    (workspace / "Projetos.md").write_text(projetos, encoding="utf-8")

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.md", "depois")])

    dados = json.loads(resultado.stdout)
    assert dados["status"] == ("envelhecida" if envelhece else "aplicado")


def test_marcador_de_radical_igual_entre_extensoes_e_conservador(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "radical-igual")
    criar_item(workspace, "abc.txt")
    (workspace / "Pauta.md").write_text(
        "  — inbox abc, despachado em 2026-08-05\n", encoding="utf-8"
    )

    resultado = aplicar(executar_modulo, workspace, [resposta("abc.txt")])

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "envelhecida"
    assert "conversa" in " ".join(dados["acoes"])


def test_acoes_de_envelhecimento_misto_sao_exatas(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "misto")
    criar_item(workspace, "marcado.md")
    (workspace / "Pauta.md").write_text(
        "  — inbox marcado, despachado em 2026-08-05\n", encoding="utf-8"
    )
    respostas = [resposta("ausente.md"), resposta("marcado.md")]

    resultado = aplicar(executar_modulo, workspace, respostas)

    assert json.loads(resultado.stdout)["acoes"] == [
        "Resolva na conversa os itens que já têm registro no destino.",
        "Depois, gere a página de novo para o restante.",
    ]


@pytest.mark.parametrize(
    ("caso", "decisao", "conteudo"),
    [
        ("item-binario", "pauta", b"\xff"),
        ("item-vazio", "pauta", b" \n\t"),
        ("projetos-binario", "projeto", b"nota"),
    ],
)
def test_preflight_recusa_dominio_previsivel_sem_efeito(
    caso, decisao, conteudo, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"dominio-{caso}")
    criar_item(workspace, "item.md", conteudo)
    if caso == "projetos-binario":
        (workspace / "Projetos.md").write_bytes(b"\xff")
    antes = fotografar(workspace)
    extras = {"projeto": "Museu"} if decisao == "projeto" else {}

    resultado = aplicar(
        executar_modulo,
        workspace,
        [resposta("item.md", decisao, conteudo=conteudo, **extras)],
    )

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado" and dados["resultados"] is None
    assert dados["problemas"] and dados["acoes"]
    assert fotografar(workspace) == antes


def test_projetos_nao_utf8_aparece_uma_vez_com_varias_respostas_projeto(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "projetos-binario-unico")
    criar_item(workspace, "primeiro.md", b"primeiro")
    criar_item(workspace, "segundo.md", b"segundo")
    (workspace / "Projetos.md").write_bytes(b"\xff")

    resultado = aplicar(
        executar_modulo,
        workspace,
        [
            resposta("primeiro.md", "projeto", b"primeiro", projeto="Museu"),
            resposta("segundo.md", "projeto", b"segundo", projeto="Museu"),
        ],
    )

    dados = json.loads(resultado.stdout)
    assert dados["problemas"].count("Projetos.md não é texto UTF-8.") == 1
    assert dados["acoes"].count("Confira Projetos.md e tente novamente.") == 1


@pytest.mark.parametrize(("arquivo", "tipo"), [("Pauta.md", "pasta"), ("Projetos.md", "symlink")])
def test_preflight_recusa_destino_textual_nao_regular(
    arquivo, tipo, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"destino-{arquivo}")
    criar_item(workspace, "item.md")
    destino = workspace / arquivo
    destino.unlink()
    if tipo == "pasta":
        destino.mkdir()
    else:
        alvo = tmp_path / f"alvo-{arquivo}"
        alvo.write_text("# fora", encoding="utf-8")
        destino.symlink_to(alvo)
    antes = fotografar(workspace)

    resultado = aplicar(executar_modulo, workspace, [resposta("item.md")])

    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado"
    assert fotografar(workspace) == antes


def test_falha_de_conferencia_precede_item_ausente(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "precedencia")
    protegido = criar_item(workspace, "protegido.md")
    real = Path.read_bytes

    def negar(caminho):
        if caminho == protegido:
            raise PermissionError(13, "Permissão negada")
        return real(caminho)

    monkeypatch.setattr(Path, "read_bytes", negar)
    codigo, dados, _ = operar_aplicacao(
        workspace,
        bloco([resposta("ausente.md"), resposta("protegido.md")]),
    )

    assert codigo == 1 and dados["status"] == "recusado"
    assert dados["mensagem"] == "Não foi possível conferir a página agora. Confira as permissões e tente novamente."


def test_permission_error_na_resolucao_e_falha_de_conferencia(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "resolucao-permissao")
    protegido = criar_item(workspace, "protegido.md")
    real = Path.stat

    def negar(caminho, *args, **kwargs):
        if caminho == protegido:
            raise PermissionError(13, "Permissão negada")
        return real(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", negar)
    codigo, dados, _ = operar_aplicacao(
        workspace, bloco([resposta("protegido.md")])
    )

    assert codigo == 1 and dados["status"] == "recusado"
    assert "localizar" in " ".join(dados["problemas"])
    assert protegido.read_bytes() == b"abc"


def test_estrutura_invalida_precede_item_ausente(tmp_path, executar_cli, executar_modulo):
    workspace = criar_workspace(tmp_path, executar_cli, "precedencia-estrutura")
    resultado = aplicar(
        executar_modulo,
        workspace,
        [{"item": "ausente.md", "decisao": "gaveta", "digital": DIGITAL_ABC}],
    )
    assert json.loads(resultado.stdout)["status"] == "recusado"


def test_bloco_so_depois_pode_ser_reaplicado_sem_efeito(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "so-depois")
    criar_item(workspace, "abc.md")
    respostas = [resposta("abc.md", "depois", observacao="lembrar")]
    antes = fotografar(workspace)

    primeira = aplicar(executar_modulo, workspace, respostas)
    segunda = aplicar(executar_modulo, workspace, respostas)

    assert primeira.returncode == segunda.returncode == 0
    assert json.loads(primeira.stdout)["status"] == json.loads(segunda.stdout)["status"] == "aplicado"
    assert fotografar(workspace) == antes


def test_bloco_vazio_aplica_mesmo_com_destino_textual_nao_regular(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "vazio-sem-provas")
    (workspace / "Pauta.md").unlink()
    (workspace / "Pauta.md").mkdir()

    resultado = aplicar(executar_modulo, workspace, [])

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0 and dados["status"] == "aplicado"
    assert dados["resultados"] == []


def test_recusa_global_humana_imprime_mensagem_problemas_e_acoes_em_stderr(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "humano-global")
    resultado = aplicar(
        executar_modulo,
        workspace,
        [{"item": "x", "decisao": "gaveta"}],
        usar_json=False,
    )
    assert resultado.returncode == 1 and resultado.stdout == ""
    linhas = resultado.stderr.splitlines()
    assert len(linhas) >= 3
    assert any("Resposta 1:" in linha for linha in linhas)


def test_preflight_e_modulo_puro_sem_prints(tmp_path, executar_cli, capsys):
    workspace = criar_workspace(tmp_path, executar_cli, "puro")
    criar_item(workspace, "abc.md")
    from neoprumo.superficie_preflight import conferir

    resultado = conferir(json.loads(bloco([resposta("abc.md")])), workspace)
    captura = capsys.readouterr()
    assert captura.out == captura.err == ""
    assert resultado["plano"] and resultado["recusa"] is None
    assert resultado["plano"][0]["bytes"] == b"abc"
    assert resultado["plano"][0]["digital"] == DIGITAL_ABC
    assert resultado["plano"][0]["caminho"] == (workspace / "Inbox" / "abc.md").resolve()
