import re
import stat


SECAO = re.compile(r"^## Sessão ([01]\d|2[0-3]):[0-5]\d$")


def observar_diario(workspace, dia):
    caminho = workspace / "Diario" / f"{dia}.md"
    estado = {"existe": False, "secoes": 0}
    try:
        modo = caminho.lstat().st_mode
    except FileNotFoundError:
        return estado, []
    except OSError as erro:
        return estado, [f"Diário do dia: não pôde ser observado ({erro})."]
    estado["existe"] = True
    if stat.S_ISLNK(modo):
        return estado, ["Diário do dia: é um atalho simbólico e não será seguido."]
    if not stat.S_ISREG(modo):
        return estado, ["Diário do dia: deveria ser um arquivo, mas é um diretório ou outro tipo."]
    try:
        texto = caminho.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return estado, ["Diário do dia: o conteúdo não é texto UTF-8."]
    except OSError as erro:
        return estado, [f"Diário do dia: não pôde ser lido ({erro})."]
    linhas = texto.splitlines()
    if not linhas or not linhas[0].startswith("# "):
        return estado, ["Diário do dia: falta o título canônico."]
    if linhas[0] != f"# {dia}":
        return estado, ["Diário do dia: o título aponta para outra data."]
    estado["secoes"] = sum(bool(SECAO.fullmatch(linha)) for linha in linhas)
    return estado, []
