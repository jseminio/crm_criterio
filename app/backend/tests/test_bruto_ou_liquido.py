"""Contrato bruto ou líquido e o MRR sempre em bruto (02/10/2026, aprovado por Eduardo)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Contrato, GrupoEconomico, MatrizDeProposta, Oportunidade, Proposta
from crm.domain import mrr
from crm.domain.listas import Situacao, SituacaoContrato, TipoDeEventoDeContrato, TipoDeMatriz

HOJE = date(2026, 10, 2)


def _contrato(preco, base=None, situacao=SituacaoContrato.ATIVO, eventos=()):
    return NS(id=1, grupo_id=1, situacao=situacao, preco_mensal=preco, data_inicio=None, base_do_valor=base,
              eventos=list(eventos))


def test_liquido_vira_bruto_pelo_imposto_ao_centavo():
    ev = NS(tipo=TipoDeEventoDeContrato.REAJUSTE, data_do_evento=HOJE, preco_mensal_anterior=D("8000"),
            preco_mensal_novo=D("8900"), iniciativa=None, id=1)
    (liq,), (bru,), (sem,) = (mrr.em_bruto([_contrato(D("8900"), b, eventos=[ev])], D("0.11")) for b in ("liquido", "bruto", None))
    # 8.900 ÷ 0,89 = 10.000, sem arredondar a R$ 50; em MRR, × 13 ÷ 12 (13 parcelas, 09/10/2026)
    assert liq.preco_mensal == D("10833.33")
    assert (liq.eventos[0].preco_mensal_anterior, liq.eventos[0].preco_mensal_novo) == (D("9737.82"), D("10833.33"))
    assert bru.preco_mensal == sem.preco_mensal == D("9641.67")  # 8.900 × 13 ÷ 12
    assert bru.eventos[0].preco_mensal_novo == D("9641.67")


def test_imposto_fora_da_faixa_e_recusado():
    with pytest.raises(ValueError):
        mrr.em_bruto([], D("1"))


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        grupos = [GrupoEconomico(nome=n) for n in ("Líquido", "Bruto", "Sem base", "Da proposta")]
        s.add_all(grupos)
        s.flush()
        s.add_all([
            Contrato(grupo_id=grupos[0].id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("8900"), base_do_valor="liquido"),
            Contrato(grupo_id=grupos[1].id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("5000"), base_do_valor="bruto"),
            Contrato(grupo_id=grupos[2].id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("1000")),
            Contrato(grupo_id=grupos[2].id, anterior_ao_crm=True, situacao=SituacaoContrato.ENCERRADO, preco_mensal=D("700")),
        ])
        com_proposta = Oportunidade(grupo_id=grupos[3].id, nome="Com proposta", situacao=Situacao.ACEITA, preco_mensal=D("6900"))
        sem_proposta = Oportunidade(grupo_id=grupos[3].id, nome="Sem proposta", situacao=Situacao.ACEITA, preco_mensal=D("3000"))
        matriz = MatrizDeProposta(tipo=TipoDeMatriz.CONTABIL, nome_arquivo="m.pptx", conteudo_base64="", enviada_por="t",
                                  faltando=[], desconhecidos=[])
        s.add_all([com_proposta, sem_proposta, matriz])
        s.flush()
        s.add(Proposta(oportunidade_id=com_proposta.id, numero=1, ano=2026, matriz_id=matriz.id, valores={},
                       valor_liquido=D("6900"), valor_bruto=D("7750")))
        s.commit()
        return {"com_proposta": com_proposta.id, "sem_proposta": sem_proposta.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def test_mrr_soma_em_bruto_e_conta_os_convertidos(cliente):
    m = cliente.get("/api/mrr", params={"hoje": HOJE.isoformat()}).json()
    # 8.900 líquido → 10.000 bruto; 5.000 bruto; 1.000 sem base: 16.000, e × 13 ÷ 12 em MRR
    assert m["atual"]["valor"] == "17333.33"
    assert (m["imposto"], m["contratos_liquidos"], m["contratos_sem_base"]) == ("0.11", 1, 1)


def test_contrato_da_proposta_nasce_liquido_e_sem_proposta_nasce_vazio(cliente, ids):
    r = cliente.post(f"/api/oportunidades/{ids['com_proposta']}/converter-em-contrato", json={})
    assert r.status_code == 201, r.text
    assert r.json()["base_do_valor"] == "liquido"
    r = cliente.post(f"/api/oportunidades/{ids['sem_proposta']}/converter-em-contrato", json={})
    assert r.json()["base_do_valor"] is None


def test_marcar_bruto_ou_liquido_vale_ate_no_encerrado(cliente):
    contratos = cliente.get("/api/contratos").json()["itens"]
    encerrado = next(c for c in contratos if c["situacao"] == "Encerrado")
    r = cliente.patch(f"/api/contratos/{encerrado['id']}", json={"base_do_valor": "liquido"})
    assert r.status_code == 200, r.text
    assert r.json()["base_do_valor"] == "liquido"
    r = cliente.patch(f"/api/contratos/{encerrado['id']}", json={"preco_mensal": "800"})
    assert r.status_code == 422  # o resto continua travado
    assert cliente.patch(f"/api/contratos/{encerrado['id']}", json={"base_do_valor": "meio"}).status_code == 422
