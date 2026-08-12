import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from neoprumo.configuracao_estado import observar
from neoprumo.configuracao_linhagem import inspecionar_gravacao
from neoprumo.configuracao_modelo import canonizar, digital_bytes
from neoprumo.configuracao_operacoes import DEFAULTS
from neoprumo.configuracao_rito import publicar, rotacionar


def _artefato(pasta, arquivo, tipo, conteudo):
    (pasta / arquivo).write_bytes(conteudo)
    return {"arquivo": arquivo, "tipo": tipo, "digital": digital_bytes(conteudo)}


def _gravacao(casa, nome, status="publicado", anterior=None, gesto="defaults",
              artefatos=None, composicao=None, instante=None):
    pasta = casa / nome
    pasta.mkdir(parents=True)
    registro = {
        "registro": 1,
        "gesto": gesto,
        "autorizada_em": instante or "2026-08-01T10:00:00-03:00",
        "anterior": anterior,
        "publicacao": {"status": status},
        "artefatos": artefatos or [],
    }
    if gesto == "snapshot-conflito":
        registro["composicao"] = composicao or []
    else:
        registro["regras"] = []
    (pasta / "registro.json").write_text(json.dumps(registro), encoding="utf-8")
    return pasta


def _snapshot(casa, nome, conteudos, instante):
    pasta = casa / nome
    pasta.mkdir(parents=True)
    artefatos = []
    for indice, conteudo in enumerate(conteudos, 1):
        artefatos.append(_artefato(pasta, f"participante-{indice}.ini", "participante", conteudo))
    registro = {
        "registro": 1, "gesto": "snapshot-conflito", "autorizada_em": instante,
        "anterior": None, "publicacao": {"status": "nao publica"},
        "artefatos": artefatos,
        "composicao": [digital_bytes(c) for c in conteudos],
    }
    (pasta / "registro.json").write_text(json.dumps(registro), encoding="utf-8")
    return pasta


def test_avaliar_nao_aceita_cabeca(executar_cli):
    with pytest.raises(SystemExit) as erro:
        executar_cli("configuracao", "avaliar", "-", "--cabeca", "x")
    assert erro.value.code == 2


def test_rotacao_protege_snapshot_de_conflito_vivo(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    raiz, irma = DEFAULTS.encode(), b"[configuracao]\nversao = 1\n# irma\n"
    (workspace / "Configuracao.ini").write_bytes(raiz)
    (workspace / "Configuracao 2.ini").write_bytes(irma)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    casa.mkdir(parents=True)
    antigo = _snapshot(casa, "antigo", [raiz, irma], "2026-08-01T00:00:00-03:00")
    for numero in range(7):
        _snapshot(casa, f"novo-{numero}", [bytes([numero])], f"2026-08-{numero + 2:02d}T00:00:00-03:00")
    rotacionar(workspace)
    assert (antigo / "participante-1.ini").exists()
    assert not (antigo / "poda.json").exists()


def test_rotacao_reavalia_protecao_e_deixa_poda_parcial(tmp_path, executar_cli, monkeypatch):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    casa.mkdir(parents=True)
    antigo = _snapshot(casa, "antigo", [b"a", b"b"], "2026-08-01T00:00:00-03:00")
    for numero in range(7):
        _snapshot(casa, f"novo-{numero}", [bytes([numero])], f"2026-08-{numero + 2:02d}T00:00:00-03:00")
    chamadas = 0

    def proteção_variável(_workspace, _finais):
        nonlocal chamadas
        chamadas += 1
        return {"antigo"} if chamadas >= 3 else set()

    monkeypatch.setattr("neoprumo.configuracao_rito._protegidas", proteção_variável)
    rotacionar(workspace)
    presentes = [(antigo / f"participante-{n}.ini").exists() for n in (1, 2)]
    assert presentes.count(True) == presentes.count(False) == 1
    poda = json.loads((antigo / "poda.json").read_text())
    assert len(poda["payloads_removidos"]) == 2
    assert inspecionar_gravacao(antigo)["saude"] == "poda parcial"


def test_rotacao_protege_todas_as_cabecas_do_fork(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    cabeças = []
    for numero, nome in enumerate(("A", "B"), 1):
        pasta = _gravacao(casa, nome, instante=f"2026-08-0{numero}T00:00:00-03:00")
        item = _artefato(pasta, "candidato.ini", "candidato", DEFAULTS.encode())
        registro = json.loads((pasta / "registro.json").read_text())
        registro["artefatos"] = [item]
        (pasta / "registro.json").write_text(json.dumps(registro))
        cabeças.append(pasta)
    for numero in range(7):
        _snapshot(casa, f"novo-{numero}", [bytes([numero])], f"2026-08-{numero + 3:02d}T00:00:00-03:00")
    rotacionar(workspace)
    assert all((pasta / "candidato.ini").exists() for pasta in cabeças)


def test_rotacao_protege_fonte_de_rejeicao_incompleta(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    histórico = "histórico".encode()
    fonte = _snapshot(casa, "fonte", [histórico], "2026-08-01T00:00:00-03:00")
    rejeição = _gravacao(casa, "rejeicao", status="publicacao incompleta",
                         gesto="rejeitar", instante="2026-08-02T00:00:00-03:00")
    registro = json.loads((rejeição / "registro.json").read_text())
    registro["destino"] = {"tipo": "artefato"}
    registro["origem_restauracao"] = {
        "gravacao": "fonte",
        "artefato": {"tipo": "participante", "arquivo": "participante-1.ini"},
        "digital": digital_bytes(histórico),
    }
    (rejeição / "registro.json").write_text(json.dumps(registro))
    for numero in range(7):
        _snapshot(casa, f"novo-{numero}", [bytes([numero])], f"2026-08-{numero + 3:02d}T00:00:00-03:00")
    rotacionar(workspace)
    assert (fonte / "participante-1.ini").exists()


def test_staging_so_e_descartavel_com_todos_os_bytes_duplicados(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    final = _gravacao(casa, "final")
    artefato = _artefato(final, "candidato.ini", "candidato", DEFAULTS.encode())
    registro = json.loads((final / "registro.json").read_text())
    registro["artefatos"] = [artefato]
    (final / "registro.json").write_text(json.dumps(registro))
    for nome, conteudo in (("duplicado.preparando", DEFAULTS.encode()),
                           ("unico.preparando", b"[configuracao]\nversao = 1\n# unico\n")):
        staging = _gravacao(casa, nome, status="publicacao incompleta")
        item = _artefato(staging, "candidato.ini", "candidato", conteudo)
        dados = json.loads((staging / "registro.json").read_text())
        dados["artefatos"] = [item]
        (staging / "registro.json").write_text(json.dumps(dados))
    avisos = observar(workspace)["avisos"]
    assert any("duplicado.preparando" in aviso and "descartável" in aviso for aviso in avisos)
    assert any("unico.preparando" in aviso and "bytes não preservados" in aviso for aviso in avisos)


def test_morte_antes_do_rename_deixa_so_staging(tmp_path, executar_cli, monkeypatch):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    real_rename = os.rename

    def morrer(origem, destino):
        if str(origem).endswith(".preparando"):
            raise OSError("morte simulada")
        return real_rename(origem, destino)

    monkeypatch.setattr("neoprumo.configuracao_rito.os.rename", morrer)
    with pytest.raises(OSError, match="morte simulada"):
        publicar(workspace, "defaults", DEFAULTS, None, [])
    casa = workspace / ".neoprumo/configuracao/linhagem"
    assert not [p for p in casa.iterdir() if not p.name.endswith(".preparando")]
    assert len([p for p in casa.iterdir() if p.name.endswith(".preparando")]) == 1
    assert not (workspace / "Configuracao.ini").exists()


def test_morte_entre_publicar_e_marcar_governa_sem_promover(tmp_path, executar_cli, monkeypatch):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    from neoprumo import configuracao_rito
    real_atomico = configuracao_rito._atomico

    def morrer(caminho, conteudo):
        if caminho.name == "registro.json" and caminho.parent.name.endswith(tuple("0123456789abcdef")):
            raise OSError("morte na marcação")
        return real_atomico(caminho, conteudo)

    monkeypatch.setattr(configuracao_rito, "_atomico", morrer)
    with pytest.raises(OSError, match="morte na marcação"):
        publicar(workspace, "defaults", DEFAULTS, None, [])
    estado = observar(workspace)
    assert estado["estado"] == "vigente por autorização observada"
    gravação = estado["finais"][0]
    assert gravação["registro"]["publicacao"]["status"] == "publicacao incompleta"


def test_token_recusado_nao_promove_staging(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    staging = _gravacao(casa, "recuperavel.preparando", status="publicacao incompleta")
    item = _artefato(staging, "candidato.ini", "candidato", DEFAULTS.encode())
    registro = json.loads((staging / "registro.json").read_text())
    registro["artefatos"] = [item]
    (staging / "registro.json").write_text(json.dumps(registro))
    preview = executar_cli("configuracao", "defaults", "--workspace", workspace, "--json")
    dados = json.loads(preview.stdout)
    entrada = json.dumps({"recibo": dados["decisao"], "token": "0" * 64})
    recusado = executar_cli("configuracao", "defaults", "--confirmada", "--workspace", workspace, "--json", input=entrada)
    assert recusado.returncode == 1
    assert staging.exists()
    assert not (casa / "recuperavel").exists()


def test_resolver_usa_observada_governante_como_base(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    a, _ = publicar(workspace, "defaults", DEFAULTS, None, [])
    casa = workspace / ".neoprumo/configuracao/linhagem"
    mapa_a = json.loads((casa / a / "registro.json").read_text())["regras"]
    projetada = canonizar(
        "[regra x]\ndominio = email\nexecucao = semantica\npredicado = cobrança\npolitica = revisar\norigem = teste\n",
        mapa_a,
    )
    b = casa / "B"
    b.mkdir()
    item = _artefato(b, "candidato.ini", "candidato", projetada["canonico"].encode())
    registro = {"registro": 1, "gesto": "gravar", "autorizada_em": "2026-08-11T10:00:00-03:00",
                "anterior": a, "regras": projetada["mapa"],
                "publicacao": {"status": "publicacao incompleta"}, "artefatos": [item]}
    (b / "registro.json").write_text(json.dumps(registro))
    (workspace / "Configuracao.ini").write_text(projetada["canonico"])
    (workspace / "Configuracao 2.ini").write_text(DEFAULTS)
    fase1 = executar_cli("configuracao", "resolver", "--workspace", workspace, "--json")
    dados = json.loads(fase1.stdout)
    assert fase1.returncode == 0
    assert {classe["decisao"]["cabeca"] for classe in dados["classes"]} == {"B"}


def test_resolver_exige_cabeca_na_fase_um_quando_raiz_nao_desempata_fork(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    ids = []
    for nome, texto in (("A", DEFAULTS), ("B", "[configuracao]\nversao = 1\n# ramo B\n")):
        projeção = canonizar(texto)
        pasta = _gravacao(casa, nome)
        item = _artefato(pasta, "candidato.ini", "candidato", projeção["canonico"].encode())
        registro = json.loads((pasta / "registro.json").read_text())
        registro["artefatos"] = [item]
        registro["regras"] = projeção["mapa"]
        (pasta / "registro.json").write_text(json.dumps(registro))
        ids.append(nome)
    raiz = "[configuracao]\nversao = 1\n# edição manual\n"
    (workspace / "Configuracao.ini").write_text(raiz)
    (workspace / "Configuracao 2.ini").write_text(DEFAULTS)
    recusa = executar_cli("configuracao", "resolver", "--workspace", workspace, "--json")
    assert recusa.returncode == 1
    assert all(nome in json.loads(recusa.stdout)["mensagem"] for nome in ids)
    foto = executar_cli("configuracao", "resolver", "--cabeca", "A", "--workspace", workspace, "--json")
    assert foto.returncode == 0
    dados = json.loads(foto.stdout)
    classe = dados["classes"][0]
    entrada = json.dumps({"recibo": classe["decisao"], "token": classe["token"]})
    fase2 = executar_cli(
        "configuracao", "resolver", "--snapshot", dados["snapshot"],
        "--escolher", classe["digital"][:12], "--confirmada",
        "--workspace", workspace, "--json", input=entrada,
    )
    assert fase2.returncode == 0


def test_cinco_estados_de_ausencia_sao_particao_total(tmp_path, executar_cli):
    nunca = tmp_path / "nunca"
    executar_cli("setup", nunca)
    assert observar(nunca)["estado"] == "nunca configurada"

    conhecida = tmp_path / "conhecida"
    executar_cli("setup", conhecida)
    publicar(conhecida, "defaults", DEFAULTS, None, [])
    (conhecida / "Configuracao.ini").unlink()
    assert observar(conhecida)["estado"] == "conhecida agora ausente"

    autorizada = tmp_path / "autorizada"
    executar_cli("setup", autorizada)
    _, ok = publicar(autorizada, "defaults", DEFAULTS, None, [])
    assert ok
    pasta = next((autorizada / ".neoprumo/configuracao/linhagem").iterdir())
    registro = json.loads((pasta / "registro.json").read_text())
    registro["publicacao"] = {"status": "publicacao incompleta"}
    (pasta / "registro.json").write_text(json.dumps(registro))
    (autorizada / "Configuracao.ini").unlink()
    assert observar(autorizada)["estado"] == "ausente com candidato autorizado não publicado"

    historica = tmp_path / "historica"
    executar_cli("setup", historica)
    casa = historica / ".neoprumo/configuracao/linhagem"
    _snapshot(casa, "foto", [b"historico"], "2026-08-01T00:00:00-03:00")
    assert observar(historica)["estado"] == "ausente com cópia histórica recuperável"

    sem_fonte = tmp_path / "sem-fonte"
    executar_cli("setup", sem_fonte)
    _gravacao(sem_fonte / ".neoprumo/configuracao/linhagem", "evidencia")
    assert observar(sem_fonte)["estado"] == "ausente sem fonte recuperável"


def test_staging_parcial_so_oferece_recuperacao_manual(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    staging = _gravacao(casa, "parcial.preparando", status="publicacao incompleta")
    pre_image = _artefato(staging, "pre-image.ini", "pre-image", b"rascunho")
    registro = json.loads((staging / "registro.json").read_text())
    registro["artefatos"] = [
        {"arquivo": "candidato.ini", "tipo": "candidato", "digital": "0" * 64},
        pre_image,
    ]
    (staging / "registro.json").write_text(json.dumps(registro))
    estado = observar(workspace)
    assert estado["estado"] == "ausente sem fonte recuperável"
    assert any("parcial" in aviso and "bytes não preservados" in aviso for aviso in estado["avisos"])


def test_saudes_com_poda_sao_mutuamente_exclusivas(tmp_path):
    casa = tmp_path / "linhagem"
    completa = _gravacao(casa, "completa")
    item = _artefato(completa, "candidato.ini", "candidato", DEFAULTS.encode())
    registro = json.loads((completa / "registro.json").read_text())
    registro["artefatos"] = [item]
    (completa / "registro.json").write_text(json.dumps(registro))
    assert inspecionar_gravacao(completa)["saude"] == "completa"
    (completa / "poda.json").write_text(json.dumps({"poda": 1, "payloads_removidos": [], "em": "agora"}))
    assert inspecionar_gravacao(completa)["saude"] == "poda parcial"


@pytest.mark.parametrize("tipo", ["ausente", "poda-divergente"])
def test_ausencia_e_poda_divergente_nao_se_disfarcam(tmp_path, executar_cli, tipo):
    workspace = tmp_path / tipo
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    pasta = _gravacao(casa, "A")
    artefato = {"arquivo": "candidato.ini", "tipo": "candidato", "digital": digital_bytes(DEFAULTS.encode())}
    dados = json.loads((pasta / "registro.json").read_text())
    dados["artefatos"] = [artefato]
    (pasta / "registro.json").write_text(json.dumps(dados))
    if tipo == "poda-divergente":
        (pasta / "poda.json").write_text(json.dumps({"poda": 1, "payloads_removidos": [{"arquivo": "candidato.ini", "digital": "0" * 64}], "em": "agora"}))
        assert inspecionar_gravacao(pasta)["saude"] == "inválida"
    else:
        estado = observar(workspace)
        assert estado["estado"] == "ausente sem fonte recuperável"
        assert estado["linhagem"]["incompletas_em_observacao"] == [{"id": "A", "payloads_ausentes": ["candidato.ini"]}]


def test_pai_ausente_aparece_na_superficie(tmp_path, executar_cli):
    workspace = tmp_path / "ws"
    executar_cli("setup", workspace)
    casa = workspace / ".neoprumo/configuracao/linhagem"
    _gravacao(casa, "filho", anterior="pai-sumido")
    estado = observar(workspace)
    assert estado["linhagem"]["pais_ausentes"] == [{"filho": "filho", "anterior": "pai-sumido"}]
