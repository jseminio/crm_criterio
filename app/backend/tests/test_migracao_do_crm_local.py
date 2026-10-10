"""Migrar do CRM local para a nuvem (decisões de Eduardo, 10/10/2026): os dados de negócio vêm do backup do local;
usuários, perfis, integrações e o registro de manutenção da nuvem ficam como estão. Prévia sem gravar; backup da
nuvem antes; só o Administrador; confirmação explícita."""

from __future__ import annotations

import io
from decimal import Decimal as D

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.backup import exportar
from crm.backup.migracao import migrar, previa
from crm.db.base import Base
from crm.db.modelos import ConfiguracaoDoSistema, Contrato, GrupoEconomico, ManutencaoAplicada, Perfil, Usuario
from crm.domain.listas import SituacaoContrato

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


def _motor() -> sa.Engine:
    motor = sa.create_engine("sqlite+pysqlite:///:memory:", future=True, poolclass=sa.pool.StaticPool,
                             connect_args={"check_same_thread": False})

    @sa.event.listens_for(motor, "connect")
    def _fk(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    return motor


@pytest.fixture
def backup_do_local() -> bytes:
    local = _motor()
    with Session(local) as s:
        g = GrupoEconomico(nome="Inbel")
        s.add(g)
        s.flush()
        s.add(Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("44725.80"), escopo="Contábil"))
        s.add(Perfil(nome="Do local", permissoes=[]))
        s.add(ConfiguracaoDoSistema(chave="ia.anthropic_chave", valor="cifrada-com-a-chave-do-local", cifrado=True))
        s.commit()
    arquivo = io.BytesIO()
    exportar(local, arquivo)
    return arquivo.getvalue()


@pytest.fixture
def nuvem(engine):
    with Session(engine) as s:
        admin = Perfil(nome="Administrador", administrador=True, permissoes=[])
        comercial = Perfil(nome="Comercial", permissoes=["funil.ver", "configuracoes.backup"])
        s.add_all([admin, comercial])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=comercial.id))
        s.add(GrupoEconomico(nome="Grupo de teste da nuvem"))
        s.add(ConfiguracaoDoSistema(chave="ia.anthropic_chave", valor="cifrada-com-a-chave-da-nuvem", cifrado=True))
        s.add(ManutencaoAplicada(id="2026_10_10_perdida_e_motivos", descricao="x", resultado="ok"))
        s.commit()
    return engine


def test_previa_mostra_o_que_entra_e_o_que_fica_sem_gravar(nuvem, backup_do_local):
    p = previa(nuvem, io.BytesIO(backup_do_local))
    assert p.pode_migrar and p.motivo is None
    por = {l.tabela: l for l in p.linhas}
    assert (por["grupo_economico"].no_arquivo, por["grupo_economico"].na_nuvem, por["grupo_economico"].acao) == (1, 1, "substitui")
    assert por["perfil"].acao == por["usuario"].acao == por["configuracao_do_sistema"].acao == "preserva"
    with Session(nuvem) as s:
        assert [g.nome for g in s.scalars(sa.select(GrupoEconomico))] == ["Grupo de teste da nuvem"]


def test_migrar_traz_os_dados_do_local_e_preserva_os_da_nuvem(nuvem, backup_do_local, tmp_path):
    resumo, antes = migrar(nuvem, io.BytesIO(backup_do_local), pasta_do_backup=tmp_path)
    assert antes.exists() and antes.parent == tmp_path  # o backup da nuvem como estava
    with Session(nuvem) as s:
        assert [g.nome for g in s.scalars(sa.select(GrupoEconomico))] == ["Inbel"]
        assert s.scalars(sa.select(Contrato)).one().preco_mensal == D("44725.80")
        # da nuvem, intactos
        assert {p.nome for p in s.scalars(sa.select(Perfil))} == {"Administrador", "Comercial"}
        assert s.scalars(sa.select(Usuario)).one().email == "karine@grupocriterio.com.br"
        assert s.get(ConfiguracaoDoSistema, "ia.anthropic_chave").valor == "cifrada-com-a-chave-da-nuvem"
        assert s.get(ManutencaoAplicada, "2026_10_10_perdida_e_motivos") is not None


@pytest.fixture
def cliente(nuvem):
    fabrica = sessionmaker(bind=nuvem, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


def test_pela_api_so_o_administrador_e_com_confirmacao(cliente, backup_do_local, monkeypatch, tmp_path):
    import crm.api.app as modulo

    corpo = {"content": backup_do_local, "headers": {"Content-Type": "application/zip"}}
    assert cliente.post("/api/migracao/previa", headers=KARINE, **{"content": backup_do_local}).status_code == 403
    r = cliente.post("/api/migracao/previa", headers=ADMIN, content=backup_do_local)
    assert r.status_code == 200, r.text
    assert r.json()["pode_migrar"] and r.json()["registros_que_entram"] >= 2
    assert cliente.post("/api/migracao/migrar", headers=ADMIN, content=backup_do_local).status_code == 400
    monkeypatch.setattr(modulo.Path, "home", classmethod(lambda cls: tmp_path))
    r = cliente.post("/api/migracao/migrar", headers={**ADMIN, "x-confirmacao": "MIGRAR"}, content=backup_do_local)
    assert r.status_code == 200, r.text
    assert r.json()["backup_de_antes"].startswith("crm-antes-de-migrar-")
    assert cliente.get("/api/grupos", headers=ADMIN).json()["itens"][0]["nome"] == "Inbel"
