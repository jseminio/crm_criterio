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


class TestRelatorioDeConferencia:
    """A rodada guardada é o que a tela mostra a quem vai confiar (ou não) na base."""

    def _rodar(self, sessao, propostas, avisos=(), arquivo="planilha.xlsx", lidas=10):
        from crm.carga.persistencia import registrar_execucao
        from crm.carga.planilha_2026 import Relatorio

        leitura = Relatorio(total_lidas=lidas, importadas=len(propostas))
        leitura.avisos.extend(avisos)
        resultado = importar(sessao, propostas)
        return registrar_execucao(sessao, arquivo, leitura, resultado), resultado

    def test_guarda_os_numeros_da_leitura_e_da_gravacao(self, sessao: Session):
        execucao, _ = self._rodar(sessao, [proposta()], lidas=436)

        assert execucao.lidas == 436
        assert execucao.criadas == 1
        assert execucao.grupos_criados == 1

    def test_gravadas_soma_o_que_esta_no_crm_depois_da_rodada(self, sessao: Session):
        """Numa recarga sem mudança, 'criadas' é zero — e o que a pessoa quer saber
        é quantas estão lá, não quantas foram novas."""
        entrada = [proposta()]
        importar(sessao, entrada)

        execucao, _ = self._rodar(sessao, entrada)

        assert (execucao.criadas, execucao.inalteradas) == (0, 1)
        assert execucao.gravadas == 1

    def test_aviso_que_bloqueia_pede_uma_pessoa(self, sessao: Session):
        from crm.carga.planilha_2026 import Aviso

        execucao, _ = self._rodar(
            sessao, [proposta()], [Aviso(9, "situação", "fora da lista", bloqueia=True)]
        )

        assert [o.tipo.value for o in execucao.ocorrencias] == ["Precisa de você"]

    def test_registro_que_entrou_mas_so_uma_pessoa_completa_tambem_pede_uma_pessoa(
        self, sessao: Session
    ):
        """A aceita sem data entra no CRM — e mesmo assim alguém precisa preenchê-la."""
        from crm.carga.planilha_2026 import Aviso

        execucao, _ = self._rodar(
            sessao,
            [proposta()],
            [Aviso(9, "data de aceite", "aceita sem data", acao_humana=True)],
        )

        assert execucao.ocorrencias[0].tipo.value == "Precisa de você"

    def test_conversao_automatica_e_um_ajuste(self, sessao: Session):
        from crm.carga.planilha_2026 import Aviso

        execucao, _ = self._rodar(
            sessao, [proposta()], [Aviso(9, "tipo de canal", "'Socio' convertido para 'Sócios'")]
        )

        assert execucao.ocorrencias[0].tipo.value == "Ajustado sozinho"

    def test_mudanca_na_recarga_aparece_legivel(self, sessao: Session):
        """'Enviar proposta → Aceita', não '<Situacao.ACEITA: ...>'."""
        importar(sessao, [proposta()])

        execucao, _ = self._rodar(
            sessao, [proposta(situacao=Situacao.ACEITA, data_aceite=date(2026, 4, 1))]
        )

        mudancas = [o for o in execucao.ocorrencias if o.tipo.value == "Mudou na recarga"]
        situacao = next(o for o in mudancas if o.campo == "situacao")
        assert situacao.texto == "Sogamax: Enviar proposta → Aceita"
        assert "<" not in situacao.texto

    def test_linha_incompleta_ja_explicada_pela_leitura_nao_e_contada_duas_vezes(
        self, sessao: Session
    ):
        from crm.carga.planilha_2026 import Aviso

        execucao, _ = self._rodar(
            sessao,
            [proposta(linha=5, nome_oportunidade=None)],
            [Aviso(5, "nome", "linha sem nome de oportunidade", bloqueia=True)],
        )

        da_linha_5 = [o for o in execucao.ocorrencias if o.linha == 5]
        assert len(da_linha_5) == 1

    def test_linha_incompleta_sem_aviso_da_leitura_ainda_e_registrada(self, sessao: Session):
        execucao, _ = self._rodar(sessao, [proposta(linha=5, nome_oportunidade=None)])

        assert any(o.campo == "linha incompleta" for o in execucao.ocorrencias)

    def test_duplicata_vira_pendencia_com_a_primeira_linha(self, sessao: Session):
        execucao, _ = self._rodar(sessao, [proposta(linha=317), proposta(linha=318)])

        duplicata = next(o for o in execucao.ocorrencias if o.campo == "linha duplicada")
        assert duplicata.tipo.value == "Precisa de você"
        assert duplicata.linha == 317

    def test_guarda_so_o_nome_do_arquivo(self, sessao: Session):
        """O caminho revela a estrutura de pastas de quem rodou e não ajuda a conferir."""
        unix, _ = self._rodar(sessao, [proposta()], arquivo="/Users/alguem/Downloads/planilha.xlsx")
        win, _ = self._rodar(sessao, [proposta()], arquivo="C:\\pasta\\planilha.xlsx")

        assert unix.arquivo == "planilha.xlsx"
        assert win.arquivo == "planilha.xlsx"

    def test_cada_rodada_e_um_registro_novo_e_o_historico_fica(self, sessao: Session):
        entrada = [proposta()]
        self._rodar(sessao, entrada)
        self._rodar(sessao, entrada)

        from crm.db.modelos import ExecucaoDeCarga

        assert sessao.scalar(sa.select(sa.func.count()).select_from(ExecucaoDeCarga)) == 2

    def test_a_data_da_rodada_tem_fuso(self, sessao: Session):
        execucao, _ = self._rodar(sessao, [proposta()])

        assert execucao.executada_em.tzinfo is not None


class TestEdicaoNoCrmSobreviveARecarga:
    """A planilha e o CRM editam a mesma oportunidade, em paralelo.

    Sem estas travas, preencher a data do aceite na tela e rodar a carga de novo
    a apagava — a planilha não tem nenhuma. Foi provado antes da correção.
    """

    def _editar_no_crm(self, sessao, **campos):
        op = sessao.scalar(sa.select(Oportunidade))
        for campo, valor in campos.items():
            setattr(op, campo, valor)
        op.campos_do_crm = sorted(set(op.campos_do_crm or []) | set(campos))
        sessao.flush()
        return op

    def test_a_data_de_aceite_preenchida_na_tela_nao_e_apagada(self, sessao: Session):
        """O caso que falhava: a planilha não tem a data, o CRM tem."""
        entrada = [proposta(situacao=Situacao.ACEITA, data_aceite=None)]
        importar(sessao, entrada)
        op = self._editar_no_crm(sessao, data_aceite=date(2026, 4, 15))

        importar(sessao, entrada)

        assert op.data_aceite == date(2026, 4, 15)

    def test_a_divergencia_vira_pendencia_e_nao_mudanca(self, sessao: Session):
        """Mantém o do CRM e deixa à vista — quem decide qual vale é uma pessoa."""
        entrada = [proposta(situacao=Situacao.ACEITA, data_aceite=None)]
        importar(sessao, entrada)
        self._editar_no_crm(sessao, data_aceite=date(2026, 4, 15))

        resultado = importar(sessao, entrada)

        assert resultado.mudancas == []
        conflito = next(o for o in resultado.ocorrencias if o.campo == "data_aceite")
        assert conflito.tipo.value == "Precisa de você"
        assert "mantido o do CRM" in conflito.texto
        assert "15" in conflito.texto or "2026-04-15" in conflito.texto

    def test_campo_editado_no_crm_que_a_planilha_concorda_nao_gera_conflito(
        self, sessao: Session
    ):
        """Divergência é o que importa. Se os dois dizem o mesmo, não há o que decidir."""
        importar(sessao, [proposta(situacao=Situacao.ENVIAR_PROPOSTA)])
        self._editar_no_crm(sessao, situacao=Situacao.ACEITA, data_aceite=date(2026, 4, 1))

        resultado = importar(
            sessao, [proposta(situacao=Situacao.ACEITA, data_aceite=date(2026, 4, 1))]
        )

        assert resultado.ocorrencias == []
        assert resultado.mudancas == []

    def test_o_que_nao_foi_editado_no_crm_continua_seguindo_a_planilha(self, sessao: Session):
        """A trava é por campo, não por oportunidade: senão editar uma observação
        congelaria a linha inteira e a planilha deixaria de valer para o resto."""
        importar(sessao, [proposta(temperatura=Temperatura.MORNO)])
        self._editar_no_crm(sessao, data_aceite=date(2026, 4, 1))

        resultado = importar(sessao, [proposta(temperatura=Temperatura.QUENTE)])

        assert {m.campo for m in resultado.mudancas} == {"temperatura"}
        assert sessao.scalar(sa.select(Oportunidade)).temperatura is Temperatura.QUENTE

    def test_a_recarga_sem_edicao_no_crm_segue_igual_ao_de_antes(self, sessao: Session):
        """A trava nova não pode alterar o comportamento de quem nunca editou."""
        importar(sessao, [proposta()])

        resultado = importar(sessao, [proposta(situacao=Situacao.ACEITA, data_aceite=date(2026, 4, 1))])

        assert {m.campo for m in resultado.mudancas} == {"situacao", "data_aceite"}

    def test_a_pendencia_de_conflito_entra_no_relatorio_de_conferencia(self, sessao: Session):
        from crm.carga.persistencia import registrar_execucao
        from crm.carga.planilha_2026 import Relatorio

        entrada = [proposta(situacao=Situacao.ACEITA, data_aceite=None)]
        importar(sessao, entrada)
        self._editar_no_crm(sessao, data_aceite=date(2026, 4, 15))

        resultado = importar(sessao, entrada)
        execucao = registrar_execucao(sessao, "p.xlsx", Relatorio(total_lidas=1, importadas=1), resultado)

        conflitos = [o for o in execucao.ocorrencias if "mantido o do CRM" in o.texto]
        assert len(conflitos) == 1
        assert conflitos[0].tipo.value == "Precisa de você"


class TestHistoricoDePrecoNaRecarga:
    def test_reajuste_vindo_da_planilha_entra_no_historico(self, sessao: Session):
        from crm.db.modelos import HistoricoDePreco

        importar(sessao, [proposta()])
        importar(sessao, [proposta(preco_mensal=Decimal("5500.00"), preco_anual=Decimal("71500.00"))])
        h = sessao.scalars(sa.select(HistoricoDePreco)).one()
        assert h.origem == "Recarga da planilha"
        assert (h.preco_mensal_anterior, h.preco_mensal_novo) == (Decimal("5000.00"), Decimal("5500.00"))

    def test_recarga_sem_mudanca_de_preco_nao_cria_historico(self, sessao: Session):
        from crm.db.modelos import HistoricoDePreco

        importar(sessao, [proposta()])
        importar(sessao, [proposta(situacao=Situacao.EM_AVALIACAO)])
        assert sessao.scalar(sa.select(sa.func.count()).select_from(HistoricoDePreco)) == 0


class TestAceiteFazCliente:
    def test_a_recarga_promove_a_cliente_o_grupo_com_proposta_aceita(self, sessao: Session):
        importar(sessao, [
            proposta(nome_oportunidade="Fechou", linha=1, situacao=Situacao.ACEITA, data_aceite=date(2026, 5, 1)),
            proposta(nome_oportunidade="Em aberto", linha=2),
        ])
        grupos = {g.nome: g.situacao for g in sessao.scalars(sa.select(GrupoEconomico))}
        assert grupos["Fechou"] is SituacaoGrupo.CLIENTE and grupos["Em aberto"] is SituacaoGrupo.PROSPECT

    def test_grupo_fundido_nao_e_promovido(self, sessao: Session):
        importar(sessao, [proposta(nome_oportunidade="X", situacao=Situacao.ACEITA, data_aceite=date(2026, 5, 1))])
        g = sessao.scalars(sa.select(GrupoEconomico)).one()
        g.situacao = SituacaoGrupo.FUNDIDO
        sessao.commit()
        importar(sessao, [proposta(nome_oportunidade="X", situacao=Situacao.ACEITA, data_aceite=date(2026, 5, 1))])
        assert sessao.scalars(sa.select(GrupoEconomico)).one().situacao is SituacaoGrupo.FUNDIDO
