#!/usr/bin/env python3
"""Recusa publicação de pacote alterado sem avanço de versão."""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone


ARQUIVOS_DO_PACOTE = (
    "nucleo",
    "skills",
    "hooks",
    "bin",
    ".claude-plugin",
    "ferramentas/__init__.py",
    "ferramentas/catraca_skills.py",
    "ferramentas/catraca_versao.py",
    "ferramentas/orcamento-skills.json",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    ".github/workflows/ci.yml",
)
ARQUIVO_CONTROLE = "ferramentas/" + "espelho" + ".sh"
ARQUIVO_VERSAO = "nucleo/neoprumo/__init__.py"
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


class Violacao(Exception):
    pass

class FalhaOperacional(Exception):
    pass

def _git(*argumentos, aceitar_falha=False):
    try:
        resultado = subprocess.run(
            ["git", *argumentos], capture_output=True, text=True
        )
    except (FileNotFoundError, OSError) as erro:
        raise FalhaOperacional(
            "Git não está disponível para a conferência."
        ) from erro
    if resultado.returncode and not aceitar_falha:
        detalhe = resultado.stderr.strip() or resultado.stdout.strip()
        raise FalhaOperacional(
            f"Git não conseguiu executar {' '.join(argumentos)}: {detalhe}"
        )
    return resultado

def _resolver(referencia):
    resultado = _git(
        "rev-parse", "--verify", f"{referencia}^{{commit}}", aceitar_falha=True
    )
    if resultado.returncode:
        raise FalhaOperacional(f"A referência {referencia} não está disponível.")
    return resultado.stdout.strip()


def _mostrar(commit, caminho, ausente_permitido=False):
    if ausente_permitido:
        listagem = _git("ls-tree", "-r", "--name-only", commit, "--", caminho)
        if caminho not in listagem.stdout.splitlines():
            return None
    return _git("show", f"{commit}:{caminho}").stdout


def _extrair_atributo(texto, nome, obrigatorio=True):
    padrao = rf'^\s*{re.escape(nome)}\s*=\s*["\']([^"\']+)["\']\s*$'
    achados = re.findall(padrao, texto, flags=re.MULTILINE)
    if len(achados) == 1:
        return achados[0]
    if not achados and not obrigatorio:
        return None
    raise FalhaOperacional(f"{nome} está ausente ou ambíguo no pacote.")


def _tupla_versao(valor):
    if not SEMVER.fullmatch(valor):
        raise Violacao(f"A versão {valor!r} não segue o formato X.Y.Z estrito.")
    return tuple(int(parte) for parte in valor.split("."))


def _data(valor, nome):
    if valor is None:
        return None
    try:
        lida = date.fromisoformat(valor)
    except (TypeError, ValueError) as erro:
        raise FalhaOperacional(f"A {nome} está ilegível: {valor!r}.") from erro
    if lida.isoformat() != valor:
        raise FalhaOperacional(f"A {nome} não está no formato AAAA-MM-DD.")
    return lida


def _metadados(commit, base=False):
    inicial = _mostrar(commit, ARQUIVO_VERSAO)
    versao = _extrair_atributo(inicial, "__version__")
    data_versao = _extrair_atributo(
        inicial, "__data_versao__", obrigatorio=not base
    )
    plugin = json.loads(_mostrar(commit, ".claude-plugin/plugin.json"))
    mercado = json.loads(_mostrar(commit, ".claude-plugin/marketplace.json"))
    projeto = _mostrar(commit, "pyproject.toml")
    secao_projeto = re.search(
        r"^\[project\]\s*$([\s\S]*?)(?=^\[|\Z)", projeto, flags=re.MULTILINE
    )
    if secao_projeto is None:
        raise FalhaOperacional("A seção project está ausente no pyproject.toml.")
    entrada_mercado = mercado["plugins"][0]
    versao_projeto = _extrair_atributo(
        secao_projeto.group(1), "version", obrigatorio=not base
    )
    declaradas = (
        versao,
        plugin.get("version") if base else plugin["version"],
        entrada_mercado.get("version") if base else entrada_mercado["version"],
        versao_projeto,
    )
    declaradas = tuple(valor for valor in declaradas if valor is not None)
    if len(set(declaradas)) != 1:
        raise Violacao("Os quatro lugares do pacote declaram versões diferentes.")
    return versao, _tupla_versao(versao), _data(data_versao, "data da versão")


def _lista_publicada(commit):
    texto = _mostrar(commit, ARQUIVO_CONTROLE, ausente_permitido=True)
    if texto is None:
        raise FalhaOperacional("O arquivo de controle da publicação está ausente.")
    linhas = texto.splitlines()
    try:
        inicio = linhas.index("ALLOWLIST=(") + 1
        fim = linhas.index(")", inicio)
    except ValueError as erro:
        raise FalhaOperacional(
            "A composição do pacote não pôde ser lida."
        ) from erro
    return tuple(linha.strip() for linha in linhas[inicio:fim])


def _pertence(caminho, membros):
    return any(caminho == item or caminho.startswith(item + "/") for item in membros)


def _sujeira(membros):
    controle = _git("status", "--porcelain", "--", ARQUIVO_CONTROLE).stdout
    if controle:
        raise FalhaOperacional("O arquivo de controle da publicação está sujo.")
    resultado = _git("status", "--porcelain", "--untracked-files=all", "--", *membros)
    linhas = resultado.stdout.splitlines()
    caminhos = [linha[3:].split(" -> ")[-1] for linha in linhas]
    if caminhos:
        raise FalhaOperacional(
            "Há arquivos sujos no pacote: " + ", ".join(sorted(caminhos))
        )


def _mudancas(base, cabeca, membros):
    saida = _git("diff", "--name-only", base, cabeca).stdout
    caminhos = set(saida.splitlines())
    pacote = any(_pertence(caminho, membros) for caminho in caminhos)
    controle = ARQUIVO_CONTROLE in caminhos
    return pacote, controle


def _versao_no_commit(commit):
    texto = _mostrar(commit, ARQUIVO_VERSAO, ausente_permitido=True)
    if texto is None:
        return None
    return _extrair_atributo(texto, "__version__")


def _e_ancestral(antigo, novo):
    resultado = _git(
        "merge-base", "--is-ancestor", antigo, novo, aceitar_falha=True
    )
    if resultado.returncode not in (0, 1):
        raise FalhaOperacional(
            "O Git não conseguiu comparar dois pontos do histórico."
        )
    return resultado.returncode == 0


def _commit_que_introduziu(versao, cabeca):
    commits = _git(
        "rev-list", "--full-history", cabeca, "--", ARQUIVO_VERSAO
    ).stdout.splitlines()
    candidatos = []
    for commit in commits:
        if _versao_no_commit(commit) != versao:
            continue
        familia = _git("rev-list", "--parents", "-n", "1", commit).stdout.split()
        anteriores = [_versao_no_commit(pai) for pai in familia[1:]]
        if not anteriores or all(anterior != versao for anterior in anteriores):
            candidatos.append(commit)
    if not candidatos:
        raise FalhaOperacional(
            "O histórico não mostra quando a versão atual foi introduzida."
        )
    mais_recentes = []
    for candidato in candidatos:
        if not any(
            candidato != outro
            and _e_ancestral(candidato, outro)
            for outro in candidatos
        ):
            mais_recentes.append(candidato)
    if len(mais_recentes) != 1:
        raise FalhaOperacional(
            "O histórico é ambíguo sobre a introdução da versão atual."
        )
    return mais_recentes[0]


def _conferir_ancora(versao, data_versao, cabeca):
    if data_versao > datetime.now(timezone.utc).date():
        raise FalhaOperacional("A data da versão é futura.")
    commit = _commit_que_introduziu(versao, cabeca)
    instante = _git("log", "-1", "--format=%cI", commit).stdout.strip()
    try:
        iso_compativel = instante[:-1] + "+00:00" if instante.endswith("Z") else instante
        data_commit = (
            datetime.fromisoformat(iso_compativel).astimezone(timezone.utc).date()
        )
    except (TypeError, ValueError) as erro:
        raise FalhaOperacional(
            "O timestamp do commit da versão está ilegível."
        ) from erro
    if abs((data_versao - data_commit).days) > 1:
        raise FalhaOperacional(
            "A data da versão não está ancorada ao commit que a introduziu."
        )


def verificar(primeiro_pai=False):
    cabeca = _resolver("HEAD")
    if primeiro_pai:
        base = _resolver("HEAD^1")
        piso = base
    else:
        piso = _resolver("origin/main")
        base = _git("merge-base", cabeca, piso).stdout.strip()
        if not base:
            raise FalhaOperacional("HEAD e origin/main não têm base comum.")

    lista_base = _lista_publicada(base)
    lista_cabeca = _lista_publicada(cabeca)
    membros = tuple(dict.fromkeys((*ARQUIVOS_DO_PACOTE, *lista_cabeca)))
    _sujeira(membros)
    versao, atual, data_atual = _metadados(cabeca)
    versao_base, anterior, data_base = _metadados(piso, base=True)
    mudou_pacote, mudou_controle = _mudancas(base, cabeca, membros)
    mudou_composicao = lista_base != lista_cabeca
    if mudou_pacote or mudou_controle or mudou_composicao:
        if atual <= anterior:
            causas = []
            if mudou_composicao:
                causas.append("a composição do pacote mudou")
            if mudou_controle:
                causas.append("o arquivo de controle mudou")
            if mudou_pacote:
                causas.append("o pacote mudou")
            detalhe = "; ".join(causas)
            raise Violacao(
                f"A versão não subiu acima do piso {versao_base}: {detalhe}."
            )
    if data_base is None and atual <= anterior:
        raise Violacao("A estreia da data exige uma versão estritamente maior.")
    if data_base is not None and atual > anterior and data_atual < data_base:
        raise Violacao("A data da versão é anterior à data da versão-base.")
    _conferir_ancora(versao, data_atual, cabeca)
    return cabeca


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="Confere o avanço da versão do pacote.")
    parser.add_argument("--primeiro-pai", action="store_true")
    opcoes = parser.parse_args(argumentos)
    try:
        cabeca = verificar(primeiro_pai=opcoes.primeiro_pai)
    except Violacao as erro:
        print(f"RECUSADO: {erro}", file=sys.stderr)
        return 1
    except (FalhaOperacional, KeyError, IndexError, json.JSONDecodeError) as erro:
        print(f"FALHA: {erro}", file=sys.stderr)
        return 2
    except Exception:
        print("FALHA: não foi possível concluir a conferência da versão.", file=sys.stderr)
        return 2
    print(f"Versão conforme no SHA {cabeca}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
