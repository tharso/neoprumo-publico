import json
import sys
from datetime import datetime

from .assunto_base import (
    conferir_prateleira, data_valida, derivar_id, entradas_de_ficha,
    id_valido, nomes_da_prateleira, normalizar, texto_de_uma_linha,
)
from .assunto_ficha import formatar_nota, inserir_nota, ler_ficha
from .assunto_repositorio import (
    criar_exclusivo, envelope, reconferir_e_gravar, resolver,
)
from .despacho_workspace import resolver_workspace_despacho


def emitir(resultado, usar_json, erro=False):
    if usar_json:
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        print(resultado["mensagem"], file=sys.stderr if erro else sys.stdout)
        for problema in resultado["problemas"]:
            print(f"Aviso: {problema}", file=sys.stderr if erro else sys.stdout)


def _workspace(caminho):
    return resolver_workspace_despacho(caminho, "assunto")


def _falha_valores(workspace, problemas):
    return 1, envelope(
        "recusado", "O assunto não foi registrado.", workspace, problemas,
        ["Corrija os valores e tente novamente."],
    )


def operar_registrar(nome, caminho=None, identificador=None, tipo=None,
                      caminho_principal=None, relacionados=None, apelidos=None):
    workspace, falha = _workspace(caminho)
    if falha:
        return 1, falha
    pasta, problema = conferir_prateleira(workspace)
    if problema:
        return 1, envelope("recusado", problema, workspace, [problema])
    identificador = identificador if identificador is not None else derivar_id(nome)
    problemas = []
    if not texto_de_uma_linha(nome):
        problemas.append("O nome precisa ser texto não vazio de uma linha, sem controles.")
    if not id_valido(identificador):
        problemas.append("O ID precisa obedecer à gramática da prateleira; informe --id.")
    valores = [("tipo", tipo), ("caminho", caminho_principal)]
    valores += [("caminho relacionado", valor) for valor in (relacionados or [])]
    valores += [("apelido", valor) for valor in (apelidos or [])]
    for rotulo, valor in valores:
        if valor is not None and not texto_de_uma_linha(valor):
            problemas.append(f"O {rotulo} precisa ser texto não vazio de uma linha, sem controles.")
    for apelido in apelidos or []:
        if "," in apelido:
            problemas.append(f"O apelido {apelido!r} não pode conter vírgula.")
    if problemas:
        return _falha_valores(workspace, problemas)
    vistos, apelidos_finais, avisos = set(), [], []
    for apelido in apelidos or []:
        chave = normalizar(apelido.strip())
        if chave in vistos:
            avisos.append(f"O apelido {apelido.strip()} estava repetido e foi usado uma vez.")
        else:
            vistos.add(chave)
            apelidos_finais.append(apelido.strip())
    nomes, falha = nomes_da_prateleira(pasta)
    nome_arquivo = f"{identificador}.md"
    ocupante = next((nome for nome in nomes if nome.casefold() == nome_arquivo.casefold()), None)
    if ocupante is not None:
        existente, problema = ler_ficha(pasta / ocupante)
        nome_atual = None
        if ocupante == nome_arquivo and existente:
            sem_titulo = any("falta um título legível" in item for item in existente["problemas"])
            if not sem_titulo:
                nome_atual = existente["nome"]
        problemas = [problema] if problema else []
        if ocupante != nome_arquivo:
            problemas.append(f"O nome está ocupado pela entrada literal {ocupante}.")
        elif nome_atual is None:
            problemas.append(f"{ocupante}: o ocupante não tem Nome legível.")
        return 1, envelope(
            "id_em_uso", f"O ID {identificador} já está em uso.", workspace,
            problemas, id=identificador, nome=nome_atual,
        )
    linhas = [f"# {nome.strip()}\n", "\n"]
    if tipo is not None:
        linhas.append(f"Tipo: {tipo.strip()}\n")
    linhas.append("Estado: ativo\n")
    if apelidos_finais:
        linhas.append("Apelidos: " + ", ".join(apelidos_finais) + "\n")
    if caminho_principal is not None:
        linhas.append(f"Caminho: {caminho_principal.strip()}\n")
    linhas.extend(f"Caminho relacionado: {valor.strip()}\n" for valor in (relacionados or []))
    linhas.extend(["\n", "## Registro\n"])
    ficha = pasta / nome_arquivo
    criado, erro = criar_exclusivo(ficha, "".join(linhas))
    if not criado:
        return 1, envelope(
            "id_em_uso", f"O ID {identificador} já está em uso.", workspace,
            [f"A criação exclusiva encontrou um ocupante ({erro})."] if erro else [],
            id=identificador, nome=None,
        )
    return 0, envelope(
        "registrado", f"Assunto registrado: {nome.strip()} ({identificador}).",
        workspace, avisos, id=identificador, item=str(ficha),
    )


def operar_mostrar(referencia, caminho=None):
    workspace, falha = _workspace(caminho)
    if falha:
        return 1, falha
    ficha, falha = resolver(workspace, referencia)
    if falha:
        return 1, falha
    campos = {chave: ficha[chave] for chave in (
        "id", "nome", "tipo", "estado", "apelidos", "caminho",
        "caminhos_relacionados", "notas",
    )}
    return 0, envelope(
        "assunto", f"Assunto: {ficha['nome']} ({ficha['id']}).", workspace,
        ficha["problemas"], **campos,
    )


def operar_listar(caminho=None, todos=False):
    workspace, falha = _workspace(caminho)
    if falha:
        return 1, falha
    pasta, problema = conferir_prateleira(workspace)
    if problema:
        return 1, envelope("recusado", problema, workspace, [problema])
    caminhos, _, problemas = entradas_de_ficha(pasta)
    assuntos = []
    for arquivo in caminhos:
        ficha, falha = ler_ficha(arquivo)
        if falha:
            problemas.append(falha)
        elif todos or ficha["estado"] == "ativo":
            assuntos.append({chave: ficha[chave] for chave in ("id", "nome", "tipo", "estado")})
            problemas.extend(ficha["problemas"])
    assuntos.sort(key=lambda item: item["id"])
    return 0, envelope(
        "assuntos", f"{len(assuntos)} assuntos encontrados.", workspace,
        problemas, assuntos=assuntos,
    )


def _origem_valida(origem):
    if origem is None:
        return True
    for prefixo in ("inbox ", "acervo "):
        if origem.startswith(prefixo):
            nome = origem[len(prefixo):]
            return texto_de_uma_linha(nome) and ")" not in nome
    return False


def operar_nota(referencia, texto, caminho=None, data=None, origem=None):
    workspace, falha = _workspace(caminho)
    if falha:
        return 1, falha
    ficha, falha = resolver(workspace, referencia)
    if falha:
        return 1, falha
    data = data or datetime.now().astimezone().strftime("%Y-%m-%d")
    problemas = []
    if not data_valida(data):
        problemas.append("A data precisa ser uma data civil válida em AAAA-MM-DD.")
    if not _origem_valida(origem):
        problemas.append("A origem precisa ser inbox <nome> ou acervo <nome>, sem controles nem ).")
    nota = formatar_nota(texto, data, origem)
    if nota is None:
        problemas.append("A nota não tem nenhuma linha com texto.")
    if problemas:
        return 1, envelope("nota_vazia" if nota is None else "recusado", "A nota não foi gravada.", workspace, problemas)
    caminho_ficha = workspace / "Assuntos" / f"{ficha['id']}.md"
    falha = reconferir_e_gravar(caminho_ficha, ficha, inserir_nota(ficha, nota))
    if falha:
        return 1, envelope("recusado", falha, workspace, [falha], id=ficha["id"])
    return 0, envelope(
        "anotado", f"Nota registrada em {ficha['nome']}.", workspace,
        ficha["problemas"], id=ficha["id"],
    )


def operar_estado(referencia, pedido, caminho=None):
    workspace, falha = _workspace(caminho)
    if falha:
        return 1, falha
    ficha, falha = resolver(workspace, referencia)
    if falha:
        return 1, falha
    indice = ficha["indices"].get("Estado")
    literal = None
    if indice is not None:
        linha = ficha["linhas"][indice].rstrip("\r\n")
        literal = linha.split(": ", 1)[1].strip()
    if literal == pedido or (indice is None and pedido == "ativo"):
        return 0, envelope(
            "sem_mudanca", f"{ficha['nome']} já está {pedido}.", workspace,
            ficha["problemas"], id=ficha["id"],
        )
    linhas = list(ficha["linhas"])
    problemas = list(ficha["problemas"])
    if indice is None:
        posicao = 1 if linhas and linhas[0].startswith("# ") else 0
        linhas.insert(posicao, f"Estado: {pedido}\n")
    else:
        terminacao = "\r\n" if linhas[indice].endswith("\r\n") else "\n"
        linhas[indice] = f"Estado: {pedido}{terminacao}"
        if literal not in ("ativo", "arquivado"):
            problemas.append(f"Estado anterior inválido normalizado pelo gesto: {literal!r}.")
    caminho_ficha = workspace / "Assuntos" / f"{ficha['id']}.md"
    falha = reconferir_e_gravar(caminho_ficha, ficha, "".join(linhas))
    if falha:
        return 1, envelope("recusado", falha, workspace, [falha], id=ficha["id"])
    status = "arquivado" if pedido == "arquivado" else "reativado"
    return 0, envelope(status, f"{ficha['nome']} foi {status}.", workspace, problemas, id=ficha["id"])


def executar_registrar(nome, usar_json=False, **opcoes):
    codigo, resultado = operar_registrar(nome, **opcoes)
    emitir(resultado, usar_json, codigo != 0)
    return codigo


def executar_mostrar(referencia, caminho=None, usar_json=False):
    codigo, resultado = operar_mostrar(referencia, caminho)
    emitir(resultado, usar_json, codigo != 0)
    return codigo


def executar_listar(caminho=None, usar_json=False, todos=False):
    codigo, resultado = operar_listar(caminho, todos)
    emitir(resultado, usar_json, codigo != 0)
    return codigo


def executar_nota(referencia, texto, caminho=None, usar_json=False, data=None, origem=None):
    codigo, resultado = operar_nota(referencia, texto, caminho, data, origem)
    emitir(resultado, usar_json, codigo != 0)
    return codigo


def executar_estado(referencia, pedido, caminho=None, usar_json=False):
    codigo, resultado = operar_estado(referencia, pedido, caminho)
    emitir(resultado, usar_json, codigo != 0)
    return codigo
