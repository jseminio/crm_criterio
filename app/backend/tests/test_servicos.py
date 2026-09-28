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
    def test_os_servicos_aprovados_com_a_linha(self):
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
            ("DIRPF", C2),  # 27/09/2026
            ("Perícia", C2),  # 27/09/2026
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
        assert len(catalogo) == 12
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
            "/api/oportunidades",
            json={"nome": "Proposta Y", "servico": "Consultoria", "servico_tema": "Trabalhista"},
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


class TestOutroServico:
    """Serviço fora do catálogo (27/09/2026): descrição obrigatória, linha "Ainda não sei"."""

    DESCRICAO = "Gestão dos contratos de aluguel da holding"

    def test_outro_exige_descricao(self, cliente):
        resposta = cliente.post("/api/oportunidades", json={"nome": "P", "servico": "Outro"})
        assert resposta.status_code == 422
        assert "descreva" in resposta.json()["detail"]

    def test_descricao_curta_demais(self, cliente):
        resposta = cliente.post(
            "/api/oportunidades", json={"nome": "P", "servico": "Outro", "servico_descricao": "  aluguel "}
        )
        assert resposta.status_code == 422

    def test_outro_fica_sem_linha(self, cliente):
        criada = cliente.post(
            "/api/oportunidades",
            json={"nome": "P", "servico": "Outro", "servico_descricao": self.DESCRICAO},
        ).json()
        assert (criada["servico"], criada["linha_servico"], criada["servico_descricao"]) == (
            "Outro", None, self.DESCRICAO
        )

    def test_servico_do_catalogo_nao_leva_descricao(self, cliente):
        resposta = cliente.post(
            "/api/oportunidades",
            json={"nome": "P", "servico": "Auditoria", "servico_descricao": self.DESCRICAO},
        )
        assert resposta.status_code == 422

    def test_trocar_para_o_catalogo_apaga_a_descricao(self, cliente):
        criada = cliente.post(
            "/api/oportunidades",
            json={"nome": "P", "servico": "Outro", "servico_descricao": self.DESCRICAO},
        ).json()
        editada = cliente.patch(f"/api/oportunidades/{criada['id']}", json={"servico": "Auditoria"}).json()
        assert (editada["servico_descricao"], editada["linha_servico"]) == (None, "C2")

    def test_trocar_para_outro_sem_descricao_recusa(self, cliente):
        criada = cliente.post("/api/oportunidades", json={"nome": "P", "servico": "Auditoria"}).json()
        resposta = cliente.patch(f"/api/oportunidades/{criada['id']}", json={"servico": "Outro"})
        assert resposta.status_code == 422

    def test_lead_com_interesse_outro(self, cliente):
        assert cliente.post("/api/leads", json={"nome": "L", "interesse": "Outro"}).status_code == 422
        lead = cliente.post(
            "/api/leads", json={"nome": "L", "interesse": "Outro", "interesse_descricao": self.DESCRICAO}
        ).json()
        assert lead["interesse_descricao"] == self.DESCRICAO
        editado = cliente.patch(f"/api/leads/{lead['id']}", json={"interesse": "Dep. Pessoal"}).json()
        assert editado["interesse_descricao"] is None

    def test_conversao_leva_a_descricao(self, cliente):
        lead = cliente.post("/api/leads", json={"nome": "L"}).json()["id"]
        cliente.patch(f"/api/leads/{lead}", json={"situacao": "Qualificado", "porte_estimado": "Médio"})
        assert cliente.post(f"/api/leads/{lead}/converter", json={"servico": "Outro"}).status_code == 422
        oportunidade = cliente.post(
            f"/api/leads/{lead}/converter", json={"servico": "Outro", "servico_descricao": self.DESCRICAO}
        ).json()
        assert (oportunidade["servico_descricao"], oportunidade["linha_servico"]) == (self.DESCRICAO, None)

    def test_pedidos_juntam_oportunidades_e_leads(self, cliente):
        cliente.post("/api/oportunidades", json={"nome": "Op", "servico": "Outro", "servico_descricao": self.DESCRICAO})
        cliente.post("/api/leads", json={"nome": "Ld", "interesse": "Outro", "interesse_descricao": "Perícia contábil judicial"})
        cliente.post("/api/oportunidades", json={"nome": "Normal", "servico": "Auditoria"})
        pedidos = cliente.get("/api/servicos/pedidos").json()
        assert sorted((p["onde"], p["nome"], p["descricao"]) for p in pedidos) == [
            ("Lead", "Ld", "Perícia contábil judicial"),
            ("Oportunidade", "Op", self.DESCRICAO),
        ]


class TestTemasDeConsultoria:
    """Consultoria pede o tema (27/09/2026); DIRPF e Perícia entram como C2."""

    def test_catalogo_traz_os_seis_temas(self, cliente):
        consultoria = next(s for s in cliente.get("/api/servicos").json() if s["nome"] == "Consultoria")
        assert [t["nome"] for t in consultoria["temas"]] == [
            "Tributária e fiscal", "Valuation, PPA e laudos", "M&A, due diligence e captação",
            "Contábil e financeira", "Societária e reestruturação", "Trabalhista",
        ]
        assert all(t["perguntas"] for t in consultoria["temas"])

    def test_consultoria_sem_tema_recusa(self, cliente):
        resposta = cliente.post("/api/oportunidades", json={"nome": "P", "servico": "Consultoria"})
        assert resposta.status_code == 422
        assert "tema" in resposta.json()["detail"]

    def test_tema_desconhecido_recusa(self, cliente):
        resposta = cliente.post(
            "/api/oportunidades", json={"nome": "P", "servico": "Consultoria", "servico_tema": "Astrologia"}
        )
        assert resposta.status_code == 422

    def test_tema_so_para_servico_com_temas(self, cliente):
        resposta = cliente.post(
            "/api/oportunidades", json={"nome": "P", "servico": "Auditoria", "servico_tema": "Trabalhista"}
        )
        assert resposta.status_code == 422

    def test_consultoria_com_tema(self, cliente):
        criada = cliente.post(
            "/api/oportunidades",
            json={"nome": "P", "servico": "Consultoria", "servico_tema": "Valuation, PPA e laudos"},
        ).json()
        assert (criada["servico_tema"], criada["linha_servico"]) == ("Valuation, PPA e laudos", "C2")

    def test_proposta_antiga_sem_tema_continua_editavel(self, cliente, sessao: Session):
        """A tela manda o rascunho inteiro, serviço incluso, a cada salvar."""
        grupo = GrupoEconomico(nome="G", origem=Origem.CRM)
        sessao.add(grupo)
        sessao.flush()
        antiga = Oportunidade(
            grupo_id=grupo.id, nome="Antiga", servico="Consultoria", situacao=Situacao.ENVIAR_PROPOSTA,
            origem=Origem.CRM,
        )
        sessao.add(antiga)
        sessao.commit()
        resposta = cliente.patch(
            f"/api/oportunidades/{antiga.id}",
            json={"servico": "Consultoria", "servico_tema": None, "observacao": "ligar segunda"},
        )
        assert resposta.status_code == 200

    def test_trocar_para_consultoria_exige_tema_e_sair_apaga(self, cliente):
        criada = cliente.post("/api/oportunidades", json={"nome": "P", "servico": "Auditoria"}).json()
        rota = f"/api/oportunidades/{criada['id']}"
        assert cliente.patch(rota, json={"servico": "Consultoria"}).status_code == 422
        com_tema = cliente.patch(rota, json={"servico": "Consultoria", "servico_tema": "Trabalhista"}).json()
        assert com_tema["servico_tema"] == "Trabalhista"
        de_volta = cliente.patch(rota, json={"servico": "Auditoria"}).json()
        assert de_volta["servico_tema"] is None

    def test_lead_e_conversao_com_tema(self, cliente):
        assert cliente.post("/api/leads", json={"nome": "L", "interesse": "Consultoria"}).status_code == 422
        lead = cliente.post(
            "/api/leads", json={"nome": "L", "interesse": "Consultoria", "interesse_tema": "Trabalhista"}
        ).json()
        assert lead["interesse_tema"] == "Trabalhista"
        cliente.patch(f"/api/leads/{lead['id']}", json={"situacao": "Qualificado", "porte_estimado": "Médio"})
        assert cliente.post(f"/api/leads/{lead['id']}/converter", json={"servico": "Consultoria"}).status_code == 422
        oportunidade = cliente.post(
            f"/api/leads/{lead['id']}/converter",
            json={"servico": "Consultoria", "servico_tema": "Trabalhista"},
        ).json()
        assert oportunidade["servico_tema"] == "Trabalhista"

    @pytest.mark.parametrize("servico", ["DIRPF", "Perícia"])
    def test_dirpf_e_pericia_sao_c2(self, cliente, servico):
        criada = cliente.post("/api/oportunidades", json={"nome": "P", "servico": servico}).json()
        assert criada["linha_servico"] == "C2"


class TestReclassificacaoPeloTipo:
    @pytest.fixture
    def propostas(self, sessao: Session) -> dict[str, int]:
        grupo = GrupoEconomico(nome="G", origem=Origem.CRM)
        sessao.add(grupo)
        sessao.flush()
        dados = {
            "alteracao": ("Consultoria", "Alteração contratual", None, Origem.CARGA_2026, "g|2026|consultoria|alteracao"),
            "pericial": ("Consultoria", "Cálculo Pericial", None, Origem.CRM, None),
            "valuation": ("Consultoria", "Valuation", None, Origem.CRM, None),
            "ja_tem_tema": ("Consultoria", "Valuation", "Trabalhista", Origem.CRM, None),
            "sem_detalhe": ("Consultoria", "Consultoria", None, Origem.CRM, None),
            "bpo": ("BPO Contábil", "Valuation", None, Origem.CRM, None),
        }
        ids = {}
        for chave, (servico, tipo, tema, origem, chave_origem) in dados.items():
            o = Oportunidade(
                grupo_id=grupo.id, nome=chave, servico=servico, tipo_servico=tipo, servico_tema=tema,
                linha_servico=C2 if servico == "Consultoria" else C1,
                situacao=Situacao.ENVIAR_PROPOSTA, origem=origem, chave_origem=chave_origem,
            )
            sessao.add(o)
            sessao.flush()
            ids[chave] = o.id
        sessao.commit()
        return ids

    def test_ensaio(self, sessao, propostas):
        from crm.db import servico_pelo_tipo

        plano = servico_pelo_tipo.planejar(sessao)
        assert {m.oportunidade_id for m in plano} == {
            propostas["alteracao"], propostas["pericial"], propostas["valuation"]
        }
        assert servico_pelo_tipo.resumir(plano) == [
            "   1  Consultoria → Legalização Empresarial",
            "   1  Consultoria → Perícia",
            "   1  Consultoria ganha o tema: Valuation, PPA e laudos",
        ]

    def test_aplicar_protege_da_recarga_e_nao_sobrescreve_tema(self, sessao, propostas):
        from crm.db import servico_pelo_tipo

        servico_pelo_tipo.aplicar(sessao, servico_pelo_tipo.planejar(sessao))
        sessao.commit()
        alteracao = sessao.get(Oportunidade, propostas["alteracao"])
        assert alteracao.servico == "Legalização Empresarial"
        assert "servico" in alteracao.campos_do_crm
        assert alteracao.chave_origem == "g|2026|consultoria|alteracao"  # a identidade não muda
        assert sessao.get(Oportunidade, propostas["valuation"]).servico_tema == "Valuation, PPA e laudos"
        assert sessao.get(Oportunidade, propostas["ja_tem_tema"]).servico_tema == "Trabalhista"
        assert sessao.get(Oportunidade, propostas["sem_detalhe"]).servico_tema is None
        assert servico_pelo_tipo.planejar(sessao) == []


def test_sdr_encerra_com_consultoria_so_com_tema(cliente):
    lead = cliente.post("/api/leads", json={"nome": "L"}).json()["id"]
    conversa = cliente.post("/api/sdr/conversas", json={"lead_id": lead, "canal": "WhatsApp"}).json()["id"]
    rota = f"/api/sdr/conversas/{conversa}/encerrar"
    corpo = {"desfecho": "Qualificado", "porte_estimado": "Médio", "interesse": "Consultoria"}
    assert cliente.post(rota, json=corpo).status_code == 422
    resposta = cliente.post(rota, json=corpo | {"interesse_tema": "Tributária e fiscal"})
    assert resposta.status_code == 200
    lead_gravado = next(l for l in cliente.get("/api/leads").json()["itens"] if l["id"] == lead)
    assert lead_gravado["interesse_tema"] == "Tributária e fiscal"
