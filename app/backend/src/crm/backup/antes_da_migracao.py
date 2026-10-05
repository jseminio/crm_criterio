"""Backup do banco (`pg_dump -Fc`) antes de aplicar migração pendente (#93, 05/10/2026).

Uso (pelo `atualizador.sh`, só quando há migração pendente):

    python -m crm.backup.antes_da_migracao --de <revisão do banco> --para <head> --dias 7

Fluxo: `pg_dump -Fc` para `<nome>.dump.parcial` → confere (arquivo não vazio e `pg_restore -l` lê o
índice) → renomeia para `.dump` → **só então** apaga os com mais de `--dias` dias (padrão 7). O mais
recente e o recém-criado ficam sempre: a retenção nunca zera a pasta.
Qualquer falha sai com código 1, apaga o parcial, não apaga backup nenhum e diz a causa no stderr.

A senha nunca vai para argumento de comando nem para log: vai na `PGPASSWORD`, só do processo filho.
O dump nasce 0600. A pasta é o volume local `crmcs_backups` (/app/backups), que sobrevive ao Redeploy.

Não substitui o backup diário do painel do Coolify: este é o ponto de volta **imediato** da
migração, na mesma máquina.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

__all__ = ["PASTA", "PREFIXO", "BackupFalhou", "para_libpq", "fazer_backup", "aplicar_retencao", "main"]

PASTA = Path("/app/backups")
PREFIXO = "crmcs-antes-da-migracao-"
TEMPO_LIMITE_SEGUNDOS = 3600


class BackupFalhou(RuntimeError):
    """Falha do backup, com a mensagem pronta para quem opera (sem senha)."""


def para_libpq(url: str) -> tuple[str, str]:
    """`postgresql+psycopg://u:senha@h:5432/db?sslmode=require` → (URI sem senha, senha).

    O URI devolvido pode ir para o argv; a senha vai só na `PGPASSWORD` do filho."""
    partes = urlsplit(url)
    esquema = partes.scheme.split("+", 1)[0].lower()
    if esquema not in ("postgresql", "postgres") or not partes.hostname:
        raise BackupFalhou("o banco configurado não é PostgreSQL; o backup antes da migração só existe para PostgreSQL.")
    restantes, senha_da_query = [], ""
    for chave, valor in parse_qsl(partes.query, keep_blank_values=True):
        if chave.lower() == "password":
            senha_da_query = valor
        else:
            restantes.append((chave, valor))
    senha = unquote(partes.password) if partes.password else senha_da_query
    host = f"[{partes.hostname}]" if ":" in partes.hostname else partes.hostname
    rede = host + (f":{partes.port}" if partes.port else "")
    if partes.username:
        rede = f"{partes.username}@{rede}"
    return urlunsplit(("postgresql", rede, partes.path, urlencode(restantes), "")), senha


_CREDENCIAL = re.compile(r"(://[^:/@\s]*:)\S*@")
_SENHA_NOMEADA = re.compile(r"((?:password|PGPASSWORD)=)[^&\s'\"]+", re.IGNORECASE)


def _limpar(texto: str) -> str:
    texto = _CREDENCIAL.sub(r"\1***@", texto or "")
    return _SENHA_NOMEADA.sub(r"\1***", texto).strip()[-800:]


def _rotulo(revisao: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", revisao or "") or "nenhuma"


def _rodar(comando: list[str], senha: str) -> subprocess.CompletedProcess:
    ambiente = dict(os.environ)
    if senha:
        ambiente["PGPASSWORD"] = senha
    try:
        return subprocess.run(comando, capture_output=True, text=True, env=ambiente, timeout=TEMPO_LIMITE_SEGUNDOS)
    except FileNotFoundError as exc:
        raise BackupFalhou(f"'{comando[0]}' não está na imagem (falta o postgresql-client).") from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupFalhou(f"'{comando[0]}' passou de {TEMPO_LIMITE_SEGUNDOS}s e foi interrompido.") from exc


def versao_do_pg_dump() -> str:
    feito = _rodar(["pg_dump", "--version"], "")
    return (feito.stdout or feito.stderr).strip()


def _versao_do_servidor(url: str) -> str:
    """Só para o log: o pg_dump recusa servidor mais novo que ele, e ver as duas versões lado a lado
    explica o erro na hora. Falha aqui não impede o backup."""
    try:
        import sqlalchemy as sa

        from crm.db.sessao import criar_engine

        motor = criar_engine(url)
        try:
            with motor.connect() as conexao:
                return str(conexao.execute(sa.text("SHOW server_version")).scalar() or "?").split(" ")[0]
        finally:
            motor.dispose()
    except Exception:  # noqa: BLE001
        return "?"


def aplicar_retencao(pasta: Path, dias: int, protegido: Path | None = None,
                     agora: datetime | None = None) -> list[Path]:
    """Apaga os backups com mais de `dias` dias (pela data de modificação). Devolve os apagados.

    Só toca em `crmcs-antes-da-migracao-*.dump`. Nunca zera a pasta: o mais recente e o `protegido`
    (o recém-criado) ficam sempre, por mais velhos que sejam. `agora` existe para o teste."""
    if dias < 1:
        raise BackupFalhou("BACKUP_ANTES_DIAS precisa ser 1 ou mais.")
    limite = (agora or datetime.now(timezone.utc)).timestamp() - dias * 86400
    dumps = sorted(pasta.glob(f"{PREFIXO}*.dump"), key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    apagados = []
    for velho in dumps[1:]:
        if protegido is not None and velho == protegido:
            continue
        if velho.stat().st_mtime < limite:
            velho.unlink(missing_ok=True)
            apagados.append(velho)
    return apagados


def fazer_backup(url: str, *, pasta: Path, de: str, para: str, dias: int, agora: datetime | None = None) -> Path:
    """Faz o dump conferido e aplica a retenção. Devolve o `.dump`. Levanta `BackupFalhou`."""
    uri, senha = para_libpq(url)
    momento = agora or datetime.now(timezone.utc)
    antigo = os.umask(0o077)
    try:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackupFalhou(f"não consegui criar {pasta}: {exc.strerror or exc}") from exc
        if not os.access(pasta, os.W_OK):
            raise BackupFalhou(f"{pasta} não é gravável (o volume crmcs_backups está montado?).")
        for orfao in pasta.glob(f"{PREFIXO}*.dump.parcial"):
            orfao.unlink(missing_ok=True)
        nome = f"{PREFIXO}{momento.strftime('%Y%m%d-%H%M%S')}-{_rotulo(de)}-para-{_rotulo(para)}.dump"
        final, parcial = pasta / nome, pasta / (nome + ".parcial")
        try:
            feito = _rodar(["pg_dump", "-Fc", "--no-owner", "-f", str(parcial), "-d", uri], senha)
            if feito.returncode != 0:
                raise BackupFalhou(f"pg_dump falhou (código {feito.returncode}): {_limpar(feito.stderr)}")
            if not parcial.exists() or parcial.stat().st_size == 0:
                raise BackupFalhou("o pg_dump terminou, mas o arquivo de backup está vazio.")
            conferido = _rodar(["pg_restore", "-l", str(parcial)], "")
            if conferido.returncode != 0:
                raise BackupFalhou(f"o backup não passou na conferência (pg_restore -l): {_limpar(conferido.stderr)}")
            parcial.chmod(0o600)
            parcial.rename(final)
        except BackupFalhou:
            parcial.unlink(missing_ok=True)
            raise
        except OSError as exc:
            parcial.unlink(missing_ok=True)
            raise BackupFalhou(f"erro ao gravar em {pasta}: {exc.strerror or exc}") from exc
        aplicar_retencao(pasta, dias, protegido=final)  # pela hora real: o mtime dos arquivos é real
        return final
    finally:
        os.umask(antigo)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backup do banco antes da migração (#93).")
    ap.add_argument("--de", default="", help="revisão atual do banco (vazio: nenhuma)")
    ap.add_argument("--para", default="", help="revisão (head) que será aplicada")
    ap.add_argument("--dias", default="7", help="por quantos dias guardar os backups (BACKUP_ANTES_DIAS)")
    ap.add_argument("--pasta", default=str(PASTA), help="onde gravar (padrão: o volume /app/backups)")
    args = ap.parse_args(argv)
    try:
        if not args.dias.strip().isdigit() or int(args.dias) < 1:
            raise BackupFalhou("BACKUP_ANTES_DIAS precisa ser um número inteiro de 1 para cima.")
        from crm.db.sessao import url_do_banco

        url = url_do_banco()
        print(f"[backup] cliente: {versao_do_pg_dump()}; servidor: PostgreSQL {_versao_do_servidor(url)}")
        final = fazer_backup(url, pasta=Path(args.pasta), de=args.de, para=args.para, dias=int(args.dias))
    except BackupFalhou as exc:
        print(f"[backup] ERRO: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — configuração do banco ausente etc.: nunca o valor
        print(f"[backup] ERRO: {type(exc).__name__}: {_limpar(str(exc).splitlines()[0] if str(exc) else '')}",
              file=sys.stderr)
        return 1
    guardados = len(list(Path(args.pasta).glob(f"{PREFIXO}*.dump")))
    print(f"[backup] OK — {final.name} ({final.stat().st_size} bytes); {guardados} guardado(s), retenção de {int(args.dias)} dia(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
