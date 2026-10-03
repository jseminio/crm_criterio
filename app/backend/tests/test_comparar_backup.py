"""Comparar um backup de outro CRM com o banco daqui, sem gravar nada (03/10/2026)."""

from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.backup import exportar
from crm.db.modelos import Base, Contrato, Empresa, GrupoEconomico
from crm.domain.listas import SituacaoContrato

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import comparar_backup as cb  # noqa: E402

T0 = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def _motor() -> sa.Engine:
    m = sa.create_engine("sqlite+pysqlite:///:memory:", poolclass=sa.pool.StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(m)
    return m


def _base(s: Session) -> None:
    """O que as duas cópias tinham em comum antes de se separarem."""
    s.add_all([
        GrupoEconomico(nome="Comum", criado_em=T0, atualizado_em=T0),
        GrupoEconomico(nome="Alterar", criado_em=T0 + timedelta(seconds=1), atualizado_em=T0),
    ])
    s.flush()
    # Dois contratos idênticos criados no mesmo segundo (a carga da carteira faz isso): contam como dois.
    for g in (1, 2):
        s.add(Contrato(grupo_id=g, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("8000"),
                       criado_em=T0, atualizado_em=T0))
    s.commit()


@pytest.fixture
def resultado(tmp_path):
    daqui, dela = _motor(), _motor()
    for m in (daqui, dela):
        with Session(m) as s:
            _base(s)
    with Session(dela) as s:  # o que foi feito no outro CRM
        alterar = s.scalar(sa.select(GrupoEconomico).where(GrupoEconomico.nome == "Alterar"))
        alterar.observacao, alterar.atualizado_em = "nova observação", T0 + timedelta(days=2)
        s.add(GrupoEconomico(nome="Novo da Karine", criado_em=T0 + timedelta(days=2), atualizado_em=T0 + timedelta(days=2)))
        s.add(Empresa(grupo_id=1, razao_social="Empresa K", cnpj="11222333000144",
                      criado_em=T0 + timedelta(days=2), atualizado_em=T0 + timedelta(days=2)))
        s.commit()
    with Session(daqui) as s:  # o que foi feito aqui depois da separação
        s.add(GrupoEconomico(nome="Meu novo", criado_em=T0 + timedelta(days=1), atualizado_em=T0 + timedelta(days=1)))
        s.execute(sa.delete(Contrato).where(Contrato.grupo_id == 2))
        s.commit()
    arquivo = tmp_path / "dela.zip"
    buf = io.BytesIO()
    exportar(dela, buf)
    arquivo.write_bytes(buf.getvalue())
    return cb.comparar(cb._do_arquivo(arquivo), daqui)


def test_acha_o_novo_e_o_alterado_la_e_conta_o_novo_daqui(resultado):
    g = resultado["grupo_economico"]
    assert [l["nome"] for l in g["so_no_arquivo"]] == ["Novo da Karine"]
    assert [(l["nome"], campos) for l, campos in g["alterados_no_arquivo"]] == [("Alterar", ["observacao"])]
    assert g["so_no_banco"] == 1
    assert [l["razao_social"] for l in resultado["empresa"]["so_no_arquivo"]] == ["Empresa K"]


def test_registros_iguais_no_mesmo_segundo_contam_um_a_um(resultado):
    c = resultado["contrato"]
    assert len(c["so_no_arquivo"]) == 1  # o contrato que saiu daqui continua no arquivo
    assert cb._rotulo("contrato", c["so_no_arquivo"][0], c["nomes"]) == "Alterar / 8000"


@pytest.mark.parametrize("a, b", [
    (True, 1), ("False", 0), ("1000", D("1000.00")), ("2026-09-30T09:00:00-03:00", "2026-09-30 12:00:00"),
    ({"b": 1, "a": 2}, '{"a": 2, "b": 1}'), (None, ""), (8000.0, "8000.00"),
])
def test_o_mesmo_valor_escrito_de_jeitos_diferentes_e_igual(a, b):
    assert cb._valor(a) == cb._valor(b)


def test_numero_redondo_nao_vira_notacao_cientifica():
    assert cb._valor("8000.00") == "8000"
