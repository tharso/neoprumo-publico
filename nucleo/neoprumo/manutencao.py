"""Lembrete local de manutenção do pacote."""

import os
from datetime import date, datetime, timezone

from . import __data_versao__


LIMIAR_DE_IDADE = 7
VARIAVEL_DE_SILENCIO = "NEOPRUMO_SEM_AVISO_DE_IDADE"


def _esta_silenciado(ambiente):
    return bool(ambiente.get(VARIAVEL_DE_SILENCIO, ""))


def _hoje_utc():
    return datetime.now(timezone.utc).date()


def _ler_data(valor):
    data_lida = date.fromisoformat(valor)
    if data_lida.isoformat() != valor:
        raise ValueError("data fora do formato canônico")
    return data_lida


def _montar_mensagem(idade):
    return (
        f"Esta versão está em uso há {idade} dias; vale conferir se saiu uma nova. "
        "No Claude: `claude plugin update neoprumo@neoprumo`. "
        "No Codex: `codex plugin marketplace upgrade neoprumo` e depois "
        "`codex plugin add neoprumo@neoprumo`."
    )


def aviso_de_manutencao(
    hoje=None,
    data_versao=None,
    ambiente=None,
    limiar=LIMIAR_DE_IDADE,
) -> str | None:
    """Devolve o lembrete por idade; qualquer falha local resulta em silêncio."""
    try:
        ambiente = os.environ if ambiente is None else ambiente
        if _esta_silenciado(ambiente):
            return None
        data_atual = _hoje_utc() if hoje is None else hoje
        versao = __data_versao__ if data_versao is None else data_versao
        data_do_pacote = _ler_data(versao)
        idade = (data_atual - data_do_pacote).days
        if not isinstance(limiar, int) or isinstance(limiar, bool) or limiar < 0:
            return None
        if idade < limiar:
            return None
        return _montar_mensagem(idade)
    except Exception:
        return None
