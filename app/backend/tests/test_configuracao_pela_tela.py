"""Configuração pela tela (07/10/2026): cifra, precedência sobre o ambiente, cópia pelo atualizador e rotas."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm import configuracao
from crm.agente.config import ler_configuracao
from crm.api.app import criar_app
from crm.api.integracoes import Falhou
from crm.api.integracoes import Testadores as Testes
from crm.configuracao import cofre
from crm.db.modelos import ConfiguracaoDoSistema
from crm.manutencao.tarefas import configuracao_para_a_tela

SEGREDO = "sk-ant-segredo-de-teste-1234"


@pytest.fixture
def fabrica(engine):
    f = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    configuracao.registrar_fabrica(f)
    yield f
    configuracao.registrar_fabrica(None)


class TestCofre:
    def test_cifra_e_decifra(self):
        cifrado = cofre.cifrar(SEGREDO)
        assert SEGREDO not in cifrado and cofre.decifrar(cifrado) == SEGREDO

    def test_outro_segredo_de_sessao_nao_le(self, monkeypatch):
        monkeypatch.setenv("CRM_SEGREDO_SESSAO", "a" * 64)
        cifrado = cofre.cifrar(SEGREDO)
        monkeypatch.setenv("CRM_SEGREDO_SESSAO", "b" * 64)
        with pytest.raises(cofre.SegredoIlegivel):
            cofre.decifrar(cifrado)


class TestPrecedencia:
    def test_sem_tela_vale_o_ambiente_e_depois_o_padrao(self, fabrica, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "do-ambiente")
        assert ler_configuracao().chave == "do-ambiente"
        assert configuracao.valor("whatsapp.versao") == "v24.0"

    def test_a_tela_vence_o_ambiente_sem_reiniciar(self, fabrica, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "do-ambiente")
        monkeypatch.setenv("CRM_LINK_DO_QUESTIONARIO", "https://antigo.exemplo.com")
        with fabrica() as s:
            configuracao.gravar(s, "anthropic.chave", "da-tela", "Eduardo")
            configuracao.gravar(s, "questionario.link", "https://questionario.criterio.com.br", "Eduardo")
            s.commit()
        config = ler_configuracao()
        assert config.chave == "da-tela" and config.link_do_questionario == "https://questionario.criterio.com.br"
        with fabrica() as s:
            configuracao.gravar(s, "anthropic.chave", None, "Eduardo")  # tirar da tela: volta o ambiente
            s.commit()
        assert ler_configuracao().chave == "do-ambiente"

    def test_segredo_vai_cifrado_para_o_banco(self, fabrica):
        with fabrica() as s:
            configuracao.gravar(s, "whatsapp.token", SEGREDO, "Eduardo")
            s.commit()
            linha = s.get(ConfiguracaoDoSistema, "whatsapp.token")
            assert linha.cifrado and SEGREDO not in linha.valor


class TestAtualizador:
    def test_copia_o_ambiente_uma_vez_sem_sobrescrever_a_tela(self, fabrica, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", SEGREDO)
        monkeypatch.setenv("CRM_AGENTE_MODELO", "claude-sonnet-5")
        monkeypatch.setenv("CRM_WHATSAPP_NUMERO_ID", "5555")
        with fabrica() as s:
            configuracao.gravar(s, "whatsapp.numero_id", "1111", "Eduardo")  # já está na tela
            s.commit()
            resultado = configuracao_para_a_tela.executar(s)
            s.commit()
            assert resultado.startswith("2 campo(s) copiado(s)")
            linhas = configuracao.linhas(s)
        assert linhas["anthropic.chave"].origem == "tela" and linhas["anthropic.chave"].final == "1234"
        assert linhas["anthropic.modelo"].valor == "claude-sonnet-5"
        assert linhas["whatsapp.numero_id"].valor == "1111"  # a tela não foi sobrescrita
        assert linhas["anthropic.chave"].alterado_por == configuracao_para_a_tela.QUEM


class FalsoTeste:
    def __init__(self):
        self.envios: list[tuple[str, str]] = []

    def testadores(self) -> Testes:
        def ia(config):
            if config.chave != SEGREDO:
                raise Falhou("A Anthropic recusou a chave da API.")
            return "A Anthropic respondeu."

        def enviar(config, para):
            self.envios.append(("whatsapp", para))
            return "enviado"

        return Testes(ia=ia, whatsapp=lambda c: "ok", email=lambda c: "ok", enviar={"whatsapp": enviar})


@pytest.fixture
def falso():
    return FalsoTeste()


@pytest.fixture
def cliente(engine, falso, monkeypatch):
    monkeypatch.setenv("CRM_WHATSAPP_NUMERO_ID", "999888")
    f = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(f, testadores=falso.testadores())) as c:
        yield c


def _grupo(resposta: dict, chave: str) -> dict:
    return next(g for g in resposta["grupos"] if g["chave"] == chave)


def _campo(grupo: dict, chave: str) -> dict:
    return next(c for c in grupo["campos"] if c["chave"] == chave)


class TestRotas:
    def test_mostra_a_origem_e_nunca_o_segredo(self, cliente):
        r = cliente.put("/api/configuracoes/integracoes/ia", json={"valores": {"anthropic.chave": SEGREDO}})
        assert r.status_code == 200, r.text
        assert SEGREDO not in r.text
        tudo = cliente.get("/api/configuracoes/integracoes")
        assert SEGREDO not in tudo.text
        chave = _campo(_grupo(tudo.json(), "ia"), "anthropic.chave")
        assert (chave["origem"], chave["valor"], chave["final"]) == ("tela", None, "1234")
        numero = _campo(_grupo(tudo.json(), "whatsapp"), "whatsapp.numero_id")
        assert (numero["origem"], numero["valor"]) == ("servidor", "999888")
        assert _campo(_grupo(tudo.json(), "whatsapp"), "whatsapp.versao")["origem"] == "padrão"
        assert _grupo(tudo.json(), "ia")["alterado_por"] == "tela de Integrações"

    def test_segredo_vazio_mantem_e_apagar_tira(self, cliente):
        cliente.put("/api/configuracoes/integracoes/ia", json={"valores": {"anthropic.chave": SEGREDO}})
        r = cliente.put("/api/configuracoes/integracoes/ia",
                        json={"valores": {"anthropic.chave": "", "anthropic.modelo": "claude-sonnet-5"}})
        ia = _grupo(r.json(), "ia")
        assert _campo(ia, "anthropic.chave")["final"] == "1234"
        assert _campo(ia, "anthropic.modelo")["valor"] == "claude-sonnet-5"
        r = cliente.put("/api/configuracoes/integracoes/ia", json={"apagar": ["anthropic.chave"]})
        assert _campo(_grupo(r.json(), "ia"), "anthropic.chave")["origem"] == "vazio"

    @pytest.mark.parametrize("grupo, valores, trecho", [
        ("whatsapp", {"whatsapp.versao": "24"}, "v24.0"),
        ("questionario", {"questionario.link": "http://inseguro"}, "https://"),
        ("disparo", {"disparo.ligado": "talvez"}, "true ou false"),
        ("ia", {"whatsapp.token": "x"}, "não é desta integração"),
    ])
    def test_valida_antes_de_gravar(self, cliente, grupo, valores, trecho):
        r = cliente.put(f"/api/configuracoes/integracoes/{grupo}", json={"valores": valores})
        assert r.status_code == 422 and trecho in r.json()["detail"]

    def test_testar_usa_o_que_acabou_de_ser_salvo(self, cliente):
        r = cliente.post("/api/configuracoes/integracoes/ia/testar").json()
        assert r["ok"] is False and "recusou" in r["mensagem"]
        cliente.put("/api/configuracoes/integracoes/ia", json={"valores": {"anthropic.chave": SEGREDO}})
        r = cliente.post("/api/configuracoes/integracoes/ia/testar").json()
        assert r["ok"] is True and r["mensagem"] == "A Anthropic respondeu."

    def test_enviar_teste_so_para_quem_foi_digitado(self, cliente, falso):
        r = cliente.post("/api/configuracoes/integracoes/whatsapp/enviar-teste", json={"para": "21 99999-0000"})
        assert r.status_code == 200 and r.json()["ok"]
        assert falso.envios == [("whatsapp", "21 99999-0000")]
        assert cliente.post("/api/configuracoes/integracoes/ia/enviar-teste", json={"para": "x@y.com"}).status_code == 409

    def test_disparo_nao_tem_teste_e_grupo_desconhecido_e_404(self, cliente):
        assert cliente.post("/api/configuracoes/integracoes/disparo/testar").status_code == 409
        assert cliente.put("/api/configuracoes/integracoes/xyz", json={}).status_code == 404

    def test_ligar_o_disparo_pela_tela(self, cliente):
        cliente.put("/api/configuracoes/integracoes/disparo", json={"valores": {"disparo.ligado": "true"}})
        assert ler_configuracao().disparo_ligado is True
