"""Integralidade do cadastro (amostra e lista de campos aprovadas por Eduardo em 13/10/2026): pontos dos campos
devidos e vazios ÷ pontos de todos os devidos, obrigatório 2 e prioritário 1, só o que nasceu desde o corte, e o
legado à parte."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy.orm import Session

from crm.api import integralidade
from crm.api.kpis_lideranca import calcular as calcular_kpis
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, Oportunidade, PessoaContato
from crm.domain.listas import MotivoRecusa, Origem, Situacao, SituacaoContrato, TipoCanal


@pytest.fixture
def cadastro(engine, monkeypatch):
    monkeypatch.setattr(integralidade, "DATA_DE_CORTE", date(2000, 1, 1))  # tudo o que o teste cria é "novo"
    with Session(engine) as s:
        cliente = GrupoEconomico(nome="Cliente X", responsavel_cs="KN")
        prospect = GrupoEconomico(nome="Prospect")
        s.add_all([cliente, prospect])
        s.flush()
        empresa = Empresa(grupo_id=cliente.id, razao_social="Cliente X Ltda", cnpj="11222333000181")
        s.add(empresa)
        s.flush()
        s.add(Contrato(grupo_id=cliente.id, empresa_id=empresa.id, situacao=SituacaoContrato.ATIVO,
                       preco_mensal=D("3000"), data_inicio=date(2026, 9, 1), escopo="BPO Contábil"))
        s.add(Oportunidade(grupo_id=prospect.id, nome="Prospect BPO", servico="BPO Financeiro", situacao=Situacao.PERDIDA,
                           captador="EL", tipo_canal=TipoCanal.SOCIOS, preco_mensal=D("5000"),
                           data_colocacao=date(2026, 9, 2), data_envio_proposta=date(2026, 9, 5)))
        s.add(PessoaContato(nome="Fulana", email="fulana@exemplo.com"))
        s.commit()
    return engine


def test_conta_os_pontos_dos_campos_devidos_com_peso_e_condicao(cadastro):
    with Session(cadastro) as s:
        r = integralidade.calcular(s)
    faltam = {(c.cadastro, c.campo) for c in r.novos if not c.preenchido}
    assert faltam == {
        ("Contrato", "Bruto ou líquido"), ("Contrato", "Signatário"), ("Contrato", "Fim da vigência"),
        ("Cliente", "Classificação (classe e semáforo)"), ("Cliente", "Porte"),
        ("Empresa", "Regime tributário"), ("Empresa", "Endereço (logradouro, município e CEP)"),
        ("Oportunidade", "Motivo de perda"), ("Oportunidade", "Porte"),
        ("Contato", "Vínculo com a empresa"), ("Contato", "Cargo"), ("Contato", "Papel (decisor, influenciador…)"),
    }
    # devidos: contrato 10 + cliente 5 + empresa 4 + oportunidade 15 + contato 6 = 40; vazios: 4 + 3 + 2 + 3 + 4 = 16
    assert sum(c.pontos for c in r.novos) == 40
    assert integralidade.Resultado.pendente_pct(r.novos) == D("40.0")
    # perdida não cobra temperatura nem próxima ação; data de envio já é devida fora de "Enviar proposta"
    campos_da_oportunidade = {c.campo for c in r.novos if c.cadastro == "Oportunidade"}
    assert "Temperatura" not in campos_da_oportunidade and "Data de envio da proposta" in campos_da_oportunidade


def test_quem_responde_e_o_captador_e_o_cs_do_grupo(cadastro):
    with Session(cadastro) as s:
        r = integralidade.calcular(s)
    dono = {c.cadastro: c.responsavel for c in r.novos}
    assert dono == {"Oportunidade": "EL", "Contrato": "KN", "Cliente": "KN", "Empresa": "KN", "Contato": None}


def test_o_legado_fica_a_parte(cadastro):
    with Session(cadastro) as s:
        prospect = s.query(GrupoEconomico).filter_by(nome="Prospect").one()
        s.add(Oportunidade(grupo_id=prospect.id, nome="Antiga", servico="Consultoria", situacao=Situacao.PERDIDA,
                           motivo_recusa=list(MotivoRecusa)[0], origem=Origem.CARGA_2026, chave_origem="antiga|2026"))
        s.commit()
        r = integralidade.calcular(s)
    assert {c.registro for c in r.legado} == {"Prospect · Consultoria"}
    assert integralidade.Resultado.pendente_pct(r.novos) == D("40.0")  # o legado não mexe no número principal


def test_o_card_mostra_as_duas_visoes_e_a_composicao_por_responsavel(cadastro):
    with Session(cadastro) as s:
        k = {k.chave: k for k in calcular_kpis(s, "2026-10", date(2026, 10, 20)).kpis}["integralidade"]
    assert k.titulo == "Integralidade do cadastro" and k.valor == D("40.0")
    x = k.extras
    assert (x["pontos_devidos"], x["pontos_pendentes"], x["obrigatorios_em_falta"], x["prioritarios_em_falta"]) == (40, 16, 4, 8)
    assert x["pendente_contrato"] == D("40.0") and x["pendente_encerramento"] is None  # nenhum encerramento devido
    secoes = [i.secao for i in k.itens]
    assert secoes[0].startswith("KN · 7 pendência(s)") and secoes[-1].startswith("Sem responsável · 3 pendência(s)")
    assert len(k.itens) == 12 and all(i.valor == 0 for i in k.itens)
    assert {i.detalhe for i in k.itens if i.grupo == "Contrato · Cliente X · BPO Contábil"} == {
        "Bruto ou líquido · Obrigatório", "Signatário · Prioritário", "Fim da vigência · Prioritário"}


def test_sem_registro_novo_fica_sem_dado(engine, monkeypatch):
    monkeypatch.setattr(integralidade, "DATA_DE_CORTE", date(2999, 1, 1))
    with Session(engine) as s:
        s.add(GrupoEconomico(nome="Qualquer"))
        s.commit()
        k = {k.chave: k for k in calcular_kpis(s, "2026-10", date(2026, 10, 20)).kpis}["integralidade"]
    assert k.valor is None and "Nenhum registro criado desde" in k.falta[0]
