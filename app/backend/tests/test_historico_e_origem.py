"""E4: histórico de preço com reajuste e origem de cada campo da volumetria."""

from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import GrupoEconomico, HistoricoDePreco, Oportunidade
from crm.domain.listas import Situacao


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


@pytest.fixture
def op(sessao: Session) -> Oportunidade:
    g = GrupoEconomico(nome="Alfa")
    sessao.add(g)
    sessao.flush()
    o = Oportunidade(grupo_id=g.id, nome="Alfa BPO", situacao=Situacao.ENVIAR_PROPOSTA,
                     preco_mensal=Decimal("1000.00"), preco_anual=Decimal("12000.00"),
                     documentos_fiscais_mes=100)
    sessao.add(o)
    sessao.commit()
    return o


class TestHistoricoDePreco:
    def test_reajuste_guarda_o_preco_anterior_e_o_motivo(self, cliente, op):
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"preco_mensal": "1100.00", "motivo_do_preco": "reajuste anual"})
        assert r.status_code == 200
        h = r.json()["historico_de_preco"]
        assert len(h) == 1
        assert (h[0]["preco_mensal_anterior"], h[0]["preco_mensal_novo"]) == ("1000.00", "1100.00")
        assert h[0]["motivo"] == "reajuste anual" and h[0]["origem"] == "CRM"
        assert r.json()["preco_mensal"] == "1100.00"

    def test_salvar_sem_mudar_o_preco_nao_cria_linha(self, cliente, op):
        # a tela manda o rascunho inteiro a cada salvar
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"preco_mensal": "1000.00", "preco_anual": "12000.00", "observacao": "x"})
        assert r.json()["historico_de_preco"] == []

    def test_motivo_sem_mudanca_de_preco_e_ignorado(self, cliente, op):
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"motivo_do_preco": "nada mudou"})
        assert r.json()["historico_de_preco"] == []

    def test_varios_reajustes_acumulam_do_mais_recente_para_o_mais_antigo(self, cliente, op):
        cliente.patch(f"/api/oportunidades/{op.id}", json={"preco_mensal": "1100.00"})
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"preco_mensal": "1210.00"})
        h = r.json()["historico_de_preco"]
        assert [x["preco_mensal_novo"] for x in h] == ["1210.00", "1100.00"]
        assert h[0]["preco_mensal_anterior"] == "1100.00"

    def test_motivo_vazio_vira_nulo(self, cliente, op):
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"preco_anual": "13000.00", "motivo_do_preco": "   "})
        assert r.json()["historico_de_preco"][0]["motivo"] is None

    def test_o_historico_nao_e_editavel_pela_api(self, cliente, op):
        assert cliente.put(f"/api/oportunidades/{op.id}/historico-de-preco", json={}).status_code == 404


class TestOrigemDaVolumetria:
    def test_grava_a_origem_de_um_campo_preenchido(self, cliente, op):
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"origem_da_volumetria": {"documentos_fiscais_mes": "Questionário"}})
        assert r.status_code == 200 and r.json()["origem_da_volumetria"] == {"documentos_fiscais_mes": "Questionário"}

    def test_recusa_origem_de_campo_que_nao_e_da_volumetria(self, cliente, op):
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"origem_da_volumetria": {"preco_mensal": "Entrevista"}})
        assert r.status_code == 422 and "preco_mensal" in r.json()["detail"]

    def test_recusa_valor_fora_da_lista(self, cliente, op):
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"origem_da_volumetria": {"documentos_fiscais_mes": "Palpite"}})
        assert r.status_code == 422

    def test_origem_de_campo_vazio_e_descartada(self, cliente, op):
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"origem_da_volumetria": {"pagamentos_mes": "Entrevista", "documentos_fiscais_mes": "Entrevista"}})
        assert r.json()["origem_da_volumetria"] == {"documentos_fiscais_mes": "Entrevista"}

    def test_limpar_o_campo_leva_a_origem_junto(self, cliente, op):
        cliente.patch(f"/api/oportunidades/{op.id}", json={"origem_da_volumetria": {"documentos_fiscais_mes": "Entrevista"}})
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"documentos_fiscais_mes": None})
        assert r.json()["origem_da_volumetria"] == {}

    def test_editar_outro_campo_nao_mexe_na_origem(self, cliente, op):
        cliente.patch(f"/api/oportunidades/{op.id}", json={"origem_da_volumetria": {"documentos_fiscais_mes": "Entrevista"}})
        r = cliente.patch(f"/api/oportunidades/{op.id}", json={"observacao": "oi"})
        assert r.json()["origem_da_volumetria"] == {"documentos_fiscais_mes": "Entrevista"}


def test_historico_e_origem_fazem_ida_e_volta_no_backup(engine, op, sessao):
    import io

    from crm.backup import exportar, importar
    from crm.db.base import Base

    sessao.add(HistoricoDePreco(oportunidade_id=op.id, origem="CRM", preco_mensal_anterior=Decimal("1"), preco_mensal_novo=Decimal("2")))
    op.origem_da_volumetria = {"documentos_fiscais_mes": "Entrevista"}
    sessao.commit()
    buf = io.BytesIO(); exportar(engine, buf); buf.seek(0)
    destino = sa.create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(destino)
    importar(destino, buf)
    with Session(destino) as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(HistoricoDePreco)) == 1
        assert s.scalars(sa.select(Oportunidade)).one().origem_da_volumetria == {"documentos_fiscais_mes": "Entrevista"}
