import json
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


DIGITAL_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def dados_embutidos(html):
    trecho = re.search(
        r'<script type="application/json" id="dados">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert trecho is not None
    return json.loads(trecho.group(1))


def criar_workspace(tmp_path, executar_cli, nome="workspace"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def criar_item(workspace, nome, conteudo):
    item = workspace / "Inbox" / nome
    if isinstance(conteudo, bytes):
        item.write_bytes(conteudo)
    else:
        item.write_text(conteudo, encoding="utf-8")
    return item


def test_superficie_despacho_gera_pagina_fiel_ordenada_e_sem_mover_itens(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli)
    antigo = criar_item(
        workspace,
        'nome-"<script><b>.md',
        'linha  1\n\tlinha 2 </script><em>não é markup</em>\n',
    )
    marca_antiga = datetime(2026, 8, 1, 9, 0).timestamp()
    os.utime(antigo, (marca_antiga, marca_antiga))
    novo = criar_item(workspace, "2026-08-04-090000.md", "mais novo")
    antes = {item.name: item.read_bytes() for item in (workspace / "Inbox").iterdir()}

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.count("\n") == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "gerado"
    assert dados["itens"] == 2
    assert dados["problemas"] == []
    pagina = Path(dados["pagina"])
    assert pagina.parent == workspace / ".neoprumo" / "superficies"
    assert pagina.stem == dados["id"]
    html = pagina.read_text(encoding="utf-8")
    nome_serializado = json.dumps(antigo.name, ensure_ascii=False)[1:-1].replace(
        "<", "\\u003c"
    )
    assert html.index(nome_serializado) < html.index(novo.name)
    assert "\\u003c/script>" in html
    assert "<em>não é markup</em>" not in html
    assert "textContent" in html
    assert "white-space: pre-wrap" in html
    assert all(decisao in html for decisao in ("pauta", "acervo", "projeto", "lixo", "depois"))
    assert "observação" in html.lower()
    assert "copiar respostas" in html.lower()
    assert not any(
        proibido in html.lower()
        for proibido in ("fetch(", "xmlhttprequest", "websocket", "src=\"http", "href=\"http", "action=\"http")
    )
    assert {item.name: item.read_bytes() for item in (workspace / "Inbox").iterdir()} == antes


def test_superficie_despacho_ordena_empate_por_nome_e_idade_indisponivel_no_fim(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import superficie_builder as modulo_builder

    workspace = criar_workspace(tmp_path, executar_cli, "ordem")
    criar_item(workspace, "2026-08-01-100000-b.md", "b")
    criar_item(workspace, "2026-08-01-100000-a.md", "a")
    criar_item(workspace, "sem-data.md", "sem data")
    timestamp_real = modulo_builder.datetime.fromtimestamp

    class DataHoraComFalha(datetime):
        @classmethod
        def fromtimestamp(cls, valor, tz=None):
            if valor == 12345:
                raise OverflowError("fora do calendário")
            return timestamp_real(valor, tz=tz)

    monkeypatch.setattr(modulo_builder, "datetime", DataHoraComFalha)
    os.utime(workspace / "Inbox" / "sem-data.md", (12345, 12345))

    resultado = executar_cli("superficie", "despacho", "--workspace", workspace, "--json")

    dados = json.loads(resultado.stdout)
    html = Path(dados["pagina"]).read_text(encoding="utf-8")
    assert html.index("2026-08-01-100000-a.md") < html.index("2026-08-01-100000-b.md")
    assert html.index("2026-08-01-100000-b.md") < html.index("sem-data.md")
    assert "idade indisponível" in html
    assert any("data" in problema for problema in dados["problemas"])


@pytest.mark.parametrize("conteudo", ["vazia", "so_ignorados"])
def test_superficie_despacho_sem_itens_nao_cria_pagina(
    conteudo, tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, conteudo)
    if conteudo == "so_ignorados":
        criar_item(workspace, ".oculto.md", "oculto")
        (workspace / "Inbox" / "pasta").mkdir()
        alvo = tmp_path / "alvo.md"
        alvo.write_text("atalho", encoding="utf-8")
        (workspace / "Inbox" / "atalho.md").symlink_to(alvo)

    resultado = executar_cli("superficie", "despacho", "--workspace", workspace, "--json")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert dados["status"] == "sem_itens"
    assert dados["pagina"] is None and dados["id"] is None and dados["itens"] == 0
    assert "nada a despachar" in dados["mensagem"].lower()
    assert not (workspace / ".neoprumo" / "superficies").exists()


@pytest.mark.parametrize("tipo", ["ausente", "arquivo", "symlink"])
def test_superficie_despacho_recusa_inbox_invalida(tipo, tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, f"inbox-{tipo}")
    inbox = workspace / "Inbox"
    inbox.rmdir()
    if tipo == "arquivo":
        inbox.write_text("não é pasta", encoding="utf-8")
    elif tipo == "symlink":
        externa = tmp_path / "inbox-externa"
        externa.mkdir()
        inbox.symlink_to(externa, target_is_directory=True)

    resultado = executar_cli("superficie", "despacho", "--workspace", workspace, "--json")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1
    assert dados["status"] == "recusado"
    assert dados["pagina"] is None and dados["id"] is None and dados["itens"] is None
    assert not (workspace / ".neoprumo" / "superficies").exists()


def test_superficie_despacho_mantem_cartao_quando_conteudo_e_ilegivel(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "ilegivel")
    criar_item(workspace, "2026-08-01-120000.bin", b"\xff\xfe")

    resultado = executar_cli("superficie", "despacho", "--workspace", workspace, "--json")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert dados["status"] == "gerado" and dados["itens"] == 1
    assert dados["problemas"]
    html = Path(dados["pagina"]).read_text(encoding="utf-8")
    assert "conteúdo não pôde ser lido" in html.lower()
    assert "2026-08-01-120000.bin" in html


def test_superficie_despacho_humano_avisa_quando_conteudo_e_ilegivel(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "aviso-humano")
    criar_item(workspace, "2026-08-01-120000.bin", b"\xff\xfe")

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace
    )

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.splitlines()[0].startswith(
        "Superfície de despacho criada:"
    )
    assert resultado.stdout.splitlines()[1].startswith("Aviso: Inbox:")
    assert "conteúdo" in resultado.stdout.splitlines()[1]


@pytest.mark.parametrize("tipo", ["arquivo", "symlink_fora", "symlink_dentro"])
def test_superficie_despacho_recusa_pasta_de_superficies_insegura(
    tipo, tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, f"superficies-{tipo}")
    criar_item(workspace, "item.md", "conteúdo")
    superficies = workspace / ".neoprumo" / "superficies"
    if tipo == "arquivo":
        superficies.write_text("ocupado", encoding="utf-8")
    else:
        alvo = tmp_path / "fora" if tipo == "symlink_fora" else workspace / "dentro"
        alvo.mkdir()
        superficies.symlink_to(alvo, target_is_directory=True)

    resultado = executar_cli("superficie", "despacho", "--workspace", workspace, "--json")

    assert resultado.returncode == 1
    assert json.loads(resultado.stdout)["status"] == "recusado"
    assert not list((tmp_path / "fora").iterdir()) if tipo == "symlink_fora" else True


def test_superficie_despacho_sufixa_colisao_de_pagina(tmp_path, executar_cli, monkeypatch):
    from neoprumo import superficie_builder as modulo_builder

    class AgoraFixo(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 5, 10, 15, 0, tzinfo=timezone(timedelta(hours=-3)))

    monkeypatch.setattr(modulo_builder, "datetime", AgoraFixo)
    workspace = criar_workspace(tmp_path, executar_cli, "colisao")
    criar_item(workspace, "item.md", "fica na Inbox")

    primeira = json.loads(executar_cli("superficie", "despacho", "--workspace", workspace, "--json").stdout)
    segunda = json.loads(executar_cli("superficie", "despacho", "--workspace", workspace, "--json").stdout)

    assert re.fullmatch(
        r"despacho-\d{4}-\d{2}-\d{2}-\d{6}", primeira["id"]
    )
    assert segunda["id"] == primeira["id"] + "-2"


def test_superficie_despacho_omite_nome_com_surrogate_sem_traceback(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import superficie_builder as modulo_builder

    workspace = criar_workspace(tmp_path, executar_cli, "surrogate")

    class EntradaOfensiva:
        name = "ofensivo-\udcff.md"

    class Entradas:
        def __enter__(self):
            return iter([EntradaOfensiva()])

        def __exit__(self, tipo, valor, traceback):
            return False

    monkeypatch.setattr(modulo_builder.os, "scandir", lambda _: Entradas())

    resultado = executar_cli("superficie", "despacho", "--workspace", workspace, "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "sem_itens" and dados["itens"] == 0
    assert dados["problemas"]
    assert "ofensivo" not in resultado.stdout and "Traceback" not in resultado.stdout


def test_superficie_despacho_workspace_indisponivel_e_argparse(executar_cli, executar_modulo):
    recusa = executar_cli("superficie", "despacho", "--json")
    assert recusa.returncode == 1 and recusa.stderr == ""
    assert json.loads(recusa.stdout)["status"] == "sem_ativo"
    assert recusa.stdout.count("\n") == 1

    sintaxe = executar_modulo("superficie", "despacho", "extra", "--json")
    assert sintaxe.returncode == 2
    assert sintaxe.stdout == "" and "usage:" in sintaxe.stderr


def test_superficie_despacho_stat_falho_conta_para_zero_e_avisa(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import superficie_builder as modulo_builder

    workspace = criar_workspace(tmp_path, executar_cli, "stat-falho")

    class EntradaSemEstado:
        name = "sem-estado.md"

        def stat(self, follow_symlinks=False):
            raise PermissionError(13, "Permissão negada")

    class Entradas:
        def __enter__(self):
            return iter([EntradaSemEstado()])

        def __exit__(self, tipo, valor, traceback):
            return False

    monkeypatch.setattr(modulo_builder.os, "scandir", lambda _: Entradas())

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0 and dados["status"] == "sem_itens"
    assert "sem-estado.md" in dados["problemas"][0]
    assert not (workspace / ".neoprumo" / "superficies").exists()


def test_superficie_despacho_recusa_inbox_nao_enumeravel(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import superficie_builder as modulo_builder

    workspace = criar_workspace(tmp_path, executar_cli, "nao-enumeravel")

    def negar(_):
        raise PermissionError(13, "Permissão negada")

    monkeypatch.setattr(modulo_builder.os, "scandir", negar)

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert dados["pagina"] is None


def test_superficie_despacho_so_acrescenta_pasta_e_pagina(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "fotografia")
    criar_item(workspace, "item.md", "conteúdo fiel")
    antes = fotografar(workspace)

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    pagina = Path(json.loads(resultado.stdout)["pagina"])
    depois = fotografar(workspace)
    novos = set(depois) - set(antes)
    assert novos == {str(pagina.parent), str(pagina)}
    assert all(depois[caminho] == estado for caminho, estado in antes.items())


def test_superficie_despacho_recusa_metadados_apontando_para_fora(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "metadados-fora")
    criar_item(workspace, "item.md", "não vazar")
    metadados = workspace / ".neoprumo"
    identidade = metadados / "workspace.json"
    identidade_bytes = identidade.read_bytes()
    identidade.unlink()
    metadados.rmdir()
    externo = tmp_path / "metadados-externos"
    externo.mkdir()
    (externo / "workspace.json").write_bytes(identidade_bytes)
    metadados.symlink_to(externo, target_is_directory=True)

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert not (externo / "superficies").exists()


def fotografar(raiz):
    foto = {}
    for pasta, diretorios, arquivos in os.walk(raiz, followlinks=False):
        for nome in diretorios + arquivos:
            caminho = Path(pasta) / nome
            estado = caminho.lstat()
            conteudo = caminho.read_bytes() if stat.S_ISREG(estado.st_mode) else None
            foto[str(caminho)] = (
                stat.S_IFMT(estado.st_mode),
                conteudo,
                estado.st_mtime_ns if stat.S_ISREG(estado.st_mode) else None,
            )
    return foto


def test_superficie_despacho_embute_digital_e_guards_do_cartao_informativo(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "schema-digital")
    criar_item(workspace, "abc.md", b"abc")
    criar_item(workspace, "binario.bin", b"\xff")

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    envelope = json.loads(resultado.stdout)
    html = Path(envelope["pagina"]).read_text(encoding="utf-8")
    dados = dados_embutidos(html)
    assert set(dados) == {"pagina", "itens"}
    assert set(dados["itens"][0]) == {"nome", "conteudo", "idade", "aviso", "digital"}
    por_nome = {item["nome"]: item for item in dados["itens"]}
    assert por_nome["abc.md"]["digital"] == DIGITAL_ABC
    assert por_nome["binario.bin"]["digital"] == DIGITAL_ABC.replace(DIGITAL_ABC, "a8100ae6aa1940d0b663bb31cd466142ebbdbd5187131b92d93818987832eb89")
    assert "item.digital === null" in html
    assert "if (item.digital === null)" in html
    assert "if (cartao.dataset.digital ===" in html
    assert "digital: cartao.dataset.digital" in html


@pytest.mark.parametrize("nome", ["abc): raro.md", "linha\nnova.md"])
def test_superficie_despacho_item_inelegivel_vira_informativo_ou_e_omitido(
    nome, tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "nome-inelegivel")
    criar_item(workspace, nome, b"abc")

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    if "\n" in nome:
        assert dados["status"] == "sem_itens" and dados["itens"] == 0
        assert nome not in resultado.stdout
        assert dados["problemas"] == [
            "Inbox: um item tem nome com caracteres de controle e não foi incluído."
        ]
    else:
        html = Path(dados["pagina"]).read_text(encoding="utf-8")
        item = dados_embutidos(html)["itens"][0]
        assert item["digital"] is None
        assert "despache-o na conversa" in item["aviso"]


def test_superficie_despacho_falha_de_leitura_cria_cartao_sem_protocolo(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import superficie_builder as modulo_builder

    workspace = criar_workspace(tmp_path, executar_cli, "leitura-falha")
    item = criar_item(workspace, "abc.md", b"abc")
    leitura_real = modulo_builder.Path.read_bytes

    def negar(caminho):
        if caminho == item:
            raise PermissionError(13, "Permissão negada")
        return leitura_real(caminho)

    monkeypatch.setattr(modulo_builder.Path, "read_bytes", negar)
    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    html = Path(dados["pagina"]).read_text(encoding="utf-8")
    embutido = dados_embutidos(html)["itens"][0]
    assert dados["status"] == "gerado" and dados["itens"] == 1
    assert embutido["digital"] is None
    assert "não pôde ser conferido" in embutido["aviso"]


def test_superficie_despacho_marcador_preexistente_vira_cartao_informativo(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "marcador-preexistente")
    criar_item(workspace, "abc.md", b"abc")
    (workspace / "Pauta.md").write_text(
        "  — inbox abc, despachado em 2026-08-05\n", encoding="utf-8"
    )

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    embutido = dados_embutidos(Path(dados["pagina"]).read_text(encoding="utf-8"))["itens"][0]
    assert dados["status"] == "gerado" and dados["itens"] == 1
    assert embutido["digital"] is None
    assert "já há registro" in embutido["aviso"].lower()


@pytest.mark.parametrize("tipo", ["permission-error", "pasta", "symlink"])
def test_superficie_despacho_recusa_sem_pagina_quando_destino_nao_e_fotografavel(
    tipo, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import superficie_builder as modulo_builder

    workspace = criar_workspace(tmp_path, executar_cli, f"fotografia-{tipo}")
    criar_item(workspace, "abc.md", b"abc")
    destino = workspace / "Pauta.md"
    if tipo == "permission-error":
        antes = fotografar(workspace)
        leitura_real = modulo_builder.Path.read_bytes

        def negar(caminho):
            if caminho == destino:
                raise PermissionError(13, "Permissão negada")
            return leitura_real(caminho)

        monkeypatch.setattr(modulo_builder.Path, "read_bytes", negar)
    else:
        destino.unlink()
        if tipo == "pasta":
            destino.mkdir()
        else:
            alvo = tmp_path / "pauta-fora.md"
            alvo.write_text("# Pauta", encoding="utf-8")
            destino.symlink_to(alvo)
        antes = fotografar(workspace)

    resultado = executar_cli(
        "superficie", "despacho", "--workspace", workspace, "--json"
    )

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 1 and dados["status"] == "recusado"
    assert dados["pagina"] is None
    if tipo == "permission-error":
        monkeypatch.setattr(modulo_builder.Path, "read_bytes", leitura_real)
    assert fotografar(workspace) == antes
