import os
import re
import stat
from datetime import datetime

from .assunto_base import conferir_prateleira, entradas_de_ficha, tem_controle
from .assunto_ficha import ler_ficha
from .diario_leitura import observar_diario
from .diario_resultado import LIMITACOES, campos_vazios, emitir, envelope
from .pauta_entradas import entradas, ler_pauta
from .regimes import data_valida
from .seed import PADRAO_NOME, _data_pelo_nome


RODAPE = re.compile(
    r"^\s+— (inbox|acervo) ([^,\x00-\x1f\x7f]+), "
    r"(despachado|incluído) em (\d{4}-\d{2}-\d{2})$"
)


def _rodape(entrada):
    corpo = [linha.rstrip("\r\n") for linha in entrada["corpo"]]
    candidatas = [
        (indice, linha) for indice, linha in enumerate(corpo)
        if linha.lstrip().startswith(("— inbox ", "— acervo "))
    ]
    if not candidatas:
        return "ausente", None
    if len(candidatas) != 1 or candidatas[0][0] != len(corpo) - 1:
        return "malformado", None
    casamento = RODAPE.fullmatch(candidatas[0][1])
    if casamento is None:
        return "malformado", None
    morada, nome, verbo, dia = casamento.groups()
    esperado = "despachado" if morada == "inbox" else "incluído"
    if verbo != esperado or tem_controle(nome) or not data_valida(dia):
        return "malformado", None
    return "valido", {"origem": f"{morada} {nome}", "dia": dia}


def _colher_pauta(workspace, dia):
    _, leitura, falha = ler_pauta(workspace, mensagens_seed=True)
    if falha:
        return [], [falha]
    _, abertas = entradas(leitura[1], concluida=False)
    _, concluidas = entradas(leitura[1], concluida=True)
    fatos, problemas = [], []
    for entrada in sorted(abertas + concluidas, key=lambda item: item["indice"]):
        estado, origem = _rodape(entrada)
        problemas.extend(entrada["problemas"])
        if estado == "malformado":
            problemas.append(
                f"{entrada['manchete']}: o rodapé de origem está malformado; a entrada ficou fora do diário."
            )
        if estado != "valido" or origem["dia"] != dia:
            continue
        fatos.append({
            "manchete": entrada["manchete"],
            "origem": origem["origem"],
            "concluida": entrada in concluidas,
            "regime": entrada["regime"],
            "vence": entrada["vence"],
        })
    return fatos, problemas


def _colher_assuntos(workspace, dia):
    pasta, falha = conferir_prateleira(workspace)
    if falha:
        return [], [falha]
    caminhos, _, problemas = entradas_de_ficha(pasta)
    fatos = []
    for caminho in caminhos:
        ficha, falha = ler_ficha(caminho)
        if falha:
            problemas.append(falha)
            continue
        problemas.extend(ficha["problemas"])
        for nota in ficha["notas"]:
            if nota["data"] == dia:
                fatos.append({
                    "assunto": ficha["id"], "nome": ficha["nome"],
                    "origem": nota["origem"],
                    "texto": nota["texto"].split("\n", 1)[0],
                })
    return fatos, problemas


def _motivo(erro):
    return erro.strerror or str(erro)


def _colher_morada(workspace, nome_morada, dia):
    pasta = workspace / nome_morada
    try:
        modo = pasta.lstat().st_mode
        if stat.S_ISLNK(modo) or not stat.S_ISDIR(modo):
            return [], [f"{nome_morada}: precisa ser uma pasta real e não será seguida."]
        fatos, problemas = [], []
        with os.scandir(pasta) as itens:
            for item in itens:
                if item.name.startswith("."):
                    continue
                try:
                    item.name.encode("utf-8")
                    modo_item = item.stat(follow_symlinks=False).st_mode
                except UnicodeEncodeError:
                    continue
                except OSError as erro:
                    problemas.append(
                        f"{nome_morada}: não foi possível observar {item.name} ({_motivo(erro)})."
                    )
                    continue
                if not stat.S_ISREG(modo_item):
                    continue
                if not PADRAO_NOME.fullmatch(os.path.splitext(item.name)[0]):
                    continue
                data = _data_pelo_nome(item.name)
                if data is not None and data.isoformat() == dia:
                    fatos.append({"morada": nome_morada.casefold(), "nome": item.name})
        return fatos, problemas
    except FileNotFoundError:
        return [], [f"{nome_morada}: não existe."]
    except OSError as erro:
        return [], [f"{nome_morada}: não pôde ser lida ({_motivo(erro)})."]


def colher(workspace, instante=None):
    referencia = instante or datetime.now().astimezone()
    dia = referencia.date().isoformat()
    pauta, problemas_pauta = _colher_pauta(workspace, dia)
    assuntos, problemas_assuntos = _colher_assuntos(workspace, dia)
    inbox, problemas_inbox = _colher_morada(workspace, "Inbox", dia)
    acervo, problemas_acervo = _colher_morada(workspace, "Acervo", dia)
    capturas = sorted(inbox + acervo, key=lambda item: item["nome"])
    diario, problemas_diario = observar_diario(workspace, dia)
    problemas = (
        problemas_pauta + problemas_assuntos + problemas_inbox
        + problemas_acervo + problemas_diario
    )
    return envelope(
        "fatos", "Fatos do dia colhidos.", workspace, problemas,
        dia=dia, pauta=pauta, assuntos=assuntos, capturas=capturas,
        total=len(pauta) + len(assuntos) + len(capturas),
        limitacoes=LIMITACOES, diario=diario,
    )


def indisponivel_extras():
    return campos_vazios()


def executar_colher(workspace, usar_json=False):
    resultado = colher(workspace)
    emitir(resultado, usar_json)
    return 0
