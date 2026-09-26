"""As travas da aprovação. O texto é escrito por IA: é aqui que o plano garante
que nada sai com preço, para quem pediu para não ser contatado, ou com fato
sem fonte."""

from __future__ import annotations

import pytest

from crm.domain.abordagem import (
    conferir,
    link_whatsapp,
    normalizar_destino,
    pode_aprovar,
    proximo_passo,
    situacao_exibida,
)
from crm.domain.listas import CanalDeAbordagem, SituacaoAbordagem

E = CanalDeAbordagem.EMAIL
W = CanalDeAbordagem.WHATSAPP


def _conferencias(**mudancas):
    campos = dict(
        canal=E,
        destinatario="diretor@empresa.com.br",
        assunto="Retomando a conversa",
        mensagem="Olá, Ana. Proponho 30 minutos na próxima semana.",
        quem_apresenta="Parceiro A",
        pesquisa=[{"fato": "Abriu filial em Niterói", "fonte": "https://exemplo.com/noticia"}],
        bloqueados=set(),
    )
    campos.update(mudancas)
    return {c.regra: c for c in conferir(**campos)}


def test_mensagem_limpa_passa_em_tudo():
    resultado = _conferencias()
    assert all(c.ok for c in resultado.values())
    assert pode_aprovar(list(resultado.values()))


@pytest.mark.parametrize(
    "trecho",
    ["por R$ 44.000", "o preço fica", "honorário mensal", "com desconto", "uns 40 mil"],
)
def test_mensagem_com_preco_nao_passa(trecho):
    resultado = _conferencias(mensagem=f"Olá, Ana. {trecho}.")
    assert not resultado["sem_preco"].ok
    assert "preço" in resultado["sem_preco"].texto


def test_colchete_para_preencher_trava():
    resultado = _conferencias(mensagem="Olá, [nome]. Na semana de [data].")
    assert not resultado["colchetes"].ok


def test_contato_nao_contatar_trava_mesmo_com_caixa_diferente():
    resultado = _conferencias(
        destinatario="Diretor@Empresa.com.br", bloqueados={"diretor@empresa.com.br"}
    )
    assert not resultado["nao_contatar"].ok


def test_fato_sem_fonte_trava():
    resultado = _conferencias(pesquisa=[{"fato": "Cresceu 30%", "fonte": ""}])
    assert not resultado["fontes"].ok


def test_email_invalido_e_telefone_sem_ddd():
    assert not _conferencias(destinatario="sem-arroba")["destinatario"].ok
    assert not _conferencias(canal=W, destinatario="9999-1234")["destinatario"].ok
    assert _conferencias(canal=W, destinatario="(21) 99999-1234")["destinatario"].ok


def test_sem_quem_apresenta_trava_e_vira_bloqueada():
    assert not _conferencias(quem_apresenta=" ")["quem_apresenta"].ok
    assert situacao_exibida(SituacaoAbordagem.A_PREPARAR, None) is SituacaoAbordagem.BLOQUEADA
    assert (
        situacao_exibida(SituacaoAbordagem.A_PREPARAR, "Parceiro A") is SituacaoAbordagem.A_PREPARAR
    )
    # Só "a preparar" vira bloqueada: um rascunho pronto continua como está.
    assert (
        situacao_exibida(SituacaoAbordagem.AGUARDANDO_APROVACAO, None)
        is SituacaoAbordagem.AGUARDANDO_APROVACAO
    )


def test_telefone_brasileiro_ganha_o_55():
    assert normalizar_destino(W, "(21) 99999-1234") == "5521999991234"
    assert normalizar_destino(W, "+55 21 99999-1234") == "5521999991234"


def test_link_do_whatsapp_leva_o_texto_codificado():
    link = link_whatsapp("(21) 99999-1234", "Olá & até já")
    assert link == "https://wa.me/5521999991234?text=Ol%C3%A1%20%26%20at%C3%A9%20j%C3%A1"
    assert link_whatsapp("123", "x") is None


def test_proximo_passo():
    assert proximo_passo(SituacaoAbordagem.BLOQUEADA, False) == "Definir quem apresenta"
    assert proximo_passo(SituacaoAbordagem.ENVIADA, True) == "Fazer o diagnóstico"
