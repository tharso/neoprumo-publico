import json
from types import SimpleNamespace

import pytest

from ferramentas.catraca_skills import main


def preparar_raiz(tmp_path, conteudos, orcamento):
    raiz = tmp_path / "projeto"
    for nome, conteudo in conteudos.items():
        partes = nome.split("/")
        if len(partes) == 1:
            caminho = raiz / "skills" / nome / "SKILL.md"
        else:
            caminho = raiz / "skills" / partes[0] / "extensoes" / f"{partes[-1]}.md"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
    ferramentas = raiz / "ferramentas"
    ferramentas.mkdir(parents=True, exist_ok=True)
    (ferramentas / "orcamento-skills.json").write_text(
        json.dumps({"skills": orcamento}), encoding="utf-8"
    )
    return raiz


def executar_catraca(raiz, comando, capsys):
    codigo = main([comando, "--raiz", str(raiz)])
    captura = capsys.readouterr()
    return SimpleNamespace(
        returncode=codigo,
        stdout=captura.out,
        stderr=captura.err,
    )


def test_verificar_aceita_contagem_exata(tmp_path, capsys):
    raiz = preparar_raiz(tmp_path, {"sonda": "uma duas três"}, {"sonda": 3})

    resultado = executar_catraca(raiz, "verificar", capsys)

    assert resultado.returncode == 0
    assert "exatamente" in resultado.stdout


def test_verificar_rejeita_estouro(tmp_path, capsys):
    raiz = preparar_raiz(tmp_path, {"sonda": "uma duas três quatro"}, {"sonda": 3})

    resultado = executar_catraca(raiz, "verificar", capsys)

    assert resultado.returncode == 1
    assert "ultrapassou" in resultado.stderr


def test_verificar_rejeita_melhora_ate_congelar_novo_teto(tmp_path, capsys):
    raiz = preparar_raiz(tmp_path, {"sonda": "uma duas"}, {"sonda": 3})

    resultado = executar_catraca(raiz, "verificar", capsys)

    assert resultado.returncode == 1
    assert "melhorou" in resultado.stderr
    assert "congelar" in resultado.stderr


def test_verificar_rejeita_skill_nova(tmp_path, capsys):
    raiz = preparar_raiz(tmp_path, {"sonda": "uma"}, {})

    resultado = executar_catraca(raiz, "verificar", capsys)

    assert resultado.returncode == 1
    assert "sem entrada" in resultado.stderr


def test_verificar_rejeita_entrada_orfa(tmp_path, capsys):
    raiz = preparar_raiz(tmp_path, {}, {"fantasma": 4})

    resultado = executar_catraca(raiz, "verificar", capsys)

    assert resultado.returncode == 1
    assert "sem skill" in resultado.stderr


def test_congelar_regrava_baseline_ordenado(tmp_path, capsys):
    raiz = preparar_raiz(
        tmp_path,
        {"zeta": "uma duas", "alfa": "uma duas três"},
        {"antiga": 99},
    )

    resultado = executar_catraca(raiz, "congelar", capsys)

    assert resultado.returncode == 0
    arquivo_orcamento = raiz / "ferramentas" / "orcamento-skills.json"
    assert arquivo_orcamento.read_text(encoding="utf-8") == (
        '{\n  "skills": {\n    "alfa": 3,\n    "zeta": 2\n  }\n}\n'
    )


@pytest.mark.parametrize("tipo", ["skill", "extensao"])
@pytest.mark.parametrize(
    ("comportamento", "conteudo", "orcamento", "comando", "codigo", "trecho"),
    [
        ("nova", "uma", {}, "verificar", 1, "sem entrada"),
        ("orfa", None, {"CHAVE": 1}, "verificar", 1, "sem skill"),
        ("estouro", "uma duas", {"CHAVE": 1}, "verificar", 1, "ultrapassou"),
        ("reducao", "uma", {"CHAVE": 2}, "verificar", 1, "melhorou"),
        ("congelar", "uma duas", {}, "congelar", 0, "congelado"),
    ],
)
def test_catraca_aplica_cinco_comportamentos_a_skills_e_extensoes(
    tipo, comportamento, conteudo, orcamento, comando, codigo, trecho, tmp_path, capsys
):
    chave = "sessao" if tipo == "skill" else "sessao/extensoes/pilha-grande"
    conteudos = {} if conteudo is None else {chave: conteudo}
    baseline = {chave if nome == "CHAVE" else nome: teto for nome, teto in orcamento.items()}
    raiz = preparar_raiz(tmp_path, conteudos, baseline)

    resultado = executar_catraca(raiz, comando, capsys)

    assert resultado.returncode == codigo
    assert trecho in (resultado.stdout + resultado.stderr)
    if comportamento == "congelar":
        dados = json.loads((raiz / "ferramentas" / "orcamento-skills.json").read_text())
        assert dados["skills"] == {chave: 2}
