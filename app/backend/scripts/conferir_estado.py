"""Conferências que só RELATAM o estado depois do Redeploy (#93). Nenhuma altera dado.

    python scripts/conferir_estado.py

Chamado pelo `atualizador.sh` (etapa CONFERÊNCIAS). Uma linha por conferência: versão do esquema contra
o head do código, a conta de `CRM_ADMIN_EMAIL`, as contagens principais e o espaço do volume de backups.
Sai sempre com 0: conferência é informação, e informação que falta não impede a API de subir. Não
imprime e-mail, nome de cliente nem a URL do banco — só contagens e situações.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import sqlalchemy as sa  # noqa: E402


def _esquema(motor: sa.Engine) -> str:
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    cabecas = set(ScriptDirectory.from_config(config).get_heads())
    with motor.connect() as conexao:
        atuais = set(MigrationContext.configure(conexao).get_current_heads())
    if atuais == cabecas:
        return f"esquema na revisão {', '.join(sorted(atuais))} = head do código: ok."
    return (f"AVISO: esquema em {', '.join(sorted(atuais)) or '<nenhuma>'}, código em {', '.join(sorted(cabecas))} "
            "(migração pendente ou RUN_MIGRATIONS=false).")


def _admin(sessao) -> str:
    from crm.acesso.entrada import ConfiguracaoDeSenha, ler_configuracao
    from crm.db.modelos import Perfil, Usuario

    config = ler_configuracao()
    if not isinstance(config, ConfiguracaoDeSenha):
        return "admin: entrada por e-mail e senha não configurada (sem CRM_ADMIN_EMAIL)."
    u = sessao.scalar(sa.select(Usuario).where(Usuario.email == config.admin_email))
    if u is None:
        return "admin: a conta de CRM_ADMIN_EMAIL ainda não existe — a API a cria ao subir, com a senha inicial."
    if not u.senha_hash:
        return "admin: a conta de CRM_ADMIN_EMAIL existe sem senha — a API lhe dá a senha inicial ao subir."
    perfil = sessao.get(Perfil, u.perfil_id)
    papel = "Administrador" if perfil is not None and perfil.administrador else "SEM perfil de Administrador"
    return f"admin: a conta de CRM_ADMIN_EMAIL existe, com senha, {'ativa' if u.ativo else 'DESATIVADA'}, {papel}."


def _contagens(sessao) -> str:
    from crm.db.modelos import Contrato, Oportunidade, Usuario

    conta = lambda modelo: sessao.scalar(sa.select(sa.func.count()).select_from(modelo))  # noqa: E731
    ativos = sessao.scalar(sa.select(sa.func.count()).select_from(Usuario).where(Usuario.ativo.is_(True)))
    return (f"contagens: {conta(Oportunidade)} oportunidades, {conta(Contrato)} contratos, "
            f"{conta(Usuario)} usuários ({ativos} ativos).")


def _espaco() -> str:
    from crm.backup.antes_da_migracao import PASTA, PREFIXO

    if not PASTA.is_dir():
        return f"AVISO: {PASTA} não existe (volume crmcs_backups não montado?): sem backup antes da migração."
    uso = shutil.disk_usage(PASTA)
    dumps = list(PASTA.glob(f"{PREFIXO}*.dump"))
    tamanho = sum(p.stat().st_size for p in dumps)
    gb = lambda n: f"{n / 1024 ** 3:.1f} GB"  # noqa: E731
    aviso = "AVISO: " if uso.free < 1024 ** 3 else ""
    return (f"{aviso}backups em {PASTA}: {len(dumps)} arquivo(s), {tamanho / 1024 ** 2:.1f} MB; "
            f"livre {gb(uso.free)} de {gb(uso.total)}.")


def main() -> int:
    from crm.db.sessao import criar_engine, url_do_banco

    try:
        motor = criar_engine(url_do_banco())
    except Exception as exc:  # noqa: BLE001
        print(f"conferências não puderam ser feitas: {type(exc).__name__}.")
        return 0
    from sqlalchemy.orm import Session

    try:
        _relatar("esquema", lambda: _esquema(motor))
        with Session(motor) as sessao:
            _relatar("admin", lambda: _admin(sessao))
            _relatar("contagens", lambda: _contagens(sessao))
    finally:
        motor.dispose()
    _relatar("espaço", _espaco)
    return 0


def _relatar(nome: str, conferencia) -> None:
    try:
        print(conferencia())
    except Exception as exc:  # noqa: BLE001 — conferência nunca derruba a subida
        print(f"AVISO: a conferência '{nome}' não pôde ser feita ({type(exc).__name__}).")


if __name__ == "__main__":
    sys.exit(main())
