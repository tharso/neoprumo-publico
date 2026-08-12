import hashlib
import json


def serializar(decisao):
    return json.dumps(decisao, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def token(decisao):
    return hashlib.sha256(serializar(decisao)).hexdigest()


def validar_envelope(texto, decisao_atual):
    try:
        envelope = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return None, "O stdin não contém o envelope JSON do recibo."
    if not isinstance(envelope, dict) or not isinstance(envelope.get("recibo"), dict) or not isinstance(envelope.get("token"), str):
        return None, "O envelope precisa conter recibo e token."
    recebido = envelope["recibo"]
    if envelope["token"] != token(recebido):
        return None, "O token não confere com o recibo recebido."
    for chave in sorted(set(recebido) | set(decisao_atual)):
        if recebido.get(chave) != decisao_atual.get(chave):
            return None, f"O componente {chave} mudou desde o preview."
    return envelope, None
