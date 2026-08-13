import os
from pathlib import Path

from .assunto_base import (
    conferir_prateleira,
    derivar_id,
    entradas_de_ficha,
    id_valido,
    nomes_da_prateleira,
    normalizar,
)
from .assunto_ficha import ler_ficha
from .destinos_textuais import gravar_atomico


def envelope(status, mensagem, workspace, problemas=None, acoes=None, **extras):
    resultado = {
        "status": status,
        "problemas": problemas or [],
        "acoes": acoes or [],
        "mensagem": mensagem,
        "workspace": str(workspace) if workspace is not None else None,
    }
    resultado.update(extras)
    return resultado


def caminho_exato(pasta, identificador):
    nomes, falha = nomes_da_prateleira(pasta)
    if falha:
        return None, falha
    nome = f"{identificador}.md"
    return (pasta / nome, None) if nome in nomes else (None, None)


def _carregar_todas(pasta):
    caminhos, _, problemas = entradas_de_ficha(pasta)
    fichas, ilegíveis = [], []
    for caminho in caminhos:
        ficha, falha = ler_ficha(caminho)
        if falha:
            ilegíveis.append(falha)
        else:
            fichas.append(ficha)
    return fichas, problemas, ilegíveis


def resolver(workspace, referencia):
    pasta, falha = conferir_prateleira(workspace)
    if falha:
        return None, envelope("recusado", falha, workspace, [falha])
    ref = referencia.strip() if isinstance(referencia, str) else ""
    if not ref or not normalizar(ref):
        return None, envelope(
            "referencia_invalida", "A referência do assunto é inválida.",
            workspace, ["A referência precisa conter texto aproveitável."]
        )
    if id_valido(ref):
        caminho, falha = caminho_exato(pasta, ref)
        if falha:
            return None, envelope("recusado", falha, workspace, [falha])
        if caminho is not None:
            ficha, problema = ler_ficha(caminho)
            if problema:
                return None, envelope(
                    "recusado", f"A ficha de {ref} não pôde ser usada.",
                    workspace, [problema], id=ref,
                )
            return ficha, None
    fichas, problemas, ilegíveis = _carregar_todas(pasta)
    if ilegíveis:
        return None, envelope(
            "resolucao_incerta",
            "A referência não pôde ser resolvida com segurança.",
            workspace, problemas + ilegíveis,
        )
    alvo = normalizar(ref)
    exatos = [
        ficha for ficha in fichas
        if any(normalizar(apelido) == alvo for apelido in ficha["apelidos"])
    ]
    casamentos = exatos or [
        ficha for ficha in fichas
        if alvo in normalizar(ficha["nome"])
        or any(alvo in normalizar(apelido) for apelido in ficha["apelidos"])
    ]
    if len(casamentos) == 1:
        return casamentos[0], None
    if len(casamentos) > 1:
        candidatas = sorted(
            ({"id": ficha["id"], "nome": ficha["nome"]} for ficha in casamentos),
            key=lambda item: item["id"],
        )
        return None, envelope(
            "ambiguo", "Mais de um assunto corresponde à referência.", workspace,
            problemas, candidatas=candidatas,
        )
    extras = {}
    sugestao = derivar_id(ref)
    if sugestao:
        extras["id_sugerido"] = sugestao
    return None, envelope(
        "assunto_inexistente", f"O assunto {ref} não existe.", workspace,
        problemas, **extras,
    )


def reconferir_e_gravar(caminho, ficha, novo_texto):
    atual, falha = ler_ficha(caminho)
    if falha or atual["digital"] != ficha["digital"]:
        return "A ficha mudou, tente de novo."
    try:
        gravar_atomico(caminho, novo_texto.encode("utf-8"))
    except OSError as erro:
        return f"A ficha não pôde ser gravada ({erro})."
    return None


def criar_exclusivo(caminho, conteudo):
    try:
        with open(caminho, "x", encoding="utf-8", newline="") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
    except FileExistsError:
        return False, None
    except OSError as erro:
        return False, erro
    return True, None
