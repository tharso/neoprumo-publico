import hashlib
import stat
from datetime import datetime

from .assunto_base import tem_controle
from .assunto_ficha import formatar_nota, inserir_nota, ler_ficha
from .assunto_repositorio import reconferir_e_gravar, resolver
from .destinos_textuais import gravar_atomico
from .movimento_acervo import mover_para_acervo
from .resultado_despacho import envelope, recusa, recusa_falha, recusa_item_vazio


def _origem_hostil(nome):
    return not nome or ")" in nome or "\n" in nome or "\r" in nome or tem_controle(nome)


def _recusa_arquivado(item, workspace, destino, ficha):
    return recusa(
        f"O assunto {ficha['nome']} está arquivado; confirme para continuar.",
        "O assunto está arquivado.",
        "Repita com --confirmado se ainda quiser registrar nele.",
        workspace, destino, item=item, identificador=item.stem,
    )


def _resolver_alvo(item, workspace, destino, referencia, confirmado):
    if _origem_hostil(item.name):
        return None, recusa(
            "O nome do item não pode ser usado como origem de uma nota.",
            "O nome do item contém controle, quebra de linha ou ).",
            "Renomeie o item antes de usar este destino.",
            workspace, destino, item=item, identificador=item.stem,
        )
    ficha, falha = resolver(workspace, referencia)
    if falha:
        falha["destino"] = destino
        falha["item"] = str(item)
        falha["id"] = item.stem
        return None, falha
    if ficha["estado"] == "arquivado" and not confirmado:
        return None, _recusa_arquivado(item, workspace, destino, ficha)
    if ficha["estado"] == "ativo" and confirmado:
        return None, recusa(
            "Não há o que confirmar.",
            "O assunto está ativo.",
            "Repita sem --confirmado.",
            workspace, destino, item=item, identificador=item.stem,
        )
    return ficha, None


def despachar_assunto(
    item, conteudo, bytes_do_conteudo, workspace, referencia, confirmado=False
):
    ficha, falha = _resolver_alvo(item, workspace, "assunto", referencia, confirmado)
    if falha:
        return 1, falha
    nota = formatar_nota(
        conteudo, datetime.now().astimezone().strftime("%Y-%m-%d"),
        f"inbox {item.name}",
    )
    if nota is None:
        return 1, recusa_item_vazio(item, workspace, "assunto")
    caminho = workspace / "Assuntos" / f"{ficha['id']}.md"
    anterior = ficha["texto"].encode("utf-8")
    novo = inserir_nota(ficha, nota).encode("utf-8")
    falha = reconferir_e_gravar(caminho, ficha, novo.decode("utf-8"))
    if falha:
        return 1, recusa(falha, falha, None, workspace, "assunto", item=item, identificador=item.stem)
    try:
        ficha_atual, problema = ler_ficha(caminho)
        item_atual = item.read_bytes()
    except OSError as erro:
        problema = str(erro)
        ficha_atual, item_atual = None, b""
    if problema or ficha_atual["digital"] != hashlib.sha256(novo).hexdigest():
        return 1, recusa(
            "A ficha mudou após a gravação; o item ficou na Inbox.",
            problema or "A ficha mudou após a gravação.", None,
            workspace, "assunto", item=item, identificador=item.stem,
        )
    if hashlib.sha256(item_atual).digest() != hashlib.sha256(bytes_do_conteudo).digest():
        return 1, recusa(
            "O item mudou durante o gesto; a nota na ficha é da versão anterior — confira os dois.",
            "O item mudou depois da gravação da nota.", None,
            workspace, "assunto", item=item, identificador=item.stem,
        )
    try:
        item.unlink()
    except OSError as erro:
        atual, problema = ler_ficha(caminho)
        if atual and atual["digital"] == hashlib.sha256(novo).hexdigest():
            try:
                gravar_atomico(caminho, anterior)
            except OSError:
                problema = "A nota ficou na ficha e o item segue na Inbox; confira antes de aplicar de novo."
        elif problema is None:
            problema = "A nota ficou na ficha e o item segue na Inbox; confira antes de aplicar de novo."
        if problema:
            return 1, recusa(
                "A nota ficou na ficha e o item segue na Inbox; confira antes de aplicar de novo.",
                problema, None, workspace, "assunto", item=item, identificador=item.stem,
            )
        return 1, recusa_falha(item, workspace, "assunto", erro)
    return 0, envelope(
        "despachado", f"Anotado no assunto {ficha['nome']}: {item.stem}.",
        workspace, "assunto", item=caminho, identificador=item.stem,
    )


def despachar_acervo_associado(item, workspace, referencia, confirmado=False):
    ficha, falha = _resolver_alvo(item, workspace, "acervo", referencia, confirmado)
    if falha:
        return 1, falha
    codigo, resultado = mover_para_acervo(item, workspace)
    if codigo:
        return codigo, resultado
    final = resultado["item"]
    nome_final = final.rsplit("/", 1)[-1]
    try:
        with open(final, "rb") as arquivo:
            dados = arquivo.read()
        texto = dados.decode("utf-8")
        cabeca = next((linha for linha in texto.splitlines() if linha.strip()), None)
    except (OSError, UnicodeDecodeError):
        cabeca = None
    texto_nota = cabeca or f"item {nome_final}"
    data = datetime.now().astimezone().strftime("%Y-%m-%d")
    nota = formatar_nota(texto_nota, data, f"acervo {nome_final}")
    caminho_ficha = workspace / "Assuntos" / f"{ficha['id']}.md"
    atual, problema = ler_ficha(caminho_ficha)
    if atual and atual["estado"] == "arquivado" and not confirmado:
        problema = "A ficha foi arquivada durante o gesto."
    if problema or not atual:
        return _nota_perdida(resultado, ficha, data, nome_final, texto_nota, problema)
    falha = reconferir_e_gravar(caminho_ficha, atual, inserir_nota(atual, nota))
    if falha:
        return _nota_perdida(resultado, ficha, data, nome_final, texto_nota, falha)
    return 0, resultado


def _nota_perdida(resultado, ficha, data, nome, texto, problema):
    resultado["problemas"].append(problema or "A nota de relação não foi gravada.")
    resultado["acoes"].append("Repare a relação com assunto nota usando data, origem e texto informados.")
    resultado["nota_perdida"] = {
        "assunto": ficha["id"], "data": data,
        "origem": f"acervo {nome}", "texto": texto,
    }
    resultado["mensagem"] += " Aviso: a relação com o assunto precisa de reparo."
    return 0, resultado
