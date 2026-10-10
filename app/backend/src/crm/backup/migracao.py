"""Migrar do CRM local para a nuvem (decisão de Eduardo em 10/10/2026: o oficial passa a ser a nuvem).

O CRM local tem os dados de verdade até hoje; a nuvem tem dados que **só existem lá** e não podem se perder:

- **usuários e perfis** de acesso (quem entra na nuvem, com as senhas);
- **configurações das integrações**, cifradas com a chave do servidor (a do local não abriria lá);
- o **registro das tarefas de manutenção** já aplicadas na nuvem;
- os **eventos do WhatsApp** que o webhook da Meta grava (se a tabela existir).

A migração traz do backup do local **todas as outras tabelas**, substituindo as da nuvem, e deixa essas intactas
(aprovado por Eduardo em 10/10/2026). Antes de gravar: a prévia, que não grava nada; e, na hora de gravar, um backup
da nuvem como estava. Tudo numa transação: qualquer erro desfaz a migração inteira.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import sqlalchemy as sa

from crm.backup.formato import ErroDeBackup, ResumoDeBackup, _abrir, _carregar_tabela, _revisao, _tabelas, exportar, verificar
from crm.db.base import agora

__all__ = ["PRESERVADAS", "LinhaDaPrevia", "PreviaDaMigracao", "previa", "migrar"]

PRESERVADAS = frozenset({"usuario", "perfil", "configuracao_do_sistema", "manutencao_aplicada", "evento_do_whatsapp"})
"""As tabelas que ficam como estão na nuvem."""


@dataclass(frozen=True)
class LinhaDaPrevia:
    tabela: str
    no_arquivo: int
    na_nuvem: int
    acao: str
    """"substitui" (vem do local), "preserva" (fica a da nuvem)."""


@dataclass(frozen=True)
class PreviaDaMigracao:
    criado_em: str
    revisao_do_arquivo: str | None
    revisao_da_nuvem: str | None
    pode_migrar: bool
    motivo: str | None
    """Por que não dá para migrar (esquemas diferentes, arquivo de outra versão); `None` quando dá."""
    linhas: list[LinhaDaPrevia]

    @property
    def registros_que_entram(self) -> int:
        return sum(l.no_arquivo for l in self.linhas if l.acao == "substitui")

    @property
    def registros_que_saem(self) -> int:
        return sum(l.na_nuvem for l in self.linhas if l.acao == "substitui")


def _contar(conexao: sa.Connection, tabela: sa.Table) -> int:
    return conexao.execute(sa.select(sa.func.count()).select_from(tabela)).scalar() or 0


def _conferir(resumo: ResumoDeBackup, manifesto: dict, revisao_da_nuvem: str | None) -> str | None:
    conhecidas = {t.name: {c.name for c in t.columns} for t in _tabelas()}
    desconhecidas = sorted(set(manifesto["tabelas"]) - set(conhecidas))
    if desconhecidas:
        return f"o arquivo tem tabelas que esta versão não conhece: {', '.join(desconhecidas)}"
    sobrando = sorted(f"{n}.{c}" for n, i in manifesto["tabelas"].items() for c in i.get("colunas", [])
                      if c not in conhecidas[n])
    if sobrando:
        return f"o arquivo tem colunas que esta versão não conhece: {', '.join(sobrando)}"
    if resumo.revisao_do_esquema and revisao_da_nuvem and resumo.revisao_do_esquema != revisao_da_nuvem:
        return (f"o CRM local está numa versão do banco ({resumo.revisao_do_esquema}) e a nuvem em outra "
                f"({revisao_da_nuvem}): atualize os dois para a mesma versão (Redeploy na nuvem; no local, a main) "
                "e gere o backup de novo")
    return None


def previa(engine: sa.Engine, origem: BinaryIO) -> PreviaDaMigracao:
    """O que a migração faria, tabela por tabela. **Não grava nada.**"""
    resumo = verificar(origem)
    origem.seek(0)
    zf, manifesto = _abrir(origem)
    with zf, engine.connect() as conexao:
        revisao = _revisao(conexao)
        motivo = _conferir(resumo, manifesto, revisao)
        linhas = [
            LinhaDaPrevia(t.name, resumo.tabelas.get(t.name, 0), _contar(conexao, t),
                          "preserva" if t.name in PRESERVADAS else "substitui")
            for t in _tabelas()
        ]
    return PreviaDaMigracao(resumo.criado_em, resumo.revisao_do_esquema, revisao, motivo is None, motivo, linhas)


def migrar(engine: sa.Engine, origem: BinaryIO, *, pasta_do_backup: Path) -> tuple[ResumoDeBackup, Path]:
    """Substitui na nuvem as tabelas que vêm do local e preserva as de `PRESERVADAS`. Antes, grava o backup da
    nuvem como estava em `pasta_do_backup`. Devolve o resumo do arquivo migrado e o caminho do backup de antes."""
    resumo = verificar(origem)
    origem.seek(0)
    zf, manifesto = _abrir(origem)
    with engine.connect() as conexao:
        motivo = _conferir(resumo, manifesto, _revisao(conexao))
    if motivo:
        zf.close()
        raise ErroDeBackup(f"Não dá para migrar: {motivo}.")

    pasta_do_backup.mkdir(parents=True, exist_ok=True)
    antes = pasta_do_backup / f"crm-antes-de-migrar-{agora():%Y%m%d-%H%M%S}.zip"
    exportar(engine, antes)
    antes.chmod(0o600)

    tabelas = [t for t in _tabelas() if t.name not in PRESERVADAS]
    with zf, engine.connect() as conexao, conexao.begin():
        for t in reversed(tabelas):
            conexao.execute(sa.delete(t))
        for tabela in tabelas:
            if tabela.name not in manifesto["tabelas"]:
                continue
            try:
                _carregar_tabela(conexao, tabela, zf.read(f"dados/{tabela.name}.jsonl"))
            except (sa.exc.DBAPIError, ValueError) as erro:
                detalhe = getattr(erro, "orig", None) or erro
                raise ErroDeBackup(f"Não foi possível gravar a tabela {tabela.name}: {detalhe}. Nada foi migrado.") from erro
        if conexao.dialect.name == "postgresql":
            for t in tabelas:
                pk = list(t.primary_key.columns)
                if len(pk) == 1 and isinstance(pk[0].type, sa.Integer):
                    conexao.execute(sa.text(
                        f"SELECT setval(pg_get_serial_sequence('{t.name}', '{pk[0].name}'), "
                        f"COALESCE((SELECT MAX({pk[0].name}) FROM {t.name}), 1), (SELECT COUNT(*) FROM {t.name}) > 0)"
                    ))
    return resumo, antes
