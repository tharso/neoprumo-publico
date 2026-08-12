import configparser
import hashlib
import io
import json
import re
from datetime import date, datetime


CAMPOS = (
    "dominio", "execucao", "predicado", "politica", "confirmacao",
    "origem", "autorizada_em", "condicao", "nota",
)
PADRAO_REVISAO = re.compile(r"^revisao (\d{4}-\d{2}-\d{2})$")


def digital_bytes(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def digital_reautorizacao(regra):
    valores = [
        regra["dominio"], regra["execucao"], regra["predicado"],
        regra["politica"], regra.get("confirmacao", "por-alvo"),
        regra.get("condicao"),
    ]
    serializado = json.dumps(
        valores, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return digital_bytes(serializado)


def _endereco_valido(valor):
    return (
        valor.count("@") == 1
        and all(valor.split("@"))
        and not any(c.isspace() or c in "<>" for c in valor)
    )


def _dominio_valido(valor):
    return (
        bool(valor) and "@" not in valor and not valor.startswith(".")
        and not valor.endswith(".") and ".." not in valor
        and not any(c.isspace() or c in "<>" for c in valor)
    )


def decompor_predicado(regra):
    if regra.get("execucao") != "hibrida":
        return None
    partes = regra.get("predicado", "").split(":", 1)
    if len(partes) != 2:
        return None
    tipo, valor = (parte.strip() for parte in partes)
    if tipo == "remetente" and _endereco_valido(valor):
        return tipo, valor
    if tipo == "remetente-dominio" and _dominio_valido(valor):
        return tipo, valor
    if tipo == "assunto-contem" and valor:
        return tipo, valor
    return None


def _validar_regra(regra):
    problemas = []
    for campo in ("dominio", "execucao", "predicado", "politica", "origem"):
        if not regra.get(campo, "").strip():
            problemas.append(f"regra {regra['id']}: falta o campo {campo}")
    if regra.get("dominio") != "email":
        problemas.append(f"regra {regra['id']}: domínio desconhecido")
    if regra.get("execucao") not in ("semantica", "hibrida"):
        problemas.append(f"regra {regra['id']}: execução sem executor no v1")
    if regra.get("confirmacao", "por-alvo") not in ("por-alvo", "permanente"):
        problemas.append(f"regra {regra['id']}: confirmação desconhecida")
    if regra.get("execucao") == "hibrida" and decompor_predicado(regra) is None:
        problemas.append(f"regra {regra['id']}: predicado híbrido malformado")
    condicao = regra.get("condicao")
    if condicao:
        achado = PADRAO_REVISAO.fullmatch(condicao)
        try:
            if not achado:
                raise ValueError
            date.fromisoformat(achado.group(1))
        except ValueError:
            problemas.append(f"regra {regra['id']}: condição desconhecida")
    return problemas


def ler_ini(conteudo):
    avisos = []
    try:
        texto = conteudo.decode("utf-8") if isinstance(conteudo, bytes) else conteudo
    except UnicodeDecodeError:
        return {"parseia": False, "recusa": "O arquivo não é UTF-8 válido.", "avisos": []}
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        parser.read_string(texto)
    except configparser.Error as erro:
        return {"parseia": False, "recusa": f"O INI não parseia: {erro}.", "avisos": []}
    if parser.defaults():
        return {"parseia": True, "integral": False, "recusa": "A seção [DEFAULT] é proibida.", "avisos": []}
    versao = parser.get("configuracao", "versao", fallback="1").strip()
    if versao != "1":
        return {"parseia": True, "integral": False, "recusa": f"A versão {versao} não é aceita.", "avisos": []}
    regras, ids, colisoes = [], {}, set()
    for secao in parser.sections():
        if secao == "configuracao":
            for chave in parser[secao]:
                if chave != "versao":
                    avisos.append(f"Chave desconhecida em [configuracao]: {chave}.")
            continue
        if not secao.startswith("regra ") or not secao[6:].strip():
            avisos.append(f"Seção desconhecida [{secao}] ignorada; use [regra <id>] em minúsculas.")
            continue
        identificador = secao[6:].strip()
        if identificador in ids:
            colisoes.add(identificador)
        regra = {"id": identificador}
        for chave, valor in parser[secao].items():
            if chave in CAMPOS:
                regra[chave] = valor.strip()
            else:
                avisos.append(f"regra {identificador}: chave desconhecida {chave} ignorada.")
        regra.setdefault("confirmacao", "por-alvo")
        ids.setdefault(identificador, []).append(regra)
        regras.append(regra)
    validas = []
    for regra in regras:
        problemas = _validar_regra(regra)
        if regra["id"] in colisoes:
            problemas.append(f"regra {regra['id']}: id duplicado após aparar")
        if problemas:
            avisos.extend(problemas)
            regra.update(estado="recusada", motivo="; ".join(problemas))
        else:
            validas.append(regra)
    conflitos = _conflitos_estruturais(validas)
    for regra in validas:
        if regra["id"] in conflitos:
            regra.update(estado="em conflito", motivo="predicado idêntico com efeito divergente")
            avisos.append(f"regra {regra['id']}: conflito estrutural.")
    return {"parseia": True, "integral": True, "versao": versao,
            "regras": regras, "validas": validas, "avisos": avisos,
            "conflito_estrutural": bool(conflitos)}


def _efeito(regra):
    return tuple(regra.get(campo) for campo in ("politica", "confirmacao", "execucao", "condicao"))


def _conflitos_estruturais(regras):
    conflitos = set()
    for indice, primeira in enumerate(regras):
        p1 = decompor_predicado(primeira)
        if p1 is None:
            continue
        for segunda in regras[indice + 1:]:
            p2 = decompor_predicado(segunda)
            if p2 and (p1[0], p1[1].casefold()) == (p2[0], p2[1].casefold()) and _efeito(primeira) != _efeito(segunda):
                conflitos.update((primeira["id"], segunda["id"]))
    return conflitos


def canonizar(conteudo, mapa_base=None, hoje=None):
    leitura = ler_ini(conteudo)
    if not leitura.get("parseia") or not leitura.get("integral"):
        return leitura
    if leitura["conflito_estrutural"]:
        leitura["recusa"] = "Há conflito estrutural entre regras."
        return leitura
    mapa_base = {item["id"]: item for item in (mapa_base or [])}
    hoje = hoje or datetime.now().astimezone().date()
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser["configuracao"] = {"versao": "1"}
    mapa = []
    for regra in sorted(leitura["validas"], key=lambda item: item["id"]):
        digital = digital_reautorizacao(regra)
        anterior = mapa_base.get(regra["id"])
        autorizada = anterior["autorizada_em"] if anterior and anterior.get("digital_reautorizacao") == digital else hoje.isoformat()
        regra["autorizada_em"] = autorizada
        secao = {}
        for campo in CAMPOS:
            if campo in regra and regra[campo] != "":
                secao[campo] = regra[campo]
        parser[f"regra {regra['id']}"] = secao
        mapa.append({"id": regra["id"], "digital_reautorizacao": digital, "autorizada_em": autorizada})
    fluxo = io.StringIO(newline="")
    parser.write(fluxo, space_around_delimiters=True)
    canonico = fluxo.getvalue().rstrip("\n") + "\n"
    leitura.update(canonico=canonico, digital=digital_bytes(canonico.encode()), mapa=mapa)
    return leitura
