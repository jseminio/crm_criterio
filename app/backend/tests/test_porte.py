"""A régua de porte — sempre sugestão, nunca decisão automática.

Ver `regua-de-porte-e-plano-de-teste.md`, seção 2. A régua não está
calibrada — só aferida contra um caso real —, então estes testes cobrem a
matemática que o documento especifica, não se ela está "certa".
"""

from __future__ import annotations

from decimal import Decimal

from crm.domain.porte import Porte, Volumetria, sugerir_porte


class TestPontuacaoPorDirecionador:
    def test_sem_nenhum_direcionador_aplicavel_nao_calcula(self):
        sugestao = sugerir_porte(Volumetria())

        assert sugestao.calculavel is False
        assert sugestao.pontuacao is None
        assert sugestao.porte is None

    def test_um_direcionador_so_ja_basta_para_calcular(self):
        sugestao = sugerir_porte(Volumetria(cnpjs_no_escopo=1))

        assert sugestao.calculavel is True
        assert sugestao.direcionadores_aplicados == 1
        assert sugestao.pontuacao == Decimal("0.00")
        assert sugestao.porte is Porte.MICRO

    def test_direcionador_ausente_fica_fora_da_media_nao_vira_zero(self):
        """Um cliente só de DP não pontua documentos fiscais — mas isso não
        pode empurrar a média para baixo como se fosse volume zero."""
        so_dp = sugerir_porte(Volumetria(empregados_clt=200))  # nota 4 sozinho
        com_fiscal_zerado = sugerir_porte(Volumetria(empregados_clt=200, documentos_fiscais_mes=0))

        assert so_dp.pontuacao == Decimal("4.00")
        assert com_fiscal_zerado.pontuacao == Decimal("2.00")  # média de 4 e 0

    def test_faixas_de_documentos_fiscais(self):
        casos = [(50, 0), (51, 1), (150, 1), (151, 2), (600, 3), (601, 4)]
        for volume, pontos_esperados in casos:
            sugestao = sugerir_porte(Volumetria(documentos_fiscais_mes=volume))
            assert sugestao.pontuacao == Decimal(pontos_esperados), volume

    def test_conciliacoes_de_cartao_nenhuma_e_zero_nao_ausente(self):
        """"Nenhuma" é uma resposta (nota 0), diferente de não ter respondido
        (None, fora da média)."""
        nenhuma = sugerir_porte(Volumetria(conciliacoes_cartao_mes=0))
        assert nenhuma.calculavel is True
        assert nenhuma.pontuacao == Decimal("0.00")


class TestAjustes:
    def test_ajuste_de_escopo_tem_teto_em_tres_servicos_adicionais(self):
        base = sugerir_porte(Volumetria(cnpjs_no_escopo=1, servicos_contratados_alem_do_primeiro=0))
        tres = sugerir_porte(Volumetria(cnpjs_no_escopo=1, servicos_contratados_alem_do_primeiro=3))
        dez = sugerir_porte(Volumetria(cnpjs_no_escopo=1, servicos_contratados_alem_do_primeiro=10))

        assert base.pontuacao == Decimal("0.00")
        assert tres.pontuacao == Decimal("0.75")  # 3 × 0,25 = 0,75, no teto
        assert dez.pontuacao == Decimal("0.75")  # trava no teto, não em 2,50

    def test_ajuste_de_grupo_e_de_auditoria_somam(self):
        sugestao = sugerir_porte(
            Volumetria(cnpjs_no_escopo=1, tem_consolidacao_de_grupo=True, e_auditada=True)
        )

        assert sugestao.pontuacao == Decimal("0.75")  # 0 + 0,50 + 0,25


class TestCortesDePorte:
    def test_cada_corte_no_limite_exato(self):
        # base isolada via um único direcionador de nota 0 não alcança os
        # cortes maiores; uso combinações de ajustes para acertar o limite.
        casos = [
            (Decimal("0.74"), Porte.MICRO),
            (Decimal("0.75"), Porte.PEQUENO),
            (Decimal("1.49"), Porte.PEQUENO),
            (Decimal("1.50"), Porte.MEDIO),
            (Decimal("2.24"), Porte.MEDIO),
            (Decimal("2.25"), Porte.GRANDE),
            (Decimal("3.24"), Porte.GRANDE),
            (Decimal("3.25"), Porte.EXTRA_GRANDE),
        ]
        from crm.domain.porte import _cortar  # função privada, só para o teste de limite

        for pontuacao, porte_esperado in casos:
            assert _cortar(pontuacao) is porte_esperado, pontuacao

    def test_horas_base_acompanha_o_porte(self):
        sugestao = sugerir_porte(Volumetria(empregados_clt=200))  # nota 4 -> Extra Grande

        assert sugestao.porte is Porte.EXTRA_GRANDE
        assert sugestao.horas_base == 80


class TestPerfilCompativelComExtraGrande:
    """O documento registra um caso real aferido — grupo home care, quatro
    CNPJs, auditoria externa e consolidação, resultado Extra Grande — mas não
    traz os volumes brutos que a pessoa digitou. Os valores abaixo são
    **fictícios**, montados só para exercitar um perfil no mesmo bairro
    (volumes altos, 4 CNPJs, grupo consolidado, auditada): não são o caso
    real, e não substituem repetir o teste da seção 4 com dado de verdade.
    """

    def test_perfil_de_volume_alto_com_grupo_e_auditoria(self):
        volumetria = Volumetria(
            documentos_fiscais_mes=650,
            lancamentos_contabeis_mes=2200,
            pagamentos_mes=1100,
            contas_bancarias=12,
            conciliacoes_cartao_mes=850,
            empregados_clt=180,
            admissoes_desligamentos_mes=30,
            cnpjs_no_escopo=4,
            tomadores_de_servico=350,
            servicos_contratados_alem_do_primeiro=3,
            tem_consolidacao_de_grupo=True,
            e_auditada=True,
        )

        sugestao = sugerir_porte(volumetria)

        assert sugestao.direcionadores_aplicados == 9
        assert sugestao.porte is Porte.EXTRA_GRANDE
