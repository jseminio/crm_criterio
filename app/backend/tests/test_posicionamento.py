"""O que o CRM escreve para o cliente e para a IA não fala em terceirizar (07/10/2026): a Critério vende
tempo e capacidade de decisão, nunca terceirização de tarefas."""

from __future__ import annotations

from crm.domain.servicos import CATALOGO
from crm.proposta.rascunho import _contextualizacao


def test_o_catalogo_nao_fala_em_terceirizar():
    assert [s.nome for s in CATALOGO if "terceiriz" in s.para_quem.casefold()] == []


def test_a_proposta_de_quem_faz_dentro_de_casa_nao_fala_em_terceirizar():
    texto = _contextualizacao("Exemplo Alfa", {"operacao": "Interna"}, ["Contábil", "Fiscal"])
    assert "terceiriz" not in texto.casefold()
    assert texto.startswith("A Exemplo Alfa avalia contar com um parceiro para os serviços")
