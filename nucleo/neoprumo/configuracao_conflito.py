import json
import os
import sys

from .configuracao_base import emitir, envelope, recusar, workspace_resolvido
from .configuracao_estado import bases_para_bytes, observar
from .configuracao_lock import LockOcupado, lock_configuracao
from .configuracao_modelo import canonizar, digital_bytes
from .configuracao_operacoes import escolher_candidatas, mapa_base
from .configuracao_recibo import token, validar_envelope
from .configuracao_rito import agora_local, publicar
from .configuracao_linhagem import casa_linhagem, inspecionar_gravacao


def _classes(estado, base):
    grupos = {}
    for caminho in [estado["ini"], *estado["irmas"]]:
        try: conteudo = caminho.read_bytes()
        except OSError: continue
        digital = digital_bytes(conteudo)
        grupos.setdefault(digital, {"bytes": conteudo, "nomes": []})["nomes"].append(caminho.name)
    classes = []
    for digital, grupo in sorted(grupos.items()):
        projeção = canonizar(grupo["bytes"], mapa_base(estado, base))
        classes.append({"digital": digital, "nomes": sorted(grupo["nomes"]), "bytes": grupo["bytes"],
                        "projecao": None if projeção.get("recusa") else projeção})
    return classes


def fotografar(workspace, estado, base):
    casa = casa_linhagem(workspace); casa.mkdir(parents=True, exist_ok=True)
    instante = agora_local()
    import secrets
    nome = instante.strftime("%Y-%m-%d-%H%M%S") + "-" + secrets.token_hex(16)
    staging = casa / (nome + ".preparando"); staging.mkdir()
    classes = _classes(estado, base)
    artefatos = []
    for indice, classe in enumerate(classes, 1):
        arquivo = f"participante-{indice}.ini"
        (staging / arquivo).write_bytes(classe["bytes"])
        item = {"arquivo": arquivo, "tipo": "participante", "digital": classe["digital"], "nomes_originais": classe["nomes"]}
        if classe["projecao"]: item["digital_canonica_projetada"] = classe["projecao"]["digital"]
        artefatos.append(item)
    composição = [c["digital"] for c in classes]
    registro = {"registro": 1, "gesto": "snapshot-conflito", "autorizada_em": instante.isoformat(),
                "anterior": base, "publicacao": {"status": "nao publica"},
                "artefatos": artefatos, "composicao": composição}
    (staging / "registro.json").write_text(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.rename(staging, casa / nome)
    recibos = []
    for classe in classes:
        if not classe["projecao"]: continue
        decisão = {"gesto": "resolver", "workspace": str(workspace.resolve()), "cabeca": base,
                   "avisos_de_risco": [], "snapshot": nome, "composicao": composição,
                   "digital_classe": classe["digital"], "digital_canonica_projetada": classe["projecao"]["digital"]}
        recibos.append({"digital": classe["digital"], "nomes": classe["nomes"], "decisao": decisão,
                        "token": token(decisão), "canonico": classe["projecao"]["canonico"]})
    return nome, recibos


def resolver_conflito(caminho=None, usar_json=False, cabeca=None, snapshot=None, escolher=None, confirmada=False):
    workspace, _ = workspace_resolvido(caminho, usar_json)
    if workspace is None: return 1
    estado = observar(workspace)
    try:
        bytes_raiz = estado["ini"].read_bytes()
    except OSError:
        bytes_raiz = None
    if snapshot is None:
        if not estado["irmas"]: return emitir(recusar(workspace, "Não há conflito reconhecido para fotografar."), usar_json, 1)
        base, problema = escolher_candidatas(bases_para_bytes(estado, bytes_raiz), cabeca)
        if problema: return emitir(recusar(workspace, problema), usar_json, 1)
        try:
            with lock_configuracao(workspace):
                atual = observar(workspace)
                if [p.name for p in atual["irmas"]] != [p.name for p in estado["irmas"]]:
                    return emitir(recusar(workspace, "A composição mudou antes da fotografia; tente novamente."), usar_json, 1)
                nome, recibos = fotografar(workspace, atual, base)
        except (LockOcupado, OSError) as erro:
            return emitir(recusar(workspace, str(erro)), usar_json, 1)
        return emitir(envelope(workspace, "fotografado", "Conflito fotografado; escolha uma classe válida.", snapshot=nome, classes=recibos), usar_json)
    pasta = casa_linhagem(workspace) / snapshot
    snapshot_inspecionado = inspecionar_gravacao(pasta)
    registro = snapshot_inspecionado.get("registro") or {}
    if (snapshot_inspecionado["saude"] == "inválida"
            or registro.get("gesto") != "snapshot-conflito"):
        return emitir(recusar(workspace, "O snapshot não existe ou está inválido."), usar_json, 1)
    candidatos = [a for a in registro.get("artefatos", []) if a.get("digital", "").startswith(escolher)]
    if len(candidatos) != 1: return emitir(recusar(workspace, "O prefixo da classe é inexistente ou ambíguo."), usar_json, 1)
    item = candidatos[0]; composição = registro.get("composicao", [])
    atuais = sorted({digital_bytes(p.read_bytes()) for p in [estado["ini"], *estado["irmas"]]})
    if atuais != sorted(composição): return emitir(recusar(workspace, "O componente composicao mudou desde o snapshot."), usar_json, 1)
    base = registro.get("anterior")
    if cabeca is not None and cabeca != base:
        return emitir(recusar(workspace, "O componente cabeca diverge do snapshot confirmado."), usar_json, 1)
    base_atual, problema = escolher_candidatas(bases_para_bytes(estado, bytes_raiz), base)
    if problema or base_atual != base:
        return emitir(recusar(workspace, "O componente cabeca mudou desde o snapshot."), usar_json, 1)
    projeção = canonizar((pasta / item["arquivo"]).read_bytes(), mapa_base(estado, base))
    decisão = {"gesto": "resolver", "workspace": str(workspace.resolve()), "cabeca": base,
               "avisos_de_risco": [], "snapshot": snapshot, "composicao": composição,
               "digital_classe": item["digital"], "digital_canonica_projetada": projeção["digital"]}
    _, problema = validar_envelope(sys.stdin.read(), decisão)
    if problema: return emitir(recusar(workspace, problema), usar_json, 1)
    try:
        with lock_configuracao(workspace):
            decisões = [{"digital": d, "decisao": "escolhida" if d == item["digital"] else "descartada em conflito"} for d in composição]
            publicar(workspace, "resolver", projeção["canonico"], base, projeção["mapa"],
                     extras={"snapshot": snapshot, "decisoes": decisões, "composicao": composição})
            for caminho_raiz in [estado["ini"], *estado["irmas"]]:
                if caminho_raiz.name != "Configuracao.ini" and digital_bytes(caminho_raiz.read_bytes()) in composição:
                    caminho_raiz.unlink()
    except (LockOcupado, OSError) as erro: return emitir(recusar(workspace, str(erro)), usar_json, 1)
    return emitir(envelope(workspace, "resolvida", "Conflito resolvido."), usar_json)
