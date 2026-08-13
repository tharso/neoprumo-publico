import fcntl
import hashlib
import os
from pathlib import Path


class TrincoOcupado(OSError):
    pass


class trinco_diario:
    def __init__(self, workspace):
        raiz = os.environ.get("XDG_STATE_HOME")
        estado = Path(raiz) if raiz else Path.home() / ".local" / "state"
        digest = hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:12]
        self.caminho = estado / "neoprumo" / "locks" / f"diario-{digest}.lock"
        self.arquivo = None

    def __enter__(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo = open(self.caminho, "a+", encoding="utf-8")
        try:
            fcntl.flock(self.arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as erro:
            self.arquivo.close()
            raise TrincoOcupado("Outra gravação do diário está em andamento.") from erro
        return self

    def __exit__(self, *_):
        fcntl.flock(self.arquivo, fcntl.LOCK_UN)
        self.arquivo.close()
