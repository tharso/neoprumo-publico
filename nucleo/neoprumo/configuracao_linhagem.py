import json
import stat
from pathlib import Path

from .configuracao_modelo import digital_bytes, digital_reautorizacao, ler_ini


PUBLICADORAS = {"publicado", "publicacao incompleta"}
PAYLOADS = {"candidato", "pre-image", "proposta-original", "rejeitada", "participante"}


def casa_linhagem(workspace):
    return Path(workspace) / ".neoprumo" / "configuracao" / "linhagem"


def _json(caminho):
    try:
        if not stat.S_ISREG(caminho.lstat().st_mode):
            return None
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _schema(registro):
    if not isinstance(registro, dict) or registro.get("registro") != 1:
        return False
    if registro.get("gesto") not in ("gravar", "adotar", "rejeitar", "defaults", "restaurar", "resolver", "snapshot-conflito"):
        return False
    publicacao = registro.get("publicacao")
    if not isinstance(publicacao, dict) or publicacao.get("status") not in ("publicado", "publicacao incompleta", "nao publica", "recuperacao promovida"):
        return False
    if registro["gesto"] == "snapshot-conflito":
        return "regras" not in registro and publicacao["status"] == "nao publica"
    if not isinstance(registro.get("regras"), list):
        return False
    if registro["gesto"] == "rejeitar" and not isinstance(registro.get("destino"), dict):
        return False
    destino = registro.get("destino", {}).get("tipo")
    origem = registro.get("origem_restauracao")
    if (registro["gesto"] == "restaurar" or destino == "artefato") != isinstance(origem, dict):
        return False
    return True


def _mapa_valido(registro, pasta, artefatos_presentes):
    if registro["gesto"] == "snapshot-conflito":
        return True
    mapa = registro["regras"]
    if any(not isinstance(item, dict) for item in mapa):
        return False
    ids = [item.get("id") for item in mapa if isinstance(item, dict)]
    if len(ids) != len(set(ids)) or any(not isinstance(item.get("digital_reautorizacao"), str) or not isinstance(item.get("autorizada_em"), str) for item in mapa if isinstance(item, dict)):
        return False
    candidato = next((item for item in registro.get("artefatos", []) if item.get("tipo") == "candidato"), None)
    if not candidato or candidato["arquivo"] not in artefatos_presentes:
        return True
    try:
        leitura = ler_ini((pasta / candidato["arquivo"]).read_bytes())
    except OSError:
        return False
    if not leitura.get("integral"):
        return False
    regras = leitura["validas"]
    esperado = {r["id"]: (digital_reautorizacao(r), r.get("autorizada_em")) for r in regras}
    recebido = {item["id"]: (item["digital_reautorizacao"], item["autorizada_em"]) for item in mapa}
    return esperado == recebido


def inspecionar_gravacao(pasta, staging=False):
    registro = _json(pasta / "registro.json")
    if not _schema(registro):
        return {"id": pasta.name.removesuffix(".preparando"), "pasta": pasta,
                "registro": registro, "saude": "inválida", "staging": staging,
                "payloads_ausentes": [], "artefatos_validos": []}
    declarados = {item.get("arquivo"): item for item in registro.get("artefatos", []) if isinstance(item, dict) and item.get("tipo") in PAYLOADS}
    presentes, validos, divergentes = set(), [], []
    for nome, item in declarados.items():
        caminho = pasta / str(nome)
        try:
            if stat.S_ISREG(caminho.lstat().st_mode):
                presentes.add(nome)
                if digital_bytes(caminho.read_bytes()) == item.get("digital"):
                    validos.append({"tipo": item["tipo"], "arquivo": nome, "digital": item["digital"]})
                else:
                    divergentes.append(nome)
        except OSError:
            pass
    poda = _json(pasta / "poda.json") if (pasta / "poda.json").exists() else None
    removidos = set()
    poda_invalida = False
    if (pasta / "poda.json").exists():
        if not isinstance(poda, dict) or poda.get("poda") != 1 or not isinstance(poda.get("payloads_removidos"), list):
            poda_invalida = True
        else:
            entradas = poda["payloads_removidos"]
            nomes = [item.get("arquivo") for item in entradas if isinstance(item, dict)]
            poda_invalida = len(nomes) != len(set(nomes))
            for item in entradas:
                nome = item.get("arquivo") if isinstance(item, dict) else None
                if nome not in declarados or item.get("digital") != declarados[nome].get("digital"):
                    poda_invalida = True
                removidos.add(nome)
    ausentes = set(declarados) - presentes
    if divergentes or poda_invalida or not _mapa_valido(registro, pasta, presentes):
        saude = "inválida"
    elif any(nome not in removidos for nome in ausentes):
        saude = "incompleta em observação"
    elif poda is None:
        saude = "completa"
    elif presentes:
        saude = "poda parcial"
    elif removidos == set(declarados):
        saude = "podada"
    else:
        saude = "poda parcial"
    return {"id": pasta.name.removesuffix(".preparando"), "pasta": pasta,
            "registro": registro, "saude": saude, "staging": staging,
            "payloads_ausentes": sorted(ausentes), "artefatos_validos": validos}


def inspecionar_linhagem(workspace):
    casa = casa_linhagem(workspace)
    finais, stagings = [], []
    try:
        modo = casa.lstat().st_mode
        if not stat.S_ISDIR(modo) or stat.S_ISLNK(modo):
            raise OSError("a linhagem não é um diretório real")
        entradas = list(casa.iterdir())
    except FileNotFoundError:
        return finais, stagings
    except OSError:
        return [{"id": "linhagem", "registro": None, "saude": "inválida", "staging": False,
                 "payloads_ausentes": [], "artefatos_validos": [], "pasta": casa}], []
    for pasta in entradas:
        try:
            if not stat.S_ISDIR(pasta.lstat().st_mode):
                continue
        except OSError:
            continue
        if pasta.name.endswith(".preparando"):
            stagings.append(inspecionar_gravacao(pasta, True))
        else:
            finais.append(inspecionar_gravacao(pasta))
    return finais, stagings


def _participantes(gravações):
    return {g["id"]: g for g in gravações if g["registro"] is not None}


def _ancestrais(identificador, mapa):
    vistos, atual = set(), identificador
    while atual in mapa:
        anterior = mapa[atual]["registro"].get("anterior")
        if anterior is None:
            return vistos, False
        if anterior in vistos or anterior == identificador:
            return vistos, True
        vistos.add(anterior)
        atual = anterior
    return vistos, False


def analisar_grafo(gravacoes):
    mapa = _participantes(gravacoes)
    ciclos = set()
    ancestrais = {}
    for identificador in mapa:
        ancestrais[identificador], ciclo = _ancestrais(identificador, mapa)
        if ciclo:
            ciclos.add(identificador)
    publicadas = {i for i, g in mapa.items() if g["registro"]["publicacao"]["status"] == "publicado"}
    cabecas = sorted(i for i in publicadas if not any(i in ancestrais[p] for p in publicadas if p != i))
    admissiveis = set()
    mudanca = True
    while mudanca:
        mudanca = False
        for i, g in mapa.items():
            if g["registro"]["publicacao"]["status"] != "publicacao incompleta" or i in admissiveis:
                continue
            pai = g["registro"].get("anterior")
            if pai is None or pai in publicadas or pai in admissiveis:
                admissiveis.add(i); mudanca = True
    encerrados = set()
    for elo in admissiveis:
        pai = mapa[elo]["registro"].get("anterior")
        if any(elo in ancestrais[p] for p in publicadas):
            encerrados.add(elo); continue
        if pai and any(p != pai and pai in ancestrais[p] and elo not in ancestrais[p] for p in publicadas):
            encerrados.add(elo)
    return {"mapa": mapa, "cabecas": cabecas, "admissiveis": admissiveis,
            "encerrados": encerrados, "ciclos": ciclos, "ancestrais": ancestrais}


def candidato(gravação):
    artefato = next((a for a in gravação["artefatos_validos"] if a["tipo"] == "candidato"), None)
    return gravação["pasta"] / artefato["arquivo"] if artefato else None
