from datetime import date, datetime

from .configuracao_modelo import decompor_predicado


def _payload(regra):
    campos = ("id", "dominio", "execucao", "predicado", "politica",
              "confirmacao", "origem", "autorizada_em", "condicao", "nota")
    return {campo: regra.get(campo) for campo in campos}


def estado_regra(regra, hoje=None):
    if regra.get("estado") in ("recusada", "em conflito"):
        return regra["estado"]
    condicao = regra.get("condicao")
    hoje = hoje or datetime.now().astimezone().date()
    if condicao and date.fromisoformat(condicao.split(" ", 1)[1]) <= hoje:
        return "pede revisão"
    return "ativa"


def casa(regra, alvo):
    predicado = decompor_predicado(regra)
    if not predicado:
        return False
    tipo, valor = predicado
    valor = valor.casefold()
    remetente = alvo["remetente"].casefold()
    if tipo == "remetente":
        return remetente == valor
    if tipo == "remetente-dominio":
        dominio = remetente.rsplit("@", 1)[1]
        return dominio == valor or dominio.endswith("." + valor)
    return valor in alvo["assunto"].casefold()


def domina(primeira, segunda):
    p1, p2 = decompor_predicado(primeira), decompor_predicado(segunda)
    if not p1 or not p2:
        return False
    t1, v1 = p1[0], p1[1].casefold()
    t2, v2 = p2[0], p2[1].casefold()
    if t1 == "remetente" and t2 == "remetente-dominio":
        dominio = v1.rsplit("@", 1)[1]
        return dominio == v2 or dominio.endswith("." + v2)
    if t1 == t2 == "remetente-dominio":
        return v1 != v2 and v1.endswith("." + v2)
    return False


def dominancias(regras):
    return [
        {"domina": a["id"], "dominada": b["id"]}
        for a in regras for b in regras if a is not b and domina(a, b)
    ]


def _efeito(regra):
    return {campo: regra.get(campo) for campo in
            ("politica", "confirmacao", "execucao", "condicao")}


def _problemas_entrada(entrada):
    if not isinstance(entrada, dict):
        return ["A entrada precisa ser um objeto JSON."]
    problemas = []
    desconhecidas = set(entrada) - {"dominio", "alvos"}
    if desconhecidas:
        problemas.append("Chaves desconhecidas: " + ", ".join(sorted(desconhecidas)) + ".")
    if entrada.get("dominio") != "email":
        problemas.append("dominio precisa ser email.")
    alvos = entrada.get("alvos")
    if not isinstance(alvos, list):
        return problemas + ["alvos precisa ser uma lista."]
    vistos = set()
    for indice, alvo in enumerate(alvos):
        prefixo = f"alvos[{indice}]"
        if not isinstance(alvo, dict):
            problemas.append(f"{prefixo} precisa ser um objeto.")
            continue
        extras = set(alvo) - {"id", "remetente", "assunto"}
        if extras:
            problemas.append(f"{prefixo} tem chaves desconhecidas: {', '.join(sorted(extras))}.")
        identificador = alvo.get("id")
        if not isinstance(identificador, str) or not identificador:
            problemas.append(f"{prefixo}.id precisa ser texto não vazio.")
        elif identificador in vistos:
            problemas.append(f"{prefixo}.id está duplicado: {identificador}.")
        else:
            vistos.add(identificador)
        remetente = alvo.get("remetente")
        if not isinstance(remetente, str) or remetente.count("@") != 1 or not all(remetente.split("@")) or any(c.isspace() or c in "<>" for c in remetente):
            problemas.append(f"{prefixo}.remetente precisa ser um endereço puro válido.")
        if not isinstance(alvo.get("assunto"), str):
            problemas.append(f"{prefixo}.assunto precisa ser texto.")
        for obrigatoria in ("id", "remetente", "assunto"):
            if obrigatoria not in alvo:
                problemas.append(f"{prefixo}: falta {obrigatoria}.")
    return problemas


def avaliar(entrada, regras, hoje=None):
    problemas = _problemas_entrada(entrada)
    if problemas:
        return None, problemas
    hoje = hoje or datetime.now().astimezone().date()
    ativas = [r for r in regras if estado_regra(r, hoje) == "ativa"]
    semanticas = [r for r in ativas if r["execucao"] == "semantica"]
    suspensas_semanticas = [r for r in regras if r["execucao"] == "semantica" and estado_regra(r, hoje) != "ativa"]
    resultados = []
    for alvo in entrada["alvos"]:
        casadas = [r for r in ativas if r["execucao"] == "hibrida" and casa(r, alvo)]
        maximas = [r for r in casadas if not any(domina(outra, r) for outra in casadas if outra is not r)]
        efeitos = {_chave_efeito(r) for r in maximas}
        efetiva = None
        conflito = []
        if len(efeitos) == 1 and maximas:
            efetiva = {"regras": [r["id"] for r in maximas], **_efeito(maximas[0])}
        elif len(efeitos) > 1:
            conflito = [_payload(r) for r in maximas]
        suspensas = []
        for regra in regras:
            if regra["execucao"] == "hibrida" and estado_regra(regra, hoje) != "ativa" and casa(regra, alvo):
                suspensas.append({**_payload(regra), "estado": estado_regra(regra, hoje),
                                  "dominaria": any(domina(regra, ativa) for ativa in casadas)})
        resultados.append({"id": alvo["id"], "casadas": [_payload(r) for r in casadas],
                           "efetiva": efetiva, "conflito": conflito,
                           "suspensas_que_casariam": suspensas})
    return {"alvos": resultados,
            "semanticas_ativas": [_payload(r) for r in semanticas],
            "suspensas_semanticas": [{**_payload(r), "estado": estado_regra(r, hoje)} for r in suspensas_semanticas]}, []


def _chave_efeito(regra):
    return tuple(regra.get(campo) for campo in ("politica", "confirmacao", "execucao", "condicao"))
