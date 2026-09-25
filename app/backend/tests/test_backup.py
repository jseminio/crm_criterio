"""Backup lógico: ida e volta sem perder nada, e recusa quando não é seguro."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.backup import ErroDeBackup, exportar, importar, verificar
from crm.db.base import Base
from crm.db.modelos import GrupoEconomico, Oportunidade
from crm.domain.listas import Situacao


def _motor_vazio() -> sa.Engine:
    motor = sa.create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False},
    )

    @sa.event.listens_for(motor, "connect")
    def _fk(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    return motor


@pytest.fixture
def com_dados(engine, sessao: Session):
    g = GrupoEconomico(nome="Grupo Ação & Ç")
    sessao.add(g)
    sessao.flush()
    sessao.add(
        Oportunidade(
            grupo_id=g.id,
            nome="Proposta ã",
            situacao=Situacao.ACEITA,
            preco_mensal=Decimal("1234.56"),
            data_aceite=date(2026, 9, 1),
            observacao="linha1\nlinha2",
        )
    )
    sessao.commit()
    return engine


def _zip(engine) -> io.BytesIO:
    buf = io.BytesIO()
    exportar(engine, buf)
    buf.seek(0)
    return buf


def _tudo(engine) -> dict:
    with engine.connect() as c:
        return {
            t.name: sorted(map(tuple, c.execute(sa.select(t)).all()), key=repr)
            for t in Base.metadata.sorted_tables
        }


def test_ida_e_volta_preserva_todos_os_dados(com_dados):
    destino = _motor_vazio()
    resumo = importar(destino, _zip(com_dados))
    assert resumo.tabelas["oportunidade"] == 1
    assert _tudo(destino) == _tudo(com_dados)


def test_dinheiro_e_data_voltam_exatos(com_dados):
    destino = _motor_vazio()
    importar(destino, _zip(com_dados))
    with Session(destino) as s:
        o = s.scalars(sa.select(Oportunidade)).one()
        assert o.preco_mensal == Decimal("1234.56")
        assert o.data_aceite == date(2026, 9, 1)
        assert o.situacao is Situacao.ACEITA


def test_recusa_destino_com_dados_sem_substituir(com_dados):
    with pytest.raises(ErroDeBackup, match="já tem dados"):
        importar(com_dados, _zip(com_dados))


def test_substituir_esvazia_e_recarrega(com_dados):
    arquivo = _zip(com_dados)
    with Session(com_dados) as s:
        s.add(GrupoEconomico(nome="Extra que deve sumir"))
        s.commit()
    importar(com_dados, arquivo, substituir=True)
    with Session(com_dados) as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(GrupoEconomico)) == 1


def test_arquivo_adulterado_e_detectado(com_dados):
    original = _zip(com_dados)
    adulterado = io.BytesIO()
    with zipfile.ZipFile(original) as zi, zipfile.ZipFile(adulterado, "w") as zo:
        for item in zi.namelist():
            dados = zi.read(item)
            if item == "dados/oportunidade.jsonl":
                dados = dados.replace(b"1234.56", b"9999.99")
            zo.writestr(item, dados)
    adulterado.seek(0)
    with pytest.raises(ErroDeBackup, match="impressão digital"):
        verificar(adulterado)


def test_falha_no_meio_nao_deixa_importacao_pela_metade(com_dados):
    arquivo = _zip(com_dados)
    quebrado = io.BytesIO()
    with zipfile.ZipFile(arquivo) as zi, zipfile.ZipFile(quebrado, "w") as zo:
        import hashlib, json

        for item in zi.namelist():
            dados = zi.read(item)
            if item == "dados/oportunidade.jsonl":
                linha = json.loads(dados)
                linha["grupo_id"] = 99999  # grupo que não existe
                dados = (json.dumps(linha) + "\n").encode()
                novo_hash = hashlib.sha256(dados).hexdigest()
            zo.writestr(item, dados)
        manifesto = json.loads(zi.read("manifesto.json"))
        manifesto["tabelas"]["oportunidade"]["sha256"] = novo_hash
        zo.writestr("manifesto.json", json.dumps(manifesto))
    quebrado.seek(0)
    destino = _motor_vazio()
    with pytest.raises(sa.exc.IntegrityError):
        importar(destino, quebrado)
    with destino.connect() as c:
        assert c.execute(sa.select(sa.func.count()).select_from(GrupoEconomico)).scalar() == 0


def test_arquivo_qualquer_nao_e_backup():
    with pytest.raises(ErroDeBackup, match="não é um backup"):
        verificar(io.BytesIO(b"lixo"))


# ------------------------------------------------------------------- rotas

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from crm.api.app import criar_app  # noqa: E402


@pytest.fixture
def cliente(com_dados):
    fabrica = sessionmaker(bind=com_dados, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica), base_url="http://localhost") as c:
        yield c


def test_rota_exporta_e_o_arquivo_importa(cliente, com_dados):
    r = cliente.get("/api/backup/exportar")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    destino = _motor_vazio()
    importar(destino, io.BytesIO(r.content))
    assert _tudo(destino) == _tudo(com_dados)


def test_rota_recusa_pedido_vindo_de_tunel(cliente):
    r = cliente.get("/api/backup/exportar", headers={"X-Forwarded-For": "1.2.3.4"})
    assert r.status_code == 403


def test_rota_recusa_host_de_fora(com_dados):
    fabrica = sessionmaker(bind=com_dados, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica), base_url="http://abc.ngrok-free.app") as c:
        assert c.get("/api/backup/exportar").status_code == 403


def test_rota_importar_exige_confirmacao_para_substituir(cliente):
    zipado = cliente.get("/api/backup/exportar").content
    assert cliente.post("/api/backup/importar?substituir=true", content=zipado).status_code == 400
    assert cliente.post("/api/backup/importar", content=zipado).status_code == 409  # destino ocupado
    ok = cliente.post(
        "/api/backup/importar?substituir=true", content=zipado, headers={"X-Confirmacao": "SUBSTITUIR"}
    )
    assert ok.status_code == 200 and ok.json()["tabelas"]["oportunidade"] == 1


def test_rota_verificar_recusa_lixo(cliente):
    assert cliente.post("/api/backup/verificar", content=b"lixo").status_code == 422


def test_endereco_da_empresa_faz_ida_e_volta(com_dados, sessao):
    from crm.db.modelos import Empresa

    g = sessao.scalars(sa.select(GrupoEconomico)).one()
    sessao.add(Empresa(grupo_id=g.id, razao_social="ACME Ltda", logradouro="Rua Ação", numero="10",
                       complemento="sala 2", bairro="Centro", municipio="Rio de Janeiro", uf="RJ", cep="20040020"))
    sessao.commit()
    destino = _motor_vazio()
    importar(destino, _zip(com_dados))
    with Session(destino) as s:
        e = s.scalars(sa.select(Empresa)).one()
        assert (e.logradouro, e.numero, e.complemento, e.bairro, e.cep) == ("Rua Ação", "10", "sala 2", "Centro", "20040020")
