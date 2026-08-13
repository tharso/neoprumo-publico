import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


AGORA = datetime(
    2026, 8, 12, 15, 4, 5, tzinfo=timezone(timedelta(hours=-3))
)


def _workspace(tmp_path, executar_cli, nome="pauta-lixo"):
    workspace = tmp_path / nome
    assert executar_cli("setup", workspace).returncode == 0
    return workspace


def test_issue_52_pauta_lixo_move_bloco_e_preserva_resto_byte_a_byte(
    tmp_path, executar_cli
):
    from neoprumo.comando_pauta import operar_pauta_lixo

    workspace = _workspace(tmp_path, executar_cli)
    pauta = workspace / "Pauta.md"
    bloco = (
        b"- [ ] Caf\xc3\xa9 antigo [em espera]\r\n"
        b"  detalhe\r\n"
        b"  \xe2\x80\x94 inbox abc, despachado em 2026-08-01\r\n"
    )
    antes = b"# Pauta\r\ntexto solto\r\n" + bloco + b"\r\n  orfa\r\n- [ ] Outra\r\n"
    pauta.write_bytes(antes)

    codigo, resultado = operar_pauta_lixo(
        "cafe antigo", caminho=workspace, instante=AGORA
    )

    assert codigo == 0 and resultado["status"] == "excluido"
    arquivo = Path(resultado["item"])
    assert arquivo.read_bytes() == bloco
    assert pauta.read_bytes() == antes.replace(bloco, b"")
    assert resultado["manchete"] == "Café antigo"
    assert resultado["origem_entrada"] == "inbox abc"
    assert resultado["candidatas"] == []


def test_issue_52_pauta_lixo_colisao_e_ambiguidades(tmp_path, executar_cli):
    from neoprumo.comando_pauta import operar_pauta_lixo

    workspace = _workspace(tmp_path, executar_cli, "colisao")
    pauta = workspace / "Pauta.md"
    pauta.write_text(
        "- [ ] Repetida\n  — inbox um, despachado em 2026-08-01\n"
        "- [ ] Repetida\n  — acervo dois, incluído em 2026-08-01\n",
        encoding="utf-8",
    )

    codigo, ambiguo = operar_pauta_lixo("repetida", caminho=workspace, instante=AGORA)
    assert codigo == 1 and len(ambiguo["candidatas"]) == 2

    lixo = workspace / ".neoprumo" / "lixo"
    lixo.mkdir(parents=True)
    radical = f"pauta-{AGORA.astimezone().strftime('%Y-%m-%d-%H%M%S')}"
    primeiro = lixo / f"{radical}.md"
    primeiro.write_bytes(b"alheio")
    codigo, sucesso = operar_pauta_lixo(
        "repetida", origem="acervo dois", caminho=workspace, instante=AGORA
    )
    assert codigo == 0
    assert primeiro.read_bytes() == b"alheio"
    assert sucesso["item"].endswith(f"{radical}-2.md")


def test_issue_52_pauta_lixo_recusa_concluida_e_cli_tem_envelope_fechado(
    tmp_path, executar_cli
):
    workspace = _workspace(tmp_path, executar_cli, "cli")
    (workspace / "Pauta.md").write_text("- [x] Já foi\n", encoding="utf-8")

    saida = executar_cli(
        "pauta", "ja foi", "lixo", "--workspace", workspace, "--json"
    )
    dados = json.loads(saida.stdout)

    assert saida.returncode == 1
    assert dados["mensagem"] == (
        "Essa entrada está concluída; ela fica como histórico da pauta e não vai pro lixo."
    )
    assert set(dados) == {
        "status", "problemas", "acoes", "mensagem", "workspace", "item",
        "id", "destino", "manchete", "origem_entrada", "candidatas",
    }


def test_issue_52_pauta_lixo_detecta_mudanca_e_preserva_sobra(
    tmp_path, executar_cli
):
    from neoprumo.comando_pauta import operar_pauta_lixo

    workspace = _workspace(tmp_path, executar_cli, "mudanca")
    pauta = workspace / "Pauta.md"
    original = b"- [ ] Sensivel\n  detalhe\n"
    pauta.write_bytes(original)

    def mudar():
        pauta.write_bytes(original + b"texto novo\n")

    codigo, resultado = operar_pauta_lixo(
        "sensivel", caminho=workspace, instante=AGORA,
        antes_de_reconferir=mudar,
    )

    assert codigo == 1 and "tente de novo" in resultado["mensagem"]
    assert pauta.read_bytes() == original + b"texto novo\n"
    assert Path(resultado["item"]).read_bytes() == original


def test_issue_52_pauta_lixo_falha_de_reescrita_mantem_pauta_e_sobra(
    tmp_path, executar_cli
):
    from neoprumo.comando_pauta import operar_pauta_lixo

    workspace = _workspace(tmp_path, executar_cli, "falha-reescrita")
    pauta = workspace / "Pauta.md"
    original = b"- [ ] Fica\n"
    pauta.write_bytes(original)

    def falhar(caminho, conteudo):
        raise PermissionError("sem permissão")

    codigo, resultado = operar_pauta_lixo(
        "fica", caminho=workspace, instante=AGORA, gravador=falhar
    )

    assert codigo == 1 and pauta.read_bytes() == original
    assert Path(resultado["item"]).read_bytes() == original


def test_issue_52_pauta_lixo_recusa_atalho_sem_tocar_na_pauta(
    tmp_path, executar_cli
):
    from neoprumo.comando_pauta import operar_pauta_lixo

    workspace = _workspace(tmp_path, executar_cli, "atalho")
    pauta = workspace / "Pauta.md"
    original = b"- [ ] Protegida\n"
    pauta.write_bytes(original)
    externo = tmp_path / "externo"
    externo.mkdir()
    (workspace / ".neoprumo" / "lixo").symlink_to(
        externo, target_is_directory=True
    )

    codigo, resultado = operar_pauta_lixo(
        "protegida", caminho=workspace, instante=AGORA
    )

    assert codigo == 1 and pauta.read_bytes() == original
    assert list(externo.iterdir()) == []
    assert resultado["item"] is None


def test_issue_52_falha_no_meio_da_copia_deixa_sobra_nomeada(
    tmp_path, executar_cli, monkeypatch
):
    from neoprumo import comando_pauta as modulo

    workspace = _workspace(tmp_path, executar_cli, "copia-parcial")
    pauta = workspace / "Pauta.md"
    original = b"- [ ] Inteira\n  detalhe\n"
    pauta.write_bytes(original)
    abrir_real = open

    class CopiaParcial:
        def __init__(self, caminho, modo):
            self.arquivo = abrir_real(caminho, modo)

        def __enter__(self):
            return self

        def __exit__(self, tipo, valor, traceback):
            self.arquivo.close()

        def write(self, dados):
            self.arquivo.write(dados[:8])
            self.arquivo.flush()
            raise OSError("interrompida")

        def flush(self):
            self.arquivo.flush()

    monkeypatch.setattr(modulo, "open", CopiaParcial, raising=False)

    codigo, resultado = modulo.operar_pauta_lixo(
        "inteira", caminho=workspace, instante=AGORA
    )

    sobra = Path(resultado["item"])
    assert codigo == 1 and pauta.read_bytes() == original
    assert sobra.read_bytes() == original[:8]
    assert sobra.name in resultado["mensagem"]
