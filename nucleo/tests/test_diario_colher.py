import json
import os
from datetime import datetime

import pytest


DIA = "2026-08-13"
LIMITACOES = [
    "A data em que uma entrada da Pauta foi concluída não é registrada; só o estado de conclusão é visível.",
    "Entrada criada à mão na Pauta, sem rodapé de origem, não tem data comprovável.",
    "Item movido pro Acervo cuja captura é de outro dia não aparece como acontecimento de hoje.",
    "Item mandado pro lixo não deixa carimbo disponível para o diário.",
    "Mudança de regime ou prazo da Pauta não deixa carimbo disponível para o diário.",
    "Assunto registrado, arquivado ou reativado não deixa carimbo disponível para o diário.",
    "Item cujo nome saiu do RG canônico não tem data comprovável pela captura.",
    "A data de uma nota de assunto é declarada pelo dono e não prova quando ela foi realmente escrita.",
]


def chamar(executar_cli, workspace):
    resultado = executar_cli(
        "diario", "colher", "--workspace", workspace, "--json"
    )
    return resultado, json.loads(resultado.stdout or resultado.stderr)


@pytest.fixture
def workspace(executar_cli, tmp_path):
    caminho = tmp_path / "casa"
    assert executar_cli("setup", caminho, "--json").returncode == 0
    return caminho


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    import neoprumo.diario_colheita as modulo

    class Relogio(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 13, 15, 20).astimezone()

    monkeypatch.setattr(modulo, "datetime", Relogio)


def test_colher_vazio_entrega_envelope_completo_sem_escrever(executar_cli, workspace):
    antes = sorted(str(item.relative_to(workspace)) for item in workspace.rglob("*"))

    resultado, envelope = chamar(executar_cli, workspace)

    depois = sorted(str(item.relative_to(workspace)) for item in workspace.rglob("*"))
    assert resultado.returncode == 0
    assert envelope == {
        "status": "fatos", "problemas": [], "acoes": [],
        "mensagem": "Fatos do dia colhidos.", "workspace": str(workspace.resolve()),
        "dia": DIA, "pauta": [], "assuntos": [], "capturas": [],
        "total": 0, "limitacoes": LIMITACOES,
        "diario": {"existe": False, "secoes": 0},
    }
    assert depois == antes


@pytest.mark.parametrize(
    ("rodape", "entra", "tem_problema"),
    [
        ("  — inbox x.md, despachado em 2026-08-13", True, False),
        ("  — acervo x.md, incluído em 2026-08-13", True, False),
        ("  — inbox x.md, despachado em 2026-08-12", False, False),
        ("  texto lançado à mão", False, False),
        ("  — inbox x, qualquer texto 2026-08-13", False, True),
        ("  — inbox x.md, despachado em 2026-02-31", False, True),
        ("  — acervo x.md, despachado em 2026-08-13", False, True),
        ("  — inbox x.md, incluído em 2026-08-13", False, True),
    ],
)
def test_rodape_estrito_separa_valido_ausente_e_malformado(
    executar_cli, workspace, rodape, entra, tem_problema
):
    (workspace / "Pauta.md").write_text(f"- [ ] Manchete\n{rodape}\n")

    _, envelope = chamar(executar_cli, workspace)

    assert bool(envelope["pauta"]) is entra
    assert bool(envelope["problemas"]) is tem_problema


@pytest.mark.parametrize(
    "corpo",
    [
        "  — inbox a.md, despachado em 2026-08-12\n  — inbox b.md, despachado em 2026-08-13",
        "  — inbox a.md, despachado em 2026-08-13\n  — inbox b, errado",
        "  — inbox imitação do dono\n  — acervo b.md, incluído em 2026-08-13",
    ],
)
def test_dois_rodapes_tornam_entrada_malformada(executar_cli, workspace, corpo):
    (workspace / "Pauta.md").write_text(f"- [ ] Dupla\n{corpo}\n")

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["pauta"] == []
    assert any("Dupla" in problema and "rodapé" in problema for problema in envelope["problemas"])


def test_pauta_intercala_concluidas_e_abertas_na_ordem_do_arquivo(executar_cli, workspace):
    (workspace / "Pauta.md").write_text(
        "- [x] Primeiro [à vista]\n  — inbox um.md, despachado em 2026-08-13\n"
        "- [ ] Segundo [vence 2026-08-20]\n  — acervo dois.md, incluído em 2026-08-13\n"
    )

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["pauta"] == [
        {"manchete": "Primeiro", "origem": "inbox um.md", "concluida": True,
         "regime": {"nome": "a_vista", "ate": None}, "vence": None},
        {"manchete": "Segundo", "origem": "acervo dois.md", "concluida": False,
         "regime": None, "vence": "2026-08-20"},
    ]


def test_assuntos_colhem_primeira_linha_e_data_declarada(executar_cli, workspace):
    (workspace / "Assuntos" / "zeta.md").write_text(
        "# Zeta\n\n## Registro\n"
        "- 2026-08-12: escrita hoje mas declarada ontem\n"
        "- 2026-08-13: conversa\n  corpo que não entra\n"
    )
    (workspace / "Assuntos" / "alfa.md").write_text(
        "# Alfa\n\n## Registro\n- 2026-08-13 (acervo mapa.md): declarada hoje\n"
    )

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["assuntos"] == [
        {"assunto": "alfa", "nome": "Alfa", "origem": "acervo mapa.md", "texto": "declarada hoje"},
        {"assunto": "zeta", "nome": "Zeta", "origem": None, "texto": "conversa"},
    ]


def test_capturas_reusam_rg_e_politica_observacional(executar_cli, workspace):
    inbox = workspace / "Inbox"
    acervo = workspace / "Acervo"
    (inbox / "2026-08-13-090000-2.md").write_text("colisão")
    (inbox / "2026-08-13-relatorio.md").write_text("fora")
    (inbox / ".2026-08-13-100000.md").write_text("oculto")
    (inbox / "2026-08-13-110000.md").mkdir()
    os.symlink(inbox / "2026-08-13-090000-2.md", inbox / "2026-08-13-120000.md")
    (acervo / "2026-08-13-130000.txt").write_text("guardado")

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["capturas"] == [
        {"morada": "inbox", "nome": "2026-08-13-090000-2.md"},
        {"morada": "acervo", "nome": "2026-08-13-130000.txt"},
    ]


def test_nome_que_nao_decodifica_em_utf8_e_ignorado(
    executar_cli, workspace, monkeypatch
):
    import neoprumo.diario_colheita as modulo

    original = modulo.os.scandir

    class Entrada:
        name = "2026-08-13-140000-\udcff.md"

        def stat(self, **_):
            raise AssertionError("nome inválido deve ser descartado antes do stat")

    class Lista:
        def __enter__(self):
            return iter([Entrada()])

        def __exit__(self, *_):
            return False

    def observar(pasta):
        return Lista() if pasta.name == "Inbox" else original(pasta)

    monkeypatch.setattr(modulo.os, "scandir", observar)
    _, envelope = chamar(executar_cli, workspace)

    assert envelope["capturas"] == []
    assert envelope["problemas"] == []


def test_assuntos_em_symlink_zeram_so_a_familia(executar_cli, workspace):
    assuntos = workspace / "Assuntos"
    assuntos.rmdir()
    alvo = workspace / "assuntos-fora"
    alvo.mkdir()
    os.symlink(alvo, assuntos)
    (workspace / "Inbox" / "2026-08-13-090000.md").write_text("segue")

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["assuntos"] == []
    assert envelope["capturas"] == [{"morada": "inbox", "nome": "2026-08-13-090000.md"}]
    assert any("Assuntos" in item for item in envelope["problemas"])


def test_item_ja_despachado_aparece_so_na_pauta(executar_cli, workspace):
    (workspace / "Pauta.md").write_text(
        "- [ ] Foi despachado\n  — inbox 2026-08-13-090000.md, despachado em 2026-08-13\n"
    )

    _, envelope = chamar(executar_cli, workspace)

    assert len(envelope["pauta"]) == 1
    assert envelope["capturas"] == []
    assert envelope["total"] == 1


def test_total_conta_captura_e_nota_como_dois_acontecimentos(executar_cli, workspace):
    (workspace / "Acervo" / "2026-08-13-090000.md").write_text("item")
    (workspace / "Assuntos" / "tema.md").write_text(
        "# Tema\n\n## Registro\n- 2026-08-13 (acervo 2026-08-13-090000.md): associado\n"
    )

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["total"] == 2


def test_fontes_degradam_sem_derrubar_as_demais(executar_cli, workspace):
    (workspace / "Pauta.md").write_bytes(b"\xff")
    (workspace / "Assuntos" / "boa.md").write_text(
        "# Boa\n\n## Registro\n- 2026-08-13: segue\n"
    )
    (workspace / "Assuntos" / "ruim.md").write_bytes(b"\xff")
    (workspace / "Inbox").rmdir()
    (workspace / "Acervo" / "2026-08-13-090000.md").write_text("segue")

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["pauta"] == []
    assert [item["assunto"] for item in envelope["assuntos"]] == ["boa"]
    assert envelope["capturas"] == [{"morada": "acervo", "nome": "2026-08-13-090000.md"}]
    assert any("Pauta.md" in item for item in envelope["problemas"])
    assert any("ruim.md" in item for item in envelope["problemas"])
    assert any("Inbox" in item for item in envelope["problemas"])


@pytest.mark.parametrize(
    ("preparo", "trecho"),
    [
        ("symlink", "atalho"), ("diretorio", "diretório"),
        ("utf8", "UTF-8"), ("sem_titulo", "título"), ("outro_dia", "outra data"),
    ],
)
def test_diario_hostil_vira_problema_sem_derrubar_fatos(
    executar_cli, workspace, preparo, trecho
):
    diario = workspace / "Diario" / f"{DIA}.md"
    if preparo == "symlink":
        alvo = workspace / "alvo.md"
        alvo.write_text(f"# {DIA}\n")
        os.symlink(alvo, diario)
    elif preparo == "diretorio":
        diario.mkdir()
    elif preparo == "utf8":
        diario.write_bytes(f"# {DIA}\n".encode() + b"\xff")
    elif preparo == "sem_titulo":
        diario.write_text("prosa\n")
    else:
        diario.write_text("# 2026-08-12\n")
    (workspace / "Inbox" / "2026-08-13-090000.md").write_text("fato")

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["capturas"]
    assert any(trecho in item for item in envelope["problemas"])


def test_secoes_contam_so_cabecalhos_inteiros_validos(executar_cli, workspace):
    (workspace / "Diario" / f"{DIA}.md").write_text(
        f"# {DIA}\n\n## Sessão 09:30\ntexto\n## Sessão inválida\n"
        "## Sessão 9:30\n## Sessão 09:30:00\n## Sessão 24:00\n"
        "prosa do dono\n## Sessão 10:45\n"
    )

    _, envelope = chamar(executar_cli, workspace)

    assert envelope["diario"] == {"existe": True, "secoes": 2}
    assert envelope["problemas"] == []
