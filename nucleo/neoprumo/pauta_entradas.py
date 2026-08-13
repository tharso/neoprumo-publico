import stat

from .regimes import (
    PREFIXO_ABERTO,
    PREFIXOS_CONCLUIDOS,
    analisar_linha,
    normalizar,
    origem_da_linha,
)


def ler_pauta(workspace, mensagens_seed=False):
    pauta = workspace / "Pauta.md"
    try:
        estado = pauta.lstat()
        if mensagens_seed and stat.S_ISLNK(estado.st_mode):
            return None, None, "Pauta.md: é um atalho simbólico e não será seguido."
        if mensagens_seed and not stat.S_ISREG(estado.st_mode):
            return None, None, "Pauta.md: deveria ser um arquivo."
        if not stat.S_ISREG(estado.st_mode):
            raise OSError("Pauta.md não é um arquivo regular")
        dados = pauta.read_bytes()
        texto = dados.decode("utf-8")
    except FileNotFoundError:
        mensagem = "Pauta.md: não existe." if mensagens_seed else "Pauta.md não existe."
        return None, None, mensagem
    except UnicodeDecodeError:
        mensagem = (
            "Pauta.md: o conteúdo não é texto UTF-8."
            if mensagens_seed else "Pauta.md não contém texto UTF-8."
        )
        return None, None, mensagem
    except OSError as erro:
        inicio = "Pauta.md: não pôde" if mensagens_seed else "Pauta.md não pôde"
        return None, None, f"{inicio} ser lida ({erro})."
    return pauta, (dados, texto), None


def entradas(texto, concluida=False):
    linhas = texto.splitlines(keepends=True)
    deslocamentos = []
    posicao = 0
    for linha in linhas:
        deslocamentos.append(posicao)
        posicao += len(linha.encode("utf-8"))
    encontradas = []
    prefixos = PREFIXOS_CONCLUIDOS if concluida else (PREFIXO_ABERTO,)
    for indice, linha_com_fim in enumerate(linhas):
        linha = linha_com_fim.rstrip("\r\n")
        if not linha.startswith(prefixos):
            continue
        leitura = analisar_linha(linha, concluida=concluida)
        corpo = []
        fim_indice = indice + 1
        for seguinte in linhas[indice + 1:]:
            texto_seguinte = seguinte.rstrip("\r\n")
            if not texto_seguinte or not texto_seguinte.startswith((" ", "\t")):
                break
            corpo.append(seguinte)
            fim_indice += 1
        origens = [origem_da_linha(item.rstrip("\r\n")) for item in corpo]
        origem = next((item for item in reversed(origens) if item), None)
        inicio = deslocamentos[indice]
        fim = deslocamentos[fim_indice] if fim_indice < len(linhas) else posicao
        encontradas.append({
            **leitura,
            "indice": indice,
            "origem": origem,
            "corpo": corpo,
            "inicio_bytes": inicio,
            "fim_bytes": fim,
        })
    return linhas, encontradas


def localizar(texto, trecho, origem):
    alvo = normalizar(trecho)
    linhas, abertas = entradas(texto)
    candidatas = [item for item in abertas if alvo in normalizar(item["manchete"])]
    if origem is not None:
        candidatas = [item for item in candidatas if item["origem"] == origem]
    if not candidatas:
        _, concluidas = entradas(texto, concluida=True)
        concluidas = [
            item for item in concluidas
            if alvo in normalizar(item["manchete"])
        ]
        if origem is not None:
            concluidas = [item for item in concluidas if item["origem"] == origem]
        return linhas, None, concluidas[0] if concluidas else None, []
    if len(candidatas) > 1:
        exibidas = [
            {"manchete": item["manchete"], "origem": item["origem"]}
            for item in candidatas
        ]
        return linhas, None, None, exibidas
    return linhas, candidatas[0], None, []
