"""O commit da requisição acontece antes da resposta sair — 27/09/2026.

Com o `scope` padrão do FastAPI (≥ 0.121), o código depois do `yield` de uma
dependência roda **depois** que a resposta foi enviada. O `commit` de
`obter_sessao` ficava ali: uma chamada logo depois da outra lia o estado
anterior (encerrar a conversa do SDR e dar a nota devolvia 409) e um commit que
falhasse chegava ao cliente como 200/201. A dependência agora é declarada com
`scope="function"` em toda a API.
"""

from __future__ import annotations

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app, obter_sessao
from crm.db.modelos import Lead


class _SessaoQueNaoConfirma(Session):
    def commit(self) -> None:
        raise RuntimeError("o banco recusou o commit")


def test_commit_que_falha_nao_devolve_sucesso(engine: sa.Engine):
    fabrica = sessionmaker(bind=engine, class_=_SessaoQueNaoConfirma, expire_on_commit=False)
    with TestClient(criar_app(fabrica), raise_server_exceptions=False) as cliente:
        resposta = cliente.post("/api/leads", json={"nome": "Lead que não grava"})

    assert resposta.status_code == 500
    with Session(engine) as conferencia:
        assert conferencia.scalar(sa.select(sa.func.count()).select_from(Lead)) == 0


def test_o_que_a_rota_devolveu_ja_esta_gravado(engine: sa.Engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    with TestClient(criar_app(fabrica)) as cliente:
        resposta = cliente.post("/api/leads", json={"nome": "Lead gravado"})

    assert resposta.status_code == 201
    with Session(engine) as conferencia:
        assert conferencia.get(Lead, resposta.json()["id"]) is not None


def _dependencias(dependant):
    for sub in dependant.dependencies:
        yield sub
        yield from _dependencias(sub)


def test_toda_rota_confirma_antes_de_responder():
    """Rota nova que esqueça o `scope` volta a responder antes do commit."""
    sem_escopo = [
        f"{', '.join(rota.methods)} {rota.path}"
        for rota in criar_app().routes
        if hasattr(rota, "dependant")
        for dep in _dependencias(rota.dependant)
        if dep.call is obter_sessao and dep.scope != "function"
    ]
    assert sem_escopo == []
