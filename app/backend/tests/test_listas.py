"""As listas controladas e o de-para da planilha de 2026.

Os valores de entrada destes testes são os que aparecem de verdade na aba
``Propostas`` da planilha de performance — incluindo as grafias duplicadas e o
valor fora de domínio. Se o de-para deixar de cobri-los, a carga quebra.
"""

import pytest

from crm.domain.listas import (
    LinhaServico,
    MotivoRecusa,
    Situacao,
    Temperatura,
    TipoCanal,
    normalizar_captador,
    normalizar_linha_servico,
    normalizar_motivo_recusa,
    normalizar_situacao,
    normalizar_temperatura,
    normalizar_tipo_canal,
)


class TestSituacao:
    @pytest.mark.parametrize(
        "bruto, esperado",
        [
            ("Enviar proposta", Situacao.ENVIAR_PROPOSTA),
            ("Enviar Proposta", Situacao.ENVIAR_PROPOSTA),  # a segunda grafia de 2026
            ("Em avaliação pela empresa", Situacao.EM_AVALIACAO),
            ("On hold", Situacao.ON_HOLD),
            ("Aceita", Situacao.ACEITA),
            ("Aceita ", Situacao.ACEITA),  # com espaço no fim, do histórico
            ("Recusada", Situacao.RECUSADA),
            ("Recusada ", Situacao.RECUSADA),
            ("Perdido", Situacao.PERDIDO),
        ],
    )
    def test_converte_as_grafias_da_planilha(self, bruto, esperado):
        assert normalizar_situacao(bruto).valor is esperado

    def test_as_duas_grafias_de_enviar_proposta_viram_o_mesmo_valor(self):
        assert (
            normalizar_situacao("Enviar proposta").valor
            is normalizar_situacao("Enviar Proposta").valor
        )

    def test_grafia_divergente_gera_aviso(self):
        resultado = normalizar_situacao("Enviar Proposta")
        assert resultado.ajustado
        assert "convertido" in resultado.aviso

    def test_grafia_canonica_nao_gera_aviso(self):
        assert normalizar_situacao("Aceita").aviso is None

    def test_desconhecida_nao_vira_valor_e_avisa(self):
        resultado = normalizar_situacao("Em negociação avançada")
        assert not resultado.ok
        assert "fora da lista" in resultado.aviso

    def test_decididas_sao_as_terminais(self):
        decididas = {s for s in Situacao if s.decidida}
        assert decididas == {Situacao.ACEITA, Situacao.RECUSADA, Situacao.PERDIDO}

    def test_so_aceita_e_ganha(self):
        assert [s for s in Situacao if s.ganha] == [Situacao.ACEITA]


class TestTipoCanal:
    def test_socio_e_socios_viram_o_mesmo_valor(self):
        """Em 2026 a planilha tem 'Socio' (77) e 'Sócios' (9) separados."""
        assert (
            normalizar_tipo_canal("Socio").valor
            is normalizar_tipo_canal("Sócios").valor
            is TipoCanal.SOCIOS
        )

    @pytest.mark.parametrize(
        "bruto, esperado",
        [
            ("Parceiros", TipoCanal.PARCEIROS),
            ("Advogados", TipoCanal.ADVOGADOS),
            ("Carteira", TipoCanal.CARTEIRA),
            ("Interno", TipoCanal.INTERNO),
            ("Colaboradores", TipoCanal.COLABORADORES),
        ],
    )
    def test_converte_os_canais_de_2026(self, bruto, esperado):
        assert normalizar_tipo_canal(bruto).valor is esperado

    def test_trafego_pago_e_afiliados_existem_mas_nao_operam(self):
        fora = {c for c in TipoCanal if not c.em_operacao}
        assert fora == {TipoCanal.TRAFEGO_PAGO, TipoCanal.AFILIADOS}

    def test_os_canais_de_2026_estao_todos_em_operacao(self):
        for bruto in ("Socio", "Parceiros", "Advogados", "Carteira", "Interno"):
            assert normalizar_tipo_canal(bruto).valor.em_operacao


class TestTemperatura:
    @pytest.mark.parametrize("bruto", ["Frio", "Frio ", "Morno", "Quente"])
    def test_converte_as_tres_temperaturas(self, bruto):
        assert normalizar_temperatura(bruto).ok

    def test_captacao_de_recursos_nao_e_temperatura(self):
        """Valor fora de domínio encontrado em uma linha de 2026."""
        resultado = normalizar_temperatura("Captação de recursos")
        assert not resultado.ok
        assert "fora da lista" in resultado.aviso


class TestLinhaServico:
    def test_c1_e_c2_com_espaco_convertem(self):
        assert normalizar_linha_servico("C1 ").valor is LinhaServico.C1
        assert normalizar_linha_servico("C2 ").valor is LinhaServico.C2

    def test_a_descricao_diz_o_que_cada_linha_reune(self):
        assert "contábil" in LinhaServico.C1.descricao
        assert "Consultoria" in LinhaServico.C2.descricao


class TestMotivoRecusa:
    @pytest.mark.parametrize(
        "bruto, esperado",
        [
            ("Preço", MotivoRecusa.PRECO),
            ("Sem retorno", MotivoRecusa.SEM_RETORNO),
            ("Não nos retornou", MotivoRecusa.SEM_RETORNO),
            ("Desistência", MotivoRecusa.DESISTENCIA),
            ("Possível desistência", MotivoRecusa.DESISTENCIA),
            ("Cliente internalizou", MotivoRecusa.CLIENTE_INTERNALIZOU),
            ("PRO-BONO", MotivoRecusa.PRO_BONO),
            ("Momento", MotivoRecusa.MOMENTO),
        ],
    )
    def test_converte_os_motivos_de_2026(self, bruto, esperado):
        assert normalizar_motivo_recusa(bruto).valor is esperado

    @pytest.mark.parametrize(
        "bruto", ["Em formalização", "Em avaliação pela empresa", "Proposta reajustada"]
    )
    def test_o_que_e_situacao_nao_vira_motivo(self, bruto):
        """A planilha mistura motivo com estado; o de-para separa e avisa."""
        resultado = normalizar_motivo_recusa(bruto)
        assert not resultado.ok
        assert "situação, não motivo" in resultado.aviso


class TestCaptador:
    @pytest.mark.parametrize("sigla", ["BO", "EL", "TC", "FS", "JC", "MO", "JS"])
    def test_os_sete_captadores_de_2026(self, sigla):
        assert normalizar_captador(sigla).valor == sigla

    def test_an_vira_bo_por_decisao_de_eduardo(self):
        resultado = normalizar_captador("AN")
        assert resultado.valor == "BO"
        assert "decisão de Eduardo" in resultado.aviso

    def test_com_espaco_converte_e_avisa(self):
        resultado = normalizar_captador("FS ")
        assert resultado.valor == "FS"
        assert resultado.ajustado

    def test_sigla_desconhecida_avisa(self):
        assert not normalizar_captador("XY").ok


class TestCamposVazios:
    @pytest.mark.parametrize(
        "funcao",
        [
            normalizar_situacao,
            normalizar_tipo_canal,
            normalizar_temperatura,
            normalizar_motivo_recusa,
            normalizar_captador,
        ],
    )
    @pytest.mark.parametrize("vazio", [None, "", "   "])
    def test_vazio_nunca_estoura_e_sempre_avisa(self, funcao, vazio):
        resultado = funcao(vazio)
        assert not resultado.ok
        assert resultado.aviso
