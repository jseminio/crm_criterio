"""Notas do Granola chegando sozinhas ao CRM (amostra aprovada por Eduardo em 23/10/2026). Dados fictícios.

A nota da pasta das reuniões com o lead vai "A usar" para a oportunidade em aberto do participante; a da pasta das
Reuniões de Resultado, para o grupo. Sem casar, vai para "Precisa de você". Nada se aplica sozinho."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal as D

import httpx2 as httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm import configuracao
from crm.acesso.catalogo import permissoes_da_rota
from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import (
    Contrato, Empresa, GrupoEconomico, Lead, NotaDoGranola, Oportunidade, Perfil, PessoaContato, ReuniaoComLead,
    ReuniaoDeResultado, Usuario, VinculoDeContato,
)
from crm.domain.granola import SituacaoDaNota, TipoDaNota, emails_de_fora, falante, participantes_em_texto
from crm.domain.listas import Situacao, SituacaoContrato, SituacaoGrupo
from crm.granola import cliente as g
from crm.granola.busca import buscar_uma_vez

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}
CHAVE = "grn_chave_de_teste_1234"
HOJE = date.today()
ONTEM = HOJE - timedelta(days=1)
RESUMO = ("## Empresa\nDistribuidora de insumos hospitalares no Rio, com filiais em Niterói.\n"
          "## Dor\nO fechamento sai 20 dias depois do mês; a sócia decide sem o caixa.")
DONO = {"name": "Eduardo Luiz", "email": "eduardo@grupocriterio.com.br"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


class Granola:
    """Um Granola falso: duas pastas e as notas de cada uma, como a API v1."""

    def __init__(self) -> None:
        self.pedidos: list[httpx.Request] = []
        self.pastas = [{"id": "fol_lead", "name": "Potencial Cliente"}, {"id": "fol_res", "name": "Reunião de Resultado"},
                       {"id": "fol_x", "name": "Outras"}]
        self.notas: dict[str, list[dict]] = {"fol_lead": [], "fol_res": []}
        self.inteiras: dict[str, dict] = {}
        self.status = 200
        self.grande_demais: set[str] = set()

    def nota(self, pasta: str, id: str, pessoas: list[dict], *, titulo="Conversa inicial", transcricao=None,
             inicio=f"{ONTEM.isoformat()}T13:00:00Z") -> None:
        self.notas[pasta].append({"id": id, "object": "note", "title": titulo, "owner": DONO,
                                  "created_at": f"{ONTEM.isoformat()}T14:00:00Z", "updated_at": None, "deleted_at": None})
        self.inteiras[id] = {
            "id": id, "title": titulo, "owner": DONO, "created_at": f"{ONTEM.isoformat()}T14:00:00Z",
            "web_url": f"https://notes.granola.ai/d/{id}", "attendees": [DONO, *pessoas],
            "calendar_event": {"scheduled_start_time": inicio, "invitees": [{"email": p["email"]} for p in pessoas]},
            "summary_markdown": RESUMO, "summary_text": "texto", "transcript": transcricao or [],
        }

    def tratar(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if pedido.headers.get("authorization") != f"Bearer {CHAVE}" or self.status == 401:
            return httpx.Response(401, json={"error": "unauthorized"})
        if self.status != 200:
            return httpx.Response(self.status, json={})
        caminho, q = pedido.url.path, pedido.url.params
        if caminho == "/v1/folders":
            if not q.get("cursor"):
                return httpx.Response(200, json={"folders": self.pastas[:2], "hasMore": True, "cursor": "c2"})
            return httpx.Response(200, json={"folders": self.pastas[2:], "hasMore": False, "cursor": None})
        if caminho == "/v1/notes":
            return httpx.Response(200, json={"notes": self.notas.get(q["folder_id"], []), "hasMore": False, "cursor": None})
        if caminho.endswith("/transcript"):
            nota = self.inteiras[caminho.split("/")[3]]
            return httpx.Response(200, json={"transcript": nota["transcript"], "hasMore": False, "cursor": None})
        if caminho.startswith("/v1/notes/"):
            id = caminho.rsplit("/", 1)[-1]
            if q.get("include") == "transcript" and id in self.grande_demais:
                return httpx.Response(413, json={"code": "TRANSCRIPT_TOO_LARGE"})
            nota = dict(self.inteiras[id])
            if q.get("include") != "transcript":
                nota["transcript"] = None
            return httpx.Response(200, json=nota)
        return httpx.Response(404, json={})

    def http(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.tratar))


@pytest.fixture
def fabrica(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=["funil.ver"])
        s.add(comercial)
        alfa = GrupoEconomico(nome="Exemplo Alfa")
        farma = GrupoEconomico(nome="Rede Farma", situacao=SituacaoGrupo.CLIENTE)
        s.add_all([alfa, farma])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", nome="Karine N", perfil_id=comercial.id))
        ea = Empresa(grupo_id=alfa.id, razao_social="Exemplo Alfa Ltda")
        ef = Empresa(grupo_id=farma.id, razao_social="Rede Farma S.A.")
        s.add_all([ea, ef])
        s.flush()
        ana = PessoaContato(nome="Ana Alfa", email="Ana@Alfa.com.br")
        rita = PessoaContato(nome="Rita Farma", email="rita@farma.com.br")
        s.add_all([ana, rita])
        s.flush()
        s.add_all([VinculoDeContato(pessoa_id=ana.id, empresa_id=ea.id), VinculoDeContato(pessoa_id=rita.id, empresa_id=ef.id)])
        o = Oportunidade(grupo_id=alfa.id, nome="Exemplo Alfa", servico="BPO Financeiro", situacao=Situacao.EM_AVALIACAO)
        perdida = Oportunidade(grupo_id=farma.id, nome="Rede Farma", servico="CFO", situacao=Situacao.PERDIDA)
        s.add_all([o, perdida])
        s.add(Contrato(grupo_id=farma.id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("5000")))
        s.commit()
        return {"alfa": alfa.id, "farma": farma.id, "oportunidade": o.id, "empresa_alfa": ea.id}


def _configurar(fabrica, **valores):
    padrao = {"granola.ligado": "true", "granola.chave": CHAVE}
    with fabrica() as s:
        for chave, valor in {**padrao, **valores}.items():
            configuracao.gravar(s, chave, valor, "teste")
        s.commit()
    configuracao.invalidar()


@pytest.fixture
def falso():
    return Granola()


@pytest.fixture
def cliente(fabrica, ids, falso):
    app = criar_app(fabrica, entrada=CONFIG, validar_token=validar, http_do_granola=falso.http)
    with TestClient(app) as c:
        yield c
    configuracao.registrar_fabrica(None)


def _config(**mudar) -> g.ConfiguracaoDoGranola:
    return g.ConfiguracaoDoGranola(**{"chave": CHAVE, "pasta_lead": "Potencial Cliente",
                                      "pasta_resultado": "Reunião de Resultado", "desde": None, **mudar})


ANA = {"name": "Ana Alfa", "email": "ana@alfa.com.br"}
RITA = {"name": "Rita Farma", "email": "rita@farma.com.br"}
ESTRANHO = {"name": "Zé", "email": "ze@desconhecido.com.br"}


# ------------------------------------------------------------------ regras puras

def test_emails_de_fora_tiram_a_casa():
    emails = ["Ana@Alfa.com.br", "eduardo@grupocriterio.com.br", "bruno@grupocriterio.com.br", "karine@outra.com.br",
              "sem-arroba", ""]
    assert emails_de_fora(emails, "eduardo@grupocriterio.com.br", ["karine@outra.com.br"]) == {"ana@alfa.com.br"}


def test_participantes_em_texto_e_falante():
    assert participantes_em_texto([("Ana", "ana@x.com"), (None, "b@y.com"), ("Só nome", None)]) == (
        "Ana <ana@x.com>, b@y.com, Só nome")
    assert len(participantes_em_texto([("A" * 200, "a@x.com"), ("B" * 200, "b@x.com")])) == 300
    assert falante({"speaker": {"name": "Rita"}}, "Eduardo") == "Rita"
    assert falante({"speaker": {"source": "microphone"}}, "Eduardo") == "Eduardo"
    assert falante({"speaker": {"source": "speaker", "attribution": "them"}}, "Eduardo") == "Participante"


# ------------------------------------------------------------------ o cliente da API

def test_cliente_pagina_as_pastas_e_le_a_nota(falso):
    falso.nota("fol_res", "not_1", [RITA], transcricao=[
        {"speaker": {"source": "microphone"}, "text": "Bom dia, Rita."},
        {"speaker": {"source": "speaker", "name": "Rita"}, "text": "Bom dia."}, {"speaker": {}, "text": " "}])
    with falso.http() as http:
        pastas = g.listar_pastas(http, _config())
        assert [p.nome for p in pastas] == ["Potencial Cliente", "Reunião de Resultado", "Outras"]
        assert g.achar_pasta(pastas, "  reunião de  RESULTADO ").id == "fol_res"
        nota = g.ler_nota(http, _config(), "not_1", com_transcricao=True)
    assert nota.transcricao == "Eduardo Luiz: Bom dia, Rita.\nRita: Bom dia."
    assert nota.data == ONTEM and nota.link == "https://notes.granola.ai/d/not_1"
    assert [e for _, e in nota.pessoas] == ["eduardo@grupocriterio.com.br", "rita@farma.com.br"]  # sem repetir
    assert falso.pedidos[0].headers["authorization"] == f"Bearer {CHAVE}"


def test_transcricao_grande_vem_em_paginas(falso):
    falso.nota("fol_res", "not_g", [RITA], transcricao=[{"speaker": {"name": "Rita"}, "text": "Longa."}])
    falso.grande_demais.add("not_g")
    with falso.http() as http:
        nota = g.ler_nota(http, _config(), "not_g", com_transcricao=True)
    assert nota.transcricao == "Rita: Longa."
    assert any(p.url.path.endswith("/not_g/transcript") for p in falso.pedidos)


def test_nota_de_lead_nao_pede_a_transcricao(falso):
    falso.nota("fol_lead", "not_l", [ANA])
    with falso.http() as http:
        nota = g.ler_nota(http, _config(), "not_l", com_transcricao=False)
    assert nota.transcricao is None
    assert all(p.url.params.get("include") is None for p in falso.pedidos)


@pytest.mark.parametrize(("status", "trecho"), [(401, "recusou a chave"), (500, "HTTP 500"), (429, "esperar")])
def test_falhas_viram_frase_sem_a_chave(falso, status, trecho):
    falso.status = status
    with falso.http() as http, pytest.raises(g.FalhaNoGranola) as falha:
        g.listar_pastas(http, _config(), esperar=lambda s: None)
    assert trecho in str(falha.value) and CHAVE not in str(falha.value)


def test_conferir_avisa_a_pasta_que_falta(falso):
    with falso.http() as http:
        assert g.conferir(http, _config()) == "Conectado ao Granola. A chave enxerga 3 pastas."
        with pytest.raises(g.FalhaNoGranola, match="'Clientes'"):
            g.conferir(http, _config(pasta_resultado="Clientes"))


# ------------------------------------------------------------------ a busca

def test_busca_casa_lead_e_resultado_e_manda_o_resto_para_voce(engine, ids, falso):
    falso.nota("fol_lead", "not_a", [ANA])                       # contato da Alfa, que tem oportunidade em aberto
    falso.nota("fol_lead", "not_z", [ESTRANHO])                  # ninguém conhecido
    falso.nota("fol_lead", "not_r", [RITA])                      # contato da Farma, sem oportunidade em aberto
    falso.nota("fol_res", "not_f", [RITA], transcricao=[{"speaker": {"name": "Rita"}, "text": "Vendemos mais."}])
    falso.nota("fol_res", "not_d", [ANA, RITA])                  # dois grupos
    with Session(engine) as s, falso.http() as http:
        r = buscar_uma_vez(s, http, _config(), HOJE)
        s.commit()
        assert (r.lidas, r.novas, r.a_usar, r.precisam, r.aviso) == (5, 5, 2, 3, None)
        notas = {n.granola_id: n for n in s.scalars(sa.select(NotaDoGranola))}
    a, z, rr, f, d = (notas[k] for k in ("not_a", "not_z", "not_r", "not_f", "not_d"))
    assert (a.situacao, a.oportunidade_id, a.tipo, a.transcricao) == (
        SituacaoDaNota.A_USAR, ids["oportunidade"], TipoDaNota.LEAD, None)
    assert a.resumo == RESUMO and a.participantes == "Eduardo Luiz <eduardo@grupocriterio.com.br>, Ana Alfa <ana@alfa.com.br>"
    assert (z.situacao, z.motivo) == (SituacaoDaNota.PRECISA_DE_VOCE, "Nenhum participante é contato do CRM.")
    assert rr.motivo == "O contato não tem oportunidade em aberto."
    assert (f.situacao, f.grupo_id, f.transcricao) == (SituacaoDaNota.A_USAR, ids["farma"], "Rita: Vendemos mais.")
    assert d.motivo == "Os participantes são de 2 grupos."


def test_busca_nao_traz_a_mesma_nota_duas_vezes_e_respeita_a_data(engine, ids, falso):
    falso.nota("fol_lead", "not_a", [ANA])
    with Session(engine) as s, falso.http() as http:
        buscar_uma_vez(s, http, _config(desde=date(2026, 10, 1)), HOJE)
        s.commit()
        r = buscar_uma_vez(s, http, _config(desde=date(2026, 10, 1)), HOJE)
    assert (r.lidas, r.novas) == (1, 0)
    listas = [p for p in falso.pedidos if p.url.path == "/v1/notes"]
    assert listas[0].url.params["created_after"] == "2026-10-01" and listas[0].url.params["folder_id"] == "fol_lead"
    assert sum(1 for p in falso.pedidos if p.url.path == "/v1/notes/not_a") == 1


def test_lead_casa_pelo_email_do_lead(engine, ids, falso):
    with Session(engine) as s:
        s.add(Lead(nome="Carlos", email="Carlos@Novo.com.br", convertido_em_id=ids["oportunidade"]))
        s.commit()
    falso.nota("fol_lead", "not_c", [{"name": "Carlos", "email": "carlos@novo.com.br"}])
    with Session(engine) as s, falso.http() as http:
        buscar_uma_vez(s, http, _config(), HOJE)
        nota = s.scalar(sa.select(NotaDoGranola))
    assert nota.oportunidade_id == ids["oportunidade"]


def test_pasta_que_falta_vira_aviso_e_a_outra_entra(engine, ids, falso):
    falso.nota("fol_lead", "not_a", [ANA])
    with Session(engine) as s, falso.http() as http:
        r = buscar_uma_vez(s, http, _config(pasta_resultado="Clientes"), HOJE)
    assert r.novas == 1 and "'Clientes'" in r.aviso


# ------------------------------------------------------------------ a tela

def test_desligada_nao_busca(cliente, fabrica, falso):
    _configurar(fabrica, **{"granola.ligado": "false"})
    assert cliente.get("/api/granola", headers=ADMIN).json()["ligada"] is False
    assert cliente.post("/api/granola/buscar", headers=ADMIN).status_code == 409
    assert falso.pedidos == []


def test_buscar_agora_e_a_fila_precisa_de_voce(cliente, fabrica, falso, ids, engine):
    _configurar(fabrica)
    falso.nota("fol_lead", "not_z", [ESTRANHO])
    falso.nota("fol_res", "not_d", [ANA, RITA])
    r = cliente.post("/api/granola/buscar", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert (r.json()["novas"], r.json()["precisam"]) == (2, 2)
    s = cliente.get("/api/granola", headers=ADMIN).json()
    assert s["ligada"] is True and s["ultima"]["novas"] == 2
    assert [n["titulo"] for n in s["precisam"]] == ["Conversa inicial", "Conversa inicial"]
    assert [o["nome"] for o in s["oportunidades"]] == ["Exemplo Alfa · BPO Financeiro"]  # só as em aberto
    assert [x["nome"] for x in s["grupos"]] == ["Rede Farma"]  # só clientes
    lead = next(n for n in s["precisam"] if n["tipo"] == "Reunião com o lead")
    res = next(n for n in s["precisam"] if n["tipo"] == "Reunião de Resultado")
    assert cliente.post(f"/api/granola/notas/{lead['id']}/destino", headers=ADMIN, json={}).status_code == 422
    depois = cliente.post(f"/api/granola/notas/{lead['id']}/destino", headers=ADMIN,
                          json={"oportunidade_id": ids["oportunidade"]}).json()
    assert [n["id"] for n in depois["precisam"]] == [res["id"]]
    chegou = cliente.get(f"/api/oportunidades/{ids['oportunidade']}/granola", headers=ADMIN).json()
    assert [(n["id"], n["resumo"], n["transcricao"]) for n in chegou] == [(lead["id"], RESUMO, None)]
    vazio = cliente.post(f"/api/granola/notas/{res['id']}/descartar", headers=ADMIN).json()
    assert vazio["precisam"] == []
    with Session(engine) as ss:
        n = ss.get(NotaDoGranola, res["id"])
        assert (n.situacao, n.resumo, n.transcricao, n.participantes) == (SituacaoDaNota.DESCARTADA, None, None, None)
        assert n.resolvida_por
    # descartada não volta na próxima busca
    assert cliente.post("/api/granola/buscar", headers=ADMIN).json()["novas"] == 0


def test_pastas_para_escolher(cliente, fabrica):
    assert cliente.get("/api/granola/pastas", headers=ADMIN).status_code == 409  # sem chave
    _configurar(fabrica, **{"granola.ligado": "false"})  # não precisa estar ligada
    assert cliente.get("/api/granola/pastas", headers=ADMIN).json() == ["Outras", "Potencial Cliente", "Reunião de Resultado"]


def test_testar_conexao_pela_tela(cliente, fabrica, falso):
    r = cliente.post("/api/configuracoes/integracoes/granola/testar", headers=ADMIN).json()
    assert (r["ok"], r["mensagem"]) == (False, "Salve a chave da API do Granola.")
    _configurar(fabrica, **{"granola.ligado": "false"})
    r = cliente.post("/api/configuracoes/integracoes/granola/testar", headers=ADMIN).json()
    assert r["ok"] is True and "3 pastas" in r["mensagem"]
    falso.status = 401
    r = cliente.post("/api/configuracoes/integracoes/granola/testar", headers=ADMIN).json()
    assert r["ok"] is False and "recusou a chave" in r["mensagem"]


def test_tela_mostra_o_grupo_e_valida_a_data(cliente):
    grupos = {x["chave"]: x for x in cliente.get("/api/configuracoes/integracoes", headers=ADMIN).json()["grupos"]}
    granola = grupos["granola"]
    assert granola["configurado"] is False and granola["testavel"] is True
    campos = {c["chave"]: c for c in granola["campos"]}
    assert campos["granola.pasta_lead"]["padrao"] == "Potencial Cliente" and campos["granola.chave"]["segredo"] is True
    ruim = cliente.put("/api/configuracoes/integracoes/granola", headers=ADMIN, json={"valores": {"granola.desde": "2026-10-01"}})
    assert ruim.status_code == 422 and "01/10/2026" in ruim.text
    ok = cliente.put("/api/configuracoes/integracoes/granola", headers=ADMIN, json={"valores": {
        "granola.ligado": "true", "granola.chave": CHAVE, "granola.desde": "01/10/2026"}})
    assert ok.status_code == 200, ok.text
    granola = next(x for x in ok.json()["grupos"] if x["chave"] == "granola")
    assert granola["configurado"] is True
    assert next(c for c in granola["campos"] if c["chave"] == "granola.chave")["final"] == "1234"


# ------------------------------------------------------------------ usar a nota

def _buscar(cliente, fabrica, falso, *notas):
    _configurar(fabrica)
    for pasta, id, pessoas, extra in notas:
        falso.nota(pasta, id, pessoas, **extra)
    assert cliente.post("/api/granola/buscar", headers=ADMIN).status_code == 200


def test_reuniao_com_lead_guardada_com_a_nota_marca_usada(cliente, fabrica, falso, ids, engine):
    _buscar(cliente, fabrica, falso, ("fol_lead", "not_a", [ANA], {}))
    oid = ids["oportunidade"]
    (nota,) = cliente.get(f"/api/oportunidades/{oid}/granola", headers=ADMIN).json()
    corpo = {"data": ONTEM.isoformat(), "participantes": nota["participantes"], "link_do_granola": nota["link"],
             "resumo": nota["resumo"], "ciencia_da_gravacao": True, "nota_do_granola_id": nota["id"]}
    outra = cliente.post(f"/api/oportunidades/{oid + 99}/proposta/reuniao-com-lead", headers=ADMIN, json=corpo)
    assert outra.status_code in (404, 422)
    r = cliente.post(f"/api/oportunidades/{oid}/proposta/reuniao-com-lead", headers=ADMIN, json=corpo)
    assert r.status_code == 201, r.text
    assert cliente.get(f"/api/oportunidades/{oid}/granola", headers=ADMIN).json() == []
    with Session(engine) as s:
        assert s.scalar(sa.select(NotaDoGranola.situacao)) is SituacaoDaNota.USADA
        assert s.scalar(sa.select(sa.func.count(ReuniaoComLead.id))) == 1
    # a mesma nota não serve duas vezes
    assert cliente.post(f"/api/oportunidades/{oid}/proposta/reuniao-com-lead", headers=ADMIN, json=corpo).status_code == 422


def test_reuniao_de_resultado_com_a_nota_marca_usada(cliente, fabrica, falso, ids, engine):
    _buscar(cliente, fabrica, falso, ("fol_res", "not_f", [RITA], {"transcricao": [
        {"speaker": {"name": "Rita"}, "text": "Vendemos mais."}]}))
    gid = ids["farma"]
    (nota,) = cliente.get(f"/api/sucesso/grupos/{gid}/granola", headers=ADMIN).json()
    assert nota["transcricao"] == "Rita: Vendemos mais."
    r = cliente.post(f"/api/sucesso/grupos/{gid}/reunioes", headers=ADMIN, json={
        "tipo": "trimestral", "data": ONTEM.isoformat(), "transcricao": nota["transcricao"],
        "nota_do_granola_id": nota["id"]})
    assert r.status_code == 201, r.text
    with Session(engine) as s:
        assert s.scalar(sa.select(NotaDoGranola.situacao)) is SituacaoDaNota.USADA
        assert s.scalar(sa.select(ReuniaoDeResultado.transcricao)) == "Rita: Vendemos mais."
    assert cliente.get(f"/api/sucesso/grupos/{gid}/granola", headers=ADMIN).json() == []


def test_descartar_na_oportunidade_e_no_grupo(cliente, fabrica, falso, ids):
    _buscar(cliente, fabrica, falso, ("fol_lead", "not_a", [ANA], {}), ("fol_res", "not_f", [RITA], {}))
    oid, gid = ids["oportunidade"], ids["farma"]
    (lead,) = cliente.get(f"/api/oportunidades/{oid}/granola", headers=ADMIN).json()
    (res,) = cliente.get(f"/api/sucesso/grupos/{gid}/granola", headers=ADMIN).json()
    assert cliente.post(f"/api/oportunidades/{oid}/granola/{res['id']}/descartar", headers=ADMIN).status_code == 409
    assert cliente.post(f"/api/oportunidades/{oid}/granola/{lead['id']}/descartar", headers=ADMIN).json() == []
    assert cliente.post(f"/api/sucesso/grupos/{gid}/granola/{res['id']}/descartar", headers=ADMIN).json() == []


# ------------------------------------------------------------------ acesso

def test_rotas_tem_dono():
    assert permissoes_da_rota("GET", "/api/granola") == ("configuracoes.integracoes",)
    assert permissoes_da_rota("POST", "/api/granola/buscar") == ("configuracoes.integracoes",)
    assert permissoes_da_rota("POST", "/api/granola/notas/3/destino") == ("configuracoes.integracoes",)
    assert permissoes_da_rota("GET", "/api/oportunidades/3/granola") == ("funil.proposta",)
    assert permissoes_da_rota("POST", "/api/sucesso/grupos/3/granola/4/descartar") == ("sucesso.editar",)
    assert permissoes_da_rota("POST", "/api/configuracoes/integracoes/google_ads/testar") == ("configuracoes.integracoes",)


def test_comercial_sem_permissao_nao_ve_a_fila_nem_a_nota(cliente, ids):
    assert cliente.get("/api/granola", headers=KARINE).status_code == 403
    assert cliente.get(f"/api/oportunidades/{ids['oportunidade']}/granola", headers=KARINE).status_code == 403
