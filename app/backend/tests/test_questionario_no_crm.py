"""Questionário servido pelo CRM, com link único (amostra aprovada por Eduardo em 11/11/2026).

O cliente envia sem login; cada envio ganha número (Q-1001…) e a chave de quem preencheu (CNPJ + primeiro nome).
A mesma empresa enviando de novo não sobrescreve nada: fica "Precisa de você" para comparar e combinar.
Dados fictícios.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.acesso.catalogo import PUBLICAS, permissoes_da_rota
from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.api.questionarios import ROTA_DO_ENVIO, LimiteDeEnvios
from crm.db.modelos import ConfiguracaoDoSistema, Oportunidade, QuestionarioRecebido
from crm.domain.listas import SituacaoDoQuestionario
from crm.questionario.importacao import chave_do_preenchedor

CNPJ = "11222333000181"


def respostas(**extra):
    base = {
        "razao_social": "Exemplo Beta Ltda", "cnpj": "11.222.333/0001-81", "contato_nome": "Ana Souza",
        "contato_cargo": "Diretora", "contato_celular": "(21) 90000-0000", "contato_email": "ana@beta.com.br",
        "servicos": ["Contábil", "Fiscal"], "como_conheceu": "Indicação de advogado",
        "vol": {"notas_emitidas": "40", "notas_recebidas": "80", "empregados_clt": "18", "cnpjs": "1"},
    }
    base.update(extra)
    return base


def envio(nome="Ana Souza", email="ana@beta.com.br", **resp):
    r = respostas(contato_nome=nome, contato_email=email, **resp)
    return {
        "versao_questionario": "BPO Full 2026 v7", "razao_social": r["razao_social"], "cnpj": CNPJ,
        "nome_fantasia": "Beta", "contato_nome": nome, "contato_cargo": "Diretora",
        "contato_celular": "(21) 90000-0000", "contato_email": email, "respostas": r,
        "avaliacao": {"porte_sugerido": "Pequeno"}, "porte_sugerido": "Pequeno",
        "consentimento_lgpd": True, "consentimento_em": "2026-11-11T12:00:00Z", "pdf_base64": None,
    }


@pytest.fixture
def cliente(engine):
    with TestClient(criar_app(sessionmaker(bind=engine, expire_on_commit=False, future=True))) as c:
        yield c


def _enviar(cliente, corpo):
    r = cliente.post(ROTA_DO_ENVIO, json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["numero"]


class TestChaveENumero:
    def test_chave_e_cnpj_mais_primeiro_nome_sem_acento(self):
        assert chave_do_preenchedor("11.222.333/0001-81", "  Ângela  Maria ") == "11222333000181-ANGELA"
        assert chave_do_preenchedor(CNPJ, "") == "11222333000181-SEMNOME"

    def test_primeiro_envio_e_q1001_e_os_seguintes_em_sequencia(self, cliente):
        assert _enviar(cliente, envio()) == "Q-1001"
        assert _enviar(cliente, envio(nome="Bruno Lima", email="bruno@beta.com.br")) == "Q-1002"


class TestEnvioPublico:
    def test_vira_oportunidade_como_a_busca_fazia(self, cliente, sessao):
        _enviar(cliente, envio())
        q = sessao.scalar(sa.select(QuestionarioRecebido))
        assert q.situacao is SituacaoDoQuestionario.IMPORTADO and q.oportunidade_id is not None
        assert q.chave_do_preenchedor == "11222333000181-ANA" and q.marcado_na_origem_em is not None
        assert sessao.get(Oportunidade, q.oportunidade_id).canal == "Questionário: Indicação de advogado"
        assert q.respostas["consentimento_em"] == "2026-11-11T12:00:00Z"

    def test_sem_consentimento_nao_grava(self, cliente, sessao):
        r = cliente.post(ROTA_DO_ENVIO, json={**envio(), "consentimento_lgpd": False})
        assert r.status_code == 422 and "autorização" in r.json()["detail"]
        assert sessao.scalar(sa.select(sa.func.count(QuestionarioRecebido.id))) == 0

    def test_cnpj_invalido_diz_o_que_conferir(self, cliente):
        r = cliente.post(ROTA_DO_ENVIO, json={**envio(), "cnpj": "123"})
        assert r.status_code == 422 and "Confira os dados" in r.json()["detail"]

    def test_campo_armadilha_ignora_o_robo(self, cliente, sessao):
        r = cliente.post(ROTA_DO_ENVIO, json={**envio(), "site_da_empresa": "http://spam"})
        assert r.status_code == 201 and r.json()["numero"] is None
        assert sessao.scalar(sa.select(sa.func.count(QuestionarioRecebido.id))) == 0

    def test_limite_por_ip(self):
        limite = LimiteDeEnvios(envios=2, janela=600)
        assert limite.permite("1.1.1.1", 0) and limite.permite("1.1.1.1", 1)
        assert not limite.permite("1.1.1.1", 2)
        assert limite.permite("2.2.2.2", 2)  # outro endereço passa
        assert limite.permite("1.1.1.1", 700)  # passou a janela

    def test_envio_grande_demais_e_recusado(self, cliente):
        r = cliente.post(ROTA_DO_ENVIO, json={**envio(), "pdf_base64": "A" * (5 * 1024 * 1024 + 10)})
        assert r.status_code == 413

    def test_rota_e_publica_e_ler_continua_exigindo_login(self, engine):
        assert ROTA_DO_ENVIO in PUBLICAS
        config = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
        fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        with TestClient(criar_app(fabrica, entrada=config, validar_token=lambda t: {})) as c:
            assert c.post(ROTA_DO_ENVIO, json=envio()).status_code == 201
            assert c.get("/api/questionarios").status_code == 401
        assert permissoes_da_rota("GET", "/api/questionarios/7/envios") == ("funil.questionarios",)
        assert permissoes_da_rota("POST", "/api/questionarios/7/combinar") == ("funil.questionarios",)


class TestMaisDeUmEnvio:
    @pytest.fixture
    def dois(self, cliente, sessao):
        _enviar(cliente, envio(nome="Ana Souza", vol={"empregados_clt": "45", "notas_emitidas": "40", "cnpjs": "1"},
                               parcelamento_situacao="Em dia"))
        _enviar(cliente, envio(nome="Bruno Lima", email="bruno@beta.com.br",
                               vol={"empregados_clt": "52", "notas_emitidas": "40", "cnpjs": "1"},
                               servicos=["Contábil", "Fiscal", "Folha / DP"]))
        primeiro, segundo = sessao.scalars(sa.select(QuestionarioRecebido).order_by(QuestionarioRecebido.numero)).all()
        return primeiro, segundo

    def test_o_segundo_nao_cria_nada_e_pede_comparacao(self, cliente, dois):
        primeiro, segundo = dois
        assert segundo.situacao is SituacaoDoQuestionario.PRECISA_DE_VOCE and segundo.oportunidade_id is None
        assert "Q-1001" in segundo.o_que_fez and "compare os envios" in segundo.o_que_fez
        linha = next(x for x in cliente.get("/api/questionarios").json() if x["id"] == segundo.id)
        assert linha["comparar_envios"] is True and linha["numero"] == "Q-1002"

    def test_mesma_pessoa_de_novo_e_avisada(self, cliente, sessao):
        _enviar(cliente, envio())
        _enviar(cliente, envio())
        ultimo = sessao.scalars(sa.select(QuestionarioRecebido).order_by(QuestionarioRecebido.numero.desc())).first()
        assert "Mesma pessoa" in ultimo.o_que_fez

    def test_comparacao_mostra_igual_diferente_e_o_que_so_um_preencheu(self, cliente, dois):
        _, segundo = dois
        c = cliente.get(f"/api/questionarios/{segundo.id}/envios").json()
        assert [e["numero"] for e in c["envios"]] == ["Q-1001", "Q-1002"]
        estado = {x["chave"]: x["estado"] for x in c["campos"]}
        assert estado["vol.empregados_clt"] == "diferente" and estado["servicos"] == "diferente"
        assert estado["vol.notas_emitidas"] == "igual" and estado["parcelamento_situacao"] == "completa"

    def test_combinar_exige_escolher_todos_os_diferentes(self, cliente, dois):
        primeiro, segundo = dois
        r = cliente.post(f"/api/questionarios/{segundo.id}/combinar", json={"escolhas": {"vol.empregados_clt": primeiro.id}})
        assert r.status_code == 409 and "escolha de qual envio vem" in r.json()["detail"]

    def test_combinar_monta_as_respostas_e_segue_o_caminho_de_sempre(self, cliente, sessao, dois):
        primeiro, segundo = dois
        escolhas = {"vol.empregados_clt": primeiro.id, "servicos": segundo.id,
                    "contato_nome": segundo.id, "contato_email": segundo.id}
        r = cliente.post(f"/api/questionarios/{segundo.id}/combinar", json={"escolhas": escolhas})
        assert r.status_code == 200, r.text
        sessao.expire_all()
        q = sessao.get(QuestionarioRecebido, segundo.id)
        assert q.respostas["vol"]["empregados_clt"] == "45"  # veio do Q-1001
        assert q.respostas["servicos"] == ["Contábil", "Fiscal", "Folha / DP"]  # veio do Q-1002
        assert q.respostas["parcelamento_situacao"] == "Em dia"  # só o Q-1001 tinha: completa sozinho
        assert q.combinacao["campos"]["vol.empregados_clt"] == "Q-1001"
        assert q.combinacao["respostas_antes"]["vol"]["empregados_clt"] == "52"  # nada se perde
        # O Q-1001 já tinha virado oportunidade aberta: o combinado vai para a mescla com o card, como sempre.
        assert q.situacao is SituacaoDoQuestionario.PRECISA_DE_VOCE and q.oportunidade_em_aberto_id == primeiro.oportunidade_id
        assert "Combinado" in q.o_que_fez

    def test_ficar_com_o_anterior_descarta_sem_apagar(self, cliente, sessao, dois):
        _, segundo = dois
        r = cliente.post(f"/api/questionarios/{segundo.id}/descartar")
        assert r.status_code == 200 and r.json()["situacao"] == "Descartado"
        assert sessao.get(QuestionarioRecebido, segundo.id) is not None
        # Descartado não conta como envio da empresa: o próximo compara só com o Q-1001.
        _enviar(cliente, envio(nome="Carla Dias", email="carla@beta.com.br"))
        ultimo = sessao.scalars(sa.select(QuestionarioRecebido).order_by(QuestionarioRecebido.numero.desc())).first()
        assert "Q-1001" in ultimo.o_que_fez

    def test_quem_nao_esta_em_comparacao_nao_combina(self, cliente, dois):
        primeiro, _ = dois
        assert cliente.post(f"/api/questionarios/{primeiro.id}/combinar", json={"escolhas": {}}).status_code == 409


class TestTarefas:
    def test_numera_os_antigos_pela_ordem_de_chegada(self, cliente, sessao):
        from crm.manutencao.tarefas import numero_dos_questionarios

        _enviar(cliente, envio())
        _enviar(cliente, envio(nome="Bruno Lima", email="bruno@beta.com.br"))
        sessao.execute(sa.update(QuestionarioRecebido).values(numero=None, chave_do_preenchedor=None))
        sessao.commit()
        assert numero_dos_questionarios.executar(sessao).startswith("2 questionário(s) numerado(s)")
        numeros = sessao.scalars(sa.select(QuestionarioRecebido.numero).order_by(QuestionarioRecebido.recebido_em)).all()
        assert numeros == [1001, 1002]
        assert numero_dos_questionarios.executar(sessao).startswith("0 questionário(s)")  # rodar de novo não muda

    @pytest.mark.parametrize("antes, depois", [
        ("https://criterio-questionario-proposta.netlify.app/questionario?v=7", "https://crmcs.criterioconsultores.com.br/questionario"),
        ("https://outro.exemplo.com.br/q", "https://outro.exemplo.com.br/q"),
    ])
    def test_troca_o_link_so_se_ainda_for_o_do_netlify(self, sessao, antes, depois):
        from crm.manutencao.tarefas import link_do_questionario_no_crm

        sessao.add(ConfiguracaoDoSistema(chave="questionario.link", valor=antes))
        sessao.commit()
        link_do_questionario_no_crm.executar(sessao)
        assert sessao.get(ConfiguracaoDoSistema, "questionario.link").valor == depois
