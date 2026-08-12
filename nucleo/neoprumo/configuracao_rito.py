import json
import os
import secrets
import stat
from datetime import datetime
from pathlib import Path

from .configuracao_fisica import participantes
from .configuracao_linhagem import (
    analisar_grafo,
    casa_linhagem,
    inspecionar_linhagem,
)
from .configuracao_modelo import digital_bytes


def agora_local():
    return datetime.now().astimezone().replace(microsecond=0)


def _atomico(caminho, conteudo):
    temporario = caminho.with_name(caminho.name + ".tmp-" + secrets.token_hex(8))
    try:
        with open(temporario, "x", encoding=None if isinstance(conteudo, bytes) else "utf-8", newline=None if isinstance(conteudo, bytes) else "") as arquivo:
            arquivo.write(conteudo)
        os.rename(temporario, caminho)
    finally:
        try:
            temporario.unlink()
        except FileNotFoundError:
            pass


def _nome(casa, instante):
    while True:
        nome = instante.strftime("%Y-%m-%d-%H%M%S") + "-" + secrets.token_hex(16)
        staging = casa / (nome + ".preparando")
        try:
            staging.mkdir()
            return nome, staging
        except FileExistsError:
            continue


def promover_stagings(workspace):
    _, stagings = inspecionar_linhagem(workspace)
    for staging in stagings:
        if staging["saude"] != "completa" or not staging["registro"]:
            continue
        registro = dict(staging["registro"])
        registro["publicacao"] = {"status": "recuperacao promovida"}
        _atomico(staging["pasta"] / "registro.json", json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
        os.rename(staging["pasta"], staging["pasta"].with_name(staging["id"]))


def publicar(workspace, gesto, canonico, base, mapa, anexos=None, destino=None,
             origem_restauracao=None, extras=None, instante=None):
    workspace = Path(workspace)
    casa = casa_linhagem(workspace)
    ini = workspace / "Configuracao.ini"
    for ponto, diretorio in ((workspace / ".neoprumo", True),
                             (workspace / ".neoprumo" / "configuracao", True),
                             (casa, True), (ini, False)):
        try:
            modo = ponto.lstat().st_mode
        except FileNotFoundError:
            continue
        esperado = stat.S_ISDIR if diretorio else stat.S_ISREG
        if stat.S_ISLNK(modo) or not esperado(modo):
            raise OSError(f"{ponto.name} precisa ser {'diretório' if diretorio else 'arquivo'} real; atalhos não são seguidos.")
    casa.mkdir(parents=True, exist_ok=True)
    instante = instante or agora_local()
    nome, staging = _nome(casa, instante)
    pre_image = ini.read_bytes() if ini.exists() else None
    artefatos = []
    payloads = [("candidato.ini", "candidato", canonico.encode("utf-8"))]
    if pre_image is not None:
        payloads.append(("pre-image.ini", "pre-image", pre_image))
    payloads.extend(anexos or [])
    try:
        for arquivo, tipo, conteudo in payloads:
            caminho = staging / arquivo
            with open(caminho, "xb") as saida:
                saida.write(conteudo)
            artefatos.append({"arquivo": arquivo, "tipo": tipo, "digital": digital_bytes(conteudo)})
        registro = {"registro": 1, "gesto": gesto, "autorizada_em": instante.isoformat(),
                    "anterior": base, "regras": mapa,
                    "publicacao": {"status": "publicacao incompleta"}, "artefatos": artefatos}
        if destino is not None:
            registro["destino"] = destino
        if origem_restauracao is not None:
            registro["origem_restauracao"] = origem_restauracao
        registro.update(extras or {})
        (staging / "registro.json").write_text(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        for item in artefatos:
            if digital_bytes((staging / item["arquivo"]).read_bytes()) != item["digital"]:
                raise OSError("A conferência do staging falhou.")
        final = casa / nome
        os.rename(staging, final)
        atual = ini.read_bytes() if ini.exists() else None
        if atual != pre_image:
            return nome, False
        temporario = workspace / (".Configuracao.ini.tmp-" + secrets.token_hex(8))
        with open(temporario, "xb") as saida:
            saida.write(canonico.encode("utf-8"))
        os.rename(temporario, ini)
        registro["publicacao"] = {"status": "publicado"}
        _atomico(final / "registro.json", json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
        rotacionar(workspace)
        return nome, True
    except Exception:
        raise


def rotacionar(workspace):
    finais, _ = inspecionar_linhagem(workspace)
    if any(g["saude"] == "inválida" for g in finais):
        return
    ordenadas = sorted(
        (g for g in finais if g["registro"]),
        key=lambda g: g["registro"]["autorizada_em"],
        reverse=True,
    )
    protegidas = _protegidas(workspace, finais)
    protegidas.update(g["id"] for g in ordenadas[:7])
    for gravação in ordenadas[7:]:
        if gravação["id"] in protegidas:
            continue
        remover = [a for a in gravação["artefatos_validos"]]
        if not remover:
            continue
        anteriores = _poda_existente(gravação["pasta"])
        por_arquivo = {item["arquivo"]: item for item in anteriores}
        por_arquivo.update({a["arquivo"]: {"arquivo": a["arquivo"], "digital": a["digital"]} for a in remover})
        poda = {"poda": 1, "payloads_removidos": list(por_arquivo.values()),
                "em": agora_local().isoformat()}
        _atomico(gravação["pasta"] / "poda.json", json.dumps(poda, ensure_ascii=False, sort_keys=True) + "\n")
        for item in remover:
            atuais, _ = inspecionar_linhagem(workspace)
            if gravação["id"] in _protegidas(workspace, atuais):
                continue
            try:
                (gravação["pasta"] / item["arquivo"]).unlink()
            except FileNotFoundError:
                pass


def _poda_existente(pasta):
    try:
        dados = json.loads((pasta / "poda.json").read_text(encoding="utf-8"))
        return dados.get("payloads_removidos", []) if dados.get("poda") == 1 else []
    except (OSError, json.JSONDecodeError):
        return []


def _protegidas(workspace, finais):
    protegidas = set(analisar_grafo(finais)["cabecas"])
    _, irmas, _ = participantes(workspace)
    if irmas:
        caminhos = [Path(workspace) / "Configuracao.ini", *irmas]
        composição = set()
        for caminho in caminhos:
            try:
                composição.add(digital_bytes(caminho.read_bytes()))
            except OSError:
                pass
        for gravação in finais:
            registro = gravação.get("registro") or {}
            if (registro.get("gesto") == "snapshot-conflito"
                    and set(registro.get("composicao", [])) == composição):
                protegidas.add(gravação["id"])
    for gravação in finais:
        registro = gravação.get("registro") or {}
        if (registro.get("gesto") == "rejeitar"
                and registro.get("publicacao", {}).get("status") == "publicacao incompleta"):
            if registro.get("anterior"):
                protegidas.add(registro["anterior"])
            origem = registro.get("origem_restauracao") or {}
            if origem.get("gravacao"):
                protegidas.add(origem["gravacao"])
    return protegidas
