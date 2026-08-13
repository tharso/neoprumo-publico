import os
import secrets
from datetime import datetime

from .diario_descritores import (
    FalhaEscrita, abrir_existente, abrir_pastas, escrever_tudo,
    identidade_dir_canonico, ler_validar, mesma_identidade,
    nome_aponta_para, remover_se_existir,
)
from .diario_lock import TrincoOcupado, trinco_diario
from .diario_resultado import emitir, envelope


def agora_local():
    return datetime.now().astimezone()


def normalizar_texto(texto):
    if not isinstance(texto, str):
        return None, "recusado", "O texto precisa ser texto UTF-8."
    linhas = texto.splitlines()
    indice = next((i for i, linha in enumerate(linhas) if linha.strip()), None)
    if indice is None:
        return None, "texto_vazio", "O texto do diário está vazio."
    normalizado = "\n".join([linhas[indice]] + linhas[:indice] + linhas[indice + 1:]) + "\n"
    try:
        normalizado.encode("utf-8")
    except UnicodeEncodeError:
        return None, "recusado", "O texto não forma UTF-8 válido."
    return normalizado, None, None


def _recusa(status, mensagem, workspace, problema, acao=None, **campos):
    return 1, envelope(
        status, mensagem, workspace, [problema], [acao] if acao else [], **campos
    )


def _dia_virou(workspace, dia):
    return _recusa(
        "dia_virou", "O dia civil virou; nada foi gravado.", workspace,
        f"A gravação autorizada era para {dia}, mas esse já não é o dia atual.",
        "Recolha os fatos do dia atual e confirme um novo texto.", dia=dia,
    )


def _indeterminado(workspace, dia, problema):
    return _recusa(
        "indeterminado", "A gravação aconteceu, mas o destino canônico mudou.",
        workspace, problema,
        f"Confira Diario/{dia}.md e não repita a gravação antes dessa conferência.",
        dia=dia,
    )


def _separador(texto):
    if texto.endswith("\n\n"):
        return ""
    if texto.endswith("\n"):
        return "\n"
    return "\n\n"


def _reservar_temporario(dia, dirfd):
    for _ in range(100):
        nome = f".diario-{dia}-{secrets.token_hex(8)}.tmp"
        try:
            descritor = os.open(
                nome, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=dirfd,
            )
            return nome, descritor
        except FileExistsError:
            continue
    raise OSError("não foi possível reservar um nome temporário novo")


def _append(workspace, dia, nome, secao, wsfd, dirfd):
    try:
        descritor, estado = abrir_existente(nome, dirfd)
    except (OSError, ValueError, UnicodeError) as erro:
        return _recusa("recusado", "O diário não pôde ser aberto com segurança.", workspace, f"Diário do dia: {erro}.", dia=dia)
    try:
        try:
            atual = ler_validar(descritor, dia)
        except (OSError, ValueError, UnicodeError) as erro:
            return _recusa("recusado", "O diário existente foi preservado.", workspace, f"Diário do dia: {erro}.", dia=dia)
        dados = (_separador(atual) + secao).encode("utf-8")
        try:
            if not identidade_dir_canonico(wsfd, dirfd):
                return _recusa("recusado", "A pasta Diario mudou; nada foi gravado.", workspace, "A pasta aberta deixou de ser a pasta Diario canônica.", dia=dia)
        except OSError as erro:
            return _recusa("recusado", "A pasta Diario não pôde ser reconferida.", workspace, f"Falha ao reconferir Diario ({erro}).", dia=dia)
        if agora_local().date().isoformat() != dia:
            return _dia_virou(workspace, dia)
        try:
            escrever_tudo(descritor, dados)
        except FalhaEscrita as erro:
            if erro.gravados:
                return _recusa("parcial", "Uma seção ficou parcialmente gravada.", workspace, f"Entraram {erro.gravados} bytes antes da falha; o diário precisa de conferência manual.", "Confira o fim do arquivo e repare a seção manualmente.", dia=dia)
            return _recusa("recusado", "Nada foi gravado no diário.", workspace, f"A escrita falhou antes do primeiro byte ({erro.erro}).", dia=dia)
        problemas, acoes = [], []
        try:
            os.fsync(descritor)
        except OSError as erro:
            problemas.append(f"Os bytes foram apensados, mas a sincronização falhou ({erro}).")
            acoes.append("Confira o arquivo antes de repetir; uma repetição cega pode duplicar a seção.")
        try:
            if not nome_aponta_para(nome, estado, dirfd):
                return _indeterminado(workspace, dia, "Os bytes foram escritos inteiros num arquivo que o nome canônico não aponta mais.")
            if not identidade_dir_canonico(wsfd, dirfd):
                return _indeterminado(workspace, dia, "A seção foi gravada na pasta antiga depois de Diario ter sido substituída.")
        except OSError as erro:
            return _indeterminado(workspace, dia, f"A seção foi escrita, mas o destino não pôde ser reconferido ({erro}).")
        return 0, envelope("gravado", "Seção apensada ao diário.", workspace, problemas, acoes, dia=dia, arquivo=str(workspace / "Diario" / nome), secao=secao.splitlines()[0])
    finally:
        os.close(descritor)


def _criar(workspace, dia, nome, secao, wsfd, dirfd):
    temporario = None
    tempfd = None
    try:
        try:
            temporario, tempfd = _reservar_temporario(dia, dirfd)
        except OSError as erro:
            return _recusa(
                "recusado", "O arquivo temporário não pôde ser criado.",
                workspace, f"Falha ao reservar um nome temporário ({erro}).", dia=dia,
            )
        dados = (f"# {dia}\n\n" + secao).encode("utf-8")
        try:
            escrever_tudo(tempfd, dados)
            os.fsync(tempfd)
        except (FalhaEscrita, OSError) as erro:
            remover_se_existir(temporario, dirfd)
            detalhe = erro.erro if isinstance(erro, FalhaEscrita) else erro
            return _recusa("recusado", "O diário não foi criado.", workspace, f"A preparação do arquivo temporário falhou ({detalhe}).", dia=dia)
        estado = os.fstat(tempfd)
        try:
            nome_temp = os.stat(temporario, dir_fd=dirfd, follow_symlinks=False)
            if not mesma_identidade(estado, nome_temp):
                remover_se_existir(temporario, dirfd)
                return _recusa("recusado", "O diário não foi criado.", workspace, "O temporário mudou antes da publicação.", dia=dia)
        except OSError as erro:
            remover_se_existir(temporario, dirfd)
            return _recusa("recusado", "O diário não foi criado.", workspace, f"O temporário não pôde ser reconferido ({erro}).", dia=dia)
        try:
            if not identidade_dir_canonico(wsfd, dirfd):
                remover_se_existir(temporario, dirfd)
                return _recusa("recusado", "A pasta Diario mudou; nada foi publicado.", workspace, "A pasta aberta deixou de ser a pasta Diario canônica.", dia=dia)
            if agora_local().date().isoformat() != dia:
                remover_se_existir(temporario, dirfd)
                return _dia_virou(workspace, dia)
            os.link(temporario, nome, src_dir_fd=dirfd, dst_dir_fd=dirfd, follow_symlinks=False)
        except FileExistsError:
            remover_se_existir(temporario, dirfd)
            return _recusa("recusado", "O diário do dia acabou de nascer; tente de novo.", workspace, "Outro escritor publicou o arquivo primeiro.", dia=dia)
        except OSError as erro:
            remover_se_existir(temporario, dirfd)
            return _recusa("recusado", "O diário não foi publicado.", workspace, f"A publicação falhou ({erro}).", dia=dia)
        try:
            final = os.stat(nome, dir_fd=dirfd, follow_symlinks=False)
            if not mesma_identidade(estado, final):
                remover_se_existir(temporario, dirfd)
                return _indeterminado(workspace, dia, "O nome final não aponta para o arquivo temporário que foi preparado.")
        except OSError as erro:
            return _indeterminado(workspace, dia, f"O arquivo foi publicado, mas seu destino não pôde ser conferido ({erro}).")
        problemas, acoes = [], []
        try:
            os.unlink(temporario, dir_fd=dirfd)
        except OSError as erro:
            problemas.append(f"O diário foi publicado, mas sobraram os nomes {nome} e {temporario} ({erro}).")
            acoes.append(f"Confira que ambos apontam para o mesmo conteúdo e remova com segurança {temporario}.")
        try:
            os.fsync(dirfd)
        except OSError as erro:
            problemas.append(f"O nome do diário existe agora, mas pode não sobreviver a uma queda ({erro}).")
            acoes.append("Confira o arquivo antes de repetir; uma repetição cega pode duplicar a seção.")
        try:
            if not identidade_dir_canonico(wsfd, dirfd):
                return _indeterminado(workspace, dia, "O diário foi publicado na pasta antiga depois de Diario ter sido substituída.")
        except OSError as erro:
            return _indeterminado(workspace, dia, f"O diário foi publicado, mas a pasta canônica não pôde ser reconferida ({erro}).")
        return 0, envelope("gravado", "Diário do dia criado.", workspace, problemas, acoes, dia=dia, arquivo=str(workspace / "Diario" / nome), secao=secao.splitlines()[0])
    finally:
        if tempfd is not None:
            os.close(tempfd)


def operar_gravar(texto, dia, workspace):
    texto, status, falha = normalizar_texto(texto)
    if falha:
        return _recusa(status, "O diário não foi gravado.", workspace, falha, dia=dia)
    try:
        with trinco_diario(workspace):
            fotografia = agora_local()
            dia_foto = fotografia.date().isoformat()
            if dia != dia_foto:
                return _dia_virou(workspace, dia)
            nome = f"{dia}.md"
            secao = f"## Sessão {fotografia.strftime('%H:%M')}\n\n{texto}"
            try:
                wsfd, dirfd = abrir_pastas(workspace)
            except OSError as erro:
                return _recusa("recusado", "A pasta Diario não pôde ser aberta com segurança.", workspace, f"Diario: {erro}.", dia=dia)
            try:
                try:
                    os.stat(nome, dir_fd=dirfd, follow_symlinks=False)
                except FileNotFoundError:
                    return _criar(workspace, dia, nome, secao, wsfd, dirfd)
                return _append(workspace, dia, nome, secao, wsfd, dirfd)
            finally:
                os.close(dirfd)
                os.close(wsfd)
    except TrincoOcupado:
        return _recusa("gravacao_em_andamento", "Outra gravação do diário está em andamento.", workspace, "O trinco do diário já está ocupado.", "Espere a outra gravação terminar e recolha novamente antes de repetir.", dia=dia)
    except OSError as erro:
        return _recusa("recusado", "O trinco do diário não pôde ser criado ou aberto.", workspace, f"Falha no trinco ({erro}).", dia=dia)


def executar_gravar(texto, dia, workspace, usar_json=False):
    codigo, resultado = operar_gravar(texto, dia, workspace)
    emitir(resultado, usar_json, erro=bool(codigo))
    return codigo
