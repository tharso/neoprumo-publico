import json
from pathlib import Path

from neoprumo.configuracao_linhagem import analisar_grafo, inspecionar_gravacao
from neoprumo.configuracao_lock import LockOcupado, lock_configuracao
from neoprumo.configuracao_modelo import digital_bytes


REGRA_A = """[regra loja]
dominio = email
execucao = hibrida
predicado = remetente-dominio: x.com
politica = arquivar
origem = conversa
"""
REGRA_B = REGRA_A.replace("arquivar", "manter")


def recibo(resultado, candidato=None):
    dados = json.loads(resultado.stdout)
    bloco = {"recibo": dados["decisao"], "token": dados["token"]}
    if candidato is not None: bloco["candidato"] = candidato
    return json.dumps(bloco)


def publicar(executar_cli, workspace, candidato=REGRA_A):
    preview = executar_cli("configuracao", "gravar", "-", "--workspace", workspace, "--json", input=candidato)
    return executar_cli("configuracao", "gravar", "-", "--confirmada", "--workspace", workspace, "--json", input=recibo(preview, candidato))


def test_adotar_rejeitar_e_restaurar_rejeitada(tmp_path, executar_cli):
    workspace = tmp_path / "ws"; executar_cli("setup", workspace); publicar(executar_cli, workspace)
    original = (workspace / "Configuracao.ini").read_text()
    (workspace / "Configuracao.ini").write_text(REGRA_B)
    adoção = executar_cli("configuracao", "adotar", "--workspace", workspace, "--json")
    adotada = executar_cli("configuracao", "adotar", "--confirmada", "--workspace", workspace, "--json", input=recibo(adoção))
    assert adotada.returncode == 0 and "manter" in (workspace / "Configuracao.ini").read_text()
    (workspace / "Configuracao.ini").write_text(REGRA_A.replace("conversa", "manual"))
    rejeição = executar_cli("configuracao", "rejeitar", "--workspace", workspace, "--json")
    rejeitada = executar_cli("configuracao", "rejeitar", "--confirmada", "--workspace", workspace, "--json", input=recibo(rejeição))
    assert rejeitada.returncode == 0 and "manter" in (workspace / "Configuracao.ini").read_text()
    mostrar = json.loads(executar_cli("configuracao", "--workspace", workspace, "--json").stdout)
    fonte = next(f for f in mostrar["configuracao"]["linhagem"]["fontes_de_restauracao"] if any(a["tipo"] == "rejeitada" for a in f["artefatos"]))
    restauração = executar_cli("configuracao", "restaurar", "--gravacao", fonte["gravacao"], "--artefato", "rejeitada", "--workspace", workspace, "--json")
    restaurada = executar_cli("configuracao", "restaurar", "--gravacao", fonte["gravacao"], "--artefato", "rejeitada", "--confirmada", "--workspace", workspace, "--json", input=recibo(restauração))
    assert restaurada.returncode == 0 and "manual" in (workspace / "Configuracao.ini").read_text()


def test_rejeitar_sem_payload_da_base_oferece_defaults(tmp_path, executar_cli):
    workspace = tmp_path / "ws"; executar_cli("setup", workspace); publicar(executar_cli, workspace)
    linhagem = next((workspace / ".neoprumo/configuracao/linhagem").iterdir())
    (linhagem / "candidato.ini").unlink()
    (workspace / "Configuracao.ini").write_text(REGRA_B)
    recusada = executar_cli("configuracao", "rejeitar", "--workspace", workspace, "--json")
    assert recusada.returncode == 1 and "--defaults" in json.loads(recusada.stdout)["mensagem"]
    preview = executar_cli("configuracao", "rejeitar", "--defaults", "--workspace", workspace, "--json")
    assert json.loads(preview.stdout)["decisao"]["destino"]["tipo"] == "defaults"


def test_conflito_fotografa_classes_e_resolve(tmp_path, executar_cli):
    workspace = tmp_path / "ws"; executar_cli("setup", workspace)
    (workspace / "Configuracao.ini").write_text(REGRA_A)
    (workspace / "Configuracao 2.ini").write_text(REGRA_B)
    (workspace / "Configuracao 3.ini").write_text(REGRA_B)
    fase1 = executar_cli("configuracao", "resolver", "--workspace", workspace, "--json")
    foto = json.loads(fase1.stdout)
    assert foto["status"] == "fotografado" and len(foto["classes"]) == 2
    classe = foto["classes"][0]
    entrada = json.dumps({"recibo": classe["decisao"], "token": classe["token"]})
    fase2 = executar_cli("configuracao", "resolver", "--snapshot", foto["snapshot"], "--escolher", classe["digital"][:12], "--confirmada", "--workspace", workspace, "--json", input=entrada)
    assert fase2.returncode == 0
    assert not (workspace / "Configuracao 2.ini").exists()


def test_lock_local_recusa_segunda_escrita_e_fica_fora_do_workspace(tmp_path):
    workspace = tmp_path / "ws"; workspace.mkdir()
    with lock_configuracao(workspace) as primeiro:
        assert workspace not in primeiro.caminho.parents
        try:
            with lock_configuracao(workspace): pass
        except LockOcupado:
            pass
        else:
            raise AssertionError("o segundo lock deveria recusar")


def _registro(pasta, status, anterior=None, artefatos=None):
    dados = {"registro": 1, "gesto": "snapshot-conflito" if status == "nao publica" else "gravar",
             "autorizada_em": "2026-08-11T10:00:00-03:00", "anterior": anterior,
             "publicacao": {"status": status}, "artefatos": artefatos or []}
    if status != "nao publica": dados["regras"] = []
    (pasta / "registro.json").write_text(json.dumps(dados))


def test_saude_poda_e_cabeca_por_fecho_transitivo(tmp_path):
    raiz = tmp_path / "linhagem"; raiz.mkdir()
    gravacoes = []
    anterior = None
    for nome, status in (("A", "publicado"), ("B", "publicacao incompleta"), ("C", "publicado")):
        pasta = raiz / nome; pasta.mkdir(); _registro(pasta, status, anterior); anterior = nome
        gravacoes.append(inspecionar_gravacao(pasta))
    assert analisar_grafo(gravacoes)["cabecas"] == ["C"]
    pasta = raiz / "P"; pasta.mkdir(); conteudo = b"x"
    artefatos = [{"arquivo": "candidato.ini", "tipo": "candidato", "digital": digital_bytes(conteudo)}]
    _registro(pasta, "nao publica", artefatos=artefatos)
    (pasta / "poda.json").write_text(json.dumps({"poda": 1, "payloads_removidos": artefatos, "em": "agora"}))
    assert inspecionar_gravacao(pasta)["saude"] == "podada"
