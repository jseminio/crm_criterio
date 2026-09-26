"""A fila de abordagens de ponta a ponta, com agente e envio falsos.

O centro é a regra do plano: **o agente prepara, só a pessoa aprova, e só a
aprovação envia** — uma vez, e só quando as conferências passam.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.agente.envio import EnvioFalhou
from crm.agente.sdr import AgenteFalhou, Preparo
from crm.api.abordagens import Servicos
from crm.api.app import criar_app
from crm.db.modelos import ExecucaoDoAgente, GrupoEconomico, PessoaContato
from crm.domain.listas import SituacaoGrupo

PREPARO = Preparo(
    historico="Staff loan em espera desde fev/25.",
    pesquisa=[{"fato": "Abriu filial em 2025", "fonte": "https://exemplo.com/omega"}],
    quem_decide="Diretora financeira",
    assunto="Retomando a conversa",
    mensagem="Olá, [nome]. Proponho 30 minutos na semana de [data].",
)


class AgenteFalso:
    modelo = "claude-opus-5"

    def __init__(self, preparo=PREPARO, falha=None):
        self.preparo = preparo
        self.falha = falha
        self.pedidos: list[dict] = []

    def preparar(self, contexto, *, instrucao=None, rascunho_anterior=None, uso=None):
        self.pedidos.append(
            {"contexto": contexto, "instrucao": instrucao, "anterior": rascunho_anterior}
        )
        uso.tokens_entrada, uso.tokens_saida = 1000, 200
        uso._entrada_ponderada = Decimal(1000)
        if self.falha:
            raise self.falha
        return self.preparo


class Ambiente:
    def __init__(self):
        self.agente = AgenteFalso()
        self.sem_chave = False
        self.envios: list[dict] = []
        self.falha_no_envio: Exception | None = None
        self.email_configurado = True

    def servicos(self) -> Servicos:
        def agente():
            if self.sem_chave:
                raise AgenteFalhou("A chave da API da Anthropic não está no .env")
            return self.agente

        def enviar(**campos):
            if self.falha_no_envio:
                raise self.falha_no_envio
            self.envios.append(campos)

        return Servicos(agente=agente, enviar_email=enviar if self.email_configurado else None)


@pytest.fixture
def ambiente() -> Ambiente:
    return Ambiente()


@pytest.fixture
def cliente(engine: sa.Engine, ambiente: Ambiente) -> TestClient:
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, ambiente.servicos)) as aberto:
        yield aberto


def _nova(cliente, **campos):
    corpo = {"grupo_nome": "Omega", "mes": "2026-10", "quem_apresenta": "Parceiro A", **campos}
    resposta = cliente.post("/api/abordagens", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _pronta(cliente, **campos):
    """Uma abordagem com rascunho aguardando aprovação e os colchetes preenchidos."""
    abordagem = _nova(cliente, destinatario="ana@omega.com.br", **campos)
    cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    resposta = cliente.patch(
        f"/api/abordagens/{abordagem['id']}",
        json={"mensagem": "Olá, Ana. Proponho 30 minutos na semana de 13/10."},
    )
    assert resposta.json()["pode_aprovar"], resposta.json()["conferencias"]
    return resposta.json()


def test_conta_nova_entra_como_prospect_e_nao_repete_no_mes(cliente, sessao: Session):
    abordagem = _nova(cliente)
    assert abordagem["situacao"] == "A preparar"
    assert abordagem["proximo_passo"] == "Preparar a ficha"
    grupo = sessao.get(GrupoEconomico, abordagem["grupo_id"])
    assert grupo.situacao is SituacaoGrupo.PROSPECT

    repetida = cliente.post(
        "/api/abordagens", json={"grupo_nome": "omega", "mes": "2026-10"}
    )
    assert repetida.status_code == 409


def test_sem_quem_apresenta_fica_bloqueada_e_nao_prepara(cliente):
    abordagem = _nova(cliente, quem_apresenta=None)
    assert abordagem["situacao"] == "Bloqueada"
    resposta = cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    assert resposta.status_code == 422

    filtrada = cliente.get("/api/abordagens", params={"situacao": "Bloqueada"}).json()
    assert filtrada["total"] == 1


def test_preparo_grava_ficha_rascunho_e_custo(cliente, ambiente, sessao: Session):
    abordagem = _nova(cliente, contexto="Já é cliente de consultoria.")
    resposta = cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    assert resposta.status_code == 202
    assert resposta.json()["situacao"] == "Pesquisando"

    pronta = cliente.get(f"/api/abordagens/{abordagem['id']}").json()
    assert pronta["situacao"] == "Aguardando aprovação"
    assert pronta["versao"] == 1
    assert pronta["mensagem"] == PREPARO.mensagem
    assert pronta["ficha"]["pesquisa"] == PREPARO.pesquisa
    assert pronta["pode_aprovar"] is False  # há [nome] e [data]
    assert ambiente.agente.pedidos[0]["contexto"].contexto_informado == "Já é cliente de consultoria."

    execucao = sessao.scalars(sa.select(ExecucaoDoAgente)).one()
    assert execucao.deu_certo and execucao.custo_usd == Decimal("0.0100")

    resumo = cliente.get("/api/abordagens/resumo", params={"mes": "2026-10"}).json()
    assert resumo["aguardando_aprovacao"] == 1
    assert Decimal(resumo["custo_usd"]) == Decimal("0.0100")


def test_sem_chave_vira_erro_explicado_e_nao_registra_execucao(
    cliente, ambiente, sessao: Session
):
    ambiente.sem_chave = True
    abordagem = _nova(cliente)
    cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    com_erro = cliente.get(f"/api/abordagens/{abordagem['id']}").json()
    assert com_erro["situacao"] == "Erro"
    assert ".env" in com_erro["erro"]
    assert sessao.scalars(sa.select(ExecucaoDoAgente)).all() == []

    # Tentar de novo depois de corrigir funciona.
    ambiente.sem_chave = False
    cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    assert cliente.get(f"/api/abordagens/{abordagem['id']}").json()["situacao"] == (
        "Aguardando aprovação"
    )


def test_falha_do_agente_registra_o_custo_da_tentativa(cliente, ambiente, sessao: Session):
    ambiente.agente = AgenteFalso(falha=AgenteFalhou("A resposta do agente foi cortada."))
    abordagem = _nova(cliente)
    cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    assert cliente.get(f"/api/abordagens/{abordagem['id']}").json()["erro"] == (
        "A resposta do agente foi cortada."
    )
    execucao = sessao.scalars(sa.select(ExecucaoDoAgente)).one()
    assert not execucao.deu_certo


def test_aprovar_com_colchetes_e_recusado(cliente, ambiente):
    abordagem = _nova(cliente, destinatario="ana@omega.com.br")
    cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    resposta = cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={})
    assert resposta.status_code == 422
    assert "colchetes" in resposta.json()["detail"]
    assert ambiente.envios == []


def test_aprovar_envia_o_email_uma_vez_so(cliente, ambiente):
    abordagem = _pronta(cliente)
    resposta = cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={})
    assert resposta.status_code == 200
    enviada = resposta.json()
    assert enviada["situacao"] == "Enviada"
    assert enviada["aprovada_por"] == "EL" and enviada["enviada_em"]
    assert ambiente.envios == [
        {
            "para": "ana@omega.com.br",
            "assunto": "Retomando a conversa",
            "corpo": "Olá, Ana. Proponho 30 minutos na semana de 13/10.",
        }
    ]

    segunda = cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={})
    assert segunda.status_code == 409
    assert len(ambiente.envios) == 1

    # Depois de enviada, o texto não muda mais.
    mudar = cliente.patch(f"/api/abordagens/{abordagem['id']}", json={"mensagem": "outra"})
    assert mudar.status_code == 409


def test_email_sem_configuracao_nao_envia_nem_muda_situacao(cliente, ambiente):
    ambiente.email_configurado = False
    abordagem = _pronta(cliente)
    resposta = cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={})
    assert resposta.status_code == 409
    assert "CRM_M365" in resposta.json()["detail"]
    assert cliente.get(f"/api/abordagens/{abordagem['id']}").json()["situacao"] == (
        "Aguardando aprovação"
    )


def test_falha_no_envio_mantem_aguardando(cliente, ambiente):
    ambiente.falha_no_envio = EnvioFalhou("O Microsoft 365 não enviou o e-mail (HTTP 403).")
    abordagem = _pronta(cliente)
    resposta = cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={})
    assert resposta.status_code == 502
    detalhe = cliente.get(f"/api/abordagens/{abordagem['id']}").json()
    assert detalhe["situacao"] == "Aguardando aprovação" and detalhe["enviada_em"] is None


def test_contato_nao_contatar_trava_a_aprovacao(cliente, ambiente, sessao: Session):
    abordagem = _pronta(cliente)
    sessao.add(
        PessoaContato(
            grupo_id=abordagem["grupo_id"], nome="Ana", email="ANA@omega.com.br", nao_contatar=True
        )
    )
    sessao.commit()
    resposta = cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={})
    assert resposta.status_code == 422
    assert "não contatar" in resposta.json()["detail"]
    assert ambiente.envios == []


def test_whatsapp_aprova_com_link_e_a_pessoa_marca_enviada(cliente, ambiente):
    abordagem = _nova(cliente, canal="WhatsApp", destinatario="(21) 99999-1234")
    cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    pronta = cliente.patch(
        f"/api/abordagens/{abordagem['id']}",
        json={"mensagem": "Olá, Ana. Podemos conversar 30 minutos?"},
    ).json()
    assert pronta["assunto"] is None
    assert pronta["link_whatsapp"].startswith("https://wa.me/5521999991234?text=Ol")

    aprovada = cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={}).json()
    assert aprovada["situacao"] == "Aprovada"
    assert ambiente.envios == []  # o WhatsApp não sai pelo CRM

    enviada = cliente.post(f"/api/abordagens/{abordagem['id']}/marcar-enviada").json()
    assert enviada["situacao"] == "Enviada"


def test_nova_versao_leva_o_pedido_e_o_rascunho_anterior(cliente, ambiente):
    abordagem = _nova(cliente)
    cliente.post(f"/api/abordagens/{abordagem['id']}/preparar")
    resposta = cliente.post(
        f"/api/abordagens/{abordagem['id']}/nova-versao", json={"instrucao": "Mais curta"}
    )
    assert resposta.status_code == 202
    assert ambiente.agente.pedidos[1]["instrucao"] == "Mais curta"
    assert ambiente.agente.pedidos[1]["anterior"] == PREPARO.mensagem
    assert cliente.get(f"/api/abordagens/{abordagem['id']}").json()["versao"] == 2


def test_diagnostico_so_depois_do_envio_e_entra_no_resumo(cliente):
    abordagem = _pronta(cliente)
    antes = cliente.patch(
        f"/api/abordagens/{abordagem['id']}", json={"diagnostico_agendado_em": "2026-10-20"}
    )
    assert antes.status_code == 422

    cliente.post(f"/api/abordagens/{abordagem['id']}/aprovar", json={})
    depois = cliente.patch(
        f"/api/abordagens/{abordagem['id']}", json={"diagnostico_agendado_em": "2026-10-20"}
    ).json()
    assert depois["proximo_passo"] == "Fazer o diagnóstico"

    resumo = cliente.get("/api/abordagens/resumo", params={"mes": "2026-10"}).json()
    assert (resumo["na_fila"], resumo["abordadas"], resumo["diagnosticos"]) == (1, 1, 1)


def test_descartar_tira_da_fila_do_resumo(cliente):
    abordagem = _nova(cliente)
    assert cliente.post(f"/api/abordagens/{abordagem['id']}/descartar").json()["situacao"] == (
        "Descartada"
    )
    resumo = cliente.get("/api/abordagens/resumo", params={"mes": "2026-10"}).json()
    assert resumo["na_fila"] == 0 and resumo["custo_usd"] is None
    # Descartada, a conta pode voltar à fila do mês.
    _nova(cliente)
