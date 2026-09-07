import json

import pytest


@pytest.mark.parametrize("usar_json", [False, True])
def test_reparo_parcial_separa_feito_do_pendente_e_preserva_conteudo(
    usar_json, tmp_path, executar_modulo
):
    workspace = tmp_path / "casa"
    assert executar_modulo("setup", workspace).returncode == 0
    transcricao = workspace / "transcricao-do-video.md"
    conteudo = "Transcrição do dono\r\nsem perder um byte.\n".encode()
    transcricao.write_bytes(conteudo)
    rascunhos = workspace / "Rascunhos"
    rascunhos.mkdir()
    (rascunhos / "ideia.md").write_bytes(b"ideia preservada\x00")
    argumentos = ["doctor", workspace, "--reparar"]
    if usar_json:
        argumentos.append("--json")

    resultado = executar_modulo(*argumentos)

    assert resultado.returncode == 1
    if usar_json:
        assert resultado.stderr == ""
        assert json.loads(resultado.stdout) == {
            "status": "com_problemas",
            "problemas": ["Rascunhos/ está solta na raiz."],
            "acoes": ["transcricao-do-video.md recolhido pra Inbox."],
            "mensagem": "O workspace tem problemas:",
            "workspace": str(workspace),
        }
    else:
        assert resultado.stdout == ""
        assert resultado.stderr == (
            "O reparo foi parcial.\n"
            "Feito:\n"
            "- transcricao-do-video.md recolhido pra Inbox.\n"
            "Continua pendente:\n"
            "- Rascunhos/ está solta na raiz.\n"
        )
    assert not transcricao.exists()
    assert (workspace / "Inbox" / transcricao.name).read_bytes() == conteudo
    assert (rascunhos / "ideia.md").read_bytes() == b"ideia preservada\x00"
    assert not (workspace / "Inbox" / "Rascunhos").exists()


def test_reparo_parcial_preserva_todos_os_itens_e_a_ordem_dos_blocos(
    tmp_path, executar_cli
):
    workspace = tmp_path / "casa"
    assert executar_cli("setup", workspace).returncode == 0
    for nome in ("b.md", "a.md"):
        (workspace / nome).write_text(nome, encoding="utf-8")
    for nome in ("Rascunhos", "Planos"):
        (workspace / nome).mkdir()

    resultado = executar_cli("doctor", workspace, "--reparar")

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert resultado.stderr == (
        "O reparo foi parcial.\n"
        "Feito:\n"
        "- a.md recolhido pra Inbox.\n"
        "- b.md recolhido pra Inbox.\n"
        "Continua pendente:\n"
        "- Planos/ está solta na raiz.\n"
        "- Rascunhos/ está solta na raiz.\n"
    )


@pytest.mark.parametrize("readotar", [False, True])
@pytest.mark.parametrize("usar_json", [False, True])
def test_criacao_parcial_preserva_mensagem_e_orientacao_de_recuperacao(
    readotar, usar_json, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import workspace as modulo

    workspace = tmp_path / "parcial"
    if readotar:
        workspace.mkdir()
        (workspace / "Pauta.md").write_bytes(b"pauta do dono\x00")
    criar_original = modulo.criar_item_ausente

    def negar_assuntos(raiz, nome, tipo):
        if nome == "Assuntos":
            raise PermissionError("acesso negado pelo teste")
        return criar_original(raiz, nome, tipo)

    monkeypatch.setattr(modulo, "criar_item_ausente", negar_assuntos)
    argumentos = ["setup", workspace]
    if readotar:
        argumentos.append("--readotar")
    if usar_json:
        argumentos.append("--json")

    resultado = executar_cli(*argumentos)

    operacao = "readoção" if readotar else "criação"
    mensagem = (
        f"A {operacao} ficou incompleta. Repita setup --readotar {workspace}."
    )
    acoes = ["Inbox recriado."]
    if not readotar:
        acoes.append("Pauta.md recriado.")
    acoes.extend(["Acervo recriado.", "Diario recriado."])
    problema = "Não foi possível criar Assuntos (acesso negado pelo teste)."
    assert resultado.returncode == 1
    if usar_json:
        assert resultado.stderr == ""
        assert json.loads(resultado.stdout) == {
            "status": "com_problemas",
            "problemas": [problema],
            "acoes": acoes,
            "mensagem": mensagem,
        }
    else:
        assert resultado.stdout == ""
        assert resultado.stderr == (
            f"{mensagem}\nFeito:\n"
            + "".join(f"- {acao}\n" for acao in acoes)
            + f"Continua pendente:\n- {problema}\n"
        )
    assert not (workspace / ".neoprumo").exists()
    if readotar:
        assert (workspace / "Pauta.md").read_bytes() == b"pauta do dono\x00"


@pytest.mark.parametrize("readotar", [False, True])
def test_falha_do_ponteiro_preserva_rota_de_ativacao_e_acao_realizada(
    readotar, tmp_path, executar_cli, monkeypatch
):
    from neoprumo import workspace as modulo

    workspace = tmp_path / "ponteiro"
    if readotar:
        workspace.mkdir()
        (workspace / "Pauta.md").write_bytes(b"pauta do dono")

    def negar_ponteiro(_workspace):
        raise PermissionError("acesso negado pelo teste")

    monkeypatch.setattr(modulo, "adotar_se_primeiro", negar_ponteiro)
    argumentos = ["setup", workspace]
    if readotar:
        argumentos.append("--readotar")

    resultado = executar_cli(*argumentos)

    if readotar:
        mensagem = "A readoção ficou incompleta."
        acoes = [
            "Inbox recriado.",
            "Acervo recriado.",
            "Assuntos recriado.",
            "Diario recriado.",
            ".neoprumo/ criada.",
            ".neoprumo/workspace.json recriado.",
        ]
    else:
        mensagem = "O workspace foi criado."
        acoes = ["Estrutura canônica criada."]
    participio = "readotado" if readotar else "criado"
    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert resultado.stderr == (
        f"{mensagem} Execute workspace usar {workspace}.\nFeito:\n"
        + "".join(f"- {acao}\n" for acao in acoes)
        + "Continua pendente:\n"
        + f"- O workspace foi {participio}, mas o ponteiro de workspace ativo "
        "não pôde ser gravado.\n"
    )


@pytest.mark.parametrize("reparar", [False, True])
def test_problemas_sem_acao_preservam_saida_atual(
    reparar, tmp_path, executar_cli
):
    workspace = tmp_path / "casa"
    assert executar_cli("setup", workspace).returncode == 0
    (workspace / "Rascunhos").mkdir()
    argumentos = ["doctor", workspace]
    if reparar:
        argumentos.append("--reparar")

    resultado = executar_cli(*argumentos)

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert resultado.stderr == (
        "O workspace tem problemas:\n- Rascunhos/ está solta na raiz.\n"
    )


def test_recusa_preserva_orientacao_sem_rotular_como_feito(tmp_path, executar_cli):
    workspace = tmp_path / "ocupado"
    workspace.mkdir()
    pauta = workspace / "Pauta.md"
    pauta.write_bytes(b"pauta do dono\x00")

    resultado = executar_cli("setup", workspace)

    assert resultado.returncode == 1
    assert resultado.stdout == ""
    assert resultado.stderr == (
        "O diretório não está vazio; nada foi alterado.\n"
        "- O diretório não está vazio.\n"
        f"- Execute setup --readotar {workspace}.\n"
    )
    assert list(workspace.iterdir()) == [pauta]
    assert pauta.read_bytes() == b"pauta do dono\x00"
