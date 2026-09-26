"""Carga da carteira anterior ao CRM: empresa por CNPJ, contrato sem data inventada, sem duplicar."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
import sqlalchemy as sa
from openpyxl import Workbook
from sqlalchemy.orm import Session

from crm.carga.carteira import Relatorio, aplicar, ler
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, Oportunidade
from crm.domain.listas import Origem, Situacao, SituacaoContrato, SituacaoGrupo
from crm.domain.mrr import movimento, mrr_atual

CNPJ = ["11222333000181", "11444777000161", "45997418000153"]  # válidos


def _fmt(c):  # 11.222.333/0001-81
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def planilha(tmp_path, linhas, aba="4. Clientes"):
    wb = Workbook()
    ws = wb.active
    ws.title = aba
    ws.append(["Instruções da aba"])
    ws.append([])
    ws.append([])
    ws.append(["#", "Razão Social", "CNPJ", "Grupo Econômico", "Escopo Contratado (referência)", "PORTE", "Ajuste", "Honorário\n(R$/mês)"[:0] + "Honorário (R$/mês)"])
    for i, (razao, cnpj, grupo, escopo, hon) in enumerate(linhas, 1):
        ws.append([i, razao, _fmt(cnpj) if cnpj else "", grupo, escopo, "Micro", None, hon])
    caminho = tmp_path / "carteira.xlsx"
    wb.save(caminho)
    return caminho


def rodar(sessao, caminho):
    rel = Relatorio()
    linhas = ler(caminho, rel)
    if rel.pode_aplicar:
        aplicar(sessao, linhas, rel)
    return rel


BASICA = [
    ("Alfa Comércio Ltda", CNPJ[0], "Grupo Alfa", "Contábil + Fiscal", 1500),
    ("Alfa Serviços SA", CNPJ[1], "Grupo Alfa", "Contábil", 2500.5),
    ("Beta Individual ME", CNPJ[2], "Sem grupo", "Contábil", 900),
]


def test_cria_grupos_empresas_e_contratos_ativos_sem_data_de_assinatura(sessao, tmp_path):
    rel = rodar(sessao, planilha(tmp_path, BASICA))
    assert rel.pode_aplicar
    assert (rel.linhas, rel.grupos_novos, rel.empresas_criadas, rel.contratos_criados) == (3, 2, 3, 3)
    assert rel.total_mensal == D("4900.50")
    nomes = {g.nome: g for g in sessao.scalars(sa.select(GrupoEconomico))}
    assert set(nomes) == {"Grupo Alfa", "Beta Individual ME"}  # individual usa a razão social
    assert nomes["Grupo Alfa"].situacao is SituacaoGrupo.CLIENTE and nomes["Grupo Alfa"].origem is Origem.CARTEIRA_ANTERIOR
    c = sessao.scalars(sa.select(Contrato)).all()
    assert all(x.situacao is SituacaoContrato.ATIVO and x.anterior_ao_crm and x.data_inicio is None for x in c)
    assert sorted(x.preco_mensal for x in c) == [D("900.00"), D("1500.00"), D("2500.50")]


def test_rodar_duas_vezes_nao_duplica(sessao, tmp_path):
    p = planilha(tmp_path, BASICA)
    rodar(sessao, p)
    rel = rodar(sessao, p)
    assert (rel.empresas_criadas, rel.contratos_criados, rel.empresas_existentes, rel.contratos_existentes) == (0, 0, 3, 3)
    assert sessao.scalar(sa.select(sa.func.count()).select_from(Contrato)) == 3


def test_reaproveita_grupo_do_crm_pelo_nome_e_prospect_vira_cliente(sessao, tmp_path):
    g = GrupoEconomico(nome="Grupo Alfa - proposta antiga", situacao=SituacaoGrupo.PROSPECT, origem=Origem.CARGA_2026)
    sessao.add(g)
    sessao.commit()
    rel = rodar(sessao, planilha(tmp_path, BASICA))
    assert (rel.grupos_reaproveitados, rel.grupos_novos, rel.prospects_que_viraram_cliente) == (1, 1, 1)
    assert sessao.get(GrupoEconomico, g.id).situacao is SituacaoGrupo.CLIENTE
    assert {e.grupo_id for e in sessao.scalars(sa.select(Empresa)) if e.cnpj in CNPJ[:2]} == {g.id}


def test_varios_grupos_parecidos_usa_o_de_mais_propostas_e_avisa(sessao, tmp_path):
    a = GrupoEconomico(nome="Grupo Alfa - a"); b = GrupoEconomico(nome="Grupo Alfa - b")
    sessao.add_all([a, b]); sessao.flush()
    sessao.add_all([Oportunidade(grupo_id=b.id, nome=f"p{i}", situacao=Situacao.ENVIAR_PROPOSTA) for i in range(3)])
    sessao.commit()
    rel = rodar(sessao, planilha(tmp_path, BASICA[:1]))
    assert any("combina com 2 grupos" in x for x in rel.avisos)
    assert sessao.scalars(sa.select(Empresa)).one().grupo_id == b.id


def test_nao_sobrescreve_preco_diferente_e_reporta_conflito(sessao, tmp_path):
    rodar(sessao, planilha(tmp_path, BASICA))
    (tmp_path / "carteira.xlsx").unlink()
    novo = [(r, c, g, e, 9999) for r, c, g, e, _ in BASICA]
    rel = rodar(sessao, planilha(tmp_path, novo))
    assert len(rel.conflitos) == 3
    assert sorted(c.preco_mensal for c in sessao.scalars(sa.select(Contrato))) == [D("900.00"), D("1500.00"), D("2500.50")]


@pytest.mark.parametrize("linha,trecho", [
    (("X Ltda", "12345678000100", "Sem grupo", "Contábil", 100), "CNPJ inválido"),
    (("X Ltda", CNPJ[0], "Sem grupo", "Contábil", 0), "maior que zero"),
    (("X Ltda", CNPJ[0], "Sem grupo", "Contábil", "abc"), "ilegível"),
])
def test_erros_bloqueiam(sessao, tmp_path, linha, trecho):
    rel = rodar(sessao, planilha(tmp_path, [linha]))
    assert not rel.pode_aplicar and trecho in " ".join(rel.erros)
    assert sessao.scalar(sa.select(sa.func.count()).select_from(Contrato)) == 0


def test_cnpj_repetido_e_erro(sessao, tmp_path):
    rel = rodar(sessao, planilha(tmp_path, [BASICA[0], BASICA[0]]))
    assert any("já apareceu" in e for e in rel.erros)


def test_escopo_a_verificar_fica_em_branco_com_aviso(sessao, tmp_path):
    rel = rodar(sessao, planilha(tmp_path, [("X Ltda", CNPJ[0], "Sem grupo", "— (verificar contrato)", 100)]))
    assert rel.pode_aplicar and any("verificar" in a for a in rel.avisos)
    assert sessao.scalars(sa.select(Contrato)).one().escopo is None


def test_planilha_sem_a_aba_e_recusada(sessao, tmp_path):
    rel = Relatorio()
    assert ler(planilha(tmp_path, BASICA, aba="Outra"), rel) == [] and not rel.pode_aplicar


def test_mrr_conta_a_carteira_anterior_desde_sempre_e_nunca_como_novo(sessao, tmp_path):
    rodar(sessao, planilha(tmp_path, BASICA))
    contratos = list(sessao.scalars(sa.select(Contrato)))
    assert mrr_atual(contratos).valor == D("4900.50")
    m = movimento(contratos, date(2026, 9, 1), date(2026, 9, 25), date(2026, 9, 25))
    assert (m.mrr_inicio, m.novo, m.mrr_fim) == (D("4900.50"), D("0.00"), D("4900.50"))
