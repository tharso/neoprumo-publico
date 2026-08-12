from pathlib import Path

from .configuracao_avaliar import dominancias, estado_regra
from .configuracao_fisica import participantes, real
from .configuracao_linhagem import analisar_grafo, candidato, inspecionar_linhagem
from .configuracao_modelo import digital_bytes, ler_ini


def _ler(caminho):
    try:
        return caminho.read_bytes(), None
    except OSError as erro:
        return None, str(erro)


def _digital_candidata(gravação):
    caminho = candidato(gravação)
    if caminho:
        try:
            return digital_bytes(caminho.read_bytes())
        except OSError:
            pass
    registro = gravação.get("registro") or {}
    item = next((a for a in registro.get("artefatos", []) if a.get("tipo") == "candidato"), None)
    return item.get("digital") if item else None


def _fontes(finais, stagings):
    fontes = []
    for gravação in finais + stagings:
        if gravação["artefatos_validos"]:
            fontes.append({"gravacao": gravação["pasta"].name if gravação["staging"] else gravação["id"],
                           "artefatos": gravação["artefatos_validos"]})
    return fontes


def _aviso_staging(staging, finais):
    recuperavel = "completo e verificável" if staging["saude"] == "completa" else "parcial"
    preservadas = {
        artefato["digital"]
        for gravação in finais
        for artefato in gravação["artefatos_validos"]
    }
    digitais = {artefato["digital"] for artefato in staging["artefatos_validos"]}
    descartavel = (
        staging["saude"] == "completa"
        and bool(digitais)
        and digitais <= preservadas
    )
    conclusão = (
        "descartável: cada byte relevante já existe em outra gravação identificada"
        if descartavel
        else "contém bytes não preservados em outro lugar"
    )
    return f"Staging abandonado {staging['pasta'].name}: {recuperavel}; {conclusão}."


def _ausencia(finais, stagings, grafo):
    publicadas = [g for g in finais if g.get("registro") and g["registro"]["publicacao"]["status"] == "publicado"]
    restauraveis = [g for g in publicadas if candidato(g)]
    autorizados = [g for g in finais if g["id"] in grafo["admissiveis"] and candidato(g)]
    autorizados += [g for g in stagings if g["saude"] == "completa" and candidato(g)]
    historicos = []
    for gravação in finais:
        status = (gravação.get("registro") or {}).get("publicacao", {}).get("status")
        for artefato in gravação["artefatos_validos"]:
            if artefato["tipo"] != "candidato" or status == "recuperacao promovida":
                historicos.append(artefato)
    if not finais and not stagings:
        return "nunca configurada", []
    if restauraveis:
        acoes = ["Restaure a versão vigente preservada com configuracao restaurar."]
        if autorizados:
            acoes.append("Recupere o candidato autorizado incompleto, sem alegar que chegou a vigorar.")
        return "conhecida agora ausente", acoes
    if autorizados:
        return "ausente com candidato autorizado não publicado", ["Recupere o candidato autorizado pelo rito, sem alegar que chegou a vigorar."]
    if historicos:
        return "ausente com cópia histórica recuperável", ["Restaure com --artefato uma fonte apenas histórica; ela não prova vigência nem autorização."]
    return "ausente sem fonte recuperável", ["A configuração existiu; nenhuma cópia recuperável restou. Grave uma nova ou use defaults."]


def observar(workspace):
    workspace = Path(workspace)
    ini, irmas, parecidas = participantes(workspace)
    avisos = [f"{nome} não é reconhecido como conflito." for nome in parecidas]
    finais, stagings = inspecionar_linhagem(workspace)
    grafo = analisar_grafo(finais)
    invalidas = [g for g in finais if g["saude"] == "inválida"]
    contaminantes = [g for g in invalidas if g.get("registro") and g["registro"]["publicacao"]["status"] in ("publicado", "publicacao incompleta")]
    if grafo["ciclos"]:
        contaminantes.extend(grafo["mapa"][i] for i in grafo["ciclos"] if i in grafo["mapa"])
    if irmas:
        estado = "conflito pendente"
    elif contaminantes or any(g.get("registro") is None for g in invalidas):
        estado = "autoridade ambígua"
    elif not ini.exists():
        estado, acoes = _ausencia(finais, stagings, grafo)
    elif not real(ini):
        estado, acoes = "não parseia", ["Substitua o atalho ou objeto pelo arquivo regular esperado."]
        avisos.append("Configuracao.ini precisa ser arquivo regular e nunca pode ser atalho.")
    else:
        acoes = []
        bytes_ini, erro = _ler(ini)
        leitura = ler_ini(bytes_ini) if bytes_ini is not None else {"parseia": False, "recusa": erro, "avisos": []}
        digital = digital_bytes(bytes_ini) if bytes_ini is not None else None
        observadas = sorted(i for i in grafo["admissiveis"] - grafo["encerrados"] if _digital_candidata(grafo["mapa"][i]) == digital)
        cabeças_casadas = [i for i in grafo["cabecas"] if _digital_candidata(grafo["mapa"][i]) == digital]
        if observadas:
            estado = "vigente por autorização observada"
            avisos.append("A gravação " + ", ".join(observadas) + " terminou sem confirmação; os bytes conferem.")
        elif cabeças_casadas:
            estado = "vigente"
        elif finais:
            estado = "proposta pendente" if leitura.get("parseia") else "proposta inválida"
            acoes = ["Adote ou rejeite a edição manual pendente."]
        elif not leitura.get("parseia"):
            estado = "não parseia"
        elif not leitura.get("integral"):
            estado = "recusada integral"
        else:
            estado = "defaults" if not leitura.get("validas") else "vigente com aviso" if leitura.get("avisos") else "vigente"
        avisos.extend(leitura.get("avisos", []))
    if irmas:
        acoes = ["Resolva o conflito com configuracao resolver."]
    elif contaminantes:
        acoes = ["Reautorize via adotar ou restaure uma gravação íntegra."]
    for staging in stagings:
        avisos.append(_aviso_staging(staging, finais))
    leitura_final = ler_ini(ini.read_bytes()) if ini.exists() and real(ini) else {"validas": []}
    regras = []
    for regra in leitura_final.get("regras", []):
        item = {campo: regra.get(campo) for campo in
                ("id", "dominio", "execucao", "predicado", "politica",
                 "confirmacao", "origem", "autorizada_em", "condicao", "nota")}
        item.update({chave: regra[chave] for chave in ("estado", "motivo") if chave in regra})
        item.setdefault("estado", estado_regra(item))
        item.setdefault("motivo", None)
        regras.append(item)
    vigentes = []
    if ini.exists() and real(ini):
        digital_ini = digital_bytes(ini.read_bytes())
        vigentes = [i for i in grafo["cabecas"] if _digital_candidata(grafo["mapa"][i]) == digital_ini]
    return {"estado": estado, "avisos": avisos, "acoes": acoes,
            "leitura": leitura_final, "ini": ini, "irmas": irmas,
            "finais": finais, "stagings": stagings, "grafo": grafo,
            "regras": regras, "dominancias": dominancias([r for r in regras if r.get("estado") == "ativa"]),
            "linhagem": {"cabecas": grafo["cabecas"], "vigente": vigentes[0] if len(vigentes) == 1 else None,
                "incompletas_observadas": sorted(grafo["admissiveis"] - grafo["encerrados"]),
                "podadas": sum(g["saude"] == "podada" for g in finais),
                "incompletas_em_observacao": [{"id": g["id"], "payloads_ausentes": g["payloads_ausentes"]} for g in finais if g["saude"] == "incompleta em observação"],
                "pais_ausentes": [{"filho": g["id"], "anterior": g["registro"].get("anterior")} for g in finais if g.get("registro") and g["registro"].get("anterior") and g["registro"].get("anterior") not in grafo["mapa"]],
                "invalidas": len(invalidas), "staging": [{"nome": g["pasta"].name, "recuperavel": "completo" if g["saude"] == "completa" else "parcial"} for g in stagings],
                "fontes_de_restauracao": _fontes(finais, stagings)}}


def bases(estado, sob_pendencia=False):
    grafo = estado["grafo"]
    if sob_pendencia:
        return sorted(set(grafo["cabecas"]) | (grafo["admissiveis"] - grafo["encerrados"]))
    try:
        conteudo = estado["ini"].read_bytes()
    except OSError:
        conteudo = None
    return bases_para_bytes(estado, conteudo)


def bases_para_bytes(estado, conteudo):
    grafo = estado["grafo"]
    if conteudo is None:
        return sorted(grafo["cabecas"])
    digital = digital_bytes(conteudo)
    observadas = sorted(
        i for i in grafo["admissiveis"] - grafo["encerrados"]
        if _digital_candidata(grafo["mapa"][i]) == digital
    )
    if observadas:
        return observadas
    cabeças = sorted(
        i for i in grafo["cabecas"]
        if _digital_candidata(grafo["mapa"][i]) == digital
    )
    return cabeças or sorted(grafo["cabecas"])
