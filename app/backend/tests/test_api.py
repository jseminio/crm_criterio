"""A API do funil, exercitada de ponta a ponta contra um banco de teste."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import GrupoEconomico, Lead, Oportunidade
from crm.domain.listas import Origem, Situacao, SituacaoGrupo, SituacaoLead, Temperatura, TipoCanal


@pytest.fixture
def cliente(engine: sa.Engine) -> TestClient:
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as aberto:
        yield aberto


@pytest.fixture
def carteira(sessao: Session) -> dict:
    """Dois grupos, três oportunidades e um lead — o mínimo para um funil."""
    alfa = GrupoEconomico(nome="Grupo Alfa", origem=Origem.CARGA_2026)
    beta = GrupoEconomico(nome="Beta Participações", origem=Origem.CARGA_2026)
    sessao.add_all([alfa, beta])
    sessao.flush()

    oportunidades = [
        Oportunidade(
            grupo_id=alfa.id, nome="Alfa BPO", situacao=Situacao.ENVIAR_PROPOSTA,
            temperatura=Temperatura.QUENTE, captador="EL", tipo_canal=TipoCanal.SOCIOS,
            servico="BPO Contábil", preco_mensal=Decimal("5000.00"),
            preco_anual=Decimal("65000.00"), data_colocacao=date(2026, 3, 1),
            origem=Origem.CARGA_2026, chave_origem="alfa|2026-03-01|bpo|mensal",
        ),
        Oportunidade(
            grupo_id=alfa.id, nome="Alfa Consultoria", situacao=Situacao.RECUSADA,
            captador="BO", tipo_canal=TipoCanal.PARCEIROS, servico="Consultoria",
            preco_anual=Decimal("30000.00"), data_colocacao=date(2026, 5, 1),
            origem=Origem.CARGA_2026, chave_origem="alfa|2026-05-01|consultoria|projeto",
        ),
        Oportunidade(
            grupo_id=beta.id, nome="Beta BPO", situacao=Situacao.ACEITA,
            captador="EL", tipo_canal=TipoCanal.SOCIOS, servico="BPO Financeiro",
            preco_mensal=Decimal("8000.00"), data_aceite=date(2026, 6, 1),
            data_colocacao=date(2026, 4, 1),
            origem=Origem.CARGA_2026, chave_origem="beta|2026-04-01|bpofin|mensal",
        ),
    ]
    lead = Lead(nome="Contato da feira", empresa_texto="Gama Ltda",
                tipo_canal=TipoCanal.SOCIOS, canal="Indicação", captador="TC",
                temperatura=Temperatura.MORNO)
    sessao.add_all([*oportunidades, lead])
    sessao.commit()
    return {"alfa": alfa.id, "beta": beta.id, "lead": lead.id,
            "primeira": oportunidades[0].id, "aceita": oportunidades[2].id}


class TestListas:
    def test_a_tela_recebe_as_listas_do_servidor(self, cliente: TestClient):
        """Duplicá-las no React criaria a segunda cópia da mesma regra."""
        dados = cliente.get("/api/listas").json()

        assert "Enviar proposta" in dados["situacoes"]
        assert "Sócios" in dados["tipos_de_canal"]
        assert "BO" in dados["captadores"]

    def test_separa_os_canais_que_ainda_nao_operam(self, cliente: TestClient):
        dados = cliente.get("/api/listas").json()

        assert "Tráfego pago" in dados["tipos_de_canal"]
        assert "Tráfego pago" not in dados["tipos_de_canal_em_operacao"]


class TestFunil:
    def test_traz_uma_coluna_por_situacao(self, cliente: TestClient, carteira):
        colunas = cliente.get("/api/funil").json()

        assert len(colunas) == len(Situacao)

    def test_coluna_vazia_nao_some(self, cliente: TestClient, carteira):
        """Coluna que desaparece ao zerar esconde que o estado existe."""
        colunas = {c["situacao"]: c for c in cliente.get("/api/funil").json()}

        assert colunas["Perdido"]["quantas"] == 0
        assert colunas["Perdido"]["oportunidades"] == []

    def test_soma_o_valor_de_cada_coluna(self, cliente: TestClient, carteira):
        colunas = {c["situacao"]: c for c in cliente.get("/api/funil").json()}

        assert Decimal(colunas["Enviar proposta"]["valor_anual"]) == Decimal("65000.00")
        assert Decimal(colunas["Recusada"]["valor_anual"]) == Decimal("30000.00")

    def test_o_cartao_traz_o_nome_do_grupo(self, cliente: TestClient, carteira):
        """Sem ele o cartão mostra a oportunidade e esconde o cliente."""
        colunas = {c["situacao"]: c for c in cliente.get("/api/funil").json()}

        cartao = colunas["Enviar proposta"]["oportunidades"][0]
        assert cartao["grupo_nome"] == "Grupo Alfa"

    def test_o_filtro_de_captador_vale_no_kanban(self, cliente: TestClient, carteira):
        colunas = cliente.get("/api/funil", params={"captador": "EL"}).json()

        assert sum(c["quantas"] for c in colunas) == 2


class TestLista:
    def test_lista_tudo(self, cliente: TestClient, carteira):
        assert cliente.get("/api/oportunidades").json()["total"] == 3

    def test_filtra_por_situacao(self, cliente: TestClient, carteira):
        pagina = cliente.get("/api/oportunidades", params={"situacao": "Aceita"}).json()

        assert pagina["total"] == 1
        assert pagina["itens"][0]["nome"] == "Beta BPO"

    def test_aceita_varias_situacoes_de_uma_vez(self, cliente: TestClient, carteira):
        pagina = cliente.get(
            "/api/oportunidades", params=[("situacao", "Aceita"), ("situacao", "Recusada")]
        ).json()

        assert pagina["total"] == 2

    def test_a_busca_alcanca_o_nome_do_grupo(self, cliente: TestClient, carteira):
        """Procura-se pelo cliente, não pelo título que alguém deu à proposta."""
        pagina = cliente.get("/api/oportunidades", params={"busca": "Participações"}).json()

        assert pagina["total"] == 1
        assert pagina["itens"][0]["nome"] == "Beta BPO"

    def test_filtra_por_grupo(self, cliente: TestClient, carteira):
        pagina = cliente.get(
            "/api/oportunidades", params={"grupo_id": carteira["alfa"]}
        ).json()

        assert pagina["total"] == 2


class TestCorteDePeriodo:
    """Pedido de Eduardo em 22/09/2026: comparar um recorte de tempo (ex.: um
    teste de prospecção) contra o resto da carteira. O corte vale nas três
    telas porque as três chamam `_consulta_de_oportunidades`."""

    def test_corta_por_data_de_colocacao_por_padrao(self, cliente: TestClient, carteira):
        """Alfa BPO (03-01) fica de fora; Beta BPO (04-01) e Alfa Consultoria
        (05-01) entram."""
        pagina = cliente.get(
            "/api/oportunidades",
            params={"data_de": "2026-04-01", "data_ate": "2026-05-01"},
        ).json()

        assert pagina["total"] == 2
        nomes = {item["nome"] for item in pagina["itens"]}
        assert nomes == {"Beta BPO", "Alfa Consultoria"}

    def test_so_data_de_ja_corta_sem_precisar_do_ate(self, cliente: TestClient, carteira):
        pagina = cliente.get("/api/oportunidades", params={"data_de": "2026-05-01"}).json()

        assert pagina["total"] == 1
        assert pagina["itens"][0]["nome"] == "Alfa Consultoria"

    def test_corta_por_data_de_aceite_quando_pedido(self, cliente: TestClient, carteira):
        """Só a Beta BPO tem data de aceite — as outras duas, mesmo dentro do
        intervalo por colocação, ficam de fora quando o corte é por aceite."""
        pagina = cliente.get(
            "/api/oportunidades",
            params={"data_tipo": "aceite", "data_de": "2026-06-01", "data_ate": "2026-06-30"},
        ).json()

        assert pagina["total"] == 1
        assert pagina["itens"][0]["nome"] == "Beta BPO"

    def test_vale_no_funil_e_nos_indicadores(self, cliente: TestClient, carteira):
        parametros = {"data_de": "2026-04-01", "data_ate": "2026-05-01"}

        colunas = cliente.get("/api/funil", params=parametros).json()
        assert sum(c["quantas"] for c in colunas) == 2

        indicadores = cliente.get("/api/indicadores", params=parametros).json()
        # As duas do intervalo já têm desfecho: Alfa Consultoria (Recusada) e
        # Beta BPO (Aceita). Alfa BPO fica de fora do corte — ainda que
        # decidida, sua colocação (03-01) está antes do intervalo.
        assert indicadores["taxa_de_conversao"]["decididas"] == 2


class TestEdicao:
    def test_move_a_oportunidade_de_situacao(self, cliente: TestClient, carteira):
        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"situacao": "On hold", "proxima_acao": "Retomar em julho"},
        )

        assert resposta.status_code == 200
        assert resposta.json()["situacao"] == "On hold"
        assert resposta.json()["proxima_acao"] == "Retomar em julho"

    def test_campo_ausente_nao_apaga_o_valor(self, cliente: TestClient, carteira):
        """Campo que não veio não é campo vazio."""
        cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}", json={"proxima_acao": "Ligar"}
        )

        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}", json={"temperatura": "Frio"}
        )

        assert resposta.json()["proxima_acao"] == "Ligar"

    def test_aceita_sem_data_de_aceite_e_recusada(self, cliente: TestClient, carteira):
        """O defeito mais comum da planilha de 2026 não se repete aqui."""
        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}", json={"situacao": "Aceita"}
        )

        assert resposta.status_code == 422
        assert "data do aceite" in resposta.json()["detail"]

    def test_aceita_com_data_passa(self, cliente: TestClient, carteira):
        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"situacao": "Aceita", "data_aceite": "2026-07-01"},
        )

        assert resposta.status_code == 200

    def test_edita_preco_e_servico(self, cliente: TestClient, carteira, sessao: Session):
        """Desde 22/09/2026 (E4) a proposta pode ser ajustada direto no CRM."""
        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"preco_mensal": "999.00", "servico": "Consultoria"},
        )

        assert resposta.status_code == 200
        detalhe = cliente.get(f"/api/oportunidades/{carteira['primeira']}").json()
        assert Decimal(detalhe["preco_mensal"]) == Decimal("999.00")
        assert detalhe["servico"] == "Consultoria"

        # E entra em campos_do_crm — mesma trava que já protegia situação e
        # temperatura contra a recarga da planilha sobrescrever de volta.
        oportunidade = sessao.get(Oportunidade, carteira["primeira"])
        assert {"preco_mensal", "servico"} <= set(oportunidade.campos_do_crm)

    def test_oportunidade_inexistente_da_404(self, cliente: TestClient, carteira):
        assert cliente.patch("/api/oportunidades/9999", json={}).status_code == 404


class TestCriacaoDeOportunidade:
    """A proposta nascendo direto no CRM — o E4, aprovado por Eduardo em
    22/09/2026."""

    def test_cria_com_grupo_novo(self, cliente: TestClient):
        resposta = cliente.post(
            "/api/oportunidades",
            json={
                "nome": "Delta Engenharia",
                "servico": "BPO Contábil",
                "preco_mensal": "3000.00",
            },
        )

        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["nome"] == "Delta Engenharia"
        assert corpo["grupo_nome"] == "Delta Engenharia"
        assert corpo["situacao"] == "Enviar proposta"
        assert corpo["origem"] == "CRM"
        assert Decimal(corpo["preco_mensal"]) == Decimal("3000.00")

    def test_data_de_colocacao_default_e_hoje(self, cliente: TestClient):
        corpo = cliente.post("/api/oportunidades", json={"nome": "Épsilon"}).json()

        assert corpo["data_colocacao"] == date.today().isoformat()

    def test_reaproveita_grupo_existente_pelo_nome(self, cliente: TestClient, carteira):
        resposta = cliente.post(
            "/api/oportunidades", json={"nome": "Alfa BPO Fase 2", "nome_do_grupo": "Grupo Alfa"}
        )

        assert resposta.json()["grupo_id"] == carteira["alfa"]

    def test_grupo_id_explicito_tem_prioridade(self, cliente: TestClient, carteira):
        resposta = cliente.post(
            "/api/oportunidades", json={"nome": "Beta Fase 2", "grupo_id": carteira["beta"]}
        )

        assert resposta.json()["grupo_id"] == carteira["beta"]

    def test_grupo_id_inexistente_da_404(self, cliente: TestClient):
        resposta = cliente.post(
            "/api/oportunidades", json={"nome": "X", "grupo_id": 9999}
        )

        assert resposta.status_code == 404

    def test_so_o_nome_e_obrigatorio(self, cliente: TestClient):
        assert cliente.post("/api/oportunidades", json={}).status_code == 422


class TestVolumetriaEPorte:
    """A régua de porte (E4, 23/09/2026) — sempre sugestão, nunca decisão.
    Ver `crm.domain.porte` e `regua-de-porte-e-plano-de-teste.md`."""

    def test_sem_volumetria_nenhuma_a_sugestao_nao_e_calculavel(
        self, cliente: TestClient, carteira
    ):
        detalhe = cliente.get(f"/api/oportunidades/{carteira['primeira']}").json()

        assert detalhe["sugestao_de_porte"]["calculavel"] is False
        assert detalhe["sugestao_de_porte"]["porte"] is None

    def test_preenche_volumetria_e_a_sugestao_aparece_na_leitura(
        self, cliente: TestClient, carteira
    ):
        cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"empregados_clt": 200},  # nota 4 sozinho -> Extra Grande
        )

        detalhe = cliente.get(f"/api/oportunidades/{carteira['primeira']}").json()

        assert detalhe["empregados_clt"] == 200
        assert detalhe["sugestao_de_porte"]["calculavel"] is True
        assert detalhe["sugestao_de_porte"]["porte"] == "Extra Grande"

    def test_direcionador_fora_do_intervalo_e_recusado(self, cliente: TestClient, carteira):
        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}", json={"empregados_clt": -1}
        )

        assert resposta.status_code == 422

    def test_complexidade_fora_de_1_a_5_e_recusada(self, cliente: TestClient, carteira):
        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}", json={"complexidade": 6}
        )

        assert resposta.status_code == 422

    def test_confirmar_porte_grava_quem_e_quando_no_servidor(
        self, cliente: TestClient, carteira, sessao: Session
    ):
        antes = datetime.now(UTC)

        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"porte": "Extra Grande", "porte_definido_por": "EL"},
        )

        assert resposta.status_code == 200
        detalhe = resposta.json()
        assert detalhe["porte"] == "Extra Grande"
        assert detalhe["porte_definido_por"] == "EL"
        # O instante vem do servidor, não do que o corpo da requisição manda
        # (o schema nem aceita `porte_definido_em` do cliente). SQLite (banco
        # de teste) devolve o datetime sem fuso — comparo sem fuso dos dois
        # lados, só para provar que o servidor gravou "agora", não um valor
        # arbitrário.
        gravado = sessao.get(Oportunidade, carteira["primeira"]).porte_definido_em
        assert gravado is not None and gravado.replace(tzinfo=UTC) >= antes

    def test_a_sugestao_nunca_grava_porte_sozinha(self, cliente: TestClient, carteira):
        """Calcular a sugestão numa leitura não pode, de tabela, confirmar
        porte nenhum — só a pessoa confirma, via PATCH explícito."""
        cliente.patch(f"/api/oportunidades/{carteira['primeira']}", json={"empregados_clt": 200})
        cliente.get(f"/api/oportunidades/{carteira['primeira']}")

        detalhe = cliente.get(f"/api/oportunidades/{carteira['primeira']}").json()
        assert detalhe["porte"] is None
        assert detalhe["porte_definido_por"] is None

    def test_salvar_outro_campo_com_porte_null_no_corpo_nao_carimba_data(
        self, cliente: TestClient, carteira, sessao: Session
    ):
        """A tela manda o rascunho inteiro a cada salvar — `porte: null`
        sempre vai junto, mesmo quando ninguém tocou nele. Regressão: isso
        chegou a carimbar `porte_definido_em` em toda gravação, só por
        `"porte"` estar presente no corpo, sem checar se o valor mudou."""
        resposta = cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"empregados_clt": 200, "porte": None},
        )

        assert resposta.status_code == 200
        assert resposta.json()["porte_definido_em"] is None
        oportunidade = sessao.get(Oportunidade, carteira["primeira"])
        assert oportunidade.porte_definido_em is None


class TestLeads:
    def test_cadastra_com_o_minimo(self, cliente: TestClient):
        """Exigir mais faria a pessoa inventar dado para conseguir salvar."""
        resposta = cliente.post("/api/leads", json={"nome": "Indicação do Bruno"})

        assert resposta.status_code == 201
        assert resposta.json()["situacao"] == "Novo"

    def test_recusa_lead_sem_nome(self, cliente: TestClient):
        assert cliente.post("/api/leads", json={"nome": ""}).status_code == 422

    def test_guarda_a_origem_em_duas_camadas(self, cliente: TestClient):
        resposta = cliente.post(
            "/api/leads",
            json={"nome": "Lead novo", "tipo_canal": "Parceiros", "canal": "Renê Dutra"},
        ).json()

        assert (resposta["tipo_canal"], resposta["canal"]) == ("Parceiros", "Renê Dutra")

    def test_filtra_os_abertos(self, cliente: TestClient, carteira):
        cliente.patch(f"/api/leads/{carteira['lead']}", json={"situacao": "Descartado"})

        assert cliente.get("/api/leads", params={"apenas_abertos": True}).json()["total"] == 0


class TestEdicaoDeLead:
    def test_muda_a_situacao(self, cliente: TestClient, carteira):
        resposta = cliente.patch(
            f"/api/leads/{carteira['lead']}", json={"situacao": "Em contato"}
        )

        assert resposta.status_code == 200
        assert resposta.json()["situacao"] == "Em contato"

    def test_nao_deixa_marcar_como_convertido_a_mao(self, cliente: TestClient, carteira):
        """Convertido pressupõe uma oportunidade; sem ela a origem nunca chega ao funil."""
        resposta = cliente.patch(
            f"/api/leads/{carteira['lead']}", json={"situacao": "Convertido"}
        )

        assert resposta.status_code == 422
        assert "conversão" in resposta.json()["detail"]

    def test_lead_convertido_nao_muda_de_situacao(self, cliente: TestClient, carteira):
        cliente.post(f"/api/leads/{carteira['lead']}/converter", json={})

        resposta = cliente.patch(
            f"/api/leads/{carteira['lead']}", json={"situacao": "Descartado"}
        )

        assert resposta.status_code == 409

    def test_lead_convertido_ainda_aceita_editar_observacao(
        self, cliente: TestClient, carteira
    ):
        """A trava é sobre a situação, não sobre o lead inteiro."""
        cliente.post(f"/api/leads/{carteira['lead']}/converter", json={})

        resposta = cliente.patch(
            f"/api/leads/{carteira['lead']}", json={"observacao": "Fechou por indicação"}
        )

        assert resposta.status_code == 200


class TestConversao:
    def test_vira_oportunidade_num_grupo_existente(self, cliente: TestClient, carteira):
        resposta = cliente.post(
            f"/api/leads/{carteira['lead']}/converter",
            json={"grupo_id": carteira["alfa"], "servico": "BPO Financeiro"},
        )

        assert resposta.status_code == 201
        assert resposta.json()["grupo_nome"] == "Grupo Alfa"
        assert resposta.json()["situacao"] == "Enviar proposta"

    def test_cria_o_grupo_quando_nao_existe(self, cliente: TestClient, carteira):
        resposta = cliente.post(f"/api/leads/{carteira['lead']}/converter", json={}).json()

        assert resposta["grupo_nome"] == "Gama Ltda"

    def test_a_origem_viaja_com_o_lead(self, cliente: TestClient, carteira):
        """Sem isso o indicador de canal mede só a entrada, não o que fecha."""
        resposta = cliente.post(f"/api/leads/{carteira['lead']}/converter", json={}).json()

        assert resposta["tipo_canal"] == "Sócios"
        assert resposta["canal"] == "Indicação"
        assert resposta["captador"] == "TC"

    def test_o_lead_fica_marcado_como_convertido(self, cliente: TestClient, carteira):
        cliente.post(f"/api/leads/{carteira['lead']}/converter", json={})

        leads = cliente.get("/api/leads").json()["itens"]
        assert leads[0]["situacao"] == "Convertido"
        assert leads[0]["convertido_em_id"] is not None

    def test_nao_converte_duas_vezes(self, cliente: TestClient, carteira):
        cliente.post(f"/api/leads/{carteira['lead']}/converter", json={})

        segunda = cliente.post(f"/api/leads/{carteira['lead']}/converter", json={})

        assert segunda.status_code == 409


class TestContratos:
    """Começo da Etapa 2 (23/09/2026): oportunidade aceita vira contrato."""

    def test_converte_a_aceita_em_contrato(self, cliente: TestClient, carteira):
        resposta = cliente.post(
            f"/api/oportunidades/{carteira['aceita']}/converter-em-contrato", json={}
        )

        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["grupo_nome"] == "Beta Participações"
        assert corpo["situacao"] == "Aguardando assinatura"
        assert corpo["escopo"] == "BPO Financeiro"
        assert corpo["preco_mensal"] == "8000.00"
        assert corpo["data_inicio"] == "2026-06-01"

    def test_ajustes_no_corpo_sobrepoem_o_que_vem_da_oportunidade(
        self, cliente: TestClient, carteira
    ):
        resposta = cliente.post(
            f"/api/oportunidades/{carteira['aceita']}/converter-em-contrato",
            json={"escopo": "BPO Financeiro + Fiscal", "signatario": "Fulano de Tal"},
        )

        corpo = resposta.json()
        assert corpo["escopo"] == "BPO Financeiro + Fiscal"
        assert corpo["signatario"] == "Fulano de Tal"

    def test_nao_converte_oportunidade_nao_aceita(self, cliente: TestClient, carteira):
        resposta = cliente.post(
            f"/api/oportunidades/{carteira['primeira']}/converter-em-contrato", json={}
        )

        assert resposta.status_code == 422

    def test_nao_converte_duas_vezes(self, cliente: TestClient, carteira):
        cliente.post(f"/api/oportunidades/{carteira['aceita']}/converter-em-contrato", json={})

        segunda = cliente.post(
            f"/api/oportunidades/{carteira['aceita']}/converter-em-contrato", json={}
        )

        assert segunda.status_code == 409

    def test_lista_e_filtra_por_situacao(self, cliente: TestClient, carteira):
        cliente.post(f"/api/oportunidades/{carteira['aceita']}/converter-em-contrato", json={})

        pagina = cliente.get("/api/contratos").json()
        assert pagina["total"] == 1

        vazia = cliente.get(
            "/api/contratos", params={"situacao": "Ativo"}
        ).json()
        assert vazia["total"] == 0

    def test_le_o_detalhe(self, cliente: TestClient, carteira):
        criado = cliente.post(
            f"/api/oportunidades/{carteira['aceita']}/converter-em-contrato", json={}
        ).json()

        detalhe = cliente.get(f"/api/contratos/{criado['id']}").json()
        assert detalhe["oportunidade_id"] == carteira["aceita"]

    def test_edita_a_situacao(self, cliente: TestClient, carteira):
        criado = cliente.post(
            f"/api/oportunidades/{carteira['aceita']}/converter-em-contrato", json={}
        ).json()

        editado = cliente.patch(
            f"/api/contratos/{criado['id']}", json={"situacao": "Ativo"}
        ).json()

        assert editado["situacao"] == "Ativo"


class TestGrupos:
    def test_lista_com_a_contagem_de_oportunidades(self, cliente: TestClient, carteira):
        """É o número que diz onde olhar primeiro no reagrupamento."""
        pagina = cliente.get("/api/grupos").json()

        assert pagina["total"] == 2
        assert pagina["itens"][0]["quantas_oportunidades"] == 2

    def test_busca_por_nome(self, cliente: TestClient, carteira):
        assert cliente.get("/api/grupos", params={"busca": "beta"}).json()["total"] == 1

    def test_funde_dois_grupos(self, cliente: TestClient, carteira):
        resposta = cliente.post(
            f"/api/grupos/{carteira['alfa']}/fundir",
            json={"absorvido_id": carteira["beta"]},
        )

        assert resposta.status_code == 200
        pagina = cliente.get("/api/grupos").json()
        assert pagina["total"] == 1
        assert pagina["itens"][0]["quantas_oportunidades"] == 3

    def test_o_grupo_fundido_some_da_lista_mas_nao_do_banco(
        self, cliente: TestClient, carteira
    ):
        cliente.post(
            f"/api/grupos/{carteira['alfa']}/fundir",
            json={"absorvido_id": carteira["beta"]},
        )

        com_fundidos = cliente.get("/api/grupos", params={"incluir_fundidos": True}).json()
        assert com_fundidos["total"] == 2
        fundido = next(g for g in com_fundidos["itens"] if g["id"] == carteira["beta"])
        assert fundido["situacao"] == "Fundido"

    def test_fusao_invalida_explica_o_motivo(self, cliente: TestClient, carteira):
        resposta = cliente.post(
            f"/api/grupos/{carteira['alfa']}/fundir",
            json={"absorvido_id": carteira["alfa"]},
        )

        assert resposta.status_code == 409
        assert "si mesmo" in resposta.json()["detail"]


class TestIndicadores:
    def test_soma_o_que_esta_em_aberto(self, cliente: TestClient, carteira):
        dados = cliente.get("/api/indicadores").json()

        # Só "Enviar proposta" da fixture está em aberto: R$ 5.000/mês, R$ 65.000/ano.
        assert dados["em_aberto"]["quantas"] == 1
        assert Decimal(dados["em_aberto"]["valor_mensal"]) == Decimal("5000.00")

    def test_soma_as_aceitas(self, cliente: TestClient, carteira):
        dados = cliente.get("/api/indicadores").json()

        assert dados["aceitas"]["quantas"] == 1
        assert Decimal(dados["aceitas"]["valor_mensal"]) == Decimal("8000.00")

    def test_diz_quantas_aceitas_tem_data_de_aceite(self, cliente: TestClient, carteira):
        """A fixture aceita tem data: é o número que destrava o ciclo médio."""
        assert cliente.get("/api/indicadores").json()["aceitas_com_data_de_aceite"] == 1

    def test_acompanha_o_filtro_de_captador(self, cliente: TestClient, carteira):
        """Os números seguem o que a pessoa está olhando no funil."""
        so_bo = cliente.get("/api/indicadores", params={"captador": "BO"}).json()

        assert so_bo["aceitas"]["quantas"] == 0
        assert so_bo["em_aberto"]["quantas"] == 0

    def test_conversao_divide_aceitas_por_decididas(self, cliente: TestClient, carteira):
        """A fixture tem 1 aceita e 1 recusada decididas, e 1 em aberto de fora."""
        dados = cliente.get("/api/indicadores").json()

        conversao = dados["taxa_de_conversao"]
        assert (conversao["aceitas"], conversao["decididas"]) == (1, 2)
        assert conversao["percentual"] == "50.0"
        assert conversao["calculavel"] is True

    def test_a_base_vazia_nao_quebra(self, cliente: TestClient):
        dados = cliente.get("/api/indicadores").json()

        assert dados["em_aberto"]["quantas"] == 0
        assert dados["ciclo_medio"]["calculavel"] is False

    def test_ciclo_medio_originacao_ate_aceite(self, cliente: TestClient, carteira):
        """Beta BPO: colocação 04-01, aceite 06-01 — 61 dias. Decisão de
        Eduardo em 23/09/2026 sobre a base do cálculo."""
        dados = cliente.get("/api/indicadores").json()

        ciclo = dados["ciclo_medio"]
        assert ciclo["calculavel"] is True
        assert ciclo["dias"] == "61.0"
        assert ciclo["amostra"] == 1

    def test_cobertura_de_proxima_acao_e_volumetria(self, cliente: TestClient, carteira):
        """Nenhuma das três tem próxima ação nem volumetria preenchida."""
        dados = cliente.get("/api/indicadores").json()

        cobertura = dados["cobertura"]
        assert cobertura["em_aberto_total"] == 1  # só Alfa BPO está em aberto
        assert cobertura["em_aberto_com_proxima_acao"] == 0
        assert cobertura["com_volumetria_completa"] == 0
        assert cobertura["total"] == 3

    def test_dependencia_da_rede_de_socios(self, cliente: TestClient, carteira):
        """Alfa BPO e Beta BPO vieram de Sócios; Alfa Consultoria, de Parceiros."""
        dados = cliente.get("/api/indicadores").json()

        dependencia = dados["dependencia_de_canal"]
        assert dependencia["da_rede_de_socios"] == 2
        assert dependencia["total"] == 3
        assert dependencia["percentual"] == "66.7"

    def test_filtra_por_servico(self, cliente: TestClient, carteira):
        pagina = cliente.get("/api/oportunidades", params={"servico": "Consultoria"}).json()

        assert pagina["total"] == 1
        assert pagina["itens"][0]["nome"] == "Alfa Consultoria"

    def test_lista_de_servicos_vem_do_banco(self, cliente: TestClient, carteira):
        servicos = cliente.get("/api/listas").json()["servicos"]

        assert servicos == ["BPO Contábil", "BPO Financeiro", "Consultoria"]


@pytest.fixture
def rodada(sessao: Session) -> int:
    """Uma rodada da carga com um de cada tipo, já gravada."""
    from crm.db.base import agora
    from crm.db.modelos import ExecucaoDeCarga, OcorrenciaDeCarga
    from crm.domain.listas import TipoDeOcorrencia as T

    execucao = ExecucaoDeCarga(
        executada_em=agora(), arquivo="planilha.xlsx", lidas=436, de_outro_ano=279,
        residuais=0, importadas=157, criadas=0, atualizadas=1, inalteradas=152,
        ignoradas_incompletas=3, ignoradas_duplicatas=1, grupos_criados=0,
        grupos_reaproveitados=0,
        ocorrencias=[
            OcorrenciaDeCarga(tipo=T.PENDENCIA, linha=317, campo="linha duplicada", texto="idênticas"),
            OcorrenciaDeCarga(tipo=T.PENDENCIA, linha=12, campo="data de aceite", texto="aceita sem data"),
            OcorrenciaDeCarga(tipo=T.PENDENCIA, linha=30, campo="data de aceite", texto="aceita sem data"),
            OcorrenciaDeCarga(tipo=T.AJUSTE, linha=8, campo="tipo de canal", texto="'Socio' → 'Sócios'"),
            OcorrenciaDeCarga(tipo=T.MUDANCA, linha=5, campo="situacao", texto="Alfa: Enviar proposta → Aceita"),
        ],
    )
    sessao.add(execucao)
    sessao.commit()
    return execucao.id


class TestConferencia:
    def test_lista_as_rodadas_com_a_contagem_por_tipo(self, cliente: TestClient, rodada):
        cargas = cliente.get("/api/cargas").json()

        assert len(cargas) == 1
        assert (cargas[0]["pendencias"], cargas[0]["ajustes"], cargas[0]["mudancas"]) == (3, 1, 1)

    def test_gravadas_e_o_que_esta_no_crm_depois_da_rodada(self, cliente: TestClient, rodada):
        """Numa recarga, 'criadas' é pequeno; o que importa é quantas estão lá."""
        assert cliente.get("/api/cargas").json()[0]["gravadas"] == 153

    def test_a_mais_recente_vem_primeiro(self, cliente: TestClient, rodada, sessao: Session):
        from crm.db.base import agora
        from crm.db.modelos import ExecucaoDeCarga

        sessao.add(ExecucaoDeCarga(
            executada_em=agora(), arquivo="depois.xlsx", lidas=1, de_outro_ano=0,
            residuais=0, importadas=1, criadas=1, atualizadas=0, inalteradas=0,
            ignoradas_incompletas=0, ignoradas_duplicatas=0, grupos_criados=1,
            grupos_reaproveitados=0))
        sessao.commit()

        assert cliente.get("/api/cargas").json()[0]["arquivo"] == "depois.xlsx"

    def test_detalhe_agrupa_por_campo(self, cliente: TestClient, rodada):
        """É o que responde 'onde está o grosso do trabalho' sem ler 140 linhas."""
        detalhe = cliente.get(f"/api/cargas/{rodada}").json()

        aceite = next(g for g in detalhe["por_campo"] if g["campo"] == "data de aceite")
        assert (aceite["tipo"], aceite["quantas"]) == ("Precisa de você", 2)

    def test_ocorrencias_na_ordem_da_planilha(self, cliente: TestClient, rodada):
        """Quem confere lê a planilha de cima para baixo."""
        itens = cliente.get(f"/api/cargas/{rodada}/ocorrencias").json()["itens"]

        linhas = [i["linha"] for i in itens]
        assert linhas == sorted(linhas)

    def test_filtra_por_tipo(self, cliente: TestClient, rodada):
        pagina = cliente.get(
            f"/api/cargas/{rodada}/ocorrencias", params={"tipo": "Precisa de você"}
        ).json()

        assert pagina["total"] == 3

    def test_filtra_por_campo(self, cliente: TestClient, rodada):
        pagina = cliente.get(
            f"/api/cargas/{rodada}/ocorrencias", params={"campo": "data de aceite"}
        ).json()

        assert pagina["total"] == 2

    def test_carga_inexistente_da_404(self, cliente: TestClient):
        assert cliente.get("/api/cargas/999").status_code == 404
        assert cliente.get("/api/cargas/999/ocorrencias").status_code == 404

    def test_sem_nenhuma_rodada_devolve_lista_vazia(self, cliente: TestClient):
        """A tela precisa distinguir 'nenhuma carga registrada' de erro."""
        assert cliente.get("/api/cargas").json() == []


class TestEdicaoMarcaOCampo:
    """A API lembra o que foi mudado na tela, para a recarga não desfazer."""

    def _oportunidade(self, sessao: Session, id_: int) -> Oportunidade:
        sessao.expire_all()
        return sessao.get(Oportunidade, id_)

    def test_editar_um_campo_que_a_planilha_controla_o_marca(
        self, cliente: TestClient, carteira, sessao: Session
    ):
        cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}", json={"temperatura": "Frio"}
        )

        assert self._oportunidade(sessao, carteira["primeira"]).campos_do_crm == ["temperatura"]

    def test_salvar_sem_mudar_o_valor_nao_marca(
        self, cliente: TestClient, carteira, sessao: Session
    ):
        """Abrir o painel e salvar não deve congelar campo nenhum."""
        atual = cliente.get(f"/api/oportunidades/{carteira['primeira']}").json()
        cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"temperatura": atual["temperatura"]},
        )

        assert self._oportunidade(sessao, carteira["primeira"]).campos_do_crm == []

    def test_campo_que_so_existe_no_crm_nao_e_marcado(
        self, cliente: TestClient, carteira, sessao: Session
    ):
        """Próxima ação e observação a planilha nem tem: não há o que proteger."""
        cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"proxima_acao": "Ligar", "observacao": "nota"},
        )

        assert self._oportunidade(sessao, carteira["primeira"]).campos_do_crm == []

    def test_edicoes_sucessivas_acumulam(
        self, cliente: TestClient, carteira, sessao: Session
    ):
        cliente.patch(f"/api/oportunidades/{carteira['primeira']}", json={"temperatura": "Frio"})
        cliente.patch(
            f"/api/oportunidades/{carteira['primeira']}",
            json={"situacao": "Aceita", "data_aceite": "2026-05-01"},
        )

        assert self._oportunidade(sessao, carteira["primeira"]).campos_do_crm == [
            "data_aceite", "situacao", "temperatura",
        ]


class TestEdicaoNaTelaSobreviveARecargaDaPlanilha:
    """De ponta a ponta: a pessoa edita pela tela e a planilha é recarregada.

    Cada lado tem os seus testes. O defeito real nasceu na junção — a carga não
    sabia o que a API havia mudado — e só um teste que atravessa os dois pega isso.
    """

    def test_data_de_aceite_preenchida_pela_api_resiste_a_recarga(
        self, cliente: TestClient, sessao: Session
    ):
        from datetime import date as Data

        from crm.carga.persistencia import importar
        from crm.domain.listas import LinhaServico
        from crm.carga.planilha_2026 import Proposta

        planilha = [Proposta(
            linha=1, nome_oportunidade="Sogamax", data_colocacao=Data(2026, 1, 1),
            servico="BPO Contábil", tipo_servico="Recorrente", linha_servico=LinhaServico.C1,
            captador="MO", canal=None, tipo_canal=None, situacao=Situacao.ACEITA,
            temperatura=None, data_aceite=None,          # a planilha NÃO tem a data
            motivo_recusa=None, motivo_recusa_original=None,
            preco_mensal=Decimal("5000.00"), preco_anual=Decimal("65000.00"),
            valor_mensalizado=None,
        )]
        importar(sessao, planilha)
        sessao.commit()
        id_ = sessao.scalar(sa.select(Oportunidade.id))

        # A pessoa preenche a data na tela...
        resposta = cliente.patch(f"/api/oportunidades/{id_}", json={"data_aceite": "2026-04-15"})
        assert resposta.status_code == 200

        # ...e a carga roda de novo, com a planilha ainda sem a data.
        sessao.expire_all()
        resultado = importar(sessao, planilha)
        sessao.commit()

        sessao.expire_all()
        assert sessao.get(Oportunidade, id_).data_aceite == Data(2026, 4, 15)
        assert any("mantido o do CRM" in o.texto for o in resultado.ocorrencias)


class TestRecortesECenarios:
    def test_recortes_por_servico_seguem_os_filtros(self, cliente, carteira):
        r = cliente.get("/api/indicadores/recortes", params={"dimensao": "servico"})
        assert r.status_code == 200
        linhas = {l["chave"]: l for l in r.json()}
        assert linhas["BPO Contábil"]["propostas"] >= 1
        assert all(set(l) >= {"conversao", "ticket_medio", "mediana"} for l in linhas.values())

    def test_dimensao_invalida_e_422(self, cliente):
        assert cliente.get("/api/indicadores/recortes", params={"dimensao": "cor"}).status_code == 422

    def test_cenarios_sem_base_devolve_null(self, cliente, carteira):
        r = cliente.get("/api/indicadores/cenarios-de-ticket")
        assert r.status_code == 200 and r.json() is None
