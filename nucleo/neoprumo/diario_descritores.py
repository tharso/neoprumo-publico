import codecs
import os
import stat


class FalhaEscrita(OSError):
    def __init__(self, gravados, erro):
        super().__init__(str(erro))
        self.gravados = gravados
        self.erro = erro


def escrever_tudo(descritor, dados):
    gravados = 0
    while gravados < len(dados):
        try:
            quantidade = os.write(descritor, dados[gravados:])
        except InterruptedError:
            continue
        except OSError as erro:
            raise FalhaEscrita(gravados, erro) from erro
        if quantidade <= 0:
            raise FalhaEscrita(gravados, OSError("a escrita não avançou"))
        gravados += quantidade
    return gravados


def mesma_identidade(primeiro, segundo):
    return (primeiro.st_dev, primeiro.st_ino) == (segundo.st_dev, segundo.st_ino)


def identidade_dir_canonico(wsfd, dirfd):
    atual = os.stat("Diario", dir_fd=wsfd, follow_symlinks=False)
    aberto = os.fstat(dirfd)
    return mesma_identidade(atual, aberto)


def abrir_pastas(workspace):
    wsfd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY)
    try:
        dirfd = os.open(
            "Diario", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=wsfd,
        )
    except BaseException:
        os.close(wsfd)
        raise
    return wsfd, dirfd


def abrir_existente(nome, dirfd):
    descritor = os.open(
        nome, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW, dir_fd=dirfd
    )
    estado = os.fstat(descritor)
    if not stat.S_ISREG(estado.st_mode):
        os.close(descritor)
        raise OSError("o diário do dia não é um arquivo regular")
    return descritor, estado


def ler_validar(descritor, dia, bloco=8192):
    decodificador = codecs.getincrementaldecoder("utf-8")()
    partes, deslocamento = [], 0
    while True:
        dados = os.pread(descritor, bloco, deslocamento)
        if not dados:
            break
        partes.append(decodificador.decode(dados, final=False))
        deslocamento += len(dados)
    partes.append(decodificador.decode(b"", final=True))
    texto = "".join(partes)
    linhas = texto.splitlines()
    if not linhas:
        raise ValueError("o diário do dia está sem título")
    if linhas[0] != f"# {dia}":
        raise ValueError("o título do diário aponta para outra data ou está ausente")
    return texto


def nome_aponta_para(nome, estado, dirfd):
    atual = os.stat(nome, dir_fd=dirfd, follow_symlinks=False)
    return mesma_identidade(atual, estado)


def remover_se_existir(nome, dirfd):
    try:
        os.unlink(nome, dir_fd=dirfd)
    except FileNotFoundError:
        pass
