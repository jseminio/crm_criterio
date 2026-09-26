"""Backup automático: confere o arquivo, respeita a retenção e nunca apaga o que não é seu."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from crm.backup import verificar
from crm.backup.agendado import PREFIXO, executar
from crm.db.modelos import GrupoEconomico


@pytest.fixture
def com_dados(engine, sessao):
    sessao.add(GrupoEconomico(nome="Alfa"))
    sessao.commit()
    return engine


def test_grava_arquivo_conferido_com_permissao_so_do_dono(com_dados, tmp_path):
    r = executar(com_dados, tmp_path / "bk")
    assert r.arquivo.name.startswith(PREFIXO) and r.registros == 1
    assert verificar(r.arquivo).total == 1
    assert oct(os.stat(r.arquivo).st_mode)[-3:] == "600"
    assert oct(os.stat(tmp_path / "bk").st_mode)[-3:] == "700"


def test_retencao_mantem_so_os_ultimos_automaticos(com_dados, tmp_path):
    base = datetime(2026, 9, 1, 12)
    for d in range(5):
        executar(com_dados, tmp_path, manter=3, agora=base + timedelta(days=d))
    assert [f.name for f in sorted(tmp_path.glob(f"{PREFIXO}*.zip"))] == [
        f"{PREFIXO}20260903-120000.zip", f"{PREFIXO}20260904-120000.zip", f"{PREFIXO}20260905-120000.zip"
    ]


def test_nunca_apaga_backup_manual_nem_o_de_antes_de_importar(com_dados, tmp_path):
    manual = tmp_path / "crm-20260101-000000.zip"
    antes = tmp_path / "antes-de-importar-20260101-000000.zip"
    manual.write_bytes(b"x"); antes.write_bytes(b"x")
    for d in range(4):
        executar(com_dados, tmp_path, manter=1, agora=datetime(2026, 9, 1 + d, 12))
    assert manual.exists() and antes.exists()


def test_falha_nao_apaga_nenhum_antigo_e_nao_deixa_arquivo_pela_metade(com_dados, tmp_path, monkeypatch):
    executar(com_dados, tmp_path, manter=1, agora=datetime(2026, 9, 1, 12))
    from crm.backup import agendado

    monkeypatch.setattr(agendado, "verificar", lambda *_: (_ for _ in ()).throw(RuntimeError("corrompido")))
    with pytest.raises(RuntimeError):
        executar(com_dados, tmp_path, manter=1, agora=datetime(2026, 9, 2, 12))
    assert [f.name for f in tmp_path.glob(f"{PREFIXO}*.zip")] == [f"{PREFIXO}20260901-120000.zip"]


def test_manter_zero_e_recusado(com_dados, tmp_path):
    with pytest.raises(ValueError):
        executar(com_dados, tmp_path, manter=0)
