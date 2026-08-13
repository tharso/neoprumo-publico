import hashlib
import os
import stat
from pathlib import Path

from .resultado_despacho import envelope, recusa, recusa_falha


def _esta_dentro(caminho, workspace):
    try:
        caminho.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def _candidatos(pasta, nome):
    caminho = Path(nome)
    yield pasta / nome
    for numero in range(2, 101):
        yield pasta / f"{caminho.stem}-{numero}{caminho.suffix}"


def _copiar_exclusivo(destino, dados, modo, tempos):
    descritor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, modo)
    try:
        with os.fdopen(descritor, "wb", closefd=False) as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
    finally:
        os.close(descritor)
    os.chmod(destino, stat.S_IMODE(modo))
    os.utime(destino, ns=tempos)


def _recusa_sobra(item, destino, workspace, motivo):
    return recusa(
        f"O item ficou na Inbox e há uma cópia no Acervo como {destino.name}; confira as duas.",
        motivo,
        "Confira as duas cópias antes de repetir o gesto.",
        workspace, "acervo", item=item, identificador=item.stem,
    )


def _recusa_destino(item, destino, workspace, motivo):
    return recusa(
        f"O item ficou na Inbox; o destino {destino.name} não pôde ser concluído ou conferido.",
        motivo,
        "Confira a Inbox e o Acervo antes de repetir o gesto.",
        workspace, "acervo", item=item, identificador=item.stem,
    )


def mover_para_acervo(item, workspace):
    pasta = workspace / "Acervo"
    acoes = []
    try:
        modo = item.lstat().st_mode
        if stat.S_ISLNK(modo):
            return 1, recusa(
                "O item é um atalho; mova o arquivo real.",
                "O destino acervo não segue atalhos.",
                "Mova o arquivo real para a Inbox.", workspace, "acervo",
                item=item, identificador=item.stem,
            )
        if not stat.S_ISREG(modo):
            raise OSError("o item não é um arquivo regular")
        estado = item.stat(follow_symlinks=False)
        dados = item.read_bytes()
        origem_digital = hashlib.sha256(dados).digest()
        try:
            modo_pasta = pasta.lstat().st_mode
        except FileNotFoundError:
            pasta.mkdir()
            acoes.append(
                "A pasta Acervo estava faltando e foi recriada. "
                "Rode doctor para conferir o workspace."
            )
        else:
            if stat.S_ISLNK(modo_pasta) or not stat.S_ISDIR(modo_pasta):
                raise OSError("Acervo precisa ser uma pasta real")
        if not _esta_dentro(pasta, workspace):
            raise OSError("Acervo aponta para fora do workspace")
        final = None
        for candidato in _candidatos(pasta, item.name):
            final = candidato
            try:
                _copiar_exclusivo(
                    candidato, dados, estado.st_mode,
                    (estado.st_atime_ns, estado.st_mtime_ns),
                )
            except FileExistsError:
                final = None
                continue
            break
        if final is None:
            return 1, recusa(
                "O Acervo já tem os 100 nomes reservados para este item.",
                "Os 100 candidatos de nome no Acervo estão ocupados.",
                "Renomeie o item ou organize as colisões e tente novamente.",
                workspace, "acervo", item=item, identificador=item.stem,
            )
        atuais = item.read_bytes()
        if hashlib.sha256(atuais).digest() != origem_digital:
            return 1, _recusa_sobra(
                item, final, workspace,
                "O item mudou durante o gesto; a cópia no Acervo é da versão anterior.",
            )
        estado_atual = item.stat(follow_symlinks=False)
        os.chmod(final, stat.S_IMODE(estado_atual.st_mode))
        os.utime(final, ns=(estado_atual.st_atime_ns, estado_atual.st_mtime_ns))
        modo_final = final.lstat().st_mode
        if not stat.S_ISREG(modo_final) or hashlib.sha256(final.read_bytes()).digest() != origem_digital:
            return 1, _recusa_sobra(
                item, final, workspace,
                "A cópia no Acervo mudou ou deixou de ser um arquivo regular.",
            )
        try:
            item.unlink()
        except OSError:
            return 1, _recusa_sobra(
                item, final, workspace,
                f"O item foi copiado pro Acervo como {final.name}, mas não saiu da Inbox.",
            )
    except OSError as erro:
        if "final" in locals() and final is not None:
            return 1, _recusa_destino(
                item, final, workspace,
                f"A cópia {final.name} não pôde ser concluída ou conferida ({erro}).",
            )
        return 1, recusa_falha(item, workspace, "acervo", erro)
    mensagem = f"Movido pro acervo: {final.name}."
    if acoes:
        mensagem += f" {acoes[0]}"
    return 0, envelope(
        "despachado", mensagem, workspace, "acervo",
        item=final, identificador=item.stem, acoes=acoes,
    )
