"""Ata pela transcrição do Granola e ajustes da área técnica (02/10/2026)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.agente import ata
from crm.api.app import criar_app
from crm.api.sucesso import ServicosDaAta
from crm.db.modelos import Contrato, GrupoEconomico, Perfil, Usuario
from crm.domain.listas import SituacaoContrato

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
BRUNO = {"Authorization": "Bearer bruno@grupocriterio.com.br|Bruno Soares"}
JEFF = {"Authorization": "Bearer jefferson@grupocriterio.com.br|Jefferson Souza"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}
HOJE = date.today()
ONTEM = HOJE - timedelta(days=1)
TRANSCRICAO = "Gestor: bom dia. Cliente: o frete está em custo na DRE, precisa ir para despesa. " * 3

ATA = {
    "resumo": "Reunião trimestral. O cliente quer abrir loja.",
    "decisoes_do_cliente": ["Abrir a segunda loja em 2027", "  "],
    "ajustes": [
        {"descricao": "Reclassificar o frete de custo para despesa na DRE", "prazo": "2026-10-10",
         "responsavel": "Jefferson", "trecho": "Jefferson fica com o frete até dia 10"},
        {"descricao": "Conciliar o cartão de setembro", "prazo": "até sexta", "responsavel": "Carla", "trecho": ""},
        {"descricao": " ", "prazo": "", "responsavel": "", "trecho": ""},
    ],
    "pendencias_do_cliente": ["Enviar extratos de setembro"],
    "pontos_sensiveis": [],
    "estrategia_e_desafios": " Abrir a segunda loja; a equipe financeira é uma pessoa só. ",
    "oportunidades": [
        {"lacuna": "Ninguém faz projeção de caixa", "servico": "bpo financeiro", "tema": "", "valor": "4.500,00",
         "trecho": "a equipe financeira é só uma pessoa"},
        {"lacuna": "Avaliar a empresa antes do sócio", "servico": "Consultoria", "tema": "Valuation, PPA e laudos",
         "valor": "", "trecho": ""},
        {"lacuna": "Algo", "servico": "Serviço inventado", "tema": "Tema inventado", "valor": "muito", "trecho": ""},
        {"lacuna": " ", "servico": "Consultoria", "tema": "", "valor": "", "trecho": ""},
    ],
}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


class ClienteFalso:
    def __init__(self, texto: str = json.dumps(ATA), stop_reason: str = "end_turn"):
        self.pedidos: list[dict] = []
        self.texto, self.stop_reason = texto, stop_reason
        self.beta = NS(messages=NS(create=self._criar))

    def _criar(self, **kwargs):
        self.pedidos.append(kwargs)
        return NS(
            stop_reason=self.stop_reason, content=[NS(type="text", text=self.texto)],
            usage=NS(input_tokens=1000, output_tokens=200, cache_creation_input_tokens=0, cache_read_input_tokens=0),
        )


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        tecnica = Perfil(nome="Área técnica", permissoes=["ajustes.concluir"])
        comercial = Perfil(nome="Comercial", permissoes=["funil.ver"])
        s.add_all([tecnica, comercial])
        g = GrupoEconomico(nome="Rede Farma")
        s.add(g)
        s.flush()
        s.add_all([
            Usuario(email="bruno@grupocriterio.com.br", nome="Bruno Soares", perfil_id=tecnica.id),
            Usuario(email="jefferson@grupocriterio.com.br", nome="Jefferson Souza", perfil_id=tecnica.id),
            Usuario(email="karine@grupocriterio.com.br", nome="Karine N", perfil_id=comercial.id),
            Usuario(email="saiu@grupocriterio.com.br", nome="Saiu", perfil_id=tecnica.id, ativo=False),
            Contrato(grupo_id=g.id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("5000")),
        ])
        s.commit()
        return {"grupo": g.id}


@pytest.fixture
def falso():
    return ClienteFalso()


@pytest.fixture
def cliente(engine, ids, falso):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    app = criar_app(fabrica, entrada=CONFIG, validar_token=validar, servicos_da_ata=lambda: ServicosDaAta(cliente=lambda: falso))
    with TestClient(app) as c:
        yield c


def _registrar(cliente, g, ajustes, **mais):
    return cliente.post(f"/api/sucesso/grupos/{g}/reunioes", headers=ADMIN, json={
        "tipo": "trimestral", "data": ONTEM.isoformat(), "ajustes": ajustes, **mais,
    })


# ------------------------------------------------------------------ a ata pela IA


def test_ata_limpa_o_rascunho_e_nao_grava_nada(cliente, ids, falso):
    r = cliente.post(f"/api/sucesso/grupos/{ids['grupo']}/ata", headers=ADMIN, json={
        "tipo": "trimestral", "data": "2026-10-02", "participantes": "Gestor e CFO", "transcricao": TRANSCRICAO,
    })
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["decisoes_do_cliente"] == ["Abrir a segunda loja em 2027"]
    assert a["ajustes"] == [  # prazo que não é data vira vazio; ajuste em branco some
        {"descricao": "Reclassificar o frete de custo para despesa na DRE", "prazo": "2026-10-10",
         # o nome citado vira o e-mail de quem recebe ajustes
         "responsavel_citado": "Jefferson", "responsavel_email": "jefferson@grupocriterio.com.br",
         "trecho": "Jefferson fica com o frete até dia 10"},
        # citada mas não cadastrada: fica sem e-mail, a pessoa escolhe
        {"descricao": "Conciliar o cartão de setembro", "prazo": None, "responsavel_citado": "Carla",
         "responsavel_email": None, "trecho": None},
    ]
    assert a["estrategia_e_desafios"] == "Abrir a segunda loja; a equipe financeira é uma pessoa só."
    assert a["oportunidades"] == [
        {"lacuna": "Ninguém faz projeção de caixa", "servico": "BPO Financeiro", "servico_tema": None,
         "valor": "4500.00", "recorrente": True, "trecho": "a equipe financeira é só uma pessoa"},
        {"lacuna": "Avaliar a empresa antes do sócio", "servico": "Consultoria", "servico_tema": "Valuation, PPA e laudos",
         "valor": None, "recorrente": False, "trecho": None},
        # serviço fora do catálogo fica vazio, para a pessoa escolher; tema e valor inválidos também
        {"lacuna": "Algo", "servico": None, "servico_tema": None, "valor": None, "recorrente": False, "trecho": None},
    ]
    assert a["custo_usd"] == "0.0080"  # 1000 × US$ 4/M + 200 × US$ 20/M
    pedido = falso.pedidos[0]
    assert pedido["model"] == "claude-opus-5-5" and pedido["fallbacks"] == "default"
    assert pedido["output_config"]["format"]["type"] == "json_schema"
    conteudo = pedido["messages"][0]["content"]
    assert "Rede Farma" in conteudo and "Trimestral, em 02/10/2026" in conteudo
    # a IA recebe quem pode receber ajuste e o catálogo, para citar só o que existe
    assert "Bruno Soares, Eduardo Luiz, Jefferson Souza" in conteudo
    assert "Consultoria (temas: Tributária e fiscal" in conteudo and "BPO Financeiro" in conteudo
    assert cliente.get(f"/api/sucesso/grupos/{ids['grupo']}/reunioes", headers=ADMIN).json() == []


@pytest.mark.parametrize("falso, trecho", [
    (ClienteFalso(stop_reason="refusal"), "recusou"),
    (ClienteFalso(stop_reason="max_tokens"), "longa demais"),
    (ClienteFalso(texto="não é json"), "formato esperado"),
])
def test_ata_falha_com_mensagem_para_a_pessoa(cliente, ids, falso, trecho):
    r = cliente.post(f"/api/sucesso/grupos/{ids['grupo']}/ata", headers=ADMIN,
                     json={"tipo": "mensal", "data": "2026-10-02", "transcricao": TRANSCRICAO})
    assert r.status_code == 502 and trecho in r.json()["detail"]


def test_ata_sem_chave_avisa(engine, ids):
    from crm.agente.sdr import AgenteFalhou

    def sem_chave():
        raise AgenteFalhou("A chave da API da Anthropic não está no .env (ANTHROPIC_API_KEY).")

    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    app = criar_app(fabrica, entrada=CONFIG, validar_token=validar, servicos_da_ata=lambda: ServicosDaAta(cliente=sem_chave))
    with TestClient(app) as c:
        r = c.post(f"/api/sucesso/grupos/{ids['grupo']}/ata", headers=ADMIN,
                   json={"tipo": "mensal", "data": "2026-10-02", "transcricao": TRANSCRICAO})
    assert r.status_code == 502 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_transcricao_curta_e_recusada(cliente, ids):
    r = cliente.post(f"/api/sucesso/grupos/{ids['grupo']}/ata", headers=ADMIN,
                     json={"tipo": "mensal", "data": "2026-10-02", "transcricao": "curta"})
    assert r.status_code == 422


def test_prazo_so_aceita_data():
    assert ata._prazo("2026-10-10") == "2026-10-10"
    assert ata._prazo("10/10/2026") is None and ata._prazo(None) is None and ata._prazo("2026-1-1") is None


# ------------------------------------------------------------------ registrar com ajustes


def test_responsaveis_sao_os_ativos_que_marcam_feito(cliente):
    r = cliente.get("/api/ajustes/responsaveis", headers=ADMIN).json()
    assert [x["nome"] for x in r] == ["Bruno Soares", "Eduardo Luiz", "Jefferson Souza"]  # o Administrador também pode


def test_registrar_reuniao_cria_os_ajustes_e_guarda_a_ata(cliente, ids):
    g = ids["grupo"]
    r = _registrar(cliente, g, [
        {"descricao": "Reclassificar o frete", "responsavel_email": "Bruno@grupocriterio.com.br", "prazo": ONTEM.isoformat()},
        {"descricao": "Conciliar o cartão", "responsavel_email": "jefferson@grupocriterio.com.br"},
    ], resumo="Resumo.", pendencias_do_cliente="Extratos", transcricao=TRANSCRICAO)
    assert r.status_code == 201, r.text
    assert (r.json()["ajustes_pendentes"], r.json()["ajustes_atrasados"], r.json()["ajustes_feitos"]) == (2, 1, 0)
    (reuniao,) = cliente.get(f"/api/sucesso/grupos/{g}/reunioes", headers=ADMIN).json()
    assert (reuniao["resumo"], reuniao["pendencias_do_cliente"], reuniao["tem_transcricao"]) == ("Resumo.", "Extratos", True)
    assert "transcricao" not in reuniao
    assert [(a["responsavel_nome"], a["responsavel_email"]) for a in reuniao["ajustes"]] == [
        ("Bruno Soares", "bruno@grupocriterio.com.br"), ("Jefferson Souza", "jefferson@grupocriterio.com.br")]
    # a transcrição não vai para o histórico de alterações
    hist = cliente.get("/api/historico", headers=ADMIN, params={"tabela": "reuniao_de_resultado"}).json()
    assert hist and all(h["campo"] != "transcricao" for h in hist)


@pytest.mark.parametrize("email", ["karine@grupocriterio.com.br", "saiu@grupocriterio.com.br", "ninguem@x.com"])
def test_responsavel_precisa_marcar_feito_e_estar_ativo(cliente, ids, email):
    r = _registrar(cliente, ids["grupo"], [{"descricao": "Ajustar", "responsavel_email": email}])
    assert r.status_code == 422 and "Perfis e acesso" in r.json()["detail"]
    assert cliente.get(f"/api/sucesso/grupos/{ids['grupo']}/reunioes", headers=ADMIN).json() == []


# ------------------------------------------------------------------ a área técnica


def test_cada_tecnico_ve_os_seus_e_marca_feito(cliente, ids):
    _registrar(cliente, ids["grupo"], [
        {"descricao": "Sem prazo", "responsavel_email": "bruno@grupocriterio.com.br"},
        {"descricao": "Com prazo", "responsavel_email": "bruno@grupocriterio.com.br", "prazo": "2026-10-20"},
        {"descricao": "Do Jefferson", "responsavel_email": "jefferson@grupocriterio.com.br"},
    ])
    meus = cliente.get("/api/ajustes", headers=BRUNO).json()
    assert [a["descricao"] for a in meus] == ["Com prazo", "Sem prazo"]  # pelo prazo, sem prazo por último
    assert meus[0]["grupo_nome"] == "Rede Farma" and meus[0]["reuniao_tipo"] == "trimestral"
    assert len(cliente.get("/api/ajustes", headers=ADMIN).json()) == 3
    do_jeff = cliente.get("/api/ajustes", headers=JEFF).json()[0]["id"]
    assert cliente.post(f"/api/ajustes/{do_jeff}/feito", headers=BRUNO, json={}).status_code == 404
    r = cliente.post(f"/api/ajustes/{meus[0]['id']}/feito", headers=BRUNO, json={"observacao": " Feito na DRE de setembro "})
    assert r.status_code == 200, r.text
    assert (r.json()["feito_por"], r.json()["observacao"]) == ("Bruno Soares", "Feito na DRE de setembro")
    assert cliente.post(f"/api/ajustes/{meus[0]['id']}/feito", headers=BRUNO, json={}).status_code == 422
    assert [a["descricao"] for a in cliente.get("/api/ajustes", headers=BRUNO).json()] == ["Sem prazo"]
    assert [a["descricao"] for a in cliente.get("/api/ajustes", headers=BRUNO, params={"situacao": "feitos"}).json()] == ["Com prazo"]
    r = cliente.post(f"/api/ajustes/{meus[0]['id']}/reabrir", headers=BRUNO)
    assert r.status_code == 200 and r.json()["feito_em"] is None
    hist = cliente.get("/api/historico", headers=ADMIN, params={"tabela": "ajuste_tecnico"}).json()
    assert any(h["usuario_nome"] == "Bruno Soares" and h["campo"] == "feito_em" for h in hist)


def test_area_tecnica_nao_ve_o_funil_e_o_comercial_nao_ve_ajustes(cliente, ids):
    assert cliente.get("/api/sucesso/funil", headers=BRUNO).status_code == 403
    assert cliente.get("/api/agenda", headers=BRUNO).status_code == 403
    assert cliente.get("/api/ajustes", headers=KARINE).status_code == 403
    assert cliente.post(f"/api/sucesso/grupos/{ids['grupo']}/ata", headers=BRUNO,
                        json={"tipo": "mensal", "data": "2026-10-02", "transcricao": TRANSCRICAO}).status_code == 403


# ------------------------------------------------------------------ oportunidades de novos negócios (03/10/2026)


VENDAS = [
    {"lacuna": "Ninguém faz projeção de caixa", "servico": "BPO Financeiro", "valor": "4500", "abrir_no_funil": True},
    {"lacuna": "Avaliar a empresa antes do sócio", "servico": "Consultoria", "servico_tema": "Valuation, PPA e laudos",
     "valor": "14000", "abrir_no_funil": True},
    {"lacuna": "Balanço sem auditoria para o banco", "servico": "Auditoria"},
]


def test_oportunidades_marcadas_viram_venda_no_funil_comercial(cliente, ids, engine):
    from crm.db.modelos import Oportunidade
    from crm.domain.listas import Situacao, TipoCanal

    g = ids["grupo"]
    r = _registrar(cliente, g, [], oportunidades=VENDAS, estrategia_e_desafios=" Abrir a segunda loja ")
    assert r.status_code == 201, r.text
    funil = r.json()
    # mensal e projeto ficam separados: um é por mês, o outro é o total
    assert (funil["vendas_abertas"], funil["vendas_por_mes"], funil["vendas_em_projeto"]) == (2, "4500.00", "14000.00")
    (reuniao,) = cliente.get(f"/api/sucesso/grupos/{g}/reunioes", headers=ADMIN).json()
    assert reuniao["estrategia_e_desafios"] == "Abrir a segunda loja"
    anotadas = reuniao["oportunidades"]
    assert [(o["servico"], o["recorrente"], o["situacao"]) for o in anotadas] == [
        ("BPO Financeiro", True, "Enviar proposta"), ("Consultoria", False, "Enviar proposta"), ("Auditoria", False, None)]
    assert anotadas[2]["oportunidade_id"] is None  # sem marcar, só anotada
    with Session(engine) as s:
        bpo = s.get(Oportunidade, anotadas[0]["oportunidade_id"])
        assert (bpo.grupo_id, bpo.nome, bpo.situacao, bpo.tipo_canal, bpo.captador) == (
            g, "Rede Farma", Situacao.ENVIAR_PROPOSTA, TipoCanal.CARTEIRA, "EL")  # Eduardo Luiz → EL
        assert (bpo.preco_mensal, bpo.preco_anual) == (D("4500.00"), None)
        assert bpo.observacao.startswith("Aberta na reunião trimestral de") and "projeção de caixa" in bpo.observacao
        valuation = s.get(Oportunidade, anotadas[1]["oportunidade_id"])
        assert (valuation.servico_tema, valuation.preco_mensal, valuation.preco_anual) == (
            "Valuation, PPA e laudos", None, D("14000.00"))
        valuation.situacao = Situacao.ACEITA  # decidida: sai das abertas
        s.commit()
    f = cliente.get("/api/sucesso/funil", headers=ADMIN).json()
    (grupo,) = f["grupos"]
    assert (grupo["vendas_abertas"], grupo["vendas_por_mes"], grupo["vendas_em_projeto"]) == (1, "4500.00", "0")
    assert cliente.get(f"/api/sucesso/grupos/{g}/reunioes", headers=ADMIN).json()[0]["oportunidades"][1]["situacao"] == "Aceita"


@pytest.mark.parametrize("venda, trecho", [
    ({"lacuna": "Avaliar a empresa", "servico": "Consultoria"}, "escolha o tema"),
    ({"lacuna": "Avaliar a empresa", "servico": "Serviço inventado"}, "fora do catálogo"),
    ({"lacuna": "Algo novo", "servico": "Outro"}, "ao menos 10"),
    ({"lacuna": "Fluxo de caixa", "servico": "BPO Financeiro", "servico_tema": "Valuation, PPA e laudos"}, "tema só vale"),
])
def test_oportunidade_invalida_nao_grava_nada(cliente, ids, venda, trecho):
    r = _registrar(cliente, ids["grupo"], [], oportunidades=[VENDAS[0], venda])
    assert r.status_code == 422 and "Oportunidade 2" in r.json()["detail"] and trecho in r.json()["detail"]
    assert cliente.get(f"/api/sucesso/grupos/{ids['grupo']}/reunioes", headers=ADMIN).json() == []


def test_captador_so_quando_as_iniciais_sao_uma_sigla_conhecida():
    from crm.api.sucesso import _captador

    assert (_captador("Eduardo Luiz"), _captador("Karine N"), _captador("Eduardo"), _captador(None)) == ("EL", None, None, None)
