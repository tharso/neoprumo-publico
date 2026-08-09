import hashlib
import json
import os
import stat
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


def resposta(nome, decisao="deixar", conteudo=b"abc", **extras):
    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")
    return {
        "item": nome,
        "decisao": decisao,
        "digital": hashlib.sha256(conteudo).hexdigest(),
        **extras,
    }


def bloco(respostas, superficie="acervo", pagina="acervo-2026-08-05-101500"):
    return json.dumps(
        {"superficie": superficie, "pagina": pagina, "respostas": respostas},
        ensure_ascii=True,
    )


def fotografar(raiz):
    foto = {}
    for pasta, diretorios, arquivos in os.walk(raiz, followlinks=False):
        for nome in diretorios + arquivos:
            caminho = Path(pasta) / nome
            estado = caminho.lstat()
            foto[str(caminho.relative_to(raiz))] = (
                stat.S_IFMT(estado.st_mode),
                caminho.read_bytes() if stat.S_ISREG(estado.st_mode) else None,
            )
    return foto


def test_builder_do_acervo_e_uma_rota_publica(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "builder")
    criar_item(workspace, "2026-08-01-090000.md", "ideia com café")

    resultado = executar_cli(
        "superficie", "acervo", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert dados["status"] == "gerado" and dados["itens"] == 1
    assert Path(dados["pagina"]).name.startswith("acervo-")


def test_roteamento_recusa_superficie_desconhecida_antes_da_pagina(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "roteamento")
    entrada = json.dumps(
        {"superficie": "outra", "pagina": "", "respostas": "tambem-invalida"}
    )

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json", input=entrada
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1
    assert dados["problemas"] == [
        "O bloco não pertence a uma superfície conhecida."
    ]


def test_preflight_do_acervo_recusa_toda_a_estrutura_sem_efeito(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "preflight")
    criar_item(workspace, "valido.md")
    antes = fotografar(workspace)
    respostas = [
        resposta("valido.md"),
        None,
        {"item": "../ruim", "decisao": "gaveta", "digital": "A" * 64},
    ]

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json",
        input=bloco(respostas),
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert dados["resultados"] is None
    assert [problema.split(":", 1)[0] for problema in dados["problemas"]] == [
        "Resposta 2", "Resposta 3", "Resposta 3", "Resposta 3"
    ]
    assert fotografar(workspace) == antes


@pytest.mark.parametrize("prova", ["ausencia", "digital", "marcador"])
def test_as_tres_provas_envelhecem_a_pagina_do_acervo(
    prova, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"prova-{prova}")
    item = criar_item(workspace, "abc.md")
    entrada = resposta("abc.md")
    if prova == "ausencia":
        item.unlink()
    elif prova == "digital":
        item.write_bytes(b"mudou")
    else:
        (workspace / "Pauta.md").write_text(
            "  — acervo abc, incluído em 2026-08-05\n", encoding="utf-8"
        )
    antes = fotografar(workspace)

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json",
        input=bloco([entrada]),
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "envelhecida"
    assert "abc.md" in " ".join(dados["problemas"])
    assert fotografar(workspace) == antes


def test_reconferencia_do_acervo_recusa_item_isolado_e_o_lote_segue(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import acervo as modulo_acervo
    from neoprumo import superficie_acervo_preflight as modulo_preflight
    from neoprumo.superficie_aplicar import operar_aplicacao

    workspace = criar_workspace(tmp_path, executar_cli, "reconferencia")
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

    monkeypatch.setattr(modulo_preflight, "ler_bytes", mudar_na_reconferencia)
    monkeypatch.setattr(modulo_acervo, "ler_bytes", mudar_na_reconferencia)
    codigo, dados, _ = operar_aplicacao(
        workspace,
        bloco([
            resposta("primeiro.md", "lixo"),
            resposta("segundo.md", "deixar", b"segundo", observacao="fica"),
        ]),
    )

    assert codigo == 1 and dados["status"] == "aplicado_com_recusas"
    assert [item["status"] for item in dados["resultados"]] == [
        "recusado", "deixado"
    ]
    assert primeiro.read_bytes() == b"mudou na corrida"


@pytest.mark.parametrize(
    ("decisao", "status", "destino"),
    [("pauta", "incluido", "pauta"), ("lixo", "excluido", "lixo")],
)
def test_acervo_unitario_move_com_envelope_proprio(
    decisao, status, destino, tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, f"unitario-{decisao}")
    item = criar_item(workspace, "abc.md", "uma ideia")

    resultado = executar_cli(
        "acervo", item.name, decisao, "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0 and dados["status"] == status
    assert dados["id"] == "abc" and dados["destino"] == destino
    assert not item.exists()
    assert "Inbox" not in resultado.stdout and "inbox" not in resultado.stdout
