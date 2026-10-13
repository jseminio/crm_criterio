"""Reajuste anual de julho pelo IPCA (decisões de Eduardo em 13/10/2026).

Julho, IPCA desde a última definição do preço até junho, adiado quem não tem 12 meses, não recorrente longo
como "Você decide", e nada aplicado sem uma pessoa autorizar.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import Contrato, EventoDeContrato, GrupoEconomico, IpcaDoMes, Oportunidade, Perfil, Usuario
from crm.domain import reajuste as r
from crm.domain.listas import IndiceDeReajuste, LinhaServico, Situacao, SituacaoContrato, TipoDeEventoDeContrato as T
from crm.indices import ipca as indice
from crm.indices.bcb import BuscaDoIpcaFalhou, _ler

S = r.SituacaoDoReajuste

# Série fictícia de teste: 0,50% todo mês, para a conta ficar conferível à mão.
MEIO = D("0.50")


def _serie(de: date, ate: date, valor: D = MEIO) -> dict[date, D]:
    meses, d = {}, de.replace(day=1)
    while d <= ate:
        meses[d] = valor
        d = date(d.year + d.month // 12, d.month % 12 + 1, 1)
    return meses


def _contrato(**kw) -> r.ContratoParaReajuste:
    padrao = dict(id=1, situacao=SituacaoContrato.ATIVO, recorrente=True, indice=IndiceDeReajuste.IPCA,
                  preco_mensal=D("7000.00"), preco_anual=D("91000.00"), parcelas_no_ano=13,
                  data_inicio=date(2026, 7, 10), anterior_ao_crm=False, data_fim=None, saida_em=None, reajustes=())
    padrao.update(kw)
    return r.ContratoParaReajuste(**padrao)


SERIE = _serie(date(2016, 1, 1), date(2027, 6, 1))


# ── Regra ──────────────────────────────────────────────────────────────────────────────────────────

def test_acumulado_e_composto_nao_somado():
    assert r.acumulado([D("1"), D("1")]).quantize(D("0.0001")) == D("2.0100")


def test_ano_normal_usa_os_12_meses_de_julho_a_junho():
    linha = r.linha_do_reajuste(_contrato(), 2027, SERIE)
    assert linha.situacao is S.REAJUSTAR
    assert (linha.de, linha.ate, linha.meses) == (date(2026, 7, 1), date(2027, 6, 1), 12)
    assert linha.ipca == r.acumulado([MEIO] * 12).quantize(D("0.0001"))
    assert linha.mensal_sugerido == (D("7000") * (1 + linha.ipca / 100)).quantize(D("0.01"))
    assert linha.anual_sugerido == linha.mensal_sugerido * 13
    assert linha.aprovavel


def test_quem_entrou_em_janeiro_fica_para_o_julho_seguinte_com_o_acumulado_desde_a_entrada():
    """O exemplo de Eduardo: entrou em janeiro, em julho tem menos de 12 meses."""
    c = _contrato(data_inicio=date(2026, 1, 20))
    adiado = r.linha_do_reajuste(c, 2026, SERIE)
    assert adiado.situacao is S.ADIADO and adiado.adiado_para == 2027 and adiado.meses == 6
    linha = r.linha_do_reajuste(c, 2027, SERIE)
    assert linha.situacao is S.REAJUSTAR
    assert (linha.de, linha.ate, linha.meses) == (date(2026, 1, 1), date(2027, 6, 1), 18)


def test_doze_meses_exatos_ja_reajusta():
    assert r.linha_do_reajuste(_contrato(data_inicio=date(2025, 7, 31)), 2026, SERIE).situacao is S.REAJUSTAR
    assert r.linha_do_reajuste(_contrato(data_inicio=date(2025, 8, 1)), 2026, SERIE).situacao is S.ADIADO


def test_o_ultimo_reajuste_e_a_nova_base():
    c = _contrato(data_inicio=date(2024, 3, 1), reajustes=(date(2026, 7, 1),))
    assert r.linha_do_reajuste(c, 2026, SERIE).situacao is S.REAJUSTADO
    linha = r.linha_do_reajuste(c, 2027, SERIE)
    assert (linha.de, linha.meses) == (date(2026, 7, 1), 12)


def test_renegociacao_no_meio_do_ano_adia_o_reajuste():
    """Lei 10.192/2001: 12 meses desde a última revisão do preço."""
    c = _contrato(data_inicio=date(2024, 3, 1), reajustes=(date(2027, 3, 15),))
    assert r.linha_do_reajuste(c, 2027, SERIE).situacao is S.ADIADO


def test_assinado_depois_de_julho_nao_entra_no_ano():
    assert r.linha_do_reajuste(_contrato(data_inicio=date(2027, 8, 1)), 2027, SERIE) is None


def test_nao_recorrente_longo_e_voce_decide_e_curto_que_acabou_nao_entra():
    projeto = _contrato(recorrente=False, preco_mensal=None, preco_anual=D("60000"), data_inicio=date(2026, 3, 1))
    linha = r.linha_do_reajuste(projeto, 2027, SERIE)
    assert linha.situacao is S.DECIDIR and linha.anual_sugerido > D("60000")
    acabou = _contrato(recorrente=False, preco_mensal=None, preco_anual=D("60000"), data_inicio=date(2026, 3, 1),
                       data_fim=date(2027, 2, 28))
    assert r.linha_do_reajuste(acabou, 2027, SERIE) is None


def test_sem_reajuste_igpm_saida_e_encerrado():
    assert r.linha_do_reajuste(_contrato(indice=IndiceDeReajuste.SEM_REAJUSTE), 2027, SERIE).situacao is S.SEM_REAJUSTE
    assert r.linha_do_reajuste(_contrato(indice=IndiceDeReajuste.IGPM), 2027, SERIE).situacao is S.DECIDIR
    assert r.linha_do_reajuste(_contrato(saida_em=date(2027, 9, 30)), 2027, SERIE) is None
    assert r.linha_do_reajuste(_contrato(situacao=SituacaoContrato.ENCERRADO), 2027, SERIE) is None


def test_carteira_anterior_ao_crm_presume_o_julho_anterior():
    linha = r.linha_do_reajuste(_contrato(data_inicio=None, anterior_ao_crm=True), 2027, SERIE)
    assert linha.base_presumida and linha.meses == 12 and "anterior ao CRM" in linha.observacao


def test_sem_junho_publicado_e_previa_e_nao_aprova():
    linha = r.linha_do_reajuste(_contrato(), 2027, _serie(date(2026, 7, 1), date(2027, 5, 1)))
    assert linha.meses_faltando == (date(2027, 6, 1),)
    assert not linha.aprovavel


# ── Banco Central ──────────────────────────────────────────────────────────────────────────────────

def test_le_a_serie_do_banco_central():
    assert _ler([{"data": "01/06/2027", "valor": "0.26"}]) == {date(2027, 6, 1): D("0.26")}
    with pytest.raises(BuscaDoIpcaFalhou):
        _ler({"erro": "x"})


def test_atualizar_grava_o_que_falta_e_revisa_o_que_mudou(sessao: Session):
    sessao.add(IpcaDoMes(mes=date(2027, 4, 1), variacao=D("0.40")))
    sessao.flush()
    pedidos = []

    def buscar(de, ate):
        pedidos.append((de, ate))
        return {date(2027, 4, 1): D("0.43"), date(2027, 5, 1): D("0.30")}

    feito = indice.atualizar(sessao, date(2027, 6, 10), buscar)
    assert (feito.novos, feito.revistos, feito.ultimo_mes) == (1, 1, date(2027, 5, 1))
    assert pedidos == [(date(2027, 4, 1), date(2027, 6, 10))]
    assert indice.serie(sessao) == {date(2027, 4, 1): D("0.43"), date(2027, 5, 1): D("0.30")}
    assert not indice.precisa_atualizar(sessao, date(2027, 6, 10))


def test_banco_central_fora_nao_apaga_nada(sessao: Session):
    sessao.add(IpcaDoMes(mes=date(2027, 4, 1), variacao=D("0.40")))
    sessao.flush()

    def fora(de, ate):
        raise BuscaDoIpcaFalhou("o Banco Central não respondeu (ConnectError)")

    feito = indice.atualizar(sessao, date(2027, 7, 15), fora)
    assert feito.erro and indice.serie(sessao) == {date(2027, 4, 1): D("0.40")}


# ── API ────────────────────────────────────────────────────────────────────────────────────────────

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


@pytest.fixture
def base(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        contratos = Perfil(nome="Contratos", permissoes=["contratos.ver"])
        a, b, c = GrupoEconomico(nome="Cliente A"), GrupoEconomico(nome="Cliente B"), GrupoEconomico(nome="Cliente C")
        s.add_all([contratos, a, b, c])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=contratos.id))
        op = Oportunidade(grupo_id=b.id, nome="B", situacao=Situacao.ACEITA, linha_servico=LinhaServico.C1,
                          reajuste=IndiceDeReajuste.IPCA)
        s.add(op)
        s.flush()
        s.add_all([
            Contrato(grupo_id=a.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("7000"), preco_anual=D("91000"),
                     data_inicio=date(2026, 7, 5), escopo="BPO Financeiro"),
            Contrato(grupo_id=b.id, oportunidade_id=op.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("5000"),
                     data_inicio=date(2026, 1, 20), escopo="Contábil"),
            Contrato(grupo_id=c.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("4000"),
                     data_inicio=date(2027, 3, 1), escopo="Contábil"),
        ])
        # Buscado há tempo: a regra das 12 horas não segura a próxima busca.
        s.add_all(IpcaDoMes(mes=m, variacao=v, buscado_em=datetime(2026, 1, 1, tzinfo=timezone.utc)) for m, v in _serie(date(2025, 1, 1), date(2027, 6, 1)).items())
        s.commit()


@pytest.fixture
def chamadas():
    return []


@pytest.fixture
def cliente(engine, base, chamadas):
    def buscar(de, ate):
        chamadas.append((de, ate))
        return {}

    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar, buscar_ipca=buscar)) as c:
        yield c


def test_tabela_do_ano(cliente):
    resp = cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-15"}, headers=ADMIN).json()
    assert resp["ipca_completo"] is True
    por_grupo = {l["grupo"]: l for l in resp["linhas"]}
    assert por_grupo["Cliente A"]["situacao"] == "Reajustar" and por_grupo["Cliente A"]["meses"] == 12
    assert por_grupo["Cliente B"]["situacao"] == "Reajustar" and por_grupo["Cliente B"]["meses"] == 18
    assert por_grupo["Cliente C"]["situacao"] == "Adiado" and por_grupo["Cliente C"]["adiado_para"] == 2028


def test_aprovar_grava_o_evento_com_quem_autorizou_e_o_valor_alterado(cliente, engine):
    tabela = cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-15"}, headers=ADMIN).json()
    a = next(l for l in tabela["linhas"] if l["grupo"] == "Cliente A")
    b = next(l for l in tabela["linhas"] if l["grupo"] == "Cliente B")
    corpo = {"ano": 2027, "itens": [
        {"contrato_id": a["contrato_id"], "preco_mensal_novo": a["mensal_sugerido"], "preco_anual_novo": a["anual_sugerido"]},
        {"contrato_id": b["contrato_id"], "preco_mensal_novo": "5300.00"},
    ]}
    resp = cliente.post("/api/reajustes/aprovar", json=corpo, headers=ADMIN)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"aplicados": 2, "autorizado_por": "Eduardo Luiz"}
    with Session(engine) as s:
        ev_b = s.query(EventoDeContrato).filter_by(contrato_id=b["contrato_id"]).one()
        assert ev_b.tipo is T.REAJUSTE and ev_b.data_do_evento == date(2027, 7, 1)
        assert ev_b.preco_mensal_novo == D("5300.00") and "alterado à mão" in ev_b.descricao
        assert "Autorizado por Eduardo Luiz" in ev_b.descricao and "jan/2026 a jun/2027" in ev_b.descricao
        assert s.get(Contrato, a["contrato_id"]).preco_mensal == D(a["mensal_sugerido"])
    depois = cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-15"}, headers=ADMIN).json()
    assert {l["grupo"]: l["situacao"] for l in depois["linhas"]}["Cliente B"] == "Reajustado"


def test_aprovar_e_tudo_ou_nada(cliente, engine):
    tabela = cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-15"}, headers=ADMIN).json()
    ids = {l["grupo"]: l["contrato_id"] for l in tabela["linhas"]}
    corpo = {"ano": 2027, "itens": [
        {"contrato_id": ids["Cliente A"], "preco_mensal_novo": "7400.00"},
        {"contrato_id": ids["Cliente C"], "preco_mensal_novo": "4200.00"},
    ]}
    resp = cliente.post("/api/reajustes/aprovar", json=corpo, headers=ADMIN)
    assert resp.status_code == 409 and "Cliente C" in resp.json()["detail"]
    with Session(engine) as s:
        assert s.query(EventoDeContrato).count() == 0


def test_sem_junho_nao_aprova(cliente, engine):
    with Session(engine) as s:
        s.query(IpcaDoMes).filter(IpcaDoMes.mes == date(2027, 6, 1)).delete()
        s.commit()
    tabela = cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-05"}, headers=ADMIN).json()
    assert tabela["ipca_completo"] is False
    a = next(l for l in tabela["linhas"] if l["grupo"] == "Cliente A")
    assert a["aprovavel"] is False and a["meses_faltando"] == ["2027-06-01"]
    resp = cliente.post("/api/reajustes/aprovar", json={"ano": 2027, "itens": [
        {"contrato_id": a["contrato_id"], "preco_mensal_novo": "7400.00"}]}, headers=ADMIN)
    assert resp.status_code == 409 and "jun/2027" in resp.json()["detail"]


def test_quem_so_ve_contratos_nao_aprova(cliente):
    assert cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-15"}, headers=KARINE).status_code == 200
    resp = cliente.post("/api/reajustes/aprovar", json={"ano": 2027, "itens": [{"contrato_id": 1, "preco_mensal_novo": "1"}]},
                        headers=KARINE)
    assert resp.status_code == 403


def test_tela_completa_o_ipca_sozinha_so_quando_falta_o_mes(cliente, chamadas):
    cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-15"}, headers=ADMIN)
    assert chamadas == []  # junho já está guardado
    cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-08-15"}, headers=ADMIN)
    assert chamadas == [(date(2027, 6, 1), date(2027, 8, 15))]  # falta julho: busca
    serie = cliente.get("/api/ipca", params={"desde": "2027-05-01"}, headers=ADMIN).json()
    assert [m["mes"] for m in serie] == ["2027-06-01", "2027-05-01"]
