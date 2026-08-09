import unicodedata

from .superficie_base import codificavel_utf8


def nome_projeto_valido(nome):
    return (
        codificavel_utf8(nome)
        and bool(nome.strip())
        and len(nome.splitlines()) == 1
        and not any(
            unicodedata.category(caractere) in ("Cc", "Cs", "Zl", "Zp")
            for caractere in nome
        )
    )
