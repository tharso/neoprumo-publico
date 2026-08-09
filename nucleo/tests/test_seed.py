import json
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


INSTANTE = datetime(2026, 8, 4, 23, 30, tzinfo=timezone.utc)


def test_resumo_de_workspace_saudavel_e_vazio(tmp_path, executar_cli):
    from neoprumo.seed import resumir

    workspace = tmp_path / "vazio"
    assert executar_cli("setup", workspace).returncode == 0

    resultado = resumir(workspace, instante=INSTANTE)

    assert resultado == {
        "status": "resumido",
        "problemas": [],
        "acoes": [],
        "mensagem": "Resumo do workspace pronto.",
        "workspace": str(workspace),
        "gerado_em": "2026-08-04T23:30:00+00:00",
        "inbox": {
            "total": 0,
            "idade_mais_antigo_dias": None,
            "idade_mais_novo_dias": None,
        },
        "pauta": {"abertos": 0, "concluidos": 0},
        "acervo": {"total": 0, "idade_mais_antigo_dias": None},
        "estrutura": {"status": "saudavel", "problemas": []},
    }


def test_seed_conta_itens_e_calcula_idades_por_nome_ou_mtime(
    tmp_path, executar_cli
):
    from neoprumo.seed import resumir

    fuso = timezone(timedelta(hours=-3))
    instante = datetime(2026, 8, 5, 0, 30, tzinfo=fuso)
    workspace = tmp_path / "idades"
    assert executar_cli("setup", workspace).returncode == 0
    inbox = workspace / "Inbox"

    (inbox / "2026-08-04-235959.md").write_bytes(b"")
    (inbox / "2026-08-03-101500-2.txt").write_text("colisão", encoding="utf-8")
    (inbox / "2026-08-06-000000.bin").write_bytes(b"\x00\xff")
    fora_do_padrao = inbox / "lembrete"
    fora_do_padrao.write_text("sem extensão", encoding="utf-8")
    impossivel = inbox / "2026-02-31-120000.dat"
    impossivel.write_bytes(b"\x80")
    definir_mtime(fora_do_padrao, datetime(2026, 7, 30, 12, tzinfo=fuso))
    definir_mtime(impossivel, datetime(2026, 8, 1, 12, tzinfo=fuso))

    (inbox / ".oculto.md").write_text("ignorar", encoding="utf-8")
    (inbox / "subdiretorio").mkdir()
    alvo = tmp_path / "fora.txt"
    alvo.write_text("ignorar", encoding="utf-8")
    (inbox / "atalho.txt").symlink_to(alvo)

    acervo = workspace / "Acervo"
    antigo = acervo / "recorte-sem-data"
    antigo.write_bytes("referência".encode("utf-8"))
    definir_mtime(antigo, datetime(2026, 7, 26, 8, tzinfo=fuso))
    (acervo / "2026-08-05-000001-12.md").write_text("hoje", encoding="utf-8")

    resultado = resumir(workspace, instante=instante)

    assert resultado["inbox"] == {
        "total": 5,
        "idade_mais_antigo_dias": 6,
        "idade_mais_novo_dias": 0,
    }
    assert resultado["acervo"] == {
        "total": 2,
        "idade_mais_antigo_dias": 10,
    }
    assert resultado["problemas"] == []


def test_seed_conta_checklists_da_pauta_pela_regra_lexical(
    tmp_path, executar_cli
):
    from neoprumo.seed import resumir

    workspace = tmp_path / "pauta"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Pauta.md").write_text(
        "# Pauta\n"
        "- [ ] aberto\n"
        "- [x] concluído\n"
        "- [X] concluído maiúsculo\n"
        "  - [ ] checklist herdado\n"
        "texto comum\n"
        "```\n"
        "- [ ] bloco de código também conta\n"
        "```\n",
        encoding="utf-8",
    )

    resultado = resumir(workspace, instante=INSTANTE)

    assert resultado["pauta"] == {"abertos": 2, "concluidos": 2}


def test_seed_cli_json_entrega_envelope_completo_do_workspace_ativo(
    tmp_path, executar_cli
):
    workspace = tmp_path / "ativo"
    assert executar_cli("setup", workspace).returncode == 0

    resultado = executar_cli("seed", "--json")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.count("\n") == 1
    dados = json.loads(resultado.stdout)
    assert set(dados) == {
        "status",
        "problemas",
        "acoes",
        "mensagem",
        "workspace",
        "gerado_em",
        "inbox",
        "pauta",
        "acervo",
        "estrutura",
    }
    assert dados["status"] == "resumido"
    assert dados["workspace"] == str(workspace.resolve())
    assert dados["acoes"] == []
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}",
        dados["gerado_em"],
    )


def test_seed_humano_tem_quatro_linhas_fixas_quando_vazio(tmp_path, executar_cli):
    workspace = tmp_path / "humano"
    assert executar_cli("setup", workspace).returncode == 0

    resultado = executar_cli("seed", "--workspace", workspace)

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.splitlines() == [
        "Inbox: vazia.",
        "Pauta: vazia.",
        "Acervo: vazio.",
        "Estrutura: saudável.",
    ]


def test_seed_humano_povoado_usa_singular_e_pinna_virada_da_meia_noite(
    tmp_path, executar_cli, capsys
):
    from neoprumo.seed import executar_seed, resumir

    fuso = timezone(timedelta(hours=-3))
    instante = datetime(2026, 8, 5, 0, 30, tzinfo=fuso)
    workspace = tmp_path / "singular"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Inbox" / "2026-08-04-235959.md").write_text(
        "ontem por segundos", encoding="utf-8"
    )
    (workspace / "Acervo" / "2026-08-04-235958.bin").write_bytes(b"\x00")
    (workspace / "Pauta.md").write_text(
        "# Pauta\n- [ ] uma aberta\n- [x] uma concluída\n",
        encoding="utf-8",
    )

    resumo = resumir(workspace, instante=instante)
    codigo = executar_seed(workspace, instante=instante)
    saida = capsys.readouterr()

    assert resumo["inbox"]["idade_mais_antigo_dias"] == 1
    assert resumo["inbox"]["idade_mais_novo_dias"] == 1
    assert codigo == 0
    assert saida.err == ""
    assert saida.out.splitlines() == [
        "Inbox: 1 item; mais antigo há 1 dia; mais novo há 1 dia.",
        "Pauta: 1 aberto, 1 concluído.",
        "Acervo: 1 item; mais antigo há 1 dia.",
        "Estrutura: saudável.",
    ]


def test_seed_humano_povoado_usa_plural_e_mostra_problemas_da_estrutura(
    tmp_path, executar_cli, capsys
):
    from neoprumo.seed import executar_seed

    fuso = timezone(timedelta(hours=-3))
    instante = datetime(2026, 8, 5, 12, 0, tzinfo=fuso)
    workspace = tmp_path / "plural"
    assert executar_cli("setup", workspace).returncode == 0
    inbox = workspace / "Inbox"
    (inbox / "2026-08-03-080000.md").write_text("antigo", encoding="utf-8")
    (inbox / "2026-08-05-080000.md").write_text("novo", encoding="utf-8")
    acervo = workspace / "Acervo"
    (acervo / "2026-08-02-080000.md").write_text("antigo", encoding="utf-8")
    (acervo / "2026-08-04-080000.md").write_text("novo", encoding="utf-8")
    (workspace / "Pauta.md").write_text(
        "# Pauta\n"
        "- [ ] aberta um\n"
        "- [ ] aberta dois\n"
        "- [x] concluída um\n"
        "- [X] concluída dois\n",
        encoding="utf-8",
    )
    (workspace / "Projetos.md").unlink()
    (workspace / "Diario").rmdir()

    codigo = executar_seed(workspace, instante=instante)
    saida = capsys.readouterr()

    assert codigo == 0
    assert saida.err == ""
    assert saida.out.splitlines() == [
        "Inbox: 2 itens; mais antigo há 2 dias; mais novo há 0 dias.",
        "Pauta: 2 abertos, 2 concluídos.",
        "Acervo: 2 itens; mais antigo há 3 dias.",
        "Estrutura: com 2 problemas.",
    ]


def test_seed_humano_explica_inbox_e_acervo_que_nao_pode_ver(
    tmp_path, executar_cli, capsys
):
    from neoprumo.seed import executar_seed

    workspace = tmp_path / "areas-invisiveis"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Inbox").rmdir()
    (workspace / "Acervo").rmdir()

    codigo = executar_seed(workspace, instante=INSTANTE)
    saida = capsys.readouterr()

    assert codigo == 0
    assert saida.err == ""
    assert saida.out.splitlines() == [
        "Inbox: não deu pra ver (Inbox: não existe).",
        "Pauta: vazia.",
        "Acervo: não deu pra ver (Acervo: não existe).",
        "Estrutura: com 2 problemas.",
        "Aviso: Inbox: não existe.",
        "Aviso: Acervo: não existe.",
    ]


def test_seed_workspace_explicito_vence_o_ativo(tmp_path, executar_cli):
    ativo = tmp_path / "ativo"
    explicito = tmp_path / "explicito"
    assert executar_cli("setup", ativo).returncode == 0
    assert executar_cli("setup", explicito).returncode == 0
    (explicito / "Inbox" / "2026-08-04-120000.md").write_text(
        "só aqui", encoding="utf-8"
    )

    resultado = executar_cli("seed", "--workspace", explicito, "--json")

    dados = json.loads(resultado.stdout)
    assert resultado.returncode == 0
    assert dados["workspace"] == str(explicito.resolve())
    assert dados["inbox"]["total"] == 1


def test_seed_sem_configuracao_recusa_com_envelope_completo(executar_cli):
    resultado = executar_cli("seed", "--json")

    assert resultado.returncode == 1
    assert resultado.stderr == ""
    assert_recusa_com_areas_nulas(resultado.stdout, "sem_ativo", None)


def test_seed_recusa_workspace_ativo_que_deixou_de_ser_valido(
    tmp_path, executar_cli
):
    workspace = tmp_path / "quebrado"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / ".neoprumo").rename(workspace / ".identidade-removida")

    resultado = executar_cli("seed", "--json")

    assert resultado.returncode == 1
    assert_recusa_com_areas_nulas(
        resultado.stdout, "ativo_invalido", str(workspace.resolve())
    )


def test_seed_recusa_workspace_explicito_sem_identidade(tmp_path, executar_cli):
    caminho = tmp_path / "nao-workspace"
    caminho.mkdir()

    resultado = executar_cli("seed", "--workspace", caminho, "--json")

    assert resultado.returncode == 1
    assert resultado.stderr == ""
    dados = assert_recusa_com_areas_nulas(
        resultado.stdout, "recusado", str(caminho.resolve())
    )
    assert "não é um workspace" in dados["problemas"][0]
    assert "setup" in dados["acoes"][0].lower()


def test_seed_recusa_humana_vai_para_stderr(tmp_path, executar_cli):
    caminho = tmp_path / "invalido"

    resultado = executar_cli("seed", "--workspace", caminho)

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "não é um workspace" in resultado.stderr


def test_seed_erro_de_sintaxe_sai_com_codigo_2(executar_modulo):
    for argumentos in (("seed", "extra"), ("seed", "--desconhecida")):
        resultado = executar_modulo(*argumentos)

        assert resultado.returncode == 2
        assert "usage:" in resultado.stderr
        assert "Traceback" not in resultado.stderr


def test_estrutura_do_seed_espelha_doctor_saudavel_e_incompleto(
    tmp_path, executar_cli
):
    for nome, remover in (("saudavel", None), ("incompleto", "Inbox")):
        workspace = tmp_path / nome
        assert executar_cli("setup", workspace).returncode == 0
        if remover:
            (workspace / remover).rmdir()

        doctor = executar_cli("doctor", workspace, "--json")
        seed = executar_cli("seed", "--workspace", workspace, "--json")

        dados_doctor = json.loads(doctor.stdout)
        dados_seed = json.loads(seed.stdout)
        assert dados_seed["estrutura"] == {
            "status": dados_doctor["status"],
            "problemas": dados_doctor["problemas"],
        }
        assert seed.returncode == 0
    assert doctor.returncode == 1


def test_seed_trata_pauta_nao_utf8_sem_traceback(tmp_path, executar_cli):
    workspace = tmp_path / "pauta-binaria"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Pauta.md").write_bytes(b"\xff\xfe\x80")

    resultado = executar_cli("seed", "--workspace", workspace, "--json")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    dados = json.loads(resultado.stdout)
    assert dados["pauta"] is None
    assert any(
        "Pauta.md" in problema and "UTF-8" in problema
        for problema in dados["problemas"]
    )
    assert "Traceback" not in resultado.stdout


def test_seed_trata_areas_ausente_tipo_errado_e_symlink_como_nulas(
    tmp_path, executar_cli
):
    workspace = tmp_path / "areas-quebradas"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Inbox").rmdir()
    (workspace / "Acervo").rmdir()
    (workspace / "Acervo").write_text("não é pasta", encoding="utf-8")
    (workspace / "Pauta.md").unlink()
    pauta_externa = tmp_path / "Pauta-fora.md"
    pauta_externa.write_text("- [ ] não seguir", encoding="utf-8")
    (workspace / "Pauta.md").symlink_to(pauta_externa)

    resultado = executar_cli("seed", "--workspace", workspace, "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["inbox"] is None
    assert dados["pauta"] is None
    assert dados["acervo"] is None
    assert any(
        "Inbox" in problema and "não existe" in problema
        for problema in dados["problemas"]
    )
    assert any(
        "Pauta.md" in problema and "simbólico" in problema
        for problema in dados["problemas"]
    )
    assert any(
        "Acervo" in problema and "pasta" in problema
        for problema in dados["problemas"]
    )


def test_seed_trata_area_ilegivel_como_nula_e_avisa(
    tmp_path, executar_cli, monkeypatch, capsys
):
    from neoprumo import seed as modulo_seed

    workspace = tmp_path / "sem-permissao"
    assert executar_cli("setup", workspace).returncode == 0
    scandir_real = modulo_seed.os.scandir

    def negar_inbox(caminho):
        if caminho == workspace / "Inbox":
            raise PermissionError(13, "Permissão negada")
        return scandir_real(caminho)

    monkeypatch.setattr(modulo_seed.os, "scandir", negar_inbox)

    codigo = modulo_seed.executar_seed(workspace, usar_json=True, instante=INSTANTE)
    saida = capsys.readouterr()

    assert codigo == 0
    assert saida.err == ""
    dados = json.loads(saida.out)
    assert dados["inbox"] is None
    assert any(
        "Inbox" in problema and "Permissão negada" in problema
        for problema in dados["problemas"]
    )


def test_seed_humano_adiciona_avisos_de_leitura(tmp_path, executar_cli):
    workspace = tmp_path / "aviso"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Pauta.md").write_bytes(b"\xff")

    resultado = executar_cli("seed", "--workspace", workspace)

    assert resultado.returncode == 0
    assert len(resultado.stdout.splitlines()) == 5
    assert resultado.stdout.splitlines()[1].startswith("Pauta: não deu pra ver")
    assert resultado.stdout.splitlines()[4].startswith("Aviso: Pauta.md")


def test_seed_ignora_item_quando_mtime_nao_pode_ser_lido(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import seed as modulo_seed

    workspace = tmp_path / "mtime-inacessivel"
    assert executar_cli("setup", workspace).returncode == 0
    scandir_real = modulo_seed.os.scandir

    class EntradaSemMtime:
        name = "sem-data.txt"

        def stat(self, follow_symlinks=False):
            raise PermissionError(13, "Permissão negada")

    class Entradas:
        def __enter__(self):
            return iter([EntradaSemMtime()])

        def __exit__(self, tipo, valor, traceback):
            return False

    def substituir_inbox(caminho):
        if caminho == workspace / "Inbox":
            return Entradas()
        return scandir_real(caminho)

    monkeypatch.setattr(modulo_seed.os, "scandir", substituir_inbox)

    resultado = modulo_seed.resumir(workspace, instante=INSTANTE)

    assert resultado["inbox"] == {
        "total": 0,
        "idade_mais_antigo_dias": None,
        "idade_mais_novo_dias": None,
    }
    assert any(
        "sem-data.txt" in problema and "não foi contado" in problema
        for problema in resultado["problemas"]
    )


@pytest.mark.parametrize("incompleto", [False, True])
def test_seed_e_somente_leitura_no_workspace_e_na_configuracao(
    incompleto, tmp_path, executar_cli
):
    workspace = tmp_path / ("incompleto" if incompleto else "saudavel")
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Inbox" / "2026-08-04-120000.bin").write_bytes(b"\x00\xff")
    if incompleto:
        (workspace / ".neoprumo" / "workspace.json").unlink()
        (workspace / "Acervo").rmdir()
    configuracao = tmp_path / "configuracao-xdg" / "neoprumo"
    antes = fotografar(workspace, configuracao)

    resultado = executar_cli("seed", "--json")

    assert resultado.returncode == 0
    assert fotografar(workspace, configuracao) == antes


def fotografar(*raizes):
    foto = {}
    for raiz in raizes:
        caminhos = [raiz]
        for pasta, diretorios, arquivos in os.walk(raiz, followlinks=False):
            caminhos.extend(
                Path(pasta) / nome for nome in diretorios + arquivos
            )
        for caminho_bruto in caminhos:
            caminho = Path(caminho_bruto)
            estado = caminho.lstat()
            conteudo = caminho.read_bytes() if stat.S_ISREG(estado.st_mode) else None
            foto[str(caminho)] = (
                stat.S_IFMT(estado.st_mode),
                conteudo,
                estado.st_mtime_ns,
            )
    return foto


def assert_recusa_com_areas_nulas(saida, status, workspace):
    dados = json.loads(saida)
    assert dados["status"] == status
    assert dados["workspace"] == workspace
    assert dados["problemas"]
    assert dados["acoes"]
    for campo in ("gerado_em", "inbox", "pauta", "acervo", "estrutura"):
        assert campo in dados
        assert dados[campo] is None
    return dados


def definir_mtime(caminho, instante):
    marca = instante.timestamp()
    os.utime(caminho, (marca, marca))
