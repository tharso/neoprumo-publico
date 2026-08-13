from pathlib import Path

from .resultado_despacho import envelope, recusa_falha


def _esta_dentro(caminho, workspace):
    try:
        caminho.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def _caminho_sem_colisao(pasta, nome):
    original = pasta / nome
    if not original.exists():
        return original
    caminho = Path(nome)
    numero = 2
    while True:
        candidato = pasta / f"{caminho.stem}-{numero}{caminho.suffix}"
        if not candidato.exists():
            return candidato
        numero += 1


def mover_para_lixo(item, workspace):
    pasta = workspace / ".neoprumo" / "lixo"
    try:
        if not _esta_dentro(pasta, workspace):
            raise OSError("o destino aponta para fora do workspace")
        pasta.mkdir(parents=True, exist_ok=True)
        destino_final = _caminho_sem_colisao(pasta, item.name)
        item.replace(destino_final)
    except OSError as erro:
        return 1, recusa_falha(item, workspace, "lixo", erro)
    return 0, envelope(
        "despachado", f"Movido pro lixo (recuperável): {destino_final.name}.",
        workspace, "lixo", item=destino_final, identificador=item.stem,
    )
