"""A carga grava, reconhece o que já está lá e diz o que mudou."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.carga.persistencia import importar
from crm.carga.planilha_2026 import Proposta
from crm.db.modelos import GrupoEconomico, Oportunidade
from crm.domain.listas import (
    LinhaServico,
    MotivoRecusa,
    Origem,
    Situacao,
    SituacaoGrupo,
    Temperatura,
    TipoCanal,
)


def proposta(**campos) -> Proposta:
    """Uma proposta de 2026 plausível, com os campos que o teste quiser trocar."""
    base = dict(
        linha=1,
        nome_oportunidade="Sogamax",
        data_colocacao=date(2026, 1, 1),
        servico="BPO Contábil",
        tipo_servico="Recorrente",
        linha_servico=LinhaServico.C1,
        captador="MO",
        canal="Renê Dutra",
        tipo_canal=TipoCanal.PARCEIROS,
        situacao=Situacao.ENVIAR_PROPOSTA,
        temperatura=Temperatura.MORNO,
        data_aceite=None,
        motivo_recusa=None,
        motivo_recusa_original=None,
        preco_mensal=Decimal("5000.00"),
        preco_anual=Decimal("65000.00"),
        valor_mensalizado=Decimal("5416.67"),
    )
    base.update(campos)
    return Proposta(**base)


class TestPrimeiraCarga:
    def test_cria_a_oportunidade_e_o_grupo(self, sessao: Session):
        resultado = importar(sessao, [proposta()])

        assert (resultado.criadas, resultado.grupos_criados) == (1, 1)
        gravada = sessao.scalar(sa.select(Oportunidade))
        assert gravada.nome == "Sogamax"
        assert gravada.origem is Origem.CARGA_2026
        assert gravada.chave_origem

    def test_o_grupo_nasce_prospect_e_marcado_como_vindo_da_carga(self, sessao: Session):
        importar(sessao, [proposta()])

        grupo = sessao.scalar(sa.select(GrupoEconomico))
        assert grupo.situacao is SituacaoGrupo.PROSPECT
        assert grupo.origem is Origem.CARGA_2026

    def test_propostas_do_mesmo_cliente_dividem_o_grupo(self, sessao: Session):
        """Se duas linhas dizem o mesmo nome, são o mesmo cliente — e isso o
        dado sustenta sozinho, sem ninguém decidir nada."""
        resultado = importar(
            sessao,
            [
                proposta(linha=1, tipo_servico="Recorrente"),
                proposta(linha=2, tipo_servico="Financial Advisory"),
            ],
        )

        assert resultado.criadas == 2
        assert resultado.grupos_criados == 1
        assert resultado.grupos_reaproveitados == 1

    def test_o_nome_do_grupo_ignora_caixa(self, sessao: Session):
        resultado = importar(
            sessao,
            [
                proposta(linha=1, nome_oportunidade="Sogamax"),
                proposta(linha=2, nome_oportunidade="SOGAMAX", tipo_servico="Consultoria"),
            ],
        )

        assert resultado.grupos_criados == 1

    def test_guarda_a_linha_da_planilha_para_o_relatorio(self, sessao: Session):
        importar(sessao, [proposta(linha=280)])

        assert sessao.scalar(sa.select(Oportunidade)).linha_planilha == 280


class TestRecarga:
    """A decisão de rodar em paralelo torna a recarga rotina, não exceção."""

    def test_rodar_de_novo_nao_cria_nada(self, sessao: Session):
        entrada = [proposta()]
        importar(sessao, entrada)

        segunda = importar(sessao, entrada)

        assert (segunda.criadas, segunda.atualizadas, segunda.inalteradas) == (0, 0, 1)
        assert sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade)) == 1

    def test_rodar_de_novo_nao_duplica_o_grupo(self, sessao: Session):
        entrada = [proposta()]
        importar(sessao, entrada)
        importar(sessao, entrada)

        assert sessao.scalar(sa.select(sa.func.count()).select_from(GrupoEconomico)) == 1

    def test_inserir_uma_linha_acima_nao_confunde_a_identidade(self, sessao: Session):
        """O motivo de a chave não ser o número da linha."""
        importar(sessao, [proposta(linha=10)])

        segunda = importar(sessao, [proposta(linha=11)])

        assert segunda.criadas == 0
        assert sessao.scalar(sa.select(Oportunidade)).linha_planilha == 11

    def test_mudanca_de_situacao_e_aplicada_e_relatada(self, sessao: Session):
        importar(sessao, [proposta()])

        segunda = importar(
            sessao, [proposta(situacao=Situacao.ACEITA, data_aceite=date(2026, 4, 1))]
        )

        assert segunda.atualizadas == 1
        campos = {m.campo for m in segunda.mudancas}
        assert campos == {"situacao", "data_aceite"}
        assert sessao.scalar(sa.select(Oportunidade)).situacao is Situacao.ACEITA

    def test_a_mudanca_guarda_o_antes_e_o_depois(self, sessao: Session):
        """Quem confere precisa ver o que mudou, não só que mudou."""
        importar(sessao, [proposta()])

        segunda = importar(sessao, [proposta(preco_mensal=Decimal("6000.00"))])

        mudanca = next(m for m in segunda.mudancas if m.campo == "preco_mensal")
        assert (mudanca.de, mudanca.para) == (Decimal("5000.00"), Decimal("6000.00"))
        assert "5000" in mudanca.texto and "6000" in mudanca.texto

    def test_o_que_sumiu_da_planilha_continua_no_crm(self, sessao: Session):
        """Sumir de uma planilha não é decisão de negócio — pode ser filtro."""
        importar(sessao, [proposta(linha=1), proposta(linha=2, nome_oportunidade="Tabor")])

        importar(sessao, [proposta(linha=1)])

        assert sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade)) == 2


class TestDinheiro:
    def test_arredonda_para_centavos(self, sessao: Session):
        importar(sessao, [proposta(preco_mensal=Decimal("189673.1701255126"))])

        assert sessao.scalar(sa.select(Oportunidade)).preco_mensal == Decimal("189673.17")

    def test_o_arredondamento_nao_acontece_em_silencio(self, sessao: Session):
        resultado = importar(sessao, [proposta(preco_mensal=Decimal("189673.1701255126"))])

        assert any("arredondado" in aviso for aviso in resultado.avisos)

    def test_valor_ja_em_centavos_nao_gera_aviso(self, sessao: Session):
        resultado = importar(sessao, [proposta(preco_mensal=Decimal("5000.00"))])

        assert not any("arredondado" in aviso for aviso in resultado.avisos)

    def test_o_arredondamento_nao_vira_falsa_mudanca_na_recarga(self, sessao: Session):
        """Sem isto, toda recarga acusaria mudança de preço que não houve."""
        entrada = [proposta(preco_mensal=Decimal("189673.1701255126"))]
        importar(sessao, entrada)

        segunda = importar(sessao, entrada)

        assert segunda.mudancas == []
        assert segunda.inalteradas == 1


class TestOQueNaoEntra:
    def test_proposta_sem_nome_nao_vira_oportunidade(self, sessao: Session):
        resultado = importar(sessao, [proposta(nome_oportunidade=None)])

        assert resultado.ignoradas_incompletas == 1
        assert resultado.criadas == 0
        assert any("sem nome" in aviso for aviso in resultado.avisos)

    def test_proposta_sem_situacao_nao_vira_oportunidade(self, sessao: Session):
        resultado = importar(sessao, [proposta(situacao=None)])

        assert resultado.ignoradas_incompletas == 1

    def test_linha_repetida_entra_uma_vez_so(self, sessao: Session):
        """O defeito das linhas 317 e 318 da planilha real."""
        resultado = importar(sessao, [proposta(linha=317), proposta(linha=318)])

        assert resultado.criadas == 1
        assert resultado.ignoradas_duplicatas == 1
        assert any("idênticas" in aviso for aviso in resultado.avisos)

    def test_a_primeira_linha_e_a_que_fica(self, sessao: Session):
        importar(sessao, [proposta(linha=317), proposta(linha=318)])

        assert sessao.scalar(sa.select(Oportunidade)).linha_planilha == 317

    def test_cenarios_alternativos_nao_sao_duplicatas(self, sessao: Session):
        """Mesmo cliente, mesma data, serviços diferentes: propostas distintas.
        Fundi-las apagaria a negociação."""
        resultado = importar(
            sessao,
            [
                proposta(linha=1, tipo_servico="Recorrente", preco_anual=Decimal("30000")),
                proposta(linha=2, tipo_servico="Projeto", preco_anual=Decimal("150000")),
            ],
        )

        assert resultado.criadas == 2
        assert resultado.ignoradas_duplicatas == 0


class TestRelatorio:
    def test_o_resumo_traz_os_numeros_que_importam(self, sessao: Session):
        resumo = importar(sessao, [proposta()]).resumo()

        assert "Oportunidades criadas:      1" in resumo
        assert "Grupos econômicos criados:  1" in resumo

    def test_o_resumo_lista_as_mudancas(self, sessao: Session):
        importar(sessao, [proposta()])

        resumo = importar(sessao, [proposta(situacao=Situacao.RECUSADA,
                                            motivo_recusa=MotivoRecusa.PRECO)]).resumo()

        assert "Mudanças (2)" in resumo
        assert "situacao" in resumo
