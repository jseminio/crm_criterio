"""O CSV das contas âncora entra na fila sem duplicar e avisando o que pulou."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Abordagem, GrupoEconomico
from crm.domain.listas import CanalDeAbordagem, Origem

_ARQUIVO = Path(__file__).resolve().parents[1] / "scripts" / "importar_abordagens.py"
_spec = importlib.util.spec_from_file_location("importar_abordagens", _ARQUIVO)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

CSV = (
    "conta;mes;quem_apresenta;canal;destinatario;contexto\n"
    "Conta Alfa;2026-10;Parceiro A;;;Staff loan em espera\n"
    "Conta Beta;2026-10;;WhatsApp;(21) 99999-1234;\n"
    "Conta Gama;2026-13;Parceiro A;;;\n"
    "Conta Delta;2026-10;Parceiro A;Carta;;\n"
)


def test_le_e_enfileira_avisando_o_que_pulou(tmp_path, sessao: Session):
    arquivo = tmp_path / "contas.csv"
    arquivo.write_text(CSV, encoding="utf-8")
    sessao.add(GrupoEconomico(nome="conta alfa", origem=Origem.CARGA_2026))
    sessao.flush()

    relatorio = script.enfileirar_linhas(sessao, script.ler_csv(arquivo))

    assert relatorio == [
        "linha 2: Conta Alfa entrou na fila de 2026-10",
        "linha 3: Conta Beta entrou na fila de 2026-10 (bloqueada: falta quem apresenta)",
        "linha 4: mês inválido '2026-13' — pulada",
        "linha 5: canal 'Carta' desconhecido — pulada",
    ]
    abordagens = sessao.scalars(sa.select(Abordagem).order_by(Abordagem.id)).all()
    assert [a.grupo.nome for a in abordagens] == ["conta alfa", "Conta Beta"]  # reaproveitou
    assert abordagens[0].contexto == "Staff loan em espera"
    assert abordagens[1].canal is CanalDeAbordagem.WHATSAPP

    de_novo = script.enfileirar_linhas(sessao, script.ler_csv(arquivo))
    assert de_novo[0] == "linha 2: Conta Alfa já está na fila de 2026-10 — pulada"
    assert sessao.scalar(sa.select(sa.func.count(Abordagem.id))) == 2


def test_aceita_virgula_como_separador(tmp_path):
    arquivo = tmp_path / "contas.csv"
    arquivo.write_text("conta,mes\nConta Alfa,2026-10\n", encoding="utf-8")
    assert script.ler_csv(arquivo) == [{"conta": "Conta Alfa", "mes": "2026-10"}]
