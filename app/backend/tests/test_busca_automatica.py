"""Busca automática dos questionários do site (02/10/2026, aprovado por Eduardo): sem ninguém apertar
botão, o CRM busca ao subir e a cada 10 minutos; o painel mostra a última, a próxima e a falha."""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.api.app import criar_app
from crm.api.busca_automatica import buscar_uma_vez, laco_da_busca
from crm.api.questionarios import ESTADO_DA_BUSCA, EstadoDaBusca
from crm.db.modelos import Oportunidade, QuestionarioRecebido
from tests.test_questionario import FonteFalsa, linha


def _fabrica(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_uma_busca_importa_e_registra_o_resultado(engine):
    fonte, estado = FonteFalsa([linha()]), EstadoDaBusca()
    buscar_uma_vez(_fabrica(engine), lambda: fonte, None, estado)
    r = estado.retrato()
    assert (r["novos"], r["erro"], r["ultima_manual"]) == (1, None, False) and r["ultima_em"] is not None
    assert fonte.marcados == ["q-1"]
    with _fabrica(engine)() as s:
        assert s.scalar(sa.select(sa.func.count(QuestionarioRecebido.id))) == 1
        assert s.scalar(sa.select(sa.func.count(Oportunidade.id))) == 1  # já vira oportunidade, como no botão
    buscar_uma_vez(_fabrica(engine), lambda: fonte, None, estado)  # de novo: nada novo, nada duplicado
    assert estado.retrato()["novos"] == 0


def test_falha_vai_para_o_painel_sem_derrubar(engine):
    estado = EstadoDaBusca()
    buscar_uma_vez(_fabrica(engine), lambda: FonteFalsa(falhar_busca=True), None, estado)
    assert "recusou a chave" in estado.retrato()["erro"]
    buscar_uma_vez(_fabrica(engine), lambda: None, None, estado)
    assert "Falta configurar" in estado.retrato()["erro"]

    class Quebrada:
        def novos(self):
            raise RuntimeError("bug")

    buscar_uma_vez(_fabrica(engine), lambda: Quebrada(), None, estado)
    assert "Falha inesperada na busca (RuntimeError)" in estado.retrato()["erro"]


def test_o_laco_busca_ja_e_de_novo_depois_do_intervalo(engine):
    fonte, estado = FonteFalsa([linha()]), EstadoDaBusca()

    async def rodar():
        tarefa = asyncio.create_task(laco_da_busca(_fabrica(engine), lambda: fonte, None, timedelta(seconds=0.2), estado))
        await asyncio.sleep(0.05)
        primeira = estado.retrato()
        assert primeira["automatica"] and primeira["novos"] == 1 and primeira["proxima_em"] is not None
        fonte.linhas.append(linha(id_="q-2", cnpj="98.765.432/0001-10"))
        await asyncio.sleep(0.3)
        assert estado.retrato()["novos"] == 1 and "q-2" in fonte.marcados
        tarefa.cancel()
        try:
            await tarefa
        except asyncio.CancelledError:
            pass
        assert not estado.retrato()["automatica"]

    asyncio.run(rodar())


def test_o_crm_liga_a_busca_ao_subir_e_o_painel_mostra(engine):
    fonte = FonteFalsa([linha()])
    with TestClient(criar_app(_fabrica(engine), fonte_de_questionarios=lambda: fonte, busca_automatica=True)) as c:
        for _ in range(50):  # a primeira busca roda em segundo plano, logo ao subir
            if fonte.marcados:
                break
            time.sleep(0.05)
        r = c.get("/api/questionarios/busca").json()
        assert (r["automatica"], r["intervalo_minutos"], r["novos"], r["erro"]) == (True, 10, 1, None)
        assert r["proxima_em"] is not None
        assert len(c.get("/api/questionarios").json()) == 1
    assert not ESTADO_DA_BUSCA.retrato()["automatica"]  # desligou junto com o CRM


def test_buscar_agora_registra_como_manual(engine):
    fonte = FonteFalsa([linha()])
    with TestClient(criar_app(_fabrica(engine), fonte_de_questionarios=lambda: fonte)) as c:
        assert c.post("/api/questionarios/buscar").status_code == 200
        r = c.get("/api/questionarios/busca").json()
        assert (r["automatica"], r["ultima_manual"], r["novos"]) == (False, True, 1)
        fonte.falhar_busca = True
        assert c.post("/api/questionarios/buscar").status_code == 502
        assert "recusou a chave" in c.get("/api/questionarios/busca").json()["erro"]
