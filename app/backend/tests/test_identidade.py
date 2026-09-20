"""A identidade da proposta na planilha — a chave que permite recarregar."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from crm.carga.identidade import chave_de_origem, detectar_duplicatas


@dataclass(frozen=True)
class Falsa:
    """O mínimo que a identidade precisa ler, mais os campos comparados."""

    linha: int = 1
    nome_oportunidade: str | None = "Sogamax"
    data_colocacao: date | None = date(2026, 1, 1)
    servico: str | None = "BPO Contábil"
    tipo_servico: str | None = "Recorrente"
    linha_servico: str | None = None
    captador: str | None = "MO"
    canal: str | None = None
    tipo_canal: str | None = None
    situacao: str | None = "Recusada"
    temperatura: str | None = None
    data_aceite: date | None = None
    motivo_recusa: str | None = None
    motivo_recusa_original: str | None = None
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    valor_mensalizado: Decimal | None = None


class TestChave:
    def test_a_chave_ignora_caixa_acento_e_espaco(self):
        """Recarregar não pode duplicar porque alguém corrigiu a grafia."""
        assert chave_de_origem(Falsa(nome_oportunidade="  SOGAMÁX ")) == chave_de_origem(
            Falsa(nome_oportunidade="sogamax")
        )

    def test_a_chave_nao_depende_do_numero_da_linha(self):
        """É o ponto inteiro: inserir uma linha acima não muda identidade."""
        assert chave_de_origem(Falsa(linha=7)) == chave_de_origem(Falsa(linha=402))

    def test_campo_vazio_e_valor_legitimo(self):
        """Há propostas sem data de colocação. Elas precisam de identidade também."""
        assert chave_de_origem(Falsa(data_colocacao=None))

    def test_o_tipo_de_servico_separa_cenarios_do_mesmo_cliente(self):
        """As cinco colisões reais da planilha se resolvem exatamente aqui."""
        assert chave_de_origem(Falsa(tipo_servico="Recorrente")) != chave_de_origem(
            Falsa(tipo_servico="Financial Advisory")
        )


class TestDuplicatas:
    def test_planilha_limpa_nao_gera_nada(self):
        assert detectar_duplicatas([Falsa(linha=1), Falsa(linha=2, nome_oportunidade="Tabor")]) == []

    def test_linhas_identicas_sao_reconhecidas_como_repeticao(self):
        """O defeito encontrado nas linhas 317 e 318 da planilha real."""
        duplicatas = detectar_duplicatas([Falsa(linha=317), Falsa(linha=318)])

        assert len(duplicatas) == 1
        assert duplicatas[0].identicas is True
        assert duplicatas[0].linhas == [317, 318]
        assert "idênticas" in duplicatas[0].texto

    def test_mesma_identidade_com_valores_diferentes_pede_conferencia(self):
        """Aqui o defeito seria da chave, não da planilha — ninguém decide sozinho."""
        base = Falsa(linha=10, preco_anual=Decimal("30000"))
        outra = replace(base, linha=11, preco_anual=Decimal("150000"))

        duplicatas = detectar_duplicatas([base, outra])

        assert duplicatas[0].identicas is False
        assert duplicatas[0].campos_divergentes == ["preco_anual"]
        assert "conferir" in duplicatas[0].texto

    def test_duplicatas_saem_na_ordem_da_planilha(self):
        """Quem confere lê de cima para baixo."""
        itens = [
            Falsa(linha=300, nome_oportunidade="Sales"),
            Falsa(linha=301, nome_oportunidade="Sales"),
            Falsa(linha=100, nome_oportunidade="Tabor"),
            Falsa(linha=101, nome_oportunidade="Tabor"),
        ]
        assert [d.linhas[0] for d in detectar_duplicatas(itens)] == [100, 300]
