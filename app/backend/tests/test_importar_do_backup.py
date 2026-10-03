"""Trazer o que foi feito em outro CRM sem apagar nada daqui (03/10/2026)."""

from __future__ import annotations

import io
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.backup import exportar
from crm.db.modelos import Base, Empresa, GrupoEconomico, Oportunidade, PessoaContato, VinculoDeContato
from crm.domain.listas import Situacao, Temperatura

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import comparar_backup as cb  # noqa: E402
import importar_do_backup as imp  # noqa: E402

T0 = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
DEPOIS = T0 + timedelta(days=2)


def _motor() -> sa.Engine:
    m = sa.create_engine("sqlite+pysqlite:///:memory:", poolclass=sa.pool.StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(m)
    return m


def _comum(s: Session, dela: bool) -> None:
    t = DEPOIS if dela else T0
    g = GrupoEconomico(nome="Salus", criado_em=T0, atualizado_em=T0)
    s.add(g)
    s.flush()
    # lá a empresa ganhou o CNPJ; aqui continua sem
    e = Empresa(grupo_id=g.id, razao_social="Salus", cnpj="66108756000167" if dela else None, criado_em=t, atualizado_em=t)
    rafael = PessoaContato(nome="Rafael Monteiro Machado", email="r@x.com", criado_em=T0, atualizado_em=T0)
    igor = PessoaContato(nome="Igor Clare" if dela else "Igor", email="i@x.com", telefone="351 9" if dela else "+351 9",
                         observacao="Fonte: carteira" if dela else "+55 21 9999", cargo="Sócio" if dela else None,
                         criado_em=T0, atualizado_em=t)
    s.add_all([e, rafael, igor])
    s.add_all([
        Oportunidade(grupo_id=g.id, nome="Salus", situacao=Situacao.ACEITA, chave_origem="p-1",
                     data_aceite=date(2026, 8, 1) if dela else None, temperatura=Temperatura.FRIO if dela else Temperatura.MORNO,
                     preco_mensal=D("900") if dela else D("1000"), criado_em=T0, atualizado_em=t),
    ])
    s.flush()
    if dela:
        s.add(VinculoDeContato(pessoa_id=rafael.id, empresa_id=e.id))
        sem_email = PessoaContato(nome="Rafael", criado_em=DEPOIS, atualizado_em=DEPOIS)
        s.add(sem_email)
        s.flush()
        s.add(VinculoDeContato(pessoa_id=sem_email.id, empresa_id=e.id))
        s.add(Empresa(grupo_id=g.id, razao_social="Nova Ltda", cnpj="11222333000144", criado_em=DEPOIS, atualizado_em=DEPOIS))
    s.commit()


def _arquivo(m: sa.Engine, tmp_path) -> dict:
    buf = io.BytesIO()
    exportar(m, buf)
    caminho = tmp_path / "dela.zip"
    caminho.write_bytes(buf.getvalue())
    return cb._do_arquivo(caminho)


def test_acrescenta_preenche_e_troca_so_o_aprovado(tmp_path):
    daqui, dela = _motor(), _motor()
    with Session(daqui) as s:
        _comum(s, dela=False)
    with Session(dela) as s:
        _comum(s, dela=True)
    plano = imp.montar(_arquivo(dela, tmp_path), daqui)
    assert any("não duplica" in a for a in plano.avisos)  # "Rafael" é o Rafael Monteiro Machado
    assert [r["_rotulo"] for r in plano.inserir["empresa"]] == ["Salus / 11222333000144 · Nova Ltda"]
    assert len(plano.inserir["vinculo_de_contato"]) == 1  # Rafael Monteiro Machado ↔ Salus, uma vez só
    assert ("oportunidade", "Salus / Salus", "preco_mensal", "1000", "900") in plano.pendentes  # preço: decide à mão
    imp.gravar(plano, daqui)
    with Session(daqui) as s:
        salus = s.scalar(sa.select(Empresa).where(Empresa.razao_social == "Salus"))
        assert salus.cnpj == "66108756000167"  # preenchido: era a mesma empresa, sem CNPJ aqui
        assert s.scalar(sa.select(sa.func.count(Empresa.id))) == 2
        assert [p.nome for p in s.scalars(sa.select(PessoaContato).order_by(PessoaContato.id))] == [
            "Rafael Monteiro Machado", "Igor Clare"]
        igor = s.scalar(sa.select(PessoaContato).where(PessoaContato.email == "i@x.com"))
        assert (igor.telefone, igor.cargo) == ("+351 9", "Sócio")  # mesmo telefone: fica o daqui, com o +
        assert igor.observacao == "Fonte: carteira\n+55 21 9999"  # a observação junta as duas
        op = s.scalar(sa.select(Oportunidade))
        assert (op.data_aceite, op.temperatura, op.preco_mensal) == (date(2026, 8, 1), Temperatura.FRIO, D("1000.00"))
        (v,) = s.scalars(sa.select(VinculoDeContato))
        assert (v.pessoa_id, v.empresa_id) == (1, salus.id)
    # de novo: nada a fazer
    plano = imp.montar(_arquivo(dela, tmp_path), daqui)
    assert not plano.inserir.get("empresa") and not plano.inserir.get("vinculo_de_contato")
    assert [m for m in plano.mudar if m[0] != "pessoa_contato"] == []
