"""Mesclar o questionário com uma oportunidade já aberta (amostra aprovada por Eduardo em 15/10/2026): o card aberto
a partir do lead, sem CNPJ, recebe o questionário em vez de ganhar uma duplicada (o caso da Mainô). Dados fictícios."""

from __future__ import annotations

import sqlalchemy as sa
import pytest
from sqlalchemy.orm import Session

from crm.db.modelos import (
    Empresa, FusaoDeGrupos, GrupoEconomico, Lead, Oportunidade, PessoaContato, QuestionarioRecebido, RegistroDeAlteracao,
    VinculoDeContato,
)
from crm.domain.listas import MotivoRecusa, Situacao, SituacaoGrupo, Temperatura

from test_questionario import CNPJ_ALFA, _buscar, cliente, fonte, linha  # noqa: F401  (fixtures do mesmo molde)


def _card(sessao: Session, nome="Exemplo Alfa", **kw) -> Oportunidade:
    """O card que o vendedor abriu a partir do lead: grupo sem empresa, sem CNPJ, com preço e captador."""
    g = GrupoEconomico(nome=nome, situacao=SituacaoGrupo.PROSPECT)
    sessao.add(g)
    sessao.flush()
    o = Oportunidade(grupo_id=g.id, nome=f"{nome} · BPO Financeiro", servico="BPO Financeiro", situacao=Situacao.ENVIAR_PROPOSTA,
                     captador="EL", temperatura=Temperatura.QUENTE, preco_mensal=6000, contas_bancarias=4, **kw)
    sessao.add(o)
    sessao.commit()
    return o


def _contato_no_card(sessao: Session, card: Oportunidade, email="ana@exemplo.com.br"):
    e = Empresa(grupo_id=card.grupo_id, razao_social=f"{card.nome} (sem CNPJ)")
    sessao.add(e)
    sessao.flush()
    sessao.add(PessoaContato(nome="Ana Souza", email=email, vinculos=[VinculoDeContato(empresa_id=e.id)]))
    sessao.commit()


class TestOCasoDaMaino:
    """O card sem CNPJ e o questionário de outro contato: o CRM cria tudo, e a mescla desfaz a duplicação."""

    def test_sugere_o_card_mostra_a_previa_e_mescla(self, cliente, sessao):
        card = _card(sessao)
        q = _buscar(cliente)["novos"][0]
        assert q["cliente_novo"] is True and q["oportunidade_id"] not in (None, card.id)
        duplicada_id = q["oportunidade_id"]

        sugestoes = cliente.get(f"/api/questionarios/{q['id']}/sugestoes").json()
        assert [(s["oportunidade_id"], s["motivo"]) for s in sugestoes] == [(card.id, "nome parecido")]

        p = cliente.get(f"/api/questionarios/{q['id']}/mescla", params={"oportunidade_id": card.id}).json()
        assert p["recusa"] is None and (p["fusao_de"], p["fusao_em"]) == ("Exemplo Alfa", "Exemplo Alfa")
        assert p["duplicada_id"] == duplicada_id and p["duplicada_intocada"] is True and p["duplicada_recusa"] is None
        campos = {c["campo"]: c for c in p["campos"]}
        assert campos["empresa_id"]["acao"] == "preenche"
        assert campos["documentos_fiscais_mes"]["acao"] == "preenche"
        assert (campos["contas_bancarias"]["acao"], campos["contas_bancarias"]["no_card"]) == ("diferente", "4")

        r = cliente.post(f"/api/questionarios/{q['id']}/mesclar",
                         json={"oportunidade_id": card.id, "excluir_duplicada": True})
        assert r.status_code == 200, r.text
        assert r.json()["oportunidade_id"] == card.id and r.json()["situacao"] == "Importado"
        sessao.expire_all()
        o = sessao.get(Oportunidade, card.id)
        assert o.empresa.cnpj == CNPJ_ALFA and o.documentos_fiscais_mes == 120 and o.complexidade == 2
        assert (o.contas_bancarias, o.preco_mensal, o.captador, o.temperatura) == (4, 6000, "EL", Temperatura.QUENTE)
        assert o.origem_da_volumetria["documentos_fiscais_mes"] == "Questionário"
        assert sessao.get(Oportunidade, duplicada_id) is None
        assert sessao.scalar(sa.select(RegistroDeAlteracao.depois).where(RegistroDeAlteracao.acao == "excluiu")).startswith("Duplicada")
        fusao = sessao.scalars(sa.select(FusaoDeGrupos)).one()
        assert fusao.principal_id == card.grupo_id  # o grupo do card fica; o do questionário é fundido (desfazível)
        assert sessao.get(QuestionarioRecebido, q["id"]).grupo_id == card.grupo_id
        assert "Mesclado em" in r.json()["o_que_fez"] and "duplicada" in r.json()["o_que_fez"]

    def test_usar_do_questionario_troca_so_o_que_a_pessoa_pediu(self, cliente, sessao):
        card = _card(sessao)
        q = _buscar(cliente)["novos"][0]
        r = cliente.post(f"/api/questionarios/{q['id']}/mesclar", json={
            "oportunidade_id": card.id, "usar_do_questionario": ["contas_bancarias"], "excluir_duplicada": True})
        assert r.status_code == 200
        sessao.expire_all()
        assert sessao.get(Oportunidade, card.id).contas_bancarias == 2
        recusa = cliente.post(f"/api/questionarios/{q['id']}/mesclar", json={
            "oportunidade_id": _card(sessao, "Outro").id, "usar_do_questionario": ["preco_mensal"]})
        assert recusa.status_code == 409 and "Só volumetria e notas" in recusa.json()["detail"]

    def test_duplicada_mexida_nao_e_marcada_e_fica_se_nao_pedir(self, cliente, sessao):
        card = _card(sessao)
        q = _buscar(cliente)["novos"][0]
        dup = sessao.get(Oportunidade, q["oportunidade_id"])
        dup.preco_mensal = 3000
        sessao.commit()
        p = cliente.get(f"/api/questionarios/{q['id']}/mescla", params={"oportunidade_id": card.id}).json()
        assert p["duplicada_intocada"] is False
        assert cliente.post(f"/api/questionarios/{q['id']}/mesclar", json={"oportunidade_id": card.id}).status_code == 200
        sessao.expire_all()
        assert sessao.get(Oportunidade, dup.id).grupo_id == card.grupo_id  # veio junto na fusão, para a pessoa decidir


class TestRegraD:
    """Achou o card pelo contato: o CRM não cria nada e pergunta."""

    def test_mesmo_email_do_contato_nao_cria_e_pergunta(self, cliente, sessao):
        card = _card(sessao, "Nome Bem Diferente")
        _contato_no_card(sessao, card)
        q = _buscar(cliente)["novos"][0]
        assert q["situacao"] == "Precisa de você" and q["oportunidade_em_aberto_id"] == card.id
        assert q["oportunidade_id"] is None and "mesmo e-mail do contato" in q["o_que_fez"]
        assert sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade)) == 1
        assert sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == CNPJ_ALFA)) is None

    def test_mesclar_cadastra_o_cnpj_no_grupo_do_card_sem_fundir(self, cliente, sessao):
        card = _card(sessao, "Nome Bem Diferente")
        _contato_no_card(sessao, card)
        q = _buscar(cliente)["novos"][0]
        r = cliente.post(f"/api/questionarios/{q['id']}/resolver", json={"acao": "anexar"})
        assert r.status_code == 200
        sessao.expire_all()
        empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == CNPJ_ALFA))
        assert empresa.grupo_id == card.grupo_id and sessao.get(Oportunidade, card.id).empresa_id == empresa.id
        assert sessao.scalar(sa.select(sa.func.count()).select_from(FusaoDeGrupos)) == 0

    def test_criar_nova_cria_o_cliente_que_a_regra_d_segurou(self, cliente, sessao):
        card = _card(sessao, "Nome Bem Diferente")
        _contato_no_card(sessao, card)
        q = _buscar(cliente)["novos"][0]
        r = cliente.post(f"/api/questionarios/{q['id']}/resolver", json={"acao": "criar"}).json()
        assert r["cliente_novo"] is True and r["oportunidade_id"] not in (None, card.id) and r["situacao"] == "Importado"

    def test_lead_convertido_tambem_segura(self, cliente, sessao):
        card = _card(sessao, "Nome Bem Diferente")
        sessao.add(Lead(nome="Ana", telefone="+55 21 90000-0000", convertido_em_id=card.id))
        sessao.commit()
        q = _buscar(cliente)["novos"][0]
        assert q["oportunidade_em_aberto_id"] == card.id and "lead convertido" in q["o_que_fez"]

    def test_card_de_outro_cnpj_nao_segura(self, cliente, sessao):
        """A mesma pessoa (um contador) respondendo por outra empresa: o card já tem outro CNPJ."""
        card = _card(sessao, "Nome Bem Diferente")
        e = Empresa(grupo_id=card.grupo_id, razao_social="Outra Ltda", cnpj="99888777000166")
        sessao.add(e)
        sessao.flush()
        card.empresa_id = e.id
        sessao.add(PessoaContato(nome="Ana", email="ana@exemplo.com.br", vinculos=[VinculoDeContato(empresa_id=e.id)]))
        sessao.commit()
        assert _buscar(cliente)["novos"][0]["cliente_novo"] is True


class TestRecusas:
    def test_cnpj_de_outro_grupo_que_ja_existia(self, cliente, sessao):
        g = GrupoEconomico(nome="Dono do CNPJ", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(g)
        sessao.flush()
        sessao.add(Empresa(grupo_id=g.id, razao_social="Exemplo Alfa", cnpj=CNPJ_ALFA))
        sessao.commit()
        q = _buscar(cliente)["novos"][0]
        card = _card(sessao, "Outro Card")
        r = cliente.post(f"/api/questionarios/{q['id']}/mesclar", json={"oportunidade_id": card.id})
        assert r.status_code == 409 and "funda os grupos" in r.json()["detail"]

    def test_destino_fechado_ou_o_mesmo(self, cliente, sessao):
        q = _buscar(cliente)["novos"][0]
        mesmo = cliente.post(f"/api/questionarios/{q['id']}/mesclar", json={"oportunidade_id": q["oportunidade_id"]})
        assert mesmo.status_code == 409 and "já está nesta" in mesmo.json()["detail"]
        fechado = _card(sessao, "Fechado")
        fechado.situacao, fechado.motivo_recusa = Situacao.PERDIDA, list(MotivoRecusa)[0]
        sessao.commit()
        r = cliente.post(f"/api/questionarios/{q['id']}/mesclar", json={"oportunidade_id": fechado.id})
        assert r.status_code == 409 and "não está em aberto" in r.json()["detail"]
