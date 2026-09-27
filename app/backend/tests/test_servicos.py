"""O catálogo de serviços e a linha C1/C2 que sai dele — 27/09/2026."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.carga.planilha_2026 import carregar
from crm.db import linha_por_servico
from crm.db.modelos import GrupoEconomico, Oportunidade
from crm.domain.abordagem import fala_de_preco
from crm.domain.listas import LinhaServico, Origem, Situacao
from crm.domain.porte import DIRECIONADORES
from crm.domain.servicos import CATALOGO, linha_do_servico, servico_do_catalogo

C1, C2 = LinhaServico.C1, LinhaServico.C2


class TestCatalogo:
    def test_os_dez_servicos_aprovados_com_a_linha(self):
        assert [(s.nome, s.linha) for s in CATALOGO] == [
            ("BPO Contábil, Fiscal e Dep. Pessoal", C1),
            ("BPO Contábil e Fiscal", C1),
            ("Dep. Pessoal", C1),
            ("BPO Financeiro", C1),
            ("Endereço Fiscal", C1),
            ("Representante Legal", C1),
            ("Consultoria", C2),
            ("Legalização Empresarial", C2),
            ("Auditoria", C2),
            ("FSCP", C2),
        ]

    def test_fscp_por_extenso(self):
        assert servico_do_catalogo("FSCP").nome_por_extenso == "Finance Statement Closing Procedure"

    def test_nenhum_texto_fala_de_preco(self):
        """O catálogo é o roteiro da IA, e a IA não informa preço."""
        for s in CATALOGO:
            textos = [s.para_quem, *s.fora_do_perfil, *(p.texto for p in s.perguntas)]
            assert not any(fala_de_preco(t) for t in textos), s.nome

    def test_toda_pergunta_da_regua_aponta_um_direcionador_que_existe(self):
        campos = {d.campo for d in DIRECIONADORES}
        for s in CATALOGO:
            for p in s.perguntas:
                assert p.direcionador is None or p.direcionador in campos, (s.nome, p.direcionador)

    @pytest.mark.parametrize(
        "nome, linha",
        [
            ("BPO Contábil", C1),  # nome antigo da planilha
            ("Legalização", C2),  # nome antigo, e agora não recorrente
            ("Representação", C1),
            ("endereço fiscal", C1),  # a planilha escreve em minúsculas
            ("  consultoria ", C2),
            ("Serviço que não existe", None),
            (None, None),
        ],
    )
    def test_linha_pelo_servico(self, nome, linha):
        assert linha_do_servico(nome) is linha


class TestCarga:
    @staticmethod
    def linha(**campos):
        base = {
            "Ano": 2026, "Nome da oportunidade": "Grupo Exemplo", "Status": "Aceita",
            "Tipo Canal": "Socio", "Responsável": "C1", "Responsável 2": "EL",
        }
        return base | campos

    def test_vale_o_servico_e_a_discordancia_vira_aviso(self):
        propostas, rel = carregar([self.linha(**{"Serviço": "Legalização", "Responsável": "C1"})])
        assert propostas[0].linha_servico is C2
        aviso = next(a for a in rel.avisos if a.campo == "linha de serviço")
        assert "vale o serviço" in aviso.texto and not aviso.bloqueia

    def test_servico_fora_do_catalogo_mantem_a_coluna(self):
        propostas, rel = carregar([self.linha(**{"Serviço": "Algo novo", "Responsável": "C2"})])
        assert propostas[0].linha_servico is C2
        assert not [a for a in rel.avisos if a.campo == "linha de serviço"]

    def test_concordando_nao_ha_aviso(self):
        _, rel = carregar([self.linha(**{"Serviço": "BPO Contábil", "Responsável": "C1"})])
        assert not [a for a in rel.avisos if a.campo == "linha de serviço"]


@pytest.fixture
def cliente(engine: sa.Engine) -> TestClient:
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as aberto:
        yield aberto


class TestRotas:
    def test_catalogo_sem_preco_e_com_a_linha(self, cliente):
        catalogo = cliente.get("/api/servicos").json()
        assert len(catalogo) == 10
        fscp = next(s for s in catalogo if s["nome"] == "FSCP")
        assert (fscp["linha"], fscp["recorrente"], fscp["transbordo"]) == ("C2", False, "Consultoria (C2)")
        assert not any("preco" in chave for s in catalogo for chave in s)

    def test_nova_oportunidade_ganha_a_linha_do_servico(self, cliente):
        criada = cliente.post(
            "/api/oportunidades", json={"nome": "Proposta X", "servico": "Auditoria"}
        ).json()
        assert criada["linha_servico"] == "C2"

    def test_trocar_o_servico_troca_a_linha_e_protege_da_recarga(self, cliente, sessao: Session):
        criada = cliente.post(
            "/api/oportunidades", json={"nome": "Proposta Y", "servico": "Consultoria"}
        ).json()
        editada = cliente.patch(
            f"/api/oportunidades/{criada['id']}", json={"servico": "Dep. Pessoal"}
        ).json()
        assert editada["linha_servico"] == "C1"
        assert "linha_servico" in sessao.get(Oportunidade, criada["id"]).campos_do_crm

    def test_servico_fora_do_catalogo_nao_mexe_na_linha(self, cliente):
        criada = cliente.post(
            "/api/oportunidades", json={"nome": "Proposta Z", "servico": "Auditoria"}
        ).json()
        editada = cliente.patch(
            f"/api/oportunidades/{criada['id']}", json={"servico": "Algo que não existe"}
        ).json()
        assert editada["linha_servico"] == "C2"

    def test_conversao_do_lead_leva_a_linha(self, cliente):
        lead = cliente.post("/api/leads", json={"nome": "Lead"}).json()["id"]
        cliente.patch(f"/api/leads/{lead}", json={"situacao": "Qualificado", "porte_estimado": "Médio"})
        oportunidade = cliente.post(
            f"/api/leads/{lead}/converter", json={"servico": "BPO Financeiro"}
        ).json()
        assert oportunidade["linha_servico"] == "C1"


class TestReclassificacao:
    @pytest.fixture
    def oportunidades(self, sessao: Session) -> dict[str, int]:
        grupo = GrupoEconomico(nome="Grupo", origem=Origem.CRM)
        sessao.add(grupo)
        sessao.flush()
        dados = {
            "legalizacao_c1": ("Legalização", C1),
            "bpo_c2": ("BPO Contábil", C2),
            "consultoria_ok": ("Consultoria", C2),
            "fora": ("Algo novo", C1),
            "sem_linha": ("Auditoria", None),
        }
        ids = {}
        for chave, (servico, linha) in dados.items():
            o = Oportunidade(
                grupo_id=grupo.id, nome=chave, servico=servico, linha_servico=linha,
                situacao=Situacao.ENVIAR_PROPOSTA, origem=Origem.CRM,
            )
            sessao.add(o)
            sessao.flush()
            ids[chave] = o.id
        sessao.commit()
        return ids

    def test_ensaio_mostra_so_o_que_muda(self, sessao, oportunidades):
        plano = linha_por_servico.planejar(sessao)
        assert {m.oportunidade_id for m in plano} == {
            oportunidades["legalizacao_c1"], oportunidades["bpo_c2"], oportunidades["sem_linha"]
        }
        assert linha_por_servico.resumir(plano) == [
            "   1  Auditoria: vazio → C2",
            "   1  BPO Contábil: C2 → C1",
            "   1  Legalização: C1 → C2",
        ]

    def test_aplicar_grava_e_depois_nao_sobra_nada(self, sessao, oportunidades):
        linha_por_servico.aplicar(sessao, linha_por_servico.planejar(sessao))
        sessao.commit()
        assert sessao.get(Oportunidade, oportunidades["legalizacao_c1"]).linha_servico is C2
        assert sessao.get(Oportunidade, oportunidades["fora"]).linha_servico is C1
        assert linha_por_servico.planejar(sessao) == []
