"""A carga das propostas de 2026 e o relatório de conferência."""

from datetime import date
from decimal import Decimal

import pytest

from crm.carga.planilha_2026 import carregar
from crm.domain.listas import Situacao, TipoCanal


def linha(**campos):
    """Uma linha da planilha, com os campos mínimos preenchidos."""
    base = {
        "Ano": 2026,
        "Nome da oportunidade": "Grupo Exemplo",
        "Status": "Aceita",
        "Tipo Canal": "Socio",
        "Temperatura": "Quente",
        "Responsável": "C1",
        "Responsável 2": "EL",
        "Preço mensal": 5000,
    }
    base.update(campos)
    return base


class TestRecorteDeAno:
    def test_so_2026_entra(self):
        _, rel = carregar([linha(Ano=2026), linha(Ano=2025), linha(Ano=2024)])
        assert rel.importadas == 1
        assert rel.descartadas_outro_ano == 2

    def test_linha_sem_ano_entra(self):
        """A planilha tem o ano preenchido; ausência não descarta em silêncio."""
        _, rel = carregar([linha(Ano=None)])
        assert rel.importadas == 1


class TestNormalizacao:
    def test_as_duas_grafias_de_socio_viram_o_mesmo_canal(self):
        propostas, _ = carregar([linha(**{"Tipo Canal": "Socio"}),
                                 linha(**{"Tipo Canal": "Sócios"})])
        assert {p.tipo_canal for p in propostas} == {TipoCanal.SOCIOS}

    def test_an_vira_bo(self):
        propostas, rel = carregar([linha(**{"Responsável 2": "AN"})])
        assert propostas[0].captador == "BO"
        assert any("decisão de Eduardo" in a.texto for a in rel.avisos)

    def test_temperatura_fora_do_dominio_nao_bloqueia_mas_avisa(self):
        propostas, rel = carregar([linha(Temperatura="Captação de recursos")])
        assert propostas[0].temperatura is None
        assert propostas[0].situacao is Situacao.ACEITA  # a linha entra assim mesmo
        assert any(a.campo == "temperatura" for a in rel.avisos)


class TestPreservacaoDoOriginal:
    def test_motivo_que_e_situacao_guarda_o_texto_original(self):
        propostas, rel = carregar(
            [linha(Status="Recusada", **{"Motivo da Recusa": "Em formalização"})]
        )
        assert propostas[0].motivo_recusa is None
        assert propostas[0].motivo_recusa_original == "Em formalização"
        assert any("situação, não motivo" in a.texto for a in rel.avisos)

    def test_nada_e_descartado_em_silencio(self):
        """Todo valor que não converte gera aviso."""
        _, rel = carregar(
            [linha(Status="Situação inventada", **{"Tipo Canal": "Canal inventado"})]
        )
        campos = {a.campo for a in rel.avisos}
        assert {"situação", "tipo de canal"} <= campos


class TestPendencias:
    def test_aceita_sem_data_avisa_sem_bloquear(self):
        """As 40 aceitas de 2026 não têm data; Eduardo preencherá no CRM."""
        _, rel = carregar([linha(Status="Aceita", **{"Data do aceite": None})])
        aviso = next(a for a in rel.avisos if a.campo == "data de aceite")
        assert not aviso.bloqueia
        assert "Eduardo preencherá" in aviso.texto

    def test_aceita_com_data_nao_avisa(self):
        _, rel = carregar(
            [linha(Status="Aceita", **{"Data do aceite": date(2026, 3, 10)})]
        )
        assert not [a for a in rel.avisos if a.campo == "data de aceite"]

    def test_preco_vazio_e_intencional(self):
        _, rel = carregar([linha(**{"Preço mensal": None})])
        aviso = next(a for a in rel.avisos if a.campo == "preço mensal")
        assert not aviso.bloqueia
        assert "intencional" in aviso.texto

    def test_linha_sem_nome_bloqueia(self):
        propostas, rel = carregar([linha(**{"Nome da oportunidade": None})])
        assert not propostas[0].completa
        assert any(a.campo == "nome" and a.bloqueia for a in rel.avisos)

    def test_situacao_desconhecida_bloqueia(self):
        _, rel = carregar([linha(Status="Qualquer coisa")])
        assert rel.com_pendencia == 1


class TestValores:
    def test_precos_viram_decimal(self):
        propostas, _ = carregar(
            [linha(**{"Preço mensal": 4500, "Preço anual": 58500,
                      "Valor mensalizado": 4875})]
        )
        p = propostas[0]
        assert p.preco_mensal == Decimal("4500")
        assert p.preco_anual == Decimal("58500")
        assert p.valor_mensalizado == Decimal("4875")

    def test_valor_ilegivel_nao_estoura(self):
        """A planilha tem uma célula com #DIV/0!."""
        propostas, _ = carregar([linha(**{"Preço anual": "#DIV/0!"})])
        assert propostas[0].preco_anual is None


class TestRelatorio:
    def test_conta_ajuste_e_pendencia_por_linha_nao_por_aviso(self):
        _, rel = carregar(
            [linha(**{"Tipo Canal": "Sócios", "Responsável 2": "FS "})]  # 2 ajustes
        )
        assert rel.com_ajuste == 1

    def test_resumo_traz_os_numeros_que_importam(self):
        _, rel = carregar([linha(), linha(Ano=2024)])
        texto = rel.resumo()
        assert "Lidas: 2" in texto
        assert "Importadas: 1" in texto
        assert "De outro ano, ignoradas: 1" in texto

    def test_carga_vazia_nao_estoura(self):
        propostas, rel = carregar([])
        assert propostas == []
        assert rel.total_lidas == 0


class TestLinhasResiduais:
    """A planilha tem, no fim da aba, linhas com valores soltos — sobra de
    cálculo em colunas sem cabeçalho, não propostas."""

    def test_sem_nome_e_sem_situacao_e_ignorada(self):
        _, rel = carregar([{"Ano": None, "Preço anual": 4500000}])
        assert rel.importadas == 0
        assert rel.descartadas_residuais == 1

    def test_residual_aparece_no_relatorio(self):
        _, rel = carregar([{"Ano": None, "Preço anual": 4500000}])
        assert any(a.campo == "linha residual" for a in rel.avisos)
        assert "Residuais, ignoradas: 1" in rel.resumo()

    def test_linha_sem_nome_mas_com_situacao_ainda_entra(self):
        """Falta de nome é pendência a resolver, não motivo para descartar."""
        propostas, rel = carregar([linha(**{"Nome da oportunidade": None})])
        assert rel.importadas == 1
        assert rel.descartadas_residuais == 0
        assert not propostas[0].completa
