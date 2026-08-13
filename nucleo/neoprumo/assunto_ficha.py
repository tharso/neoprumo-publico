import re
import stat
from pathlib import Path

from .assunto_base import data_valida, digital, normalizar, tem_controle


NOTA = re.compile(
    r"^- (\d{4}-\d{2}-\d{2})(?: \((inbox|acervo) ([^)]+)\))?: (.*?)(?:\r?\n)?$"
)


def _valor(caminho, chave, bruto, problemas):
    valor = bruto.strip()
    if not valor or tem_controle(valor):
        problemas.append(f"{caminho.name}: {chave} tem valor inválido e foi ignorado.")
        return None
    return valor


def _apelidos(caminho, valor, problemas):
    vistos, saida = set(), []
    for parte in valor.split(","):
        apelido = parte.strip()
        if not apelido:
            problemas.append(f"{caminho.name}: Apelidos contém uma entrada vazia.")
            continue
        chave = normalizar(apelido)
        if chave in vistos:
            problemas.append(f"{caminho.name}: Apelidos contém uma repetição.")
            continue
        vistos.add(chave)
        saida.append(apelido)
    return saida


def _notas(caminho, linhas, inicio, fim, problemas):
    notas, fora, indice = [], 0, inicio + 1
    while indice < fim:
        linha = linhas[indice]
        casamento = NOTA.match(linha)
        if not casamento or not data_valida(casamento.group(1)):
            fora += 1
            indice += 1
            continue
        data, tipo, nome, cabeca = casamento.groups()
        if tipo and (not nome or tem_controle(nome) or ")" in nome):
            fora += 1
            indice += 1
            continue
        corpo = []
        indice += 1
        while indice < fim and linhas[indice].startswith("  "):
            corpo.append(linhas[indice][2:].rstrip("\r\n"))
            indice += 1
        texto = "\n".join([cabeca] + corpo)
        notas.append({
            "data": data,
            "origem": f"{tipo} {nome}" if tipo else None,
            "texto": texto,
        })
    if fora:
        problemas.append(
            f"{caminho.name}: {fora} linhas do Registro fora do formato de nota."
        )
    return notas


def analisar(caminho, dados):
    texto = dados.decode("utf-8")
    linhas = texto.splitlines(keepends=True)
    problemas = []
    nome = None
    if linhas and linhas[0].startswith("# "):
        candidato = linhas[0][2:].strip()
        if candidato and not tem_controle(candidato):
            nome = candidato
    if nome is None:
        problemas.append(f"{caminho.name}: falta um título legível; o ID será exibido.")
        nome = caminho.stem
    campos = {"tipo": None, "estado": "ativo", "apelidos": [], "caminho": None}
    relacionados, ocorrencias, indices = [], set(), {}
    primeira_secao = len(linhas)
    for indice, linha in enumerate(linhas):
        if linha.startswith("## "):
            primeira_secao = indice
            break
    for indice, linha in enumerate(linhas[:primeira_secao]):
        texto_linha = linha.rstrip("\r\n")
        if ": " not in texto_linha:
            continue
        chave, bruto = texto_linha.split(": ", 1)
        if chave == "Caminho relacionado":
            valor = _valor(caminho, chave, bruto, problemas)
            if valor is not None:
                relacionados.append(valor)
            continue
        if chave not in {"Tipo", "Estado", "Apelidos", "Caminho"}:
            continue
        if chave in ocorrencias:
            problemas.append(f"{caminho.name}: o campo {chave} aparece mais de uma vez.")
            continue
        ocorrencias.add(chave)
        indices[chave] = indice
        valor = _valor(caminho, chave, bruto, problemas)
        if valor is None:
            continue
        if chave == "Estado":
            if valor not in ("ativo", "arquivado"):
                problemas.append(f"{caminho.name}: Estado desconhecido ({valor}); tratado como ativo.")
            else:
                campos["estado"] = valor
        elif chave == "Apelidos":
            campos["apelidos"] = _apelidos(caminho, valor, problemas)
        else:
            campos[{"Tipo": "tipo", "Caminho": "caminho"}[chave]] = valor
    registros = [i for i, linha in enumerate(linhas) if linha.rstrip("\r\n") == "## Registro"]
    notas, limite = [], None
    if registros:
        inicio = registros[0]
        limite = next((i for i in range(inicio + 1, len(linhas)) if linhas[i].startswith("## ")), len(linhas))
        notas = _notas(caminho, linhas, inicio, limite, problemas)
    if len(registros) > 1:
        problemas.append(f"{caminho.name}: mais de uma seção Registro; o núcleo usa a primeira.")
    return {
        "id": caminho.stem, "nome": nome, **campos,
        "caminhos_relacionados": relacionados, "notas": notas,
        "problemas": problemas, "texto": texto, "linhas": linhas,
        "indices": indices, "registro": registros[0] if registros else None,
        "limite_registro": limite, "digital": digital(dados),
    }


def ler_ficha(caminho):
    try:
        modo = caminho.lstat().st_mode
        if stat.S_ISLNK(modo) or not stat.S_ISREG(modo):
            return None, f"{caminho.name}: não é uma ficha regular."
        dados = caminho.read_bytes()
        return analisar(caminho, dados), None
    except UnicodeDecodeError:
        return None, f"{caminho.name}: não é texto UTF-8."
    except OSError as erro:
        return None, f"{caminho.name}: ilegível ({erro})."


def formatar_nota(texto, data, origem=None):
    linhas = texto.splitlines()
    indice = next((i for i, linha in enumerate(linhas) if linha.strip()), None)
    if indice is None:
        return None
    cabeca = linhas[indice]
    restantes = linhas[:indice] + linhas[indice + 1:]
    marcador = f" ({origem})" if origem else ""
    return f"- {data}{marcador}: {cabeca}\n" + "".join(
        f"  {linha}\n" for linha in restantes
    )


def inserir_nota(ficha, nota):
    linhas = ficha["linhas"]
    if ficha["registro"] is None:
        separador = "" if not ficha["texto"] or ficha["texto"].endswith("\n\n") else ("\n" if ficha["texto"].endswith("\n") else "\n\n")
        return ficha["texto"] + separador + "## Registro\n" + nota
    posicao = sum(len(linha) for linha in linhas[:ficha["limite_registro"]])
    antes, depois = ficha["texto"][:posicao], ficha["texto"][posicao:]
    separador = "" if antes.endswith("\n") else "\n"
    return antes + separador + nota + depois
