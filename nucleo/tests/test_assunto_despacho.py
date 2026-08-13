import hashlib
import json
import os
import stat

import pytest


def setup(executar_cli, tmp_path):
    workspace = tmp_path / "casa"
    assert executar_cli("setup", workspace, "--json").returncode == 0
    assert executar_cli(
        "assunto", "registrar", "Satélite perdido", "--id", "satelite",
        "--tipo", "pessoa", "--workspace", workspace, "--json",
    ).returncode == 0
    return workspace


def json_de(resultado):
    return json.loads(resultado.stdout or resultado.stderr)


def test_despacho_assunto_grava_nota_integral_antes_de_remover(executar_cli, tmp_path):
    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "mapa.md.txt"
    item.write_text("\nCabeça\n  detalhe\n\nfinal\r\n")

    resultado = executar_cli(
        "despacho", item.name, "assunto", "SATÉLITE", "--workspace", workspace,
        "--json",
    )

    envelope = json_de(resultado)
    assert resultado.returncode == 0
    assert envelope["status"] == "despachado"
    assert not item.exists()
    ficha = (workspace / "Assuntos" / "satelite.md").read_text()
    assert "(inbox mapa.md.txt): Cabeça\n  \n    detalhe\n  \n  final\n" in ficha
    mostrado = executar_cli(
        "assunto", "mostrar", "satelite", "--workspace", workspace, "--json"
    )
    assert json_de(mostrado)["notas"][0]["texto"] == "Cabeça\n\n  detalhe\n\nfinal"


def test_guarda_compara_item_com_os_bytes_que_construiram_a_nota(
    executar_cli, tmp_path, monkeypatch
):
    from pathlib import Path

    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "mudou.md"
    item.write_bytes(b"versao nova")
    leitura_real = Path.read_bytes
    leituras = 0

    def mudar_entre_leituras(caminho):
        nonlocal leituras
        if caminho == item:
            leituras += 1
            return b"versao antiga" if leituras == 1 else b"versao nova"
        return leitura_real(caminho)

    monkeypatch.setattr(Path, "read_bytes", mudar_entre_leituras)
    resultado = executar_cli(
        "despacho", item.name, "assunto", "satelite",
        "--workspace", workspace, "--json",
    )

    dados = json_de(resultado)
    assert resultado.returncode == 1
    assert item.exists()
    assert "versão anterior" in dados["mensagem"]


def test_atalho_projeto_oferece_nascimento_sem_criar(executar_cli, tmp_path):
    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "ideia.md"
    item.write_text("algo")

    resultado = executar_cli(
        "despacho", item.name, "projeto", "Projeto Lunar",
        "--workspace", workspace, "--json",
    )

    envelope = json_de(resultado)
    assert resultado.returncode == 1
    assert envelope["status"] == "assunto_inexistente"
    assert envelope["id_sugerido"] == "projeto-lunar"
    assert envelope["tipo_sugerido"] == "projeto"
    assert item.exists()


def test_assunto_arquivado_exige_confirmacao(executar_cli, tmp_path):
    workspace = setup(executar_cli, tmp_path)
    executar_cli("assunto", "arquivar", "satelite", "--workspace", workspace, "--json")
    item = workspace / "Inbox" / "sinal.txt"
    item.write_text("sinal")

    recusado = executar_cli(
        "despacho", item.name, "assunto", "satelite", "--workspace", workspace,
        "--json",
    )
    assert recusado.returncode == 1
    assert json_de(recusado)["status"] == "recusado"
    aceito = executar_cli(
        "despacho", item.name, "assunto", "satelite", "--confirmado",
        "--workspace", workspace, "--json",
    )
    assert aceito.returncode == 0
    assert not item.exists()


@pytest.mark.parametrize("destino", ["assunto", "projeto", "acervo_associado"])
def test_confirmado_sem_assunto_arquivado_e_recusado(
    destino, executar_cli, tmp_path
):
    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / f"{destino}.txt"
    item.write_text("não mover")
    argumentos = ["despacho", item.name]
    if destino == "acervo_associado":
        argumentos.extend(("acervo", "--assunto", "satelite"))
    else:
        argumentos.extend((destino, "satelite"))

    resultado = executar_cli(
        *argumentos, "--confirmado", "--workspace", workspace, "--json"
    )

    dados = json_de(resultado)
    assert resultado.returncode == 1
    assert dados["status"] == "recusado"
    assert dados["mensagem"] == "Não há o que confirmar."
    assert item.read_text() == "não mover"
    assert not (workspace / "Acervo" / item.name).exists()


def test_acervo_usa_criacao_exclusiva_preserva_metadados_e_nome_completo(
    executar_cli, tmp_path
):
    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "mapa.tar.gz"
    item.write_bytes(b"\xff\x00")
    item.chmod(0o640)
    os.utime(item, (1_700_000_000, 1_700_000_000))
    (workspace / "Acervo" / "mapa.tar.gz").write_bytes(b"existente")

    resultado = executar_cli(
        "despacho", item.name, "acervo", "--assunto", "satelite",
        "--workspace", workspace, "--json",
    )

    envelope = json_de(resultado)
    final = workspace / "Acervo" / "mapa.tar-2.gz"
    assert resultado.returncode == 0
    assert final.read_bytes() == b"\xff\x00"
    assert stat.S_IMODE(final.stat().st_mode) == 0o640
    assert int(final.stat().st_mtime) == 1_700_000_000
    assert envelope["status"] == "despachado"
    ficha = (workspace / "Assuntos" / "satelite.md").read_text()
    assert "(acervo mapa.tar-2.gz): item mapa.tar-2.gz" in ficha


def test_acervo_esgota_cem_nomes_sem_tocar_na_origem(executar_cli, tmp_path):
    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "mapa.txt"
    item.write_text("novo")
    for numero in range(1, 101):
        nome = "mapa.txt" if numero == 1 else f"mapa-{numero}.txt"
        (workspace / "Acervo" / nome).write_text("ocupado")

    resultado = executar_cli(
        "despacho", item.name, "acervo", "--workspace", workspace, "--json"
    )
    assert resultado.returncode == 1
    assert item.read_text() == "novo"
    assert "100" in " ".join(json_de(resultado)["problemas"])


def test_acervo_que_resolve_fora_do_workspace_recusa_sem_traceback(
    executar_cli, tmp_path, monkeypatch
):
    from pathlib import Path

    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "privado.txt"
    item.write_text("não sair")
    acervo = workspace / "Acervo"
    externo = tmp_path / "externo"
    externo.mkdir()
    resolver_real = Path.resolve

    def resolver_fora(caminho, *args, **kwargs):
        if caminho == acervo:
            return externo
        return resolver_real(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolver_fora)
    resultado = executar_cli(
        "despacho", item.name, "acervo", "--workspace", workspace, "--json"
    )

    dados = json_de(resultado)
    assert resultado.returncode == 1
    assert dados["status"] == "recusado"
    assert any("fora do workspace" in problema for problema in dados["problemas"])
    assert item.read_text() == "não sair"


def test_symlink_e_posicional_fora_dos_destinos_sao_recusados(executar_cli, tmp_path):
    workspace = setup(executar_cli, tmp_path)
    real = workspace / "real.txt"
    real.write_text("conteúdo")
    atalho = workspace / "Inbox" / "atalho.txt"
    atalho.symlink_to(real)

    recusado = executar_cli(
        "despacho", atalho.name, "acervo", "--workspace", workspace, "--json"
    )
    assert recusado.returncode == 1
    assert "atalho" in json_de(recusado)["mensagem"]

    item = workspace / "Inbox" / "normal.txt"
    item.write_text("normal")
    invalido = executar_cli(
        "despacho", item.name, "pauta", "sobra", "--workspace", workspace, "--json"
    )
    assert invalido.returncode == 1
    assert "referência só acompanha" in json_de(invalido)["mensagem"]


def test_projetos_quebrado_nao_bloqueia_despacho(executar_cli, tmp_path):
    workspace = setup(executar_cli, tmp_path)
    (workspace / "Projetos.md").write_bytes(b"\xff")
    item = workspace / "Inbox" / "livre.md"
    item.write_text("livre")

    resultado = executar_cli(
        "despacho", item.name, "pauta", "--workspace", workspace, "--json"
    )
    assert resultado.returncode == 0


def test_unlink_falho_compensa_somente_se_a_ficha_ainda_for_do_gesto(
    executar_cli, tmp_path, monkeypatch
):
    from pathlib import Path

    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "sobra.md"
    item.write_text("versão registrada")
    ficha = workspace / "Assuntos" / "satelite.md"
    anterior = ficha.read_bytes()
    unlink_real = Path.unlink

    def falhar(caminho, *args, **kwargs):
        if caminho == item:
            raise PermissionError("travado")
        return unlink_real(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", falhar)
    resultado = executar_cli(
        "despacho", item.name, "assunto", "satelite",
        "--workspace", workspace, "--json",
    )
    assert resultado.returncode == 1
    assert item.exists()
    assert ficha.read_bytes() == anterior


def test_edicao_concorrente_na_ficha_nao_e_desfeita_quando_unlink_falha(
    executar_cli, tmp_path, monkeypatch
):
    from pathlib import Path

    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "concorrente.md"
    item.write_text("nota do gesto")
    ficha = workspace / "Assuntos" / "satelite.md"
    unlink_real = Path.unlink

    def editar_e_falhar(caminho, *args, **kwargs):
        if caminho == item:
            ficha.write_text(ficha.read_text() + "edição concorrente\n")
            raise PermissionError("travado")
        return unlink_real(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", editar_e_falhar)
    resultado = executar_cli(
        "despacho", item.name, "assunto", "satelite",
        "--workspace", workspace, "--json",
    )
    dados = json_de(resultado)
    assert resultado.returncode == 1
    assert "edição concorrente" in ficha.read_text()
    assert "nota ficou na ficha" in dados["mensagem"]


def test_falha_da_relacao_depois_do_move_entrega_nota_reproduzivel(
    executar_cli, tmp_path, monkeypatch
):
    import neoprumo.assunto_despacho as modulo

    workspace = setup(executar_cli, tmp_path)
    item = workspace / "Inbox" / "mapa.txt"
    item.write_text("Cabeça exata\ncorpo")
    monkeypatch.setattr(
        modulo, "reconferir_e_gravar", lambda *args: "a ficha mudou, tente de novo"
    )

    resultado = executar_cli(
        "despacho", item.name, "acervo", "--assunto", "satelite",
        "--workspace", workspace, "--json",
    )
    dados = json_de(resultado)
    assert resultado.returncode == 0
    assert dados["status"] == "despachado"
    assert dados["problemas"] and dados["acoes"]
    assert dados["nota_perdida"] == {
        "assunto": "satelite",
        "data": dados["nota_perdida"]["data"],
        "origem": "acervo mapa.txt",
        "texto": "Cabeça exata",
    }
    assert not item.exists()
