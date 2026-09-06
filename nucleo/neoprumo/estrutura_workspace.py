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

PERMITIDOS_NA_RAIZ = {
    *(nome.split("/", 1)[0] for nome in ESTRUTURA),
    "Configuracao.ini",
    "Projetos.md",
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


def _entradas_sobrando(workspace):
    try:
        entradas = Path(workspace).iterdir()
        return sorted(
            (
                entrada
                for entrada in entradas
                if entrada.name not in PERMITIDOS_NA_RAIZ
                and not entrada.name.startswith(".")
                and not entrada.is_symlink()
            ),
            key=lambda entrada: entrada.name,
        )
    except OSError:
        return []


def _aviso_de_arquivo_solto(nome):
    return f"{nome} está solto na raiz (pode ir pra Inbox)."


def _aviso_de_pasta_solta(nome):
    return f"{nome}/ está solta na raiz."


def sobras_da_raiz(workspace):
    problemas = []
    for entrada in _entradas_sobrando(workspace):
        if entrada.is_dir():
            problemas.append(_aviso_de_pasta_solta(entrada.name))
        else:
            problemas.append(_aviso_de_arquivo_solto(entrada.name))
    return problemas


def _destino_sem_colisao(inbox, nome):
    destino = inbox / nome
    if not _entrada_existe(destino):
        return destino
    caminho = Path(nome)
    numero = 2
    while True:
        destino = inbox / f"{caminho.stem}-{numero}{caminho.suffix}"
        if not _entrada_existe(destino):
            return destino
        numero += 1


def _entrada_existe(caminho):
    try:
        caminho.lstat()
    except FileNotFoundError:
        return False
    return True


def recolher_arquivos_soltos(workspace):
    workspace = Path(workspace)
    inbox = workspace / "Inbox"
    acoes = []
    falhas = {}
    for entrada in _entradas_sobrando(workspace):
        if entrada.is_dir():
            continue
        try:
            entrada.rename(_destino_sem_colisao(inbox, entrada.name))
        except OSError as erro:
            detalhe = f" ({erro})" if str(erro) else ""
            falhas[_aviso_de_arquivo_solto(entrada.name)] = (
                f"Não foi possível recolher {entrada.name} pra Inbox{detalhe}."
            )
            continue
        acoes.append(f"{entrada.name} recolhido pra Inbox.")
    return acoes, falhas


def inspecionar_estrutura(caminho):
    workspace = Path(caminho)
    if not tem_marca_real(workspace):
        return {
            "status": "nao_e_workspace",
            "problemas": ["Falta a pasta .neoprumo."],
        }
    problemas = problemas_da_estrutura(workspace) + sobras_da_raiz(workspace)
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
