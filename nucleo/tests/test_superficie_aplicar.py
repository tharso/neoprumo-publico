import hashlib
import json
from datetime import datetime

import pytest


def criar_workspace(tmp_path, executar_cli, nome="workspace"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def criar_item(workspace, nome, conteudo="conteúdo"):
    item = workspace / "Inbox" / nome
    if isinstance(conteudo, bytes):
        item.write_bytes(conteudo)
    else:
        item.write_text(conteudo, encoding="utf-8")
    return item


def bloco(
    respostas, workspace=None,
    pagina="despacho-2026-08-05-101500", superficie="despacho"
):
    completas = []
    for resposta in respostas:
        if not isinstance(resposta, dict) or "digital" in resposta:
            completas.append(resposta)
            continue
        completa = dict(resposta)
        item = completa.get("item")
        caminho = workspace / "Inbox" / item if workspace and isinstance(item, str) else None
        dados = caminho.read_bytes() if caminho is not None and caminho.is_file() else b"abc"
        completa["digital"] = hashlib.sha256(dados).hexdigest()
        completas.append(completa)
    return json.dumps(
        {"superficie": superficie, "pagina": pagina, "respostas": completas},
        ensure_ascii=True,
    )


def test_superficie_aplicar_executa_as_quatro_moradas_e_adia_na_ordem(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli)
    criar_item(workspace, "pauta.md", "Fazer o vitral\nMedir a janela")
    bytes_acervo = b"\x00\xff" + "referência".encode("utf-8")
    criar_item(workspace, "acervo.bin", bytes_acervo)
    criar_item(workspace, "projeto.md", "Conversar com a curadora")
    criar_item(workspace, "lixo.md", "descartar")
    adiado = criar_item(workspace, "depois.md", "esperar")
    respostas = [
        {"item": "pauta.md", "decisao": "pauta", "observacao": "  urgente  "},
        {"item": "acervo.bin", "decisao": "acervo"},
        {"item": "projeto.md", "decisao": "projeto", "projeto": "Museu"},
        {"item": "lixo.md", "decisao": "lixo"},
        {"item": "depois.md", "decisao": "depois", "observacao": "esperar orçamento"},
    ]

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json", input=bloco(respostas, workspace)
    )

    assert resultado.returncode == 0
    assert resultado.stderr == "" and resultado.stdout.count("\n") == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "aplicado"
    assert (dados["despachados"], dados["recusados"], dados["adiados"]) == (4, 0, 1)
    assert [item["entrada"] for item in dados["resultados"]] == [r["item"] for r in respostas]
    assert dados["resultados"][0]["observacao"] == "  urgente  "
    assert "regime" not in dados["resultados"][0]
    assert "vence" not in dados["resultados"][0]
    assert dados["resultados"][4] == {
        "status": "adiado",
        "problemas": [],
        "acoes": [],
        "mensagem": "Adiado: fica na Inbox.",
        "workspace": str(workspace.resolve()),
        "item": None,
        "id": "depois",
        "destino": None,
        "entrada": "depois.md",
        "observacao": "esperar orçamento",
    }
    assert dados["problemas"] == [] and dados["acoes"] == []
    assert dados["mensagem"] == "4 despachados, 0 recusados, 1 adiado."
    assert "Fazer o vitral" in (workspace / "Pauta.md").read_text(encoding="utf-8")
    assert (workspace / "Acervo" / "acervo.bin").read_bytes() == bytes_acervo
    assert "## Museu" in (workspace / "Projetos.md").read_text(encoding="utf-8")
    assert (workspace / ".neoprumo" / "lixo" / "lixo.md").is_file()
    assert adiado.is_file()


@pytest.mark.parametrize(
    "entrada",
    [
        None,
        12,
        {"item": 7, "decisao": "pauta"},
        {"item": "x.md", "decisao": "gaveta"},
        {"item": "x.md", "decisao": "projeto"},
        {"item": "x.md", "decisao": "projeto", "projeto": 9},
        {"item": "x.md", "decisao": "pauta", "observacao": 9},
        {"item": "x.md", "decisao": "pauta", "projeto": 9},
    ],
)
def test_superficie_aplicar_recusa_entrada_malformada_globalmente(
    entrada, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "estrutural")
    criar_item(workspace, "valido.md", "guardar")

    resultado = executar_modulo(
        "superficie",
        "aplicar",
        "--workspace",
        workspace,
        "--json",
        input=bloco([entrada, {"item": "valido.md", "decisao": "acervo"}], workspace),
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert dados["resultados"] is None
    assert (workspace / "Inbox" / "valido.md").is_file()


@pytest.mark.parametrize(
    "resposta",
    [
        {"item": "fantasma.md", "decisao": "pauta"},
        {"item": "binario.bin", "decisao": "pauta"},
        {"item": "projeto.md", "decisao": "projeto", "projeto": "   "},
        {"item": "projeto.md", "decisao": "projeto", "projeto": "Casa\n## Museu"},
        {"item": "projeto.md", "decisao": "projeto", "projeto": "Casa\u0007"},
    ],
)
def test_superficie_aplicar_preserva_envelope_da_recusa_de_dominio(
    resposta, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "dominio")
    criar_item(workspace, "binario.bin", b"\xff")
    criar_item(workspace, "projeto.md", "nota")

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json", input=bloco([resposta], workspace)
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] in ("recusado", "envelhecida")
    assert dados["resultados"] is None
    assert dados["problemas"] and dados["acoes"]
    assert "Traceback" not in resultado.stdout


def test_despacho_unitario_recusa_nome_de_projeto_multilinha_ou_com_controle(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "bugfix-t4")
    for indice, nome in enumerate(("Casa\n## Museu", "Casa\u0007"), start=1):
        item = criar_item(workspace, f"item-{indice}.md", "preservar")
        resultado = executar_cli("despacho", item.name, "projeto", nome, "--json")
        assert resultado.returncode == 1
        assert json.loads(resultado.stdout)["status"] == "recusado"
        assert item.is_file()


@pytest.mark.parametrize(
    "entrada",
    [
        "{quebrado",
        "[]",
        json.dumps({"superficie": "despacho", "respostas": []}),
        json.dumps({"superficie": "despacho", "pagina": "", "respostas": []}),
        json.dumps({"superficie": "despacho", "pagina": "x", "respostas": {}}),
    ],
)
def test_superficie_aplicar_recusa_bloco_invalido_sem_executar(
    entrada, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "global")
    item = criar_item(workspace, "fica.md", "fica")

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json", input=entrada
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and resultado.stderr == ""
    assert dados["status"] == "recusado"
    assert dados["resultados"] is None
    assert dados["despachados"] is None and dados["recusados"] is None and dados["adiados"] is None
    assert item.is_file()


def test_superficie_aplicar_valida_workspace_antes_do_bloco(executar_modulo):
    resultado = executar_modulo("superficie", "aplicar", "--json", input="{quebrado")
    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "sem_ativo"
    assert dados["resultados"] is None


def test_superficie_aplicar_aceita_lista_vazia_e_imprime_mensagem_humana(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "vazio")
    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, input=bloco([], workspace)
    )
    assert resultado.returncode == 0 and resultado.stderr == ""
    assert resultado.stdout == "Nenhuma resposta para aplicar.\n"


def test_superficie_aplicar_relatorio_humano_delimita_textos_externos(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "humano")
    nome = 'nome"forjado.md'
    criar_item(workspace, nome, "nota")
    resposta = {
        "item": nome,
        "decisao": "projeto",
        "projeto": 'Projeto "raro"',
        "observacao": "linha um\nlinha forjada",
    }

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, input=bloco([resposta], workspace)
    )

    assert resultado.returncode == 0 and resultado.stderr == ""
    linhas = resultado.stdout.splitlines()
    assert len(linhas) == 2
    assert "\\n" in linhas[0]
    assert json.dumps(nome, ensure_ascii=False) in linhas[0]
    assert json.dumps(resposta["observacao"], ensure_ascii=False) in linhas[0]
    assert linhas[1] == "1 despachado, 0 recusados, 0 adiados."


@pytest.mark.parametrize(
    ("campo", "recusa_global"),
    [
        ("pagina", True),
        ("superficie", True),
        ("item", False),
        ("decisao", False),
        ("projeto", False),
        ("observacao", False),
    ],
)
def test_superficie_aplicar_recusa_surrogate_sem_devolver_valor_ofensivo(
    campo, recusa_global, tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, f"surrogate-{campo}")
    criar_item(workspace, "item.md", "nota")
    dados = {
        "superficie": "despacho",
        "pagina": "pagina",
        "respostas": [
            {
                "item": "item.md",
                "decisao": "projeto" if campo == "projeto" else "pauta",
                "projeto": "Museu" if campo == "projeto" else "apoio",
                "observacao": "lembrete",
                "digital": hashlib.sha256(b"nota").hexdigest(),
            }
        ],
    }
    dados[campo] = "\ud800" if recusa_global else dados.get(campo)
    if not recusa_global:
        dados["respostas"][0][campo] = "\ud800"

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json",
        input=json.dumps(dados, ensure_ascii=True),
    )

    assert resultado.returncode == 1 and resultado.stderr == ""
    saida = json.loads(resultado.stdout)
    assert saida["status"] == "recusado"
    assert "\\ud800" not in resultado.stdout.lower()
    assert "Traceback" not in resultado.stdout
    assert saida["resultados"] is None


def test_superficie_aplicar_adia_somente_item_real_e_recusa_ausente_ou_ambiguo(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "depois")
    criar_item(workspace, "real.md", "fica")
    criar_item(workspace, "duplo.md", "um")
    criar_item(workspace, "duplo.txt", "dois")
    respostas = [
        {"item": "real.md", "decisao": "depois", "observacao": "  "},
        {"item": "ausente.md", "decisao": "depois"},
        {"item": "duplo", "decisao": "depois"},
    ]

    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json", input=bloco(respostas, workspace)
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1
    assert dados["status"] == "envelhecida" and dados["resultados"] is None
    assert (workspace / "Inbox" / "real.md").is_file()


def test_superficie_aplicar_agrega_ausencias_em_recusa_global(
    tmp_path, executar_cli, executar_modulo
):
    workspace = criar_workspace(tmp_path, executar_cli, "agregacao")
    respostas = [
        {"item": "primeiro.md", "decisao": "pauta"},
        {"item": "segundo.md", "decisao": "lixo"},
    ]
    resultado = executar_modulo(
        "superficie", "aplicar", "--workspace", workspace, "--json", input=bloco(respostas, workspace)
    )
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "envelhecida" and len(dados["problemas"]) == 2
    assert dados["acoes"] == ["Gere a página de novo."]


def test_superficie_aplicar_argparse_preserva_codigo_2(executar_modulo):
    resultado = executar_modulo("superficie", "aplicar", "extra", "--json", input="{}")
    assert resultado.returncode == 2
    assert resultado.stdout == "" and "usage:" in resultado.stderr
