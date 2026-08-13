import json
import os
import re
from datetime import datetime, timedelta, timezone
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


def dados_embutidos(html):
    trecho = re.search(
        r'<script type="application/json" id="dados">(.*?)</script>', html, re.DOTALL
    )
    assert trecho is not None
    return json.loads(trecho.group(1))


def gerar(executar_cli, workspace):
    resultado = executar_cli(
        "superficie", "acervo", "--workspace", workspace, "--json"
    )
    return resultado, json.loads(resultado.stdout)


def test_builder_embute_schema_ordem_e_template_offline(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "pagina")
    antigo_b = criar_item(workspace, "b.md", "café antigo")
    antigo_a = criar_item(workspace, "a.md", "CAFÉ empatado")
    marca_antiga = datetime(2026, 8, 3, 9, 0).timestamp()
    os.utime(antigo_a, (marca_antiga, marca_antiga))
    os.utime(antigo_b, (marca_antiga, marca_antiga))
    criar_item(workspace, "2026-08-04-090000.md", "mais novo")

    resultado, saida = gerar(executar_cli, workspace)

    assert resultado.returncode == 0 and saida["itens"] == 3
    pagina = Path(saida["pagina"])
    assert re.fullmatch(r"acervo-\d{4}-\d{2}-\d{2}-\d{6}", saida["id"])
    html = pagina.read_text(encoding="utf-8")
    itens = dados_embutidos(html)["itens"]
    assert [item["nome"] for item in itens] == [
        "a.md",
        "b.md",
        "2026-08-04-090000.md",
    ]
    assert all(set(item) == {"nome", "conteudo", "idade", "aviso", "digital"} for item in itens)
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["digital"]) for item in itens)
    assert all(texto in html for texto in (
        'normalize("NFD")', r"\p{Mn}", "toLowerCase()", "faixa", "ordem",
        'item.digital === null', "ordemVisual", 'decisao === "deixar"',
        "decisões copiadas",
    ))
    assert not any(texto in html.lower() for texto in (
        "fetch(", "xmlhttprequest", "websocket", 'src="http', 'href="http'
    ))


def test_template_tenta_fallback_e_preserva_contagem_nos_dois_sucessos():
    html = (
        Path(__file__).parents[1]
        / "neoprumo"
        / "dados"
        / "superficie-acervo.html"
    ).read_text(encoding="utf-8")
    mensagem = (
        '`${resposta.respostas.length} ${resposta.respostas.length === 1 ? '
        '"decisão copiada" : "decisões copiadas"}. Cole na conversa.`'
    )

    assert html.count("copiarComoTexto(texto);") == 2
    assert html.count(mensagem) == 2
    assert re.search(
        r"catch \(_\) \{\s*try \{\s*copiarComoTexto\(texto\);.*?"
        r"\} catch \(_\) \{\s*retorno\.textContent = \"Não deu para copiar",
        html,
        re.DOTALL,
    )


def test_template_desempata_nome_por_code_point_sem_locale_do_navegador():
    html = (
        Path(__file__).parents[1]
        / "neoprumo"
        / "dados"
        / "superficie-acervo.html"
    ).read_text(encoding="utf-8")

    assert "localeCompare" not in html
    assert (
        "a.item.nome < b.item.nome ? -1 : a.item.nome > b.item.nome ? 1 : 0"
        in html
    )


def test_builder_mantem_binario_decidivel_com_digital(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "binario")
    criar_item(workspace, "binario.bin", b"\xff\xfe")

    _, saida = gerar(executar_cli, workspace)

    html = Path(saida["pagina"]).read_text(encoding="utf-8")
    item = dados_embutidos(html)["itens"][0]
    assert item["aviso"] and re.fullmatch(r"[0-9a-f]{64}", item["digital"])
    assert "conteúdo não pôde ser lido" in item["conteudo"].lower()


def test_builder_falha_de_leitura_vira_cartao_informativo(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import superficie_acervo_builder as builder

    workspace = criar_workspace(tmp_path, executar_cli, "ilegivel")
    item = criar_item(workspace, "protegido.md")
    ler_real = builder.ler_bytes

    def negar(caminho):
        if caminho == item:
            raise PermissionError(13, "Permissão negada")
        return ler_real(caminho)

    monkeypatch.setattr(builder, "ler_bytes", negar)
    _, saida = gerar(executar_cli, workspace)

    dados = dados_embutidos(Path(saida["pagina"]).read_text(encoding="utf-8"))["itens"][0]
    assert dados["digital"] is None and dados["aviso"]
    assert saida["problemas"]


@pytest.mark.parametrize("tipo", ["ausente", "arquivo", "symlink"])
def test_builder_recusa_acervo_invalido(tipo, tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, f"acervo-{tipo}")
    acervo = workspace / "Acervo"
    acervo.rmdir()
    if tipo == "arquivo":
        acervo.write_text("ocupado", encoding="utf-8")
    elif tipo == "symlink":
        alvo = tmp_path / "acervo-fora"
        alvo.mkdir()
        acervo.symlink_to(alvo, target_is_directory=True)

    resultado, saida = gerar(executar_cli, workspace)

    assert resultado.returncode == 1 and saida["status"] == "recusado"
    assert saida["pagina"] is None
    assert not (workspace / ".neoprumo" / "superficies").exists()


def test_builder_acervo_vazio_nao_cria_pagina(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "vazio")

    resultado, saida = gerar(executar_cli, workspace)

    assert resultado.returncode == 0 and saida["status"] == "sem_itens"
    assert saida["itens"] == 0 and "Nada a garimpar" in saida["mensagem"]
    assert not (workspace / ".neoprumo" / "superficies").exists()


@pytest.mark.parametrize("tipo", ["pasta", "symlink"])
def test_builder_recusa_pauta_nao_regular_sem_criar_pagina(
    tipo, tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, f"pauta-{tipo}")
    criar_item(workspace, "item.md")
    pauta = workspace / "Pauta.md"
    pauta.unlink()
    if tipo == "pasta":
        pauta.mkdir()
    else:
        alvo = tmp_path / "pauta-fora.md"
        alvo.write_text("fora", encoding="utf-8")
        pauta.symlink_to(alvo)

    resultado, saida = gerar(executar_cli, workspace)

    assert resultado.returncode == 1 and saida["pagina"] is None
    assert not (workspace / ".neoprumo" / "superficies").exists()


def test_builder_marcador_do_acervo_informa_mas_marcador_da_inbox_nao(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "marcadores")
    criar_item(workspace, "acervo.md")
    criar_item(workspace, "inbox.md")
    (workspace / "Pauta.md").write_text(
        "  — acervo acervo, incluído em 2026-08-05\n"
        "  — inbox inbox, despachado em 2026-08-05\n",
        encoding="utf-8",
    )

    _, saida = gerar(executar_cli, workspace)

    itens = {item["nome"]: item for item in dados_embutidos(
        Path(saida["pagina"]).read_text(encoding="utf-8")
    )["itens"]}
    assert itens["acervo.md"]["digital"] is None
    assert re.fullmatch(r"[0-9a-f]{64}", itens["inbox.md"]["digital"])


@pytest.mark.parametrize("tipo", ["ausente", "binario", "pasta", "symlink"])
def test_builder_ignora_estado_de_projetos(tipo, tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, f"projetos-{tipo}")
    criar_item(workspace, "item.md")
    projetos = workspace / "Projetos.md"
    projetos.unlink(missing_ok=True)
    if tipo == "binario":
        projetos.write_bytes(b"\xff")
    elif tipo == "pasta":
        projetos.mkdir()
    elif tipo == "symlink":
        alvo = tmp_path / "projetos-fora"
        alvo.write_bytes(b"\xff")
        projetos.symlink_to(alvo)

    resultado, saida = gerar(executar_cli, workspace)

    assert resultado.returncode == 0 and saida["status"] == "gerado"


def test_builder_idade_indisponivel_fica_no_fim(tmp_path, executar_cli, monkeypatch):
    from neoprumo import superficie_acervo_builder as builder

    workspace = criar_workspace(tmp_path, executar_cli, "idade")
    criar_item(workspace, "2026-08-01-100000.md")
    sem_data = criar_item(workspace, "sem-data.md")
    timestamp_real = builder.datetime.fromtimestamp

    class DataComFalha(datetime):
        @classmethod
        def fromtimestamp(cls, valor, tz=None):
            if valor == 12345:
                raise OverflowError("fora do calendário")
            return timestamp_real(valor, tz=tz)

    monkeypatch.setattr(builder, "datetime", DataComFalha)
    os.utime(sem_data, (12345, 12345))
    _, saida = gerar(executar_cli, workspace)

    itens = dados_embutidos(Path(saida["pagina"]).read_text(encoding="utf-8"))["itens"]
    assert itens[-1]["nome"] == "sem-data.md" and itens[-1]["idade"] is None


def test_builder_sufixa_colisao_sem_fixar_hora_local(tmp_path, executar_cli, monkeypatch):
    from neoprumo import superficie_acervo_builder as builder

    class AgoraFixo(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 5, 10, 15, tzinfo=timezone(timedelta(hours=-3)))

    monkeypatch.setattr(builder, "datetime", AgoraFixo)
    workspace = criar_workspace(tmp_path, executar_cli, "colisao")
    criar_item(workspace, "item.md")

    _, primeira = gerar(executar_cli, workspace)
    _, segunda = gerar(executar_cli, workspace)

    assert re.fullmatch(r"acervo-\d{4}-\d{2}-\d{2}-\d{6}", primeira["id"])
    assert segunda["id"] == primeira["id"] + "-2"
