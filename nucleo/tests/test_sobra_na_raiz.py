"""Sobra na raiz do workspace (#79).

A inbox é a porta de entrada única (glossário do projeto). Skill de fora do Prumo
escreve onde o host está aberto e não conhece o workspace: o arquivo cai
na raiz, pula captura e despacho, e o sistema nunca sabe que ele existe.
O doctor passa a enxergar essa sobra — e, sob --reparar, a recolhe.

Decisão 2026-09-01 - Porta única de verdade.
"""

import json
from pathlib import Path


def _workspace(tmp_path, executar_cli, nome="casa"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def test_arquivo_solto_na_raiz_vira_problema_do_doctor(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "transcricao.md").write_text("conteúdo do dono", encoding="utf-8")

    resultado = executar_cli("doctor", workspace)

    assert resultado.returncode != 0
    assert "transcricao.md está solto na raiz (pode ir pra Inbox)." in resultado.stderr


def test_seed_espelha_a_sobra_do_doctor(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "transcricao.md").write_text("conteúdo do dono", encoding="utf-8")

    resultado = executar_cli("seed", "--workspace", workspace, "--json")

    resumo = json.loads(resultado.stdout)
    assert resumo["estrutura"]["status"] == "com_problemas"
    assert resumo["estrutura"]["problemas"] == [
        "transcricao.md está solto na raiz (pode ir pra Inbox)."
    ]


def test_reparo_recolhe_arquivo_solto_preservando_nome_e_conteudo(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "transcricao.md").write_text("conteúdo do dono", encoding="utf-8")

    reparo = executar_cli("doctor", workspace, "--reparar")

    assert reparo.returncode == 0
    assert "- transcricao.md recolhido pra Inbox." in reparo.stdout
    assert not (workspace / "transcricao.md").exists()
    recolhido = workspace / "Inbox" / "transcricao.md"
    assert recolhido.read_text(encoding="utf-8") == "conteúdo do dono"


def test_recolhimento_sufixa_colisao_na_inbox(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "Inbox" / "nota.md").write_text("item que já estava", encoding="utf-8")
    (workspace / "nota.md").write_text("o que caiu na raiz", encoding="utf-8")

    reparo = executar_cli("doctor", workspace, "--reparar")

    assert reparo.returncode == 0
    assert (workspace / "Inbox" / "nota.md").read_text(
        encoding="utf-8"
    ) == "item que já estava"
    assert (workspace / "Inbox" / "nota-2.md").read_text(
        encoding="utf-8"
    ) == "o que caiu na raiz"


def test_falha_ao_recolher_substitui_o_aviso_da_sobra(
    tmp_path, executar_cli, monkeypatch
):
    workspace = _workspace(tmp_path, executar_cli)
    solto = workspace / "transcricao.md"
    solto.write_text("conteúdo do dono", encoding="utf-8")
    renomear_real = Path.rename

    def falhar_ao_recolher(caminho, destino):
        if caminho == solto:
            raise OSError("disco indisponível")
        return renomear_real(caminho, destino)

    monkeypatch.setattr(Path, "rename", falhar_ao_recolher)

    reparo = executar_cli("doctor", workspace, "--reparar")

    assert reparo.returncode != 0
    assert reparo.stderr.count("transcricao.md") == 1
    assert "Não foi possível recolher transcricao.md pra Inbox" in reparo.stderr
    assert "pode ir pra Inbox" not in reparo.stderr
    assert solto.read_text(encoding="utf-8") == "conteúdo do dono"


def test_pasta_solta_e_reportada_mas_nunca_movida(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    solta = workspace / "Rascunhos"
    solta.mkdir()
    (solta / "dentro.md").write_text("organização do dono", encoding="utf-8")

    diagnostico = executar_cli("doctor", workspace)
    assert diagnostico.returncode != 0
    assert "Rascunhos/ está solta na raiz." in diagnostico.stderr

    reparo = executar_cli("doctor", workspace, "--reparar")
    assert reparo.returncode != 0
    assert (solta / "dentro.md").read_text(encoding="utf-8") == "organização do dono"
    assert not (workspace / "Inbox" / "Rascunhos").exists()


def test_allowlist_da_raiz_fica_silenciosa(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "Configuracao.ini").write_text("[configuracao]\n", encoding="utf-8")
    (workspace / "Projetos.md").write_text("# Projetos\n", encoding="utf-8")
    (workspace / ".DS_Store").write_bytes(b"\x00")
    (workspace / ".claude").mkdir()

    resultado = executar_cli("doctor", workspace)

    assert resultado.returncode == 0
    assert "Tudo certo" in resultado.stdout


def test_symlinks_na_raiz_sao_ignorados(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    pasta_externa = tmp_path / "pasta-externa"
    pasta_externa.mkdir()
    link_pasta = workspace / "AtalhoPasta"
    link_quebrado = workspace / "AtalhoQuebrado"
    link_pasta.symlink_to(pasta_externa, target_is_directory=True)
    link_quebrado.symlink_to(tmp_path / "destino-inexistente")

    diagnostico = executar_cli("doctor", workspace)
    reparo = executar_cli("doctor", workspace, "--reparar")

    assert diagnostico.returncode == 0
    assert reparo.returncode == 0
    assert link_pasta.is_symlink()
    assert link_quebrado.is_symlink()
    assert not (workspace / "Inbox" / link_pasta.name).exists()
    assert not (workspace / "Inbox" / link_quebrado.name).exists()


def test_reparo_cria_falta_e_recolhe_sobra_na_mesma_passada(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "Acervo").rmdir()
    (workspace / "transcricao.md").write_text("conteúdo do dono", encoding="utf-8")

    reparo = executar_cli("doctor", workspace, "--reparar")

    assert reparo.returncode == 0
    assert "- Acervo recriado." in reparo.stdout
    assert "- transcricao.md recolhido pra Inbox." in reparo.stdout
    assert (workspace / "Acervo").is_dir()
    assert (workspace / "Inbox" / "transcricao.md").exists()


def test_reparo_recria_inbox_antes_de_recolher_sobra(tmp_path, executar_cli):
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "Inbox").rmdir()
    (workspace / "transcricao.md").write_text("conteúdo do dono", encoding="utf-8")

    reparo = executar_cli("doctor", workspace, "--reparar")

    assert reparo.returncode == 0
    assert "- Inbox recriado." in reparo.stdout
    assert "- transcricao.md recolhido pra Inbox." in reparo.stdout
    assert (workspace / "Inbox").is_dir()
    assert (workspace / "Inbox" / "transcricao.md").read_text(
        encoding="utf-8"
    ) == "conteúdo do dono"


def test_sobra_nao_pesa_na_readocao(tmp_path, executar_cli):
    """Adotar workspace com arquivo solto na raiz segue legítimo."""
    workspace = _workspace(tmp_path, executar_cli, nome="adotada")
    (workspace / "transcricao.md").write_text("conteúdo do dono", encoding="utf-8")

    resultado = executar_cli("setup", workspace, "--readotar")

    assert resultado.returncode == 0
    assert (workspace / "transcricao.md").exists()


def test_sobra_dentro_das_pastas_canonicas_e_ignorada(tmp_path, executar_cli):
    """O escopo é a raiz: dentro do Acervo o dono organiza como quiser."""
    workspace = _workspace(tmp_path, executar_cli)
    (workspace / "Acervo" / "qualquer-nome.txt").write_text("nota", encoding="utf-8")
    (workspace / "Assuntos" / "subpasta").mkdir()

    resultado = executar_cli("doctor", workspace)

    assert resultado.returncode == 0
    assert "Tudo certo" in resultado.stdout
