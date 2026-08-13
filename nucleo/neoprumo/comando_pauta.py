import hashlib
import stat
from datetime import datetime
from pathlib import Path

from .acervo_base import esta_dentro
from .ativo import e_workspace, informar_indisponivel, resolver
from .destinos_textuais import gravar_atomico
from .pauta_entradas import ler_pauta, localizar
from .resultado_pauta import campos_nulos, emitir, envelope, recusar


def _falha(mensagem, workspace, **campos):
    return 1, recusar(mensagem, workspace, destino="lixo", **campos)


def _validar_lixo(workspace):
    metadados = workspace / ".neoprumo"
    lixo = metadados / "lixo"
    if not esta_dentro(lixo, workspace):
        return None, "O lixo aponta para fora do workspace."
    try:
        estado_metadados = metadados.lstat()
        if stat.S_ISLNK(estado_metadados.st_mode) or not stat.S_ISDIR(
            estado_metadados.st_mode
        ):
            return None, "A pasta interna do workspace não pôde ser usada."
        try:
            estado_lixo = lixo.lstat()
        except FileNotFoundError:
            lixo.mkdir()
        else:
            if stat.S_ISLNK(estado_lixo.st_mode):
                return None, "O lixo é um atalho simbólico e não será seguido."
            if not stat.S_ISDIR(estado_lixo.st_mode):
                return None, "O lixo deveria ser uma pasta."
    except OSError as erro:
        return None, f"O lixo não pôde ser preparado ({erro})."
    return lixo, None


def _nome_base(instante):
    referencia = datetime.now().astimezone() if instante is None else instante.astimezone()
    return f"pauta-{referencia.strftime('%Y-%m-%d-%H%M%S')}"


def _gravar_exclusivo(lixo, radical, bloco):
    numero = 1
    while True:
        sufixo = "" if numero == 1 else f"-{numero}"
        caminho = lixo / f"{radical}{sufixo}.md"
        try:
            with open(caminho, "xb") as arquivo:
                arquivo.write(bloco)
                arquivo.flush()
            return caminho, None
        except FileExistsError:
            numero += 1
        except OSError as erro:
            return caminho, erro


def operar_pauta_lixo(
    trecho, origem=None, caminho=None, instante=None,
    antes_de_reconferir=None, gravador=gravar_atomico,
):
    workspace = Path(caminho).expanduser().resolve() if caminho is not None else resolver()
    if workspace is None or not e_workspace(workspace):
        return 1, None
    workspace = Path(workspace).expanduser().resolve()
    pauta, leitura, erro = ler_pauta(workspace)
    if erro:
        return _falha(erro, workspace)
    dados, texto = leitura
    _, entrada, concluida, candidatas = localizar(texto, trecho, origem)
    if candidatas:
        pares = {(item["manchete"], item["origem"]) for item in candidatas}
        mensagem = (
            "As candidatas são indistinguíveis; diferencie o texto à mão."
            if len(pares) == 1
            else "Mais de uma entrada corresponde ao trecho; use --origem para desempatar."
        )
        return _falha(mensagem, workspace, candidatas=candidatas)
    if concluida:
        return _falha(
            "Essa entrada está concluída; ela fica como histórico da pauta e não vai pro lixo.",
            workspace, manchete=concluida["manchete"],
            origem_entrada=concluida["origem"],
        )
    if entrada is None:
        return _falha("Nenhuma entrada da pauta corresponde ao trecho.", workspace)
    lixo, erro = _validar_lixo(workspace)
    if erro:
        return _falha(
            erro, workspace, manchete=entrada["manchete"],
            origem_entrada=entrada["origem"],
        )
    inicio, fim = entrada["inicio_bytes"], entrada["fim_bytes"]
    bloco = dados[inicio:fim]
    restante = dados[:inicio] + dados[fim:]
    arquivo, erro = _gravar_exclusivo(lixo, _nome_base(instante), bloco)
    campos = {
        "item": arquivo,
        "identificador": arquivo.stem,
        "manchete": entrada["manchete"],
        "origem_entrada": entrada["origem"],
    }
    if erro:
        return _falha(
            f"O arquivo {arquivo.name} ficou incompleto no lixo; a pauta não mudou ({erro}).",
            workspace, **campos,
        )
    if antes_de_reconferir:
        antes_de_reconferir()
    try:
        atuais = pauta.read_bytes()
        if hashlib.sha256(atuais).digest() != hashlib.sha256(dados).digest():
            return _falha(
                "A pauta mudou desde a leitura; tente de novo.", workspace, **campos
            )
        gravador(pauta, restante)
    except OSError as erro_gravacao:
        return _falha(
            f"Pauta.md não pôde ser gravada ({erro_gravacao}); "
            f"{arquivo.name} permanece no lixo.", workspace, **campos,
        )
    return 0, envelope(
        "excluido", f"Movido pro lixo (recuperável): {arquivo.name}.",
        workspace, destino="lixo", **campos,
    )


def executar_pauta_lixo(trecho, origem=None, caminho=None, usar_json=False):
    explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None:
        return informar_indisponivel(
            usar_json=usar_json, incluir_item=True, extras=campos_nulos()
        )
    workspace = Path(workspace).expanduser().resolve()
    if not e_workspace(workspace):
        if not explicito:
            return informar_indisponivel(
                workspace, usar_json=usar_json, incluir_item=True,
                extras=campos_nulos(),
            )
        codigo, resultado = _falha(
            "O caminho não é um workspace do NeoPrumo.", workspace
        )
        emitir(resultado, usar_json, erro=True)
        return codigo
    codigo, resultado = operar_pauta_lixo(trecho, origem=origem, caminho=workspace)
    emitir(resultado, usar_json, erro=codigo != 0)
    return codigo
