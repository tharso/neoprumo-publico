import json
import stat
from pathlib import Path


ESTRUTURA = {
    "Inbox": "diretorio",
    "Pauta.md": "arquivo",
    "Acervo": "diretorio",
    "Assuntos": "diretorio",
    "Diario": "diretorio",
    ".neoprumo/workspace.json": "arquivo",
}


class FalhaDeCriacao(OSError):
    def __init__(self, caminho, acao, erro):
        self.caminho = Path(caminho)
        self.acao = acao
        self.erro_original = erro
        detalhe = f" ({erro})" if str(erro) else ""
        super().__init__(
            f"Não foi possível terminar a gravação de {self.caminho.name}{detalhe}."
        )


def tem_marca_real(workspace):
    marca = Path(workspace) / ".neoprumo"
    try:
        return stat.S_ISDIR(marca.lstat().st_mode)
    except OSError:
        return False


def _tipo_correto(item, tipo):
    return item.is_dir() if tipo == "diretorio" else item.is_file()


def problemas_da_estrutura(workspace):
    workspace = Path(workspace)
    problemas = []
    for nome, tipo in ESTRUTURA.items():
        item = workspace / nome
        try:
            existe_certo = _tipo_correto(item, tipo)
        except OSError as erro:
            detalhe = f" ({erro})" if str(erro) else ""
            problemas.append(
                f"Não foi possível conferir {nome}{detalhe}."
            )
            continue
        if not existe_certo:
            problemas.append(f"Falta {nome} ({tipo}).")
    return problemas


def inspecionar_estrutura(caminho):
    workspace = Path(caminho)
    if not tem_marca_real(workspace):
        return {
            "status": "nao_e_workspace",
            "problemas": ["Falta a pasta .neoprumo."],
        }
    problemas = problemas_da_estrutura(workspace)
    return {
        "status": "com_problemas" if problemas else "saudavel",
        "problemas": problemas,
    }


def _conteudo_inicial(nome):
    if nome == ".neoprumo/workspace.json":
        return json.dumps({"layout": 1}, ensure_ascii=False) + "\n"
    return "# Pauta\n"


def _garantir_pai(item):
    pai = item.parent
    if pai == item or pai.exists():
        return
    try:
        pai.mkdir(parents=True)
    except FileExistsError:
        pass


def criar_item_ausente(workspace, nome, tipo):
    item = Path(workspace) / nome
    if tipo == "diretorio":
        try:
            item.mkdir(parents=True)
        except FileExistsError:
            return None
        return f"{nome} recriado."

    _garantir_pai(item)
    acao = f"{nome} recriado."
    try:
        arquivo = open(item, "x", encoding="utf-8", newline="")
    except FileExistsError:
        return None
    try:
        with arquivo:
            arquivo.write(_conteudo_inicial(nome))
    except OSError as erro:
        raise FalhaDeCriacao(
            item,
            f"{nome} foi criado, mas a gravação não terminou.",
            erro,
        ) from erro
    return acao


def criar_marca(workspace):
    marca = Path(workspace) / ".neoprumo"
    try:
        marca.mkdir()
    except FileExistsError:
        try:
            if stat.S_ISDIR(marca.lstat().st_mode):
                return None
        except OSError:
            raise
        raise OSError(
            "Não foi possível criar .neoprumo: o nome está ocupado por um "
            "arquivo ou atalho."
        )
    return ".neoprumo/ criada."
