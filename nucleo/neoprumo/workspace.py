import json
import sys
from pathlib import Path

from .ativo import adotar_se_primeiro, resolver
from .estrutura_workspace import (
    ESTRUTURA,
    FalhaDeCriacao,
    criar_item_ausente,
    criar_marca,
    inspecionar_estrutura,
    problemas_da_estrutura,
    tem_marca_real,
)
from .orientacao import classificar, orientar, orientar_recuperacao


def _emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
        return
    destino = sys.stderr if erro else sys.stdout
    print(resultado["mensagem"], file=destino)
    status = resultado["status"]
    if status in {"reparado", "readotado", "ja_existe"}:
        itens = resultado["acoes"]
    elif status == "com_problemas":
        itens = resultado["acoes"] + resultado["problemas"]
    elif status == "recusado":
        itens = resultado["problemas"] + resultado["acoes"]
    else:
        itens = resultado["problemas"]
    for item in itens:
        print(f"- {item}", file=destino)


def _resultado(status, problemas, acoes, mensagem):
    return {
        "status": status,
        "problemas": problemas,
        "acoes": acoes,
        "mensagem": mensagem,
    }


def _problema_de_criacao(nome, erro):
    detalhe = f" ({erro})" if str(erro) else ""
    return f"Não foi possível criar {nome}{detalhe}."


def _conteudo_com_problemas(workspace, causas, incompletos):
    atuais = [
        problema
        for problema in problemas_da_estrutura(workspace)
        if ".neoprumo/workspace.json" not in problema
    ]
    problemas = []
    for problema in atuais:
        causa = next(
            (
                causas[nome]
                for nome in causas
                if problema.startswith(
                    (f"Falta {nome} ", f"Não foi possível conferir {nome}")
                )
            ),
            None,
        )
        problemas.append(causa or problema)
    problemas.extend(incompletos)
    return problemas


def _rota_estrutural(workspace, setup_puro=False):
    return orientar_recuperacao(
        workspace,
        setup_puro_se_inexistente=setup_puro,
    )


def _criar_conteudo(workspace):
    acoes = []
    causas = {}
    incompletos = []
    for nome, tipo in ESTRUTURA.items():
        if nome.startswith(".neoprumo/"):
            continue
        try:
            acao = criar_item_ausente(workspace, nome, tipo)
        except FalhaDeCriacao as erro:
            acoes.append(erro.acao)
            incompletos.append(str(erro))
            continue
        except OSError as erro:
            causas[nome] = _problema_de_criacao(nome, erro)
            continue
        if acao:
            acoes.append(acao)
    return acoes, _conteudo_com_problemas(workspace, causas, incompletos)


def _criar_identidade(workspace, acoes):
    incompletos = []
    try:
        acao = criar_marca(workspace)
        if acao:
            acoes.append(acao)
    except OSError as erro:
        incompletos.append(_problema_de_criacao(".neoprumo", erro))
    if tem_marca_real(workspace):
        try:
            acao = criar_item_ausente(
                workspace, ".neoprumo/workspace.json", "arquivo"
            )
            if acao:
                acoes.append(acao)
        except FalhaDeCriacao as erro:
            acoes.append(erro.acao)
            incompletos.append(str(erro))
        except OSError as erro:
            incompletos.append(_problema_de_criacao("workspace.json", erro))
    if not tem_marca_real(workspace):
        incompletos.append("A pasta .neoprumo não é uma pasta real.")
    return incompletos


def _ativar_workspace(workspace, acoes, participio):
    try:
        ativou = adotar_se_primeiro(workspace)
    except OSError:
        configurado = resolver()
        if (
            configurado is not None
            and configurado.expanduser().resolve() == workspace.resolve()
        ):
            acoes.append("Definido como workspace ativo.")
            return []
        return [
            f"O workspace foi {participio}, mas o ponteiro de workspace ativo "
            "não pôde ser gravado."
        ]
    if ativou:
        acoes.append("Definido como workspace ativo.")
    return []


def configurar(caminho, usar_json=False):
    workspace = Path(caminho).expanduser()
    estado = classificar(workspace)
    if estado == "saudavel" or tem_marca_real(workspace):
        resultado = _resultado(
            "ja_existe", [], [], f"O workspace já existe em {workspace}; nada foi alterado."
        )
        _emitir(resultado, usar_json)
        return 0
    if estado == "arquivo":
        resultado = _resultado(
            "recusado",
            ["O caminho aponta para um arquivo."],
            [],
            "O caminho aponta para um arquivo, não para uma pasta.",
        )
        _emitir(resultado, usar_json, erro=True)
        return 1
    if estado == "ilegivel":
        guia = orientar(workspace, "caminho_explicito")
        resultado = _resultado(
            "recusado",
            [guia["problema"]],
            guia["acoes"],
            guia["mensagem"],
        )
        _emitir(resultado, usar_json, erro=True)
        return 1
    if estado not in {"inexistente", "vazio"}:
        guia = orientar(workspace, "caminho_explicito")
        resultado = _resultado(
            "recusado",
            ["O diretório não está vazio."],
            guia["acoes"],
            "O diretório não está vazio; nada foi alterado.",
        )
        _emitir(resultado, usar_json, erro=True)
        return 1
    try:
        workspace.mkdir(parents=True)
    except FileExistsError:
        pass
    except OSError as erro:
        rota = _rota_estrutural(workspace, setup_puro=True)
        resultado = _resultado(
            "com_problemas",
            [_problema_de_criacao(str(workspace), erro)],
            [],
            f"O workspace não pôde ser criado. {rota}",
        )
        _emitir(resultado, usar_json, erro=True)
        return 1
    acoes_parciais, problemas = _criar_conteudo(workspace)
    if problemas:
        rota = _rota_estrutural(workspace)
        resultado = _resultado(
            "com_problemas", problemas, acoes_parciais, f"A criação ficou incompleta. {rota}"
        )
        _emitir(resultado, usar_json, erro=True)
        return 1
    problemas = _criar_identidade(workspace, acoes_parciais)
    problemas.extend(problemas_da_estrutura(workspace))
    if problemas:
        rota = _rota_estrutural(workspace)
        resultado = _resultado(
            "com_problemas", problemas, acoes_parciais, f"A criação ficou incompleta. {rota}"
        )
        _emitir(resultado, usar_json, erro=True)
        return 1
    acoes = ["Estrutura canônica criada."]
    problemas = _ativar_workspace(workspace, acoes, "criado")
    if problemas:
        resultado = _resultado(
            "com_problemas",
            problemas,
            acoes,
            "O workspace foi criado. "
            + orientar_recuperacao(workspace, falha_do_ponteiro=True),
        )
        _emitir(resultado, usar_json, erro=True)
        return 1
    mensagem = f"Workspace criado em {workspace}."
    if "Definido como workspace ativo." in acoes:
        mensagem += " Definido como workspace ativo."
    _emitir(_resultado("criado", [], acoes, mensagem), usar_json)
    return 0


def diagnosticar(caminho, reparar=False, usar_json=False):
    workspace = Path(caminho)
    inspecao = inspecionar_estrutura(workspace)
    if inspecao["status"] == "nao_e_workspace":
        guia = orientar(workspace, "caminho_explicito")
        resultado = {
            "status": "nao_e_workspace",
            "problemas": ["Falta a pasta .neoprumo."],
            "acoes": guia["acoes"],
            "mensagem": f"Isto não é um workspace do NeoPrumo. {guia['mensagem']}",
            "workspace": str(workspace),
        }
        _emitir(resultado, usar_json, erro=True)
        return 1

    problemas = inspecao["problemas"]
    if problemas:
        if reparar:
            acoes = []
            for nome, tipo in ESTRUTURA.items():
                acao = criar_item_ausente(workspace, nome, tipo)
                if acao:
                    acoes.append(acao)
            restantes = problemas_da_estrutura(workspace)
            if not restantes:
                _emitir(
                    {
                        "status": "reparado",
                        "problemas": problemas,
                        "acoes": acoes,
                        "mensagem": "Workspace reparado. O conteúdo existente foi preservado.",
                        "workspace": str(workspace),
                    },
                    usar_json,
                )
                return 0
            problemas = restantes
        resultado = {
            "status": "com_problemas",
            "problemas": problemas,
            "acoes": [],
            "mensagem": "O workspace tem problemas:",
            "workspace": str(workspace),
        }
        _emitir(resultado, usar_json, erro=True)
        return 1

    _emitir(
        {
            "status": "saudavel",
            "problemas": [],
            "acoes": [],
            "mensagem": "Tudo certo com o workspace.",
            "workspace": str(workspace),
        },
        usar_json,
    )
    return 0
