"""Regras dos eventos de contrato: vigência na assinatura, e cada tipo com o que exige."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D

import pytest

from crm.domain.eventos_de_contrato import ErroDeEvento, Pedido, efeito_do_evento
from crm.domain.listas import MotivoDeEncerramento as M
from crm.domain.listas import SituacaoContrato as S
from crm.domain.listas import TipoDeEventoDeContrato as T

ASSINATURA = date(2026, 3, 1)
HOJE = date(2026, 9, 25)


@dataclass
class C:
    situacao: S = S.ATIVO
    escopo: str | None = "BPO Contábil"
    preco_mensal: D | None = D("1000.00")
    preco_anual: D | None = D("12000.00")
    data_inicio: date | None = ASSINATURA
    data_fim: date | None = date(2027, 3, 1)


def pedido(tipo, **kw):
    return Pedido(tipo=tipo, data_do_evento=kw.pop("data_do_evento", HOJE), **kw)


class TestEstadoDoContrato:
    def test_antes_da_assinatura_nao_recebe_evento(self):
        with pytest.raises(ErroDeEvento, match="não foi assinado") as e:
            efeito_do_evento(C(situacao=S.AGUARDANDO_ASSINATURA), pedido(T.REAJUSTE, preco_mensal_novo=D("1100")))
        assert e.value.status == 409

    def test_encerrado_nao_recebe_mais_nada(self):
        with pytest.raises(ErroDeEvento, match="encerrado") as e:
            efeito_do_evento(C(situacao=S.ENCERRADO), pedido(T.ADITIVO, descricao="qualquer"))
        assert e.value.status == 409

    def test_suspenso_ainda_recebe(self):
        assert efeito_do_evento(C(situacao=S.SUSPENSO), pedido(T.REAJUSTE, preco_mensal_novo=D("1100")))

    def test_evento_nao_pode_ser_anterior_a_assinatura(self):
        with pytest.raises(ErroDeEvento, match="anterior à assinatura"):
            efeito_do_evento(C(), pedido(T.REAJUSTE, preco_mensal_novo=D("1100"), data_do_evento=date(2026, 2, 1)))


class TestPreco:
    def test_reajuste_troca_o_preco_e_so_o_que_veio(self):
        assert efeito_do_evento(C(), pedido(T.REAJUSTE, preco_mensal_novo=D("1100"))) == {"preco_mensal": D("1100")}

    def test_reajuste_sem_preco_e_recusado(self):
        with pytest.raises(ErroDeEvento, match="novo preço"):
            efeito_do_evento(C(), pedido(T.REAJUSTE))

    def test_preco_igual_ao_atual_nao_e_evento(self):
        with pytest.raises(ErroDeEvento, match="igual ao atual"):
            efeito_do_evento(C(), pedido(T.REAJUSTE, preco_mensal_novo=D("1000.00")))

    def test_expansao_nao_pode_reduzir(self):
        with pytest.raises(ErroDeEvento, match="Contração"):
            efeito_do_evento(C(), pedido(T.EXPANSAO, preco_mensal_novo=D("900")))
        assert efeito_do_evento(C(), pedido(T.EXPANSAO, preco_mensal_novo=D("1500")))["preco_mensal"] == D("1500")

    def test_contracao_nao_pode_aumentar(self):
        with pytest.raises(ErroDeEvento, match="Expansão"):
            efeito_do_evento(C(), pedido(T.CONTRACAO, preco_anual_novo=D("13000")))
        assert efeito_do_evento(C(), pedido(T.CONTRACAO, preco_anual_novo=D("9000")))["preco_anual"] == D("9000")

    def test_preco_negativo_e_recusado(self):
        with pytest.raises(ErroDeEvento, match="negativo"):
            efeito_do_evento(C(), pedido(T.REAJUSTE, preco_mensal_novo=D("-1")))

    def test_contrato_sem_preco_atual_aceita_o_primeiro_preco(self):
        assert efeito_do_evento(C(preco_mensal=None), pedido(T.EXPANSAO, preco_mensal_novo=D("500")))


class TestAditivoRenovacaoEncerramento:
    def test_aditivo_exige_descricao(self):
        with pytest.raises(ErroDeEvento, match="o que foi aditado"):
            efeito_do_evento(C(), pedido(T.ADITIVO, descricao="  "))

    def test_aditivo_pode_trocar_escopo_e_preco(self):
        e = efeito_do_evento(C(), pedido(T.ADITIVO, descricao="inclui DP", escopo_novo="BPO Contábil + DP", preco_mensal_novo=D("1400")))
        assert e == {"preco_mensal": D("1400"), "escopo": "BPO Contábil + DP"}

    def test_aditivo_so_descritivo_nao_muda_nada(self):
        assert efeito_do_evento(C(), pedido(T.ADITIVO, descricao="troca de signatário")) == {}

    def test_renovacao_exige_data_depois_da_atual(self):
        with pytest.raises(ErroDeEvento, match="nova data de fim"):
            efeito_do_evento(C(), pedido(T.RENOVACAO))
        with pytest.raises(ErroDeEvento, match="depois da atual"):
            efeito_do_evento(C(), pedido(T.RENOVACAO, data_fim_nova=date(2027, 3, 1)))
        assert efeito_do_evento(C(), pedido(T.RENOVACAO, data_fim_nova=date(2028, 3, 1))) == {"data_fim": date(2028, 3, 1)}

    def test_renovacao_de_contrato_sem_fim_conta_a_partir_do_evento(self):
        assert efeito_do_evento(C(data_fim=None), pedido(T.RENOVACAO, data_fim_nova=date(2027, 9, 25)))
        with pytest.raises(ErroDeEvento):
            efeito_do_evento(C(data_fim=None), pedido(T.RENOVACAO, data_fim_nova=HOJE))

    def test_encerramento_exige_a_categoria_do_motivo(self):
        with pytest.raises(ErroDeEvento, match="categoria do motivo"):
            efeito_do_evento(C(), pedido(T.ENCERRAMENTO))
        with pytest.raises(ErroDeEvento, match="categoria do motivo"):
            efeito_do_evento(C(), pedido(T.ENCERRAMENTO, descricao="só texto, sem categoria"))

    def test_encerramento_com_categoria_fecha_o_contrato_sem_exigir_texto(self):
        e = efeito_do_evento(C(), pedido(T.ENCERRAMENTO, motivo_categoria=M.PRECO))
        assert e == {"situacao": S.ENCERRADO, "data_fim": HOJE}

    def test_categoria_outro_exige_texto(self):
        with pytest.raises(ErroDeEvento, match="Outro"):
            efeito_do_evento(C(), pedido(T.ENCERRAMENTO, motivo_categoria=M.OUTRO))
        with pytest.raises(ErroDeEvento, match="Outro"):
            efeito_do_evento(C(), pedido(T.ENCERRAMENTO, motivo_categoria=M.OUTRO, descricao="  "))
        assert efeito_do_evento(C(), pedido(T.ENCERRAMENTO, motivo_categoria=M.OUTRO, descricao="fusão com outra empresa"))
