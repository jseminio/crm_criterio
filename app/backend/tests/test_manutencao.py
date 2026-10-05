"""(c) tarefa de manutenção roda uma vez e não repete; falha não registra; (d) ids únicos (#93)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from crm.db.modelos import ManutencaoAplicada, Perfil
from crm.manutencao import FalhaNaTarefa, Tarefa, aplicar_pendentes, estado, problemas_do_registro
from crm.manutencao.registro import TAREFAS

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture
def fabrica(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _cria_perfil(nome):
    def executar(sessao):
        sessao.add(Perfil(nome=nome, administrador=False, permissoes=[]))
        return "1 perfil criado"
    return executar


def _explode(sessao):
    sessao.add(Perfil(nome="não pode ficar", administrador=False, permissoes=[]))
    sessao.flush()
    raise RuntimeError("deu errado\n[parameters: dado de cliente]")


def _perfis(fabrica):
    with fabrica() as s:
        return sorted(s.scalars(sa.select(Perfil.nome)))


def test_c_roda_uma_vez_e_nao_repete(fabrica):
    tarefas = [Tarefa("2026_10_05_teste_um", "cria o perfil Um", _cria_perfil("Um"))]
    assert aplicar_pendentes(fabrica, tarefas, avisar=lambda _: None) == ["2026_10_05_teste_um"]
    assert aplicar_pendentes(fabrica, tarefas, avisar=lambda _: None) == []
    assert _perfis(fabrica) == ["Um"]
    with fabrica() as s:
        registro = s.get(ManutencaoAplicada, "2026_10_05_teste_um")
    assert registro.resultado == "1 perfil criado" and registro.aplicada_em is not None


def test_c_falha_nao_registra_nem_deixa_efeito_e_para_a_fila(fabrica):
    tarefas = [
        Tarefa("2026_10_05_antes", "cria Antes", _cria_perfil("Antes")),
        Tarefa("2026_10_05_explode", "falha no meio", _explode),
        Tarefa("2026_10_06_depois", "cria Depois", _cria_perfil("Depois")),
    ]
    with pytest.raises(FalhaNaTarefa) as falha:
        aplicar_pendentes(fabrica, tarefas, avisar=lambda _: None)
    assert "dado de cliente" not in str(falha.value) and "2026_10_05_explode" in str(falha.value)
    assert _perfis(fabrica) == ["Antes"]
    linhas, _ = estado(fabrica, tarefas)
    assert [(t.id, r is not None) for t, r in linhas] == [
        ("2026_10_05_antes", True), ("2026_10_05_explode", False), ("2026_10_06_depois", False)]
    # Consertada, roda no próximo Redeploy, e a anterior não repete.
    consertadas = [tarefas[0], Tarefa("2026_10_05_explode", "agora certa", _cria_perfil("Meio")), tarefas[2]]
    assert aplicar_pendentes(fabrica, consertadas, avisar=lambda _: None) == ["2026_10_05_explode", "2026_10_06_depois"]
    assert _perfis(fabrica) == ["Antes", "Depois", "Meio"]


def test_d_registro_real_sem_problema():
    assert problemas_do_registro(TAREFAS) == []


def test_d_ids_repetidos_fora_do_formato_ou_de_ordem_sao_recusados(fabrica):
    nada = lambda s: None  # noqa: E731
    ruins = [Tarefa("2026_10_06_a", "x", nada), Tarefa("2026_10_06_a", "y", nada),
             Tarefa("2026_10_05_b", "z", nada), Tarefa("Sem-Data", "w", nada)]
    problemas = problemas_do_registro(ruins)
    assert any("repetido" in p for p in problemas)
    assert any("fora de ordem" in p for p in problemas)
    assert any("formato" in p for p in problemas)
    with pytest.raises(ValueError):
        aplicar_pendentes(fabrica, ruins, avisar=lambda _: None)


def test_migracao_tolera_tabela_ja_existente():
    """Restaurar um dump da f4a7c2e9b1d3 deixa a tabela de pé e volta alembic_version: o upgrade não pode falhar."""
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    caminho = BACKEND / "migrations" / "versions" / "20261005_1400_manutencao_aplicada.py"
    spec = importlib.util.spec_from_file_location("migracao_manutencao", caminho)
    migracao = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracao)
    motor = sa.create_engine("sqlite+pysqlite:///:memory:")
    with motor.begin() as conexao:
        with Operations.context(MigrationContext.configure(conexao)):
            migracao.upgrade()  # cria
            conexao.execute(sa.text("INSERT INTO manutencao_aplicada (id, descricao, aplicada_em) "
                                    "VALUES ('2026_10_05_x', 'x', CURRENT_TIMESTAMP)"))
            migracao.upgrade()  # já existe: não falha e não apaga
            assert conexao.execute(sa.text("SELECT count(*) FROM manutencao_aplicada")).scalar() == 1
            migracao.downgrade()
            assert not sa.inspect(conexao).has_table("manutencao_aplicada")


def test_script_sem_tarefas_diz_nada_a_fazer_sem_conectar(capsys):
    sys.path.insert(0, str(BACKEND / "scripts"))
    import manutencao

    assert manutencao.main([], tarefas=[]) == 0
    assert "nada a fazer" in capsys.readouterr().out


def test_script_falha_sai_com_1(fabrica, capsys):
    sys.path.insert(0, str(BACKEND / "scripts"))
    import manutencao

    tarefas = [Tarefa("2026_10_05_explode", "falha", _explode)]
    assert manutencao.main([], fabrica=fabrica, tarefas=tarefas) == 1
    assert "falhou" in capsys.readouterr().err
    assert manutencao.main(["--listar"], fabrica=fabrica, tarefas=tarefas) == 0
    assert "PENDENTE  2026_10_05_explode" in capsys.readouterr().out
