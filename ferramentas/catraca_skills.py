import argparse
import json
import sys
from pathlib import Path


RAIZ_PADRAO = Path(__file__).resolve().parents[1]


def contar_palavras(raiz):
    contagens = {}
    pasta_skills = raiz / "skills"
    caminhos = list(pasta_skills.glob("*/SKILL.md"))
    caminhos.extend(pasta_skills.glob("*/extensoes/*.md"))
    for caminho in sorted(caminhos):
        conteudo = caminho.read_text(encoding="utf-8")
        if caminho.name == "SKILL.md":
            chave = caminho.parent.name
        else:
            chave = caminho.relative_to(pasta_skills).with_suffix("").as_posix()
        contagens[chave] = len(conteudo.split())
    return contagens


def caminho_do_baseline(raiz):
    return raiz / "ferramentas" / "orcamento-skills.json"


def verificar(raiz):
    atuais = contar_palavras(raiz)
    orcamento = json.loads(
        caminho_do_baseline(raiz).read_text(encoding="utf-8")
    )["skills"]
    problemas = []

    for nome in sorted(atuais.keys() - orcamento.keys()):
        problemas.append(f"A skill {nome} está sem entrada no orçamento congelado.")
    for nome in sorted(orcamento.keys() - atuais.keys()):
        problemas.append(f"A entrada {nome} está sem skill correspondente.")
    for nome in sorted(atuais.keys() & orcamento.keys()):
        atual = atuais[nome]
        teto = orcamento[nome]
        if atual > teto:
            problemas.append(
                f"A skill {nome} ultrapassou o teto: {atual} palavras, limite {teto}."
            )
        elif atual < teto:
            problemas.append(
                f"A skill {nome} melhorou para {atual} palavras; rode congelar "
                f"para baixar o teto atual de {teto}."
            )

    if problemas:
        print("\n".join(problemas), file=sys.stderr)
        return 1
    print("As skills estão exatamente nos orçamentos congelados.")
    return 0


def congelar(raiz):
    dados = {"skills": contar_palavras(raiz)}
    caminho_do_baseline(raiz).write_text(
        json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Orçamento das skills congelado no estado atual.")
    return 0


def main(argumentos=None):
    analisador = argparse.ArgumentParser(description="Catraca de palavras das skills")
    analisador.add_argument("comando", choices=("verificar", "congelar"))
    analisador.add_argument("--raiz", type=Path, default=RAIZ_PADRAO)
    opcoes = analisador.parse_args(argumentos)
    if opcoes.comando == "verificar":
        return verificar(opcoes.raiz)
    return congelar(opcoes.raiz)


if __name__ == "__main__":
    raise SystemExit(main())
