import hashlib
import stat
from pathlib import Path

from .assunto_despacho import despachar_acervo_associado, despachar_assunto
from .assunto_marcadores import conferir_marcador
from .despacho_workspace import resolver_workspace_despacho
from .destinos_textuais import (
    despachar_pauta,
    fotografar_destinos,
    marcador_em_destinos,
)
from .resultado_despacho import (
    emitir,
    envelope,
    recusa,
    recusa_falha,
    recusa_reconferencia,
)
from .validacao_despacho import nome_projeto_valido, validar_regime_despacho
from .movimento_acervo import mover_para_acervo
from .movimento_lixo import mover_para_lixo

DESTINOS = ("pauta", "acervo", "assunto", "projeto", "lixo")
def _esta_dentro(caminho, workspace):
    try:
        caminho.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False
def _encontrar_item(inbox, nome):
    exato = inbox / nome
    if exato.is_file():
        return exato, None
    candidatos = [
        caminho
        for caminho in inbox.iterdir()
        if caminho.is_file() and caminho.stem == nome
    ]
    if len(candidatos) == 1:
        return candidatos[0], None
    if len(candidatos) > 1:
        return None, "ambiguo"
    return None, "inexistente"
def _validar_referencia(nome, workspace, destino):
    if nome_projeto_valido(nome):
        return None
    vazio = nome is None or not isinstance(nome, str) or not nome.strip()
    return recusa(
        (
            f"O destino {destino} precisa da referência do assunto."
            if vazio
            else "O nome do projeto precisa caber em uma linha e não pode ter caracteres de controle."
        ),
        "A referência não foi informada." if vazio else "A referência tem formato inválido.",
        f"Informe a referência depois de {destino}." if vazio else "Use uma referência em uma única linha, sem caracteres de controle.",
        workspace,
        destino,
    )
def _localizar(item, workspace, destino):
    if not item or Path(item).name != item:
        return None, recusa(
            "Informe somente o nome do arquivo que está na Inbox.",
            "O item deve ser um nome de arquivo, não um caminho.",
            "Use o nome do arquivo com ou sem extensão.",
            workspace,
            destino,
        )
    inbox = workspace / "Inbox"
    if not inbox.is_dir() or not _esta_dentro(inbox, workspace):
        return None, recusa(
            "A Inbox não pôde ser lida. Rode doctor para conferir o workspace.",
            "A pasta Inbox está ausente ou aponta para fora do workspace.",
            "Rode doctor para conferir o workspace.",
            workspace,
            destino,
        )
    try:
        encontrado, problema = _encontrar_item(inbox, item)
    except OSError:
        return None, recusa(
            "A Inbox não pôde ser lida. Rode doctor para conferir o workspace.",
            "A pasta Inbox não pôde ser lida.",
            "Rode doctor para conferir o workspace.",
            workspace,
            destino,
        )
    if problema == "ambiguo":
        return None, recusa(
            f"Há mais de um item com o radical {item}. Informe o nome completo.",
            "O radical corresponde a mais de um arquivo na Inbox.",
            "Informe o nome completo, incluindo a extensão.",
            workspace,
            destino,
        )
    if problema == "inexistente":
        return None, recusa(
            f"O item {item} não foi encontrado na Inbox.",
            "O item não existe na Inbox.",
            "Confira o nome do arquivo e tente novamente.",
            workspace,
            destino,
        )
    if not _esta_dentro(encontrado, workspace):
        return None, recusa(
            "O item aponta para fora do workspace e não pode ser despachado.",
            "O item não está contido no workspace.",
            "Mova o arquivo para dentro da Inbox e tente novamente.",
            workspace,
            destino,
        )
    return encontrado, None
def _ler_item_textual(item, workspace, destino):
    try:
        dados = item.read_bytes()
        return dados.decode("utf-8"), dados, None
    except UnicodeDecodeError:
        return None, None, recusa(
            f"O item {item.name} não é texto UTF-8. Mova-o pro acervo.",
            "O item não é texto UTF-8.",
            "Use o destino acervo para preservar o arquivo sem interpretá-lo.",
            workspace,
            destino,
            item=item,
            identificador=item.stem,
        )
    except OSError as erro:
        return None, None, recusa_falha(item, workspace, destino, erro)


def _reconferir(item, workspace, destino, digital_esperada):
    if digital_esperada is None:
        return None
    try:
        atuais = item.read_bytes()
    except OSError as erro:
        return recusa_falha(item, workspace, destino, erro)
    if hashlib.sha256(atuais).hexdigest() != digital_esperada:
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            "O item mudou depois da conferência e não foi despachado; gere a página de novo.",
            "O conteúdo do item mudou antes da execução.",
        )
    destinos, problemas = fotografar_destinos(workspace)
    if problemas or any(not foto["regular"] for foto in destinos.values()):
        motivo = problemas[0] if problemas else "Um destino textual deixou de ser um arquivo regular."
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            "Não foi possível reconferir o item agora; ele ficou na Inbox.",
            motivo,
        )
    marcadores = marcador_em_destinos(destinos, item.stem)
    marcadores_assunto, _ = conferir_marcador(workspace, item.name)
    marcadores.extend(marcadores_assunto)
    if marcadores:
        return recusa_reconferencia(
            item,
            workspace,
            destino,
            f"Já há registro deste item em {marcadores[0]}; confira o destino e despache-o na conversa.",
            "Surgiu um registro no destino depois da conferência.",
        )
    return None


def operar_despacho(
    item, destino, referencia=None, caminho=None, item_resolvido=None,
    bytes_validados=None, digital_esperada=None, regime=None, ate=None,
    vence=None, confirmado=False, incluir_campos_regime=False, assunto=None,
):
    workspace, falha = resolver_workspace_despacho(caminho, destino)
    if falha:
        return 1, falha
    if destino not in DESTINOS:
        return 1, recusa(
            f"Destino desconhecido: {destino}. Use pauta, acervo, assunto, projeto ou lixo.",
            f"O destino {destino} não existe.",
            "Escolha pauta, acervo, assunto, projeto ou lixo.",
            workspace,
            destino,
        )
    aceita_confirmacao = destino in ("assunto", "projeto") or (
        destino == "acervo" and assunto is not None
    )
    validacao = validar_regime_despacho(
        destino, regime, ate, vence, confirmado, aceita_confirmacao
    )
    falha_regime, objeto_regime, prazo, acoes_regime = validacao
    if falha_regime:
        return 1, recusa(falha_regime, falha_regime, None, workspace, destino)
    if referencia is not None and destino not in ("assunto", "projeto"):
        return 1, recusa(
            "A referência só acompanha assunto ou projeto.",
            "Há uma referência posicional em um destino que não a aceita.",
            "Remova a referência ou escolha assunto/projeto.", workspace, destino,
        )
    if assunto is not None and destino != "acervo":
        return 1, recusa(
            "--assunto só acompanha o destino acervo.",
            "A associação foi usada fora do acervo.", None, workspace, destino,
        )
    if destino == "acervo" and referencia is not None and assunto is not None:
        return 1, recusa(
            "A referência só acompanha assunto ou projeto; no acervo, use apenas --assunto.",
            "O acervo recebeu referência posicional e --assunto.", None, workspace, destino,
        )
    if destino in ("assunto", "projeto"):
        falha = _validar_referencia(referencia, workspace, destino)
        if falha:
            return 1, falha
    if item_resolvido is None:
        encontrado, falha = _localizar(item, workspace, destino)
        if falha:
            return 1, falha
    else:
        encontrado = Path(item_resolvido)
    if destino in ("assunto", "acervo"):
        try:
            modo_item = encontrado.lstat().st_mode
        except OSError as erro:
            return 1, recusa_falha(encontrado, workspace, destino, erro)
        if stat.S_ISLNK(modo_item):
            return 1, recusa(
                "O item é um atalho; mova o arquivo real.",
                "Este destino não segue atalhos.",
                "Mova o arquivo real para a Inbox.", workspace, destino,
                item=encontrado, identificador=encontrado.stem,
            )
    falha = _reconferir(encontrado, workspace, destino, digital_esperada)
    if falha:
        return 1, falha
    if destino == "acervo" and assunto is not None:
        codigo, resultado = despachar_acervo_associado(encontrado, workspace, assunto, confirmado)
        return codigo, resultado
    if destino == "acervo":
        return mover_para_acervo(encontrado, workspace)
    if destino == "lixo":
        return mover_para_lixo(encontrado, workspace)
    if bytes_validados is None:
        conteudo, bytes_do_conteudo, falha = _ler_item_textual(
            encontrado, workspace, destino
        )
        if falha:
            return 1, falha
    else:
        bytes_do_conteudo = bytes_validados
        conteudo = bytes_validados.decode("utf-8")
    if destino == "pauta":
        return despachar_pauta(encontrado, conteudo, workspace, objeto_regime,
                               prazo, acoes_regime, incluir_campos_regime)
    codigo, resultado = despachar_assunto(
        encontrado, conteudo, bytes_do_conteudo, workspace, referencia, confirmado
    )
    if destino == "projeto" and resultado.get("status") == "assunto_inexistente":
        resultado["tipo_sugerido"] = "projeto"
    if destino == "projeto":
        resultado["destino"] = "projeto"
    return codigo, resultado


def operar_adiamento(item, caminho, item_resolvido=None, digital_esperada=None):
    workspace, falha = resolver_workspace_despacho(caminho, None)
    if falha:
        return 1, falha
    if item_resolvido is None:
        encontrado, falha = _localizar(item, workspace, None)
        if falha:
            return 1, falha
    else:
        encontrado = Path(item_resolvido)
    falha = _reconferir(encontrado, workspace, None, digital_esperada)
    if falha:
        return 1, falha
    return 0, envelope(
        "adiado",
        "Adiado: fica na Inbox.",
        workspace,
        None,
        identificador=encontrado.stem,
    )


def despachar(
    item, destino, referencia=None, caminho=None, usar_json=False,
    regime=None, ate=None, vence=None, confirmado=False, assunto=None,
):
    codigo, resultado = operar_despacho(
        item, destino, referencia, caminho,
        regime=regime, ate=ate, vence=vence, confirmado=confirmado,
        incluir_campos_regime=True, assunto=assunto,
    )
    emitir(resultado, usar_json, erro=codigo != 0)
    return codigo
