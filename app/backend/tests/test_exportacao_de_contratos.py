"""A Gestão de contratos em Excel (30/10/2026)."""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Contrato, Empresa, GrupoEconomico
from crm.domain.listas import SituacaoContrato, SituacaoGrupo
from crm.relatorios.exportacao_de_contratos import COLUNAS

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def _planilha(resposta):
    return openpyxl.load_workbook(io.BytesIO(resposta.content))["Contratos"]


def _linhas(ws):
    """As linhas de contrato, sem o cabeçalho e sem a linha de total."""
    return [[c.value for c in linha] for linha in ws.iter_rows(min_row=2) if linha[0].value
            and not str(linha[0].value).startswith("Total")]


@pytest.fixture
def dois(sessao: Session) -> dict[str, int]:
    grupo = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    sessao.add(grupo)
    sessao.flush()
    empresa = Empresa(grupo_id=grupo.id, razao_social="Alfa Ltda", cnpj="12345678000190")
    sessao.add(empresa)
    sessao.flush()
    ativo = Contrato(
        grupo_id=grupo.id, empresa_id=empresa.id, escopo="BPO Financeiro", situacao=SituacaoContrato.ATIVO,
        recorrente=True, preco_mensal=Decimal("1500.50"), preco_anual=Decimal("19506.50"), parcelas_no_ano=13,
        data_inicio=date(2026, 3, 1), data_competencia=date(2026, 3, 1), data_inicio_pagamento=date(2026, 4, 10),
        signatario="Ana",
    )
    aguardando = Contrato(
        grupo_id=grupo.id, escopo="DP", situacao=SituacaoContrato.AGUARDANDO_ASSINATURA,
        preco_mensal=Decimal("500.00"),
    )
    sessao.add_all([ativo, aguardando])
    sessao.commit()
    return {"ativo": ativo.id, "aguardando": aguardando.id}


def test_sem_contrato_devolve_o_cabecalho_e_total_zero(cliente):
    r = cliente.get("/api/contratos/exportar")
    assert r.status_code == 200
    assert r.headers["content-type"] == TIPO_XLSX
    assert f'filename="contratos-{date.today():%Y-%m-%d}.xlsx"' in r.headers["content-disposition"]
    ws = _planilha(r)
    assert [c.value for c in ws[1]] == COLUNAS
    assert _linhas(ws) == []


def test_traz_as_quinze_colunas_com_numero_e_data_de_verdade(cliente, dois):
    ws = _planilha(cliente.get("/api/contratos/exportar", params={"id": [dois["ativo"]]}))
    [linha] = _linhas(ws)
    assert linha[:9] == ["Alfa", "Alfa Ltda", "12.345.678/0001-90", "BPO Financeiro", "Ativo", "Sim", 1500.5, 19506.5, 13]
    assert [v.date() if isinstance(v, datetime) else v for v in linha[9:12]] == [
        date(2026, 3, 1), date(2026, 3, 1), date(2026, 4, 10),
    ]
    assert linha[14] == "Ana"
    assert ws["G2"].number_format == "R$ #,##0.00"
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:O2"


def test_a_ordem_e_os_contratos_sao_os_da_tela(cliente, dois):
    ws = _planilha(cliente.get("/api/contratos/exportar", params={"id": [dois["aguardando"], dois["ativo"]]}))
    assert [l[3] for l in _linhas(ws)] == ["DP", "BPO Financeiro"]


def test_respeita_a_situacao_filtrada(cliente, dois):
    ws = _planilha(cliente.get("/api/contratos/exportar", params={"situacao": ["Aguardando assinatura"]}))
    assert [l[3] for l in _linhas(ws)] == ["DP"]


def test_a_ultima_linha_soma_o_preco_mensal_e_o_anual(cliente, dois):
    ws = _planilha(cliente.get("/api/contratos/exportar"))
    assert ws["A5"].value == "Total (2 contratos)"
    assert ws["G5"].value == "=SUM(G2:G3)"
    assert ws["H5"].value == "=SUM(H2:H3)"


def test_exportar_nao_e_lido_como_id_de_contrato(cliente):
    assert cliente.get("/api/contratos/exportar").status_code == 200
