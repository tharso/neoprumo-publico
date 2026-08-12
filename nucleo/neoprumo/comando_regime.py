import hashlib
import stat
from pathlib import Path

from .ativo import e_workspace, informar_indisponivel, resolver
from .destinos_textuais import gravar_atomico
from .regimes import (
    PREFIXO_ABERTO,
    analisar_linha,
    data_valida,
    formatar_marcador,
    normalizar,
    origem_da_linha,
)
from .resultado_regime import campos_nulos, emitir, envelope, recusar


CONTRADICAO = (
    "Este item vence em {vence}, antes de acordar em {ate} — ele vai cobrar na "
    "abertura mesmo dormindo. Confirme com o dono e repita com --confirmado."
)


def _falha(mensagem, workspace, **campos):
    return 1, recusar(mensagem, workspace, **campos)


def _ler_pauta(workspace):
    pauta = workspace / "Pauta.md"
    try:
        estado = pauta.lstat()
        if not stat.S_ISREG(estado.st_mode):
            raise OSError("Pauta.md não é um arquivo regular")
        dados = pauta.read_bytes()
        texto = dados.decode("utf-8")
    except FileNotFoundError:
        return None, None, "Pauta.md não existe."
    except UnicodeDecodeError:
        return None, None, "Pauta.md não contém texto UTF-8."
    except OSError as erro:
        return None, None, f"Pauta.md não pôde ser lida ({erro})."
    return pauta, (dados, texto), None


def _entradas(texto, concluida=False):
    linhas = texto.splitlines(keepends=True)
    entradas = []
    for indice, linha_com_fim in enumerate(linhas):
        linha = linha_com_fim.rstrip("\r\n")
        leitura = analisar_linha(linha, concluida=concluida)
        prefixos = ("- [x] ", "- [X] ") if concluida else (PREFIXO_ABERTO,)
        if not linha.startswith(prefixos):
            continue
        origem = None
        for seguinte in linhas[indice + 1 :]:
            texto_seguinte = seguinte.rstrip("\r\n")
            if texto_seguinte.startswith(("- [ ]", "- [x]", "- [X]")):
                break
            origem = origem_da_linha(texto_seguinte) or origem
        entradas.append({**leitura, "indice": indice, "origem": origem})
    return linhas, entradas


def _localizar(texto, trecho, origem):
    alvo = normalizar(trecho)
    linhas, abertas = _entradas(texto)
    candidatas = [e for e in abertas if alvo in normalizar(e["manchete"])]
    if origem is not None:
        candidatas = [e for e in candidatas if e["origem"] == origem]
    if not candidatas:
        _, concluidas = _entradas(texto, concluida=True)
        concluidas = [e for e in concluidas if alvo in normalizar(e["manchete"])]
        if origem is not None:
            concluidas = [e for e in concluidas if e["origem"] == origem]
        if concluidas:
            return linhas, None, concluidas[0], []
        return linhas, None, None, []
    if len(candidatas) > 1:
        exibidas = [
            {"manchete": e["manchete"], "origem": e["origem"]}
            for e in candidatas
        ]
        return linhas, None, None, exibidas
    return linhas, candidatas[0], None, []


def _validar_flags(regime, ate, vence, sem_prazo, confirmado, atual=None):
    if ate and regime != "dormindo":
        return "--ate só pode ser usado com o regime dormindo."
    if vence and sem_prazo:
        return "--vence e --sem-prazo não podem ser usados juntos."
    if ate and not data_valida(ate):
        return "A data de acordar precisa existir e usar AAAA-MM-DD."
    if vence and not data_valida(vence):
        return "A data de prazo precisa existir e usar AAAA-MM-DD."
    if regime == "dormindo" and not ate:
        ja_dormindo = atual and atual.get("nome") == "dormindo"
        if not ja_dormindo:
            return "Dormir exige a data de acordar: use --ate."
    if regime is None and vence is None and not sem_prazo:
        return "Nada a mudar: informe um regime, --vence ou --sem-prazo."
    return None


def _novo_estado(entrada, regime, ate, vence, sem_prazo):
    atual = entrada["regime"]
    nomes = {"a-vista": "a_vista", "em-espera": "em_espera"}
    if regime == "normal":
        novo_regime = None
    elif regime == "dormindo":
        novo_regime = {"nome": "dormindo", "ate": ate or atual["ate"]}
    elif regime:
        novo_regime = {"nome": nomes[regime], "ate": None}
    else:
        novo_regime = atual
    novo_vence = None if sem_prazo else (vence or entrada["vence"])
    return novo_regime, novo_vence


def operar_regime(
    trecho, regime=None, ate=None, vence=None, sem_prazo=False,
    confirmado=False, origem=None, caminho=None, antes_de_reconferir=None,
):
    explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None:
        return 1, None
    workspace = Path(workspace).expanduser().resolve()
    if not e_workspace(workspace):
        return 1, None
    pauta, leitura, erro = _ler_pauta(workspace)
    if erro:
        return _falha(erro, workspace)
    dados, texto = leitura
    digital_inicial = hashlib.sha256(dados).digest()
    linhas, entrada, concluida, candidatas = _localizar(texto, trecho, origem)
    if candidatas:
        pares = {(c["manchete"], c["origem"]) for c in candidatas}
        mensagem = (
            "As candidatas são indistinguíveis; diferencie o texto à mão."
            if len(pares) == 1
            else "Mais de uma entrada corresponde ao trecho; use --origem para desempatar."
        )
        return _falha(mensagem, workspace, candidatas=candidatas)
    if concluida:
        return _falha(
            "Essa entrada está concluída e não pode ser alterada.", workspace,
            manchete=concluida["manchete"], origem=concluida["origem"],
        )
    if entrada is None:
        return _falha("Nenhuma entrada da pauta corresponde ao trecho.", workspace)
    falha = _validar_flags(regime, ate, vence, sem_prazo, confirmado, entrada["regime"])
    if falha:
        return _falha(falha, workspace)
    novo_regime, novo_vence = _novo_estado(entrada, regime, ate, vence, sem_prazo)
    contraditorio = (
        novo_regime and novo_regime["nome"] == "dormindo" and novo_vence
        and novo_vence < novo_regime["ate"]
    )
    if contraditorio and not confirmado:
        return _falha(
            CONTRADICAO.format(vence=novo_vence, ate=novo_regime["ate"]), workspace
        )
    if confirmado and not contraditorio:
        return _falha("Não há o que confirmar.", workspace)
    antiga = {"regime": entrada["regime"], "vence": entrada["vence"]}
    fim = linhas[entrada["indice"]][len(linhas[entrada["indice"]].rstrip("\r\n")):]
    linhas[entrada["indice"]] = (
        PREFIXO_ABERTO + entrada["manchete"]
        + formatar_marcador(novo_regime, novo_vence) + fim
    )
    novo = "".join(linhas).encode("utf-8")
    if antes_de_reconferir:
        antes_de_reconferir()
    try:
        atuais = pauta.read_bytes()
        if hashlib.sha256(atuais).digest() != digital_inicial:
            return _falha("A pauta mudou desde a leitura; tente de novo.", workspace)
        gravar_atomico(pauta, novo)
    except OSError as erro_gravacao:
        return _falha(f"Pauta.md não pôde ser gravada ({erro_gravacao}).", workspace)
    acoes = []
    if contraditorio:
        acoes.append("O dono confirmou que o prazo cobra antes de o item acordar.")
    return 0, envelope(
        "ajustado", f"Regime ajustado: {entrada['manchete']}.", workspace,
        acoes=acoes, manchete=entrada["manchete"], origem=entrada["origem"],
        regime=novo_regime, vence=novo_vence, anterior=antiga,
    )


def executar_regime(**opcoes):
    usar_json = opcoes.pop("usar_json", False)
    caminho = opcoes.get("caminho")
    explicito = caminho is not None
    workspace = Path(caminho).expanduser().resolve() if explicito else resolver()
    if workspace is None:
        return informar_indisponivel(usar_json=usar_json, extras=campos_nulos())
    if not e_workspace(workspace) and not explicito:
        return informar_indisponivel(workspace, usar_json=usar_json, extras=campos_nulos())
    codigo, resultado = operar_regime(**opcoes)
    if resultado is None:
        codigo, resultado = _falha("O caminho não é um workspace do NeoPrumo.", workspace)
    emitir(resultado, usar_json, erro=codigo != 0)
    return codigo
