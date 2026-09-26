"""Busca sem acento e lacunas de contato."""

from __future__ import annotations

from dataclasses import dataclass

from crm.domain.contatos import LACUNAS, casa, lacunas_de, normalizar


@dataclass
class P:
    nome: str = "Maria"
    email: str | None = None
    telefone: str | None = None


@dataclass
class E:
    logradouro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None


def test_normalizar_tira_acento_caixa_e_espaco():
    assert normalizar("  Ação   ÇÃO ") == "acao cao"
    assert normalizar(None) == ""


def test_busca_ignora_acento_e_caixa():
    assert casa("acao", "Rua Ação") and casa("RIO DE JANEIRO", "rio de janeiro") and not casa("beta", "Alfa")


def test_todas_as_palavras_em_qualquer_ordem_e_em_campos_diferentes():
    assert casa("silva alfa", "Alfa Comércio", "Maria Silva")
    assert not casa("silva gama", "Alfa Comércio", "Maria Silva")


def test_busca_vazia_casa_com_tudo():
    assert casa("", "qualquer") and casa("   ")


def test_numeros_comparam_sem_pontuacao():
    assert casa("11222333", "11.222.333/0001-81")
    assert casa("20040020", "20040-020")
    assert casa("99999", "(21) 99999-0000")
    assert not casa("99998", "(21) 99999-0000")


def test_sem_nada_faltam_os_sete_itens():
    assert lacunas_de(None, []) == list(LACUNAS)


def test_com_tudo_preenchido_nao_falta_nada():
    assert lacunas_de(E("Rua A", "Rio", "RJ", "20040020"), [P("Maria", "m@a.com", "2199")]) == []


def test_varios_contatos_completam_uns_aos_outros():
    ps = [P("Ana", "a@a.com", None), P("Beto", None, "2199")]
    assert lacunas_de(E("Rua A", "Rio", "RJ", "20040020"), ps) == []


def test_contato_sem_nome_nao_conta_como_contato():
    assert "Contato" in lacunas_de(E("Rua A", "Rio", "RJ", "1"), [P("  ", "m@a.com", "2199")])


def test_endereco_parcial_lista_so_o_que_falta():
    assert lacunas_de(E("Rua A", None, "RJ", None), [P("Ana", "a@a.com", "2199")]) == ["Município", "CEP"]
