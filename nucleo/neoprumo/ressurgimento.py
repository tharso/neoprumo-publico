import os
import stat
import unicodedata
from datetime import datetime
from pathlib import Path

from .acervo_base import ler_bytes, motivo, validar_pasta_acervo
from .ativo import e_workspace, informar_indisponivel, resolver
from .resultado_ressurgimento import (
    campos_nulos,
    emitir,
    envelope,
    mensagem_do_candidato,
    recusa,
)
from .resultado_seed import recusar_workspace
from .seed import _data_pelo_nome
from .superficie_base import codificavel_utf8


LIMIAR_DIAS = 7
AVISO_INAPRESENTAVEIS = (
    "{total} {itens} do acervo sem conteúdo legível pra apresentar; "
    "revise-os pelo garimpo ou na conversa."
)


def _referencia_local(instante):
    if instante is None:
        return datetime.now().astimezone()
    return instante.astimezone()


def _nome_tem_controle(nome):
    return any(unicodedata.category(caractere) == "Cc" for caractere in nome)


def _idade(entrada, estado, referencia):
    data = _data_pelo_nome(entrada.name)
    if data is None:
        data = datetime.fromtimestamp(
            estado.st_mtime, tz=referencia.tzinfo
        ).date()
    return max(0, (referencia.date() - data).days)


def _observar_idade(entrada, referencia, problemas):
    if entrada.name.startswith("."):
        return None
    if not codificavel_utf8(entrada.name):
        problemas.append(
            "Acervo: um item tem nome incompatível com UTF-8 e não foi incluído."
        )
        return None
    if _nome_tem_controle(entrada.name):
        problemas.append(
            "Acervo: um item tem nome com caracteres de controle e não foi incluído."
        )
        return None
    try:
        estado = entrada.stat(follow_symlinks=False)
    except OSError as erro:
        problemas.append(
            f"Acervo: não foi possível observar {entrada.name} ({motivo(erro)}); "
            "o item não foi incluído."
        )
        return None
    if not stat.S_ISREG(estado.st_mode):
        return None
    try:
        idade = _idade(entrada, estado, referencia)
    except (OSError, OverflowError, ValueError) as erro:
        problemas.append(
            f"Acervo: não foi possível ler a data de {entrada.name} ({motivo(erro)})."
        )
        return None
    if idade < LIMIAR_DIAS:
        return None
    return Path(entrada.path), idade


def _ler_apresentavel(caminho):
    try:
        dados = ler_bytes(caminho)
        conteudo = dados.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not any(linha.strip() for linha in conteudo.splitlines()):
        return None
    return conteudo


def _enumerar(acervo, referencia):
    candidatos = []
    problemas = []
    inapresentaveis = 0
    try:
        with os.scandir(acervo) as entradas:
            for entrada in entradas:
                observado = _observar_idade(entrada, referencia, problemas)
                if observado is None:
                    continue
                caminho, idade = observado
                conteudo = _ler_apresentavel(caminho)
                if conteudo is None:
                    inapresentaveis += 1
                    continue
                candidatos.append(
                    {
                        "nome": entrada.name,
                        "idade": idade,
                        "conteudo": conteudo,
                    }
                )
    except OSError as erro:
        return None, [f"O Acervo não pôde ser lido ({motivo(erro)})."]
    if inapresentaveis:
        problemas.append(
            AVISO_INAPRESENTAVEIS.format(
                total=inapresentaveis,
                itens="item" if inapresentaveis == 1 else "itens",
            )
        )
    candidatos.sort(key=lambda item: (-item["idade"], item["nome"]))
    return candidatos, problemas


def operar_ressurgimento(caminho, instante=None):
    workspace = Path(caminho)
    acervo = workspace / "Acervo"
    problema = validar_pasta_acervo(acervo, workspace)
    if problema:
        return 1, recusa(
            workspace,
            problema,
            "Rode doctor para conferir o workspace.",
            "O Acervo não pôde ser usado. Rode doctor para conferir o workspace.",
        )
    referencia = _referencia_local(instante)
    candidatos, problemas = _enumerar(acervo, referencia)
    if candidatos is None:
        return 1, recusa(
            workspace,
            problemas[0],
            "Confira as permissões do Acervo e tente novamente.",
            "O Acervo não pôde ser lido.",
        )
    if not candidatos:
        return 0, envelope(
            "sem_candidato",
            "Nada a ressurgir por enquanto.",
            workspace,
            elegiveis=0,
            problemas=problemas,
        )
    candidato = candidatos[referencia.date().toordinal() % len(candidatos)]
    return 0, envelope(
        "candidato",
        mensagem_do_candidato(candidato, len(candidatos)),
        workspace,
        candidato=candidato,
        elegiveis=len(candidatos),
        problemas=problemas,
    )


def executar_ressurgimento(caminho=None, usar_json=False, instante=None):
    explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None:
        return informar_indisponivel(
            usar_json=usar_json,
            extras=campos_nulos(),
        )
    workspace = Path(workspace).expanduser().resolve()
    if not e_workspace(workspace):
        if explicito:
            return recusar_workspace(
                workspace,
                usar_json,
                extras=campos_nulos(),
            )
        return informar_indisponivel(
            workspace,
            usar_json=usar_json,
            extras=campos_nulos(),
        )
    codigo, resultado = operar_ressurgimento(workspace, instante=instante)
    emitir(resultado, usar_json, erro=codigo != 0)
    return codigo
