"""Apagar um grupo de teste inteiro, com tudo o que é dele (03/10/2026)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import (
    Contrato, Empresa, GrupoEconomico, Lead, Oportunidade, PessoaContato, QuestionarioRecebido, VinculoDeContato,
)
from crm.domain.listas import Situacao, SituacaoContrato, SituacaoDoQuestionario

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import apagar_grupo as ag  # noqa: E402


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        teste, salus = GrupoEconomico(nome="karineon"), GrupoEconomico(nome="Outro grupo")
        s.add_all([teste, salus])
        s.flush()
        e = Empresa(grupo_id=teste.id, razao_social="Karine ON", cnpj="66108756000167")
        outra = Empresa(grupo_id=salus.id, razao_social="Outra", cnpj="11222333000144")
        s.add_all([e, outra])
        s.flush()
        so_dele = PessoaContato(nome="Só do teste", email="teste@x.com")
        dos_dois = PessoaContato(nome="Em dois grupos", email="dois@x.com")
        s.add_all([so_dele, dos_dois])
        s.flush()
        s.add_all([
            VinculoDeContato(pessoa_id=so_dele.id, empresa_id=e.id),
            VinculoDeContato(pessoa_id=dos_dois.id, empresa_id=e.id),
            VinculoDeContato(pessoa_id=dos_dois.id, empresa_id=outra.id),
        ])
        op = Oportunidade(grupo_id=teste.id, empresa_id=e.id, nome="Karine ON", situacao=Situacao.ENVIAR_PROPOSTA)
        s.add(op)
        s.flush()
        s.add(Lead(nome="Lead do teste", convertido_em_id=op.id))
        s.add(QuestionarioRecebido(
            externo_id="q-teste", recebido_em=datetime(2026, 10, 1, tzinfo=timezone.utc), versao="v1",
            razao_social="Karine ON", cnpj="66108756000167", contato_nome="Karine", respostas={},
            situacao=SituacaoDoQuestionario.IMPORTADO, o_que_fez="teste", grupo_id=teste.id, oportunidade_id=op.id,
        ))
        s.commit()
        return {"teste": teste.id, "outro": salus.id, "dos_dois": dos_dois.id}


def test_mostra_e_apaga_tudo_do_grupo_e_so_dele(engine, ids):
    with Session(engine) as s:
        g = ag._grupo(s, "66.108.756/0001-67", None)
        assert g.id == ids["teste"]
        itens = ag.plano(s, g)
        assert [x.nome for x in itens["contato"]] == ["Só do teste"]  # o de dois grupos fica
        assert len(itens["questionário recebido"]) == 1 and len(itens["oportunidade"]) == 1
        ag.apagar(s, itens)
        s.commit()
    with Session(engine) as s:
        assert s.get(GrupoEconomico, ids["teste"]) is None and s.get(GrupoEconomico, ids["outro"]) is not None
        assert s.scalar(sa.select(sa.func.count(Empresa.id))) == 1
        assert [p.nome for p in s.scalars(sa.select(PessoaContato))] == ["Em dois grupos"]
        assert s.scalar(sa.select(sa.func.count(VinculoDeContato.id))) == 1
        assert s.scalar(sa.select(sa.func.count(QuestionarioRecebido.id))) == 0
        lead = s.scalar(sa.select(Lead))
        assert lead is not None and lead.convertido_em_id is None  # o lead fica, sem apontar para o que saiu


def test_recusa_grupo_com_contrato(engine, ids):
    with Session(engine) as s:
        s.add(Contrato(grupo_id=ids["teste"], situacao=SituacaoContrato.ATIVO, preco_mensal=D("100")))
        s.commit()
        with pytest.raises(ag.Recusado, match="tem contrato"):
            ag.plano(s, s.get(GrupoEconomico, ids["teste"]))


@pytest.mark.parametrize("cnpj, nome, trecho", [("99999999000199", None, "Achei 0 empresas"), (None, "nao existe", "Achei 0 grupos")])
def test_sem_alvo_unico_recusa(engine, ids, cnpj, nome, trecho):
    with Session(engine) as s, pytest.raises(ag.Recusado, match=trecho):
        ag._grupo(s, cnpj, nome)
