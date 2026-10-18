"""Versão na tela (18/10/2026): o commit publicado e a data do build, sem número escrito à mão."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm import versao
from crm.acesso.catalogo import permissoes_da_rota
from crm.api.app import criar_app


@pytest.fixture(autouse=True)
def sem_cache(monkeypatch):
    monkeypatch.delenv("SOURCE_COMMIT", raising=False)
    versao.identidade.cache_clear()
    yield
    versao.identidade.cache_clear()


@pytest.mark.parametrize("valor, esperado", [
    ("a90b952e1c0f4d3b8a7e6f5d4c3b2a1908f7e6d5", "a90b952"),
    ("A90B952", "a90b952"),
    ("  a90b952\n", "a90b952"),
    ("", None),
    (None, None),
    ("main", None),
    ("abc12", None),
])
def test_commit_curto(valor, esperado):
    assert versao.commit_curto(valor) == esperado


def test_no_container_vale_o_commit_do_coolify_e_a_data_do_build(monkeypatch, tmp_path):
    arquivo = tmp_path / "DATA_DO_BUILD"
    arquivo.write_text("2026-10-18\n", encoding="utf-8")
    monkeypatch.setattr(versao, "ARQUIVO_DA_DATA", arquivo)
    monkeypatch.setattr(versao, "_git", lambda *a: pytest.fail("com SOURCE_COMMIT e DATA_DO_BUILD, não pergunta ao git"))
    monkeypatch.setenv("SOURCE_COMMIT", "a90b952e1c0f4d3b8a7e6f5d4c3b2a1908f7e6d5")
    assert versao.identidade() == {"commit": "a90b952", "data_do_build": "2026-10-18"}


def test_no_desenvolvimento_pergunta_ao_git(monkeypatch, tmp_path):
    monkeypatch.setattr(versao, "ARQUIVO_DA_DATA", tmp_path / "nao-existe")
    respostas = {("rev-parse", "HEAD"): "0e3a273ffffffffffffffffffffffffffffffff0", ("log", "-1", "--format=%cs"): "2026-10-17"}
    monkeypatch.setattr(versao, "_git", lambda *a: respostas[a])
    assert versao.identidade() == {"commit": "0e3a273", "data_do_build": "2026-10-17"}


def test_sem_git_nem_variavel_nao_inventa(monkeypatch, tmp_path):
    monkeypatch.setattr(versao, "ARQUIVO_DA_DATA", tmp_path / "nao-existe")
    monkeypatch.setattr(versao, "_git", lambda *a: None)
    assert versao.identidade() == {"commit": None, "data_do_build": None}


def test_data_estranha_no_arquivo_e_recusada(monkeypatch, tmp_path):
    arquivo = tmp_path / "DATA_DO_BUILD"
    arquivo.write_text("ontem", encoding="utf-8")
    monkeypatch.setattr(versao, "ARQUIVO_DA_DATA", arquivo)
    monkeypatch.setattr(versao, "_git", lambda *a: None)
    assert versao.identidade()["data_do_build"] is None


def test_rota_devolve_a_identidade(monkeypatch):
    monkeypatch.setattr(versao, "_git", lambda *a: None)
    monkeypatch.setattr(versao, "ARQUIVO_DA_DATA", versao.BACKEND / "nao-existe")
    monkeypatch.setenv("SOURCE_COMMIT", "a90b952")
    with TestClient(criar_app(sessionmaker(bind=sa.create_engine("sqlite://")))) as c:
        assert c.get("/api/versao").json() == {"commit": "a90b952", "data_do_build": None}


def test_qualquer_pessoa_que_entrou_ve_a_versao():
    assert permissoes_da_rota("GET", "/api/versao") == ()
