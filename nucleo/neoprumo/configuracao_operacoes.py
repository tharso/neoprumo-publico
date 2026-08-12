import json
from datetime import datetime

from .configuracao_estado import bases, observar
from .configuracao_linhagem import candidato
from .configuracao_modelo import canonizar, digital_bytes
from .configuracao_recibo import token, validar_envelope


DEFAULTS = "[configuracao]\nversao = 1\n"


def escolher_base(estado, cabeca, sob_pendencia=False):
    return escolher_candidatas(bases(estado, sob_pendencia), cabeca)


def escolher_candidatas(candidatas, cabeca):
    if not candidatas:
        return (None, None) if cabeca is None else (None, "--cabeca foi informada, mas não há base causal para escolher.")
    if len(candidatas) == 1:
        if cabeca not in (None, candidatas[0]):
            return None, f"--cabeca precisa ser {candidatas[0]}."
        return candidatas[0], None
    if cabeca not in candidatas:
        return None, "Escolha --cabeca entre: " + ", ".join(candidatas) + "."
    return cabeca, None


def mapa_base(estado, base):
    if base is None:
        return []
    gravação = estado["grafo"]["mapa"].get(base)
    return gravação["registro"].get("regras", []) if gravação else []


def preparar(workspace, gesto, entrada, cabeca=None, sob_pendencia=False,
             riscos=None, campos=None, hoje=None):
    estado = observar(workspace)
    base, problema = escolher_base(estado, cabeca, sob_pendencia)
    if problema:
        return None, estado, problema
    hoje = hoje or datetime.now().astimezone().date()
    resultado = canonizar(entrada, mapa_base(estado, base), hoje=hoje)
    if resultado.get("recusa"):
        return None, estado, resultado["recusa"]
    ini = estado["ini"]
    atual = ini.read_bytes() if ini.exists() and ini.is_file() else None
    riscos = riscos or (["Regra permanente exige confirmação consciente."]
                        if any(r.get("confirmacao") == "permanente" for r in resultado["validas"])
                        else [])
    decisão = {"gesto": gesto, "workspace": str(workspace.resolve()), "cabeca": base,
              "avisos_de_risco": riscos,
              "digital_entrada": digital_bytes(atual) if atual is not None else None,
              "digital_canonica": resultado["digital"]}
    decisão.update(campos or {})
    return {"decisao": decisão, "token": token(decisão), "canonico": resultado["canonico"],
            "mapa": resultado["mapa"], "leitura": resultado,
            "_cabeca_argumento": cabeca, "_sob_pendencia": sob_pendencia}, estado, None


def conferir_commit(texto, preparo):
    envelope, problema = validar_envelope(texto, preparo["decisao"])
    return envelope, problema


def artefato_da_gravacao(estado, nome, seletor="candidato"):
    todas = estado["finais"] + estado["stagings"]
    gravação = next((g for g in todas if g["id"] == nome or g["pasta"].name == nome), None)
    if not gravação:
        return None, None, "A gravação solicitada não existe."
    artefatos = gravação["artefatos_validos"]
    if seletor.startswith("participante-"):
        arquivo = seletor + ".ini"
        item = next((a for a in artefatos if a["arquivo"] == arquivo), None)
    else:
        item = next((a for a in artefatos if a["tipo"] == seletor or a["arquivo"] == seletor), None)
    if not item:
        disponíveis = ", ".join(a["arquivo"] for a in artefatos) or "nenhum"
        return gravação, None, f"O artefato não está íntegro; disponíveis: {disponíveis}."
    try:
        conteudo = (gravação["pasta"] / item["arquivo"]).read_bytes()
    except OSError:
        return gravação, None, "O payload do artefato não está disponível."
    if digital_bytes(conteudo) != item["digital"]:
        return gravação, None, "A digital do artefato diverge do registro."
    return gravação, (item, conteudo), None


def entrada_commit(texto):
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return None
