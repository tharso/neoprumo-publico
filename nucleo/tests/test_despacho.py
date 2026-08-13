import json
from datetime import datetime

import pytest


def test_despacho_pauta_preserva_conteudo_multilinha_e_remove_da_inbox(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "pauta")
    item = criar_item(
        workspace,
        "2026-08-04-101500.md",
        "Preparar a oficina\nLevar cartões coloridos\n\nConferir o projetor\n",
    )

    resultado = executar_cli("despacho", item.stem, "pauta")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout == f"Despachado pra pauta: {item.stem}.\n"
    assert (workspace / "Pauta.md").read_text(encoding="utf-8") == (
        "# Pauta\n"
        "- [ ] Preparar a oficina\n"
        "  Levar cartões coloridos\n"
        "  \n"
        "  Conferir o projetor\n"
        f"  — inbox {item.stem}, despachado em {hoje()}\n"
    )
    assert not item.exists()


def test_despacho_pauta_recria_arquivo_ausente_e_avisa(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "pauta-recriada")
    (workspace / "Pauta.md").unlink()
    item = criar_item(workspace, "nota.txt", "Telefonar para a tapeceira")

    resultado = executar_cli("despacho", item.name, "pauta", "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["acoes"] == [
        "O arquivo Pauta.md estava faltando e foi recriado. "
        "Rode doctor para conferir o workspace."
    ]
    assert (workspace / "Pauta.md").read_text(encoding="utf-8").startswith(
        "# Pauta\n- [ ] Telefonar para a tapeceira\n"
    )


def test_despacho_pauta_separa_registro_de_arquivo_sem_quebra_final(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "pauta-sem-quebra")
    (workspace / "Pauta.md").write_text("# Pauta", encoding="utf-8")
    item = criar_item(workspace, "compromisso.md", "Visitar o observatório")

    resultado = executar_cli("despacho", item.name, "pauta")

    assert resultado.returncode == 0
    assert (workspace / "Pauta.md").read_text(encoding="utf-8") == (
        "# Pauta\n"
        "- [ ] Visitar o observatório\n"
        f"  — inbox compromisso, despachado em {hoje()}\n"
    )


def test_despacho_acervo_move_arquivo_com_nome_e_bytes_preservados(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "acervo")
    item = criar_item(workspace, "recorte.bin", b"\x00\xff\x10arquivo")

    resultado = executar_cli("despacho", item.name, "acervo")

    destino = workspace / "Acervo" / item.name
    assert resultado.returncode == 0
    assert resultado.stdout == f"Movido pro acervo: {item.name}.\n"
    assert not item.exists()
    assert destino.read_bytes() == b"\x00\xff\x10arquivo"


def test_despacho_acervo_sufixa_colisao_sem_sobrescrever(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "acervo-colisao")
    existente = workspace / "Acervo" / "mapa.txt"
    existente.write_text("já guardado", encoding="utf-8")
    item = criar_item(workspace, "mapa.txt", "novo mapa")

    resultado = executar_cli("despacho", item.name, "acervo")

    assert resultado.returncode == 0
    assert resultado.stdout == "Movido pro acervo: mapa-2.txt.\n"
    assert existente.read_text(encoding="utf-8") == "já guardado"
    assert (workspace / "Acervo" / "mapa-2.txt").read_text(
        encoding="utf-8"
    ) == "novo mapa"


def test_despacho_acervo_recria_pasta_ausente_e_avisa_em_json(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "acervo-ausente")
    (workspace / "Acervo").rmdir()
    item = criar_item(workspace, "insubstituivel.bin", b"\x00\xfforiginal")

    resultado = executar_cli("despacho", item.name, "acervo", "--json")

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["acoes"] == [
        "A pasta Acervo estava faltando e foi recriada. "
        "Rode doctor para conferir o workspace."
    ]
    assert not item.exists()
    assert (workspace / "Acervo" / item.name).read_bytes() == b"\x00\xfforiginal"


def test_despacho_acervo_recriado_avisa_na_mensagem_humana(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "acervo-aviso-humano")
    (workspace / "Acervo").rmdir()
    item = criar_item(workspace, "mapa.md", "mapa raro")

    resultado = executar_cli("despacho", item.name, "acervo")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout == (
        "Movido pro acervo: mapa.md. "
        "A pasta Acervo estava faltando e foi recriada. "
        "Rode doctor para conferir o workspace.\n"
    )


def test_despacho_recusa_acervo_apontando_pra_fora_do_workspace(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "acervo-externo")
    acervo_externo = tmp_path / "acervo-fora"
    acervo_externo.mkdir()
    (workspace / "Acervo").rmdir()
    (workspace / "Acervo").symlink_to(acervo_externo, target_is_directory=True)
    item = criar_item(workspace, "privado.md", "não pode sair")

    resultado = executar_cli("despacho", item.name, "acervo")

    assert resultado.returncode == 1
    assert "ficou na inbox" in resultado.stderr
    assert item.read_text(encoding="utf-8") == "não pode sair"
    assert list(acervo_externo.iterdir()) == []


def test_despacho_projeto_usa_assunto_sem_alterar_documento_antigo(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "projeto-novo")
    projetos = workspace / "Projetos.md"
    conteudo_anterior = "# Projetos\n\nTexto livre que não termina com quebra"
    projetos.write_text(conteudo_anterior, encoding="utf-8")
    assert executar_cli(
        "assunto", "registrar", "Casa Amarela", "--id", "casa-amarela",
        "--workspace", workspace, "--json",
    ).returncode == 0
    item = criar_item(
        workspace,
        "ideia.md",
        "Rever a recepção\nEntrevistar três visitantes\n\nFotografar a entrada\n",
    )

    resultado = executar_cli("despacho", item.name, "projeto", "Casa Amarela")

    assert resultado.returncode == 0
    assert "Casa Amarela" in resultado.stdout
    assert projetos.read_text(encoding="utf-8") == conteudo_anterior
    ficha = (workspace / "Assuntos" / "casa-amarela.md").read_text()
    assert f"- {hoje()} (inbox ideia.md): Rever a recepção\n" in ficha
    assert not item.exists()


def test_despacho_projeto_resolve_id_e_preserva_documento_antigo(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "projeto-exato")
    projetos = workspace / "Projetos.md"
    projetos.write_text(
        "# Projetos\n\n"
        "## Casa\nstatus da casa\n\n"
        "## Casa Amarela\nstatus da casa amarela\n\n"
        "## Casa 2\nstatus da casa 2\n",
        encoding="utf-8",
    )
    anterior = projetos.read_text()
    assert executar_cli(
        "assunto", "registrar", "Casa", "--id", "casa",
        "--workspace", workspace, "--json",
    ).returncode == 0
    item = criar_item(workspace, "decisao.md", "Trocar as cortinas")

    resultado = executar_cli("despacho", item.stem, "projeto", "Casa")

    assert resultado.returncode == 0
    assert projetos.read_text(encoding="utf-8") == anterior
    assert "(inbox decisao.md): Trocar as cortinas" in (
        workspace / "Assuntos" / "casa.md"
    ).read_text()


def test_despacho_projeto_nao_recria_documento_antigo_ausente(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "projetos-recriado")
    assert executar_cli(
        "assunto", "registrar", "Varanda", "--id", "varanda",
        "--workspace", workspace, "--json",
    ).returncode == 0
    item = criar_item(workspace, "plano.md", "Primeira conversa")

    resultado = executar_cli(
        "despacho", item.name, "projeto", "Varanda", "--json"
    )

    assert resultado.returncode == 0
    dados = json.loads(resultado.stdout)
    assert dados["acoes"] == []
    assert not (workspace / "Projetos.md").exists()
    assert "(inbox plano.md): Primeira conversa" in (
        workspace / "Assuntos" / "varanda.md"
    ).read_text()


def test_despacho_projeto_ignora_documento_antigo_nao_utf8(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "projetos-binario")
    projetos = workspace / "Projetos.md"
    projetos.write_bytes(b"\xff\xfeprojetos")
    assert executar_cli(
        "assunto", "registrar", "Museu", "--id", "museu",
        "--workspace", workspace, "--json",
    ).returncode == 0
    item = criar_item(workspace, "nota.md", "Conteúdo legível")

    resultado = executar_cli("despacho", item.name, "projeto", "Museu")

    assert resultado.returncode == 0
    assert not item.exists()
    assert projetos.read_bytes() == b"\xff\xfeprojetos"


def test_despacho_lixo_move_integro_e_mantem_recuperavel(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "lixo")
    item = criar_item(workspace, "rascunho.dat", b"\xfe\x00rascunho")

    resultado = executar_cli("despacho", item.name, "lixo")

    destino = workspace / ".neoprumo" / "lixo" / item.name
    assert resultado.returncode == 0
    assert resultado.stdout == f"Movido pro lixo (recuperável): {item.name}.\n"
    assert not item.exists()
    assert destino.read_bytes() == b"\xfe\x00rascunho"


def test_despacho_lixo_sufixa_colisao_sem_apagar_o_anterior(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "lixo-colisao")
    lixo = workspace / ".neoprumo" / "lixo"
    lixo.mkdir()
    (lixo / "rascunho.md").write_text("anterior", encoding="utf-8")
    (lixo / "rascunho-2.md").write_text("segundo", encoding="utf-8")
    item = criar_item(workspace, "rascunho.md", "terceiro")

    resultado = executar_cli("despacho", item.name, "lixo")

    assert resultado.returncode == 0
    assert (lixo / "rascunho.md").read_text(encoding="utf-8") == "anterior"
    assert (lixo / "rascunho-2.md").read_text(encoding="utf-8") == "segundo"
    assert (lixo / "rascunho-3.md").read_text(encoding="utf-8") == "terceiro"


@pytest.mark.parametrize("destino", ["pauta", "projeto"])
def test_despacho_textual_recusa_arquivo_nao_utf8_sem_alterar_nada(
    tmp_path, executar_cli, destino
):
    workspace = criar_workspace(tmp_path, executar_cli, f"binario-{destino}")
    item = criar_item(workspace, "imagem.jpg", b"\xff\xfe\x00\x80")
    pauta_anterior = (workspace / "Pauta.md").read_bytes()
    argumentos = ["despacho", item.name, destino]
    if destino == "projeto":
        executar_cli(
            "assunto", "registrar", "Museu", "--id", "museu",
            "--workspace", workspace, "--json",
        )
        argumentos.append("Museu")

    resultado = executar_cli(*argumentos)

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "não é texto UTF-8" in resultado.stderr
    assert "acervo" in resultado.stderr
    assert item.read_bytes() == b"\xff\xfe\x00\x80"
    assert (workspace / "Pauta.md").read_bytes() == pauta_anterior


@pytest.mark.parametrize("destino", ["pauta", "projeto"])
def test_despacho_textual_recusa_item_sem_linha_preenchida(
    tmp_path, executar_cli, destino
):
    workspace = criar_workspace(tmp_path, executar_cli, f"vazio-{destino}")
    item = criar_item(workspace, "vazio.txt", "\n \t\n")
    argumentos = ["despacho", item.name, destino]
    if destino == "projeto":
        executar_cli(
            "assunto", "registrar", "Farol", "--id", "farol",
            "--workspace", workspace, "--json",
        )
        argumentos.append("Farol")

    resultado = executar_cli(*argumentos)

    assert resultado.returncode == 1
    assert "nenhuma linha com texto" in resultado.stderr
    assert "acervo" in resultado.stderr
    assert item.read_text(encoding="utf-8") == "\n \t\n"


def test_despacho_recusa_radical_ambiguo_e_pede_nome_completo(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "ambiguo")
    primeiro = criar_item(workspace, "lembrete.md", "um")
    segundo = criar_item(workspace, "lembrete.txt", "dois")

    resultado = executar_cli("despacho", "lembrete", "acervo")

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert "mais de um item" in resultado.stderr
    assert "nome completo" in resultado.stderr
    assert primeiro.read_text(encoding="utf-8") == "um"
    assert segundo.read_text(encoding="utf-8") == "dois"
    assert list((workspace / "Acervo").iterdir()) == []


def test_nome_com_extensao_resolve_item_exato_mesmo_com_radical_repetido(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "nome-completo")
    mantido = criar_item(workspace, "lembrete.md", "fica")
    movido = criar_item(workspace, "lembrete.txt", "vai")

    resultado = executar_cli("despacho", movido.name, "acervo")

    assert resultado.returncode == 0
    assert mantido.read_text(encoding="utf-8") == "fica"
    assert not movido.exists()
    assert (workspace / "Acervo" / movido.name).read_text(encoding="utf-8") == "vai"


def test_nome_exato_sem_extensao_vence_busca_por_radical(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "nome-sem-extensao")
    exato = criar_item(workspace, "foo", "vai")
    mantido = criar_item(workspace, "foo.md", "fica")

    resultado = executar_cli("despacho", "foo", "acervo")

    assert resultado.returncode == 0
    assert not exato.exists()
    assert (workspace / "Acervo" / "foo").read_text(encoding="utf-8") == "vai"
    assert mantido.read_text(encoding="utf-8") == "fica"


def test_despacho_recusa_item_inexistente_sem_mexer_nos_demais(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "inexistente")
    mantido = criar_item(workspace, "guardiao.md", "permanece")

    resultado = executar_cli("despacho", "fantasma", "lixo")

    assert resultado.returncode == 1
    assert "não foi encontrado" in resultado.stderr
    assert mantido.read_text(encoding="utf-8") == "permanece"
    assert not (workspace / ".neoprumo" / "lixo").exists()


def test_despacho_recusa_destino_desconhecido_sem_alterar_item(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "destino-desconhecido")
    item = criar_item(workspace, "bilhete.md", "não mexer")

    resultado = executar_cli("despacho", item.name, "gaveta")

    assert resultado.returncode == 1
    assert "Destino desconhecido" in resultado.stderr
    assert "pauta" in resultado.stderr
    assert item.read_text(encoding="utf-8") == "não mexer"


def test_despacho_recusa_projeto_sem_nome_sem_alterar_item(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "projeto-sem-nome")
    item = criar_item(workspace, "nota.md", "não mexer")

    resultado = executar_cli("despacho", item.name, "projeto")

    assert resultado.returncode == 1
    assert "referência do assunto" in resultado.stderr
    assert item.read_text(encoding="utf-8") == "não mexer"


def test_despacho_recusa_caminho_em_vez_de_nome_do_item(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "caminho-item")
    fora = tmp_path / "fora.md"
    fora.write_text("intocável", encoding="utf-8")

    resultado = executar_cli("despacho", "../fora.md", "lixo")

    assert resultado.returncode == 1
    assert "nome do arquivo" in resultado.stderr
    assert fora.read_text(encoding="utf-8") == "intocável"


def test_despacho_recusa_inbox_apontando_pra_fora_do_workspace(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "inbox-externa")
    inbox_externa = tmp_path / "inbox-fora"
    inbox_externa.mkdir()
    (inbox_externa / "nota.md").write_text("não tocar", encoding="utf-8")
    (workspace / "Inbox").rmdir()
    (workspace / "Inbox").symlink_to(inbox_externa, target_is_directory=True)

    resultado = executar_cli("despacho", "nota.md", "lixo")

    assert resultado.returncode == 1
    assert "Inbox não pôde ser lida" in resultado.stderr
    assert (inbox_externa / "nota.md").read_text(encoding="utf-8") == "não tocar"


def test_despacho_recusa_inbox_ilegivel_sem_traceback_e_sem_perder_item(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import despacho as modulo_despacho

    workspace = criar_workspace(tmp_path, executar_cli, "inbox-ilegivel")
    item = criar_item(workspace, "insubstituivel.md", "não pode sumir")
    inbox = workspace / "Inbox"
    iterdir_real = modulo_despacho.Path.iterdir

    def negar_inbox(caminho):
        if caminho == inbox:
            raise PermissionError(13, "Permissão negada")
        return iterdir_real(caminho)

    monkeypatch.setattr(modulo_despacho.Path, "iterdir", negar_inbox)

    resultado_humano = executar_cli("despacho", item.stem, "lixo")
    resultado_json = executar_cli("despacho", item.stem, "lixo", "--json")

    assert resultado_humano.returncode == 1
    assert resultado_humano.stdout == ""
    assert "Inbox não pôde ser lida" in resultado_humano.stderr
    assert "doctor" in resultado_humano.stderr
    assert "Traceback" not in resultado_humano.stderr

    assert resultado_json.returncode == 1
    assert resultado_json.stderr == ""
    dados = json.loads(resultado_json.stdout)
    assert dados == {
        "status": "recusado",
        "problemas": ["A pasta Inbox não pôde ser lida."],
        "acoes": ["Rode doctor para conferir o workspace."],
        "mensagem": (
            "A Inbox não pôde ser lida. Rode doctor para conferir o workspace."
        ),
        "workspace": str(workspace.resolve()),
        "item": None,
        "id": None,
        "destino": "lixo",
    }
    assert "Traceback" not in resultado_json.stdout

    assert item.read_text(encoding="utf-8") == "não pode sumir"
    assert not (workspace / ".neoprumo" / "lixo").exists()


def test_despacho_recusa_item_apontando_pra_fora_do_workspace(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "item-externo")
    arquivo_externo = tmp_path / "segredo.md"
    arquivo_externo.write_text("não tocar", encoding="utf-8")
    (workspace / "Inbox" / "atalho.md").symlink_to(arquivo_externo)

    resultado = executar_cli("despacho", "atalho.md", "lixo")

    assert resultado.returncode == 1
    assert "fora do workspace" in resultado.stderr
    assert arquivo_externo.read_text(encoding="utf-8") == "não tocar"
    assert (workspace / "Inbox" / "atalho.md").is_symlink()


def test_workspace_explicito_vence_ativo_no_despacho(tmp_path, executar_cli):
    ativo = criar_workspace(tmp_path, executar_cli, "ativo")
    explicito = criar_workspace(tmp_path, executar_cli, "explicito")
    item_ativo = criar_item(ativo, "mesmo.md", "fica")
    item_explicito = criar_item(explicito, "mesmo.md", "vai")

    resultado = executar_cli(
        "despacho", item_explicito.name, "acervo", "--workspace", explicito
    )

    assert resultado.returncode == 0
    assert item_ativo.read_text(encoding="utf-8") == "fica"
    assert not item_explicito.exists()
    assert (explicito / "Acervo" / "mesmo.md").read_text(
        encoding="utf-8"
    ) == "vai"


def test_despacho_sem_workspace_ativo_recusa_com_envelope_json(executar_cli):
    resultado = executar_cli("despacho", "nota", "pauta", "--json")

    assert resultado.returncode == 1
    assert resultado.stderr == ""
    dados = json.loads(resultado.stdout)
    assert dados == {
        "status": "sem_ativo",
        "problemas": ["Não há um workspace ativo resolvível."],
        "acoes": [
            "Execute setup para criar um workspace ou workspace usar para "
            "apontar um existente."
        ],
        "mensagem": (
            "Nenhum workspace ativo pôde ser resolvido. "
            "Execute setup ou workspace usar para corrigir."
        ),
        "workspace": None,
        "item": None,
        "id": None,
        "destino": "pauta",
    }


def test_despacho_recusa_workspace_ativo_que_deixou_de_ser_valido(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "ativo-invalido")
    (workspace / ".neoprumo").rename(workspace / ".marca-removida")

    resultado = executar_cli("despacho", "nota", "pauta", "--json")

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "ativo_invalido"
    assert dados["workspace"] == str(workspace.resolve())
    assert dados["destino"] == "pauta"
    assert "não pôde ser usado" in dados["mensagem"]


def test_despacho_recusa_workspace_explicito_invalido(tmp_path, executar_cli):
    caminho = tmp_path / "nao-workspace"
    caminho.mkdir()

    resultado = executar_cli(
        "despacho", "nota", "acervo", "--workspace", caminho, "--json"
    )

    assert resultado.returncode == 1
    dados = json.loads(resultado.stdout)
    assert dados["status"] == "recusado"
    assert dados["workspace"] == str(caminho.resolve())
    assert dados["item"] is None
    assert dados["id"] is None
    assert dados["destino"] == "acervo"
    assert "não é um workspace" in dados["mensagem"]


def test_despacho_json_de_sucesso_entrega_envelope_completo(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "json-sucesso")
    item = criar_item(workspace, "folheto.txt", "Referência rara")

    resultado = executar_cli("despacho", item.name, "acervo", "--json")

    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout.count("\n") == 1
    dados = json.loads(resultado.stdout)
    assert dados == {
        "status": "despachado",
        "problemas": [],
        "acoes": [],
        "mensagem": "Movido pro acervo: folheto.txt.",
        "workspace": str(workspace.resolve()),
        "item": str(workspace / "Acervo" / "folheto.txt"),
        "id": "folheto",
        "destino": "acervo",
    }


def test_falha_ao_gravar_destino_textual_mantem_item_na_inbox(
    tmp_path, executar_cli
):
    workspace = criar_workspace(tmp_path, executar_cli, "falha-gravacao")
    pauta = workspace / "Pauta.md"
    pauta.unlink()
    pauta.mkdir()
    item = criar_item(workspace, "essencial.md", "Não posso sumir")

    resultado = executar_cli("despacho", item.name, "pauta")

    assert resultado.returncode == 1
    assert "não foi possível" in resultado.stderr.lower()
    assert item.read_text(encoding="utf-8") == "Não posso sumir"
    assert pauta.is_dir()


def test_despacho_so_mexe_no_item_escolhido(tmp_path, executar_cli):
    workspace = criar_workspace(tmp_path, executar_cli, "um-por-vez")
    escolhido = criar_item(workspace, "escolhido.md", "vai")
    outro_texto = criar_item(workspace, "outro.txt", "fica texto")
    outro_binario = criar_item(workspace, "outro.bin", b"\x00\xfffica")

    resultado = executar_cli("despacho", escolhido.name, "lixo")

    assert resultado.returncode == 0
    assert not escolhido.exists()
    assert outro_texto.read_text(encoding="utf-8") == "fica texto"
    assert outro_binario.read_bytes() == b"\x00\xfffica"


def criar_workspace(tmp_path, executar_cli, nome):
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


def hoje():
    return datetime.now().strftime("%Y-%m-%d")
