"""As entidades e as travas que elas carregam."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Empresa, GrupoEconomico, Lead, Oportunidade, PessoaContato
from crm.domain.listas import (
    Origem,
    PapelContato,
    Situacao,
    SituacaoEmpresa,
    SituacaoGrupo,
    SituacaoLead,
    TipoCanal,
)


def _grupo(sessao: Session, nome: str = "Grupo Teste", **campos) -> GrupoEconomico:
    grupo = GrupoEconomico(nome=nome, **campos)
    sessao.add(grupo)
    sessao.flush()
    return grupo


class TestGrupoEconomico:
    def test_nasce_prospect_e_criado_no_crm(self, sessao: Session):
        grupo = _grupo(sessao)

        assert grupo.situacao is SituacaoGrupo.PROSPECT
        assert grupo.origem is Origem.CRM
        assert grupo.fundido_em_id is None

    def test_o_carimbo_de_criacao_tem_fuso(self, sessao: Session):
        """Data sem fuso quebra quando o servidor muda de região."""
        assert _grupo(sessao).criado_em.tzinfo is not None

    def test_um_grupo_pode_ter_uma_empresa_so(self, sessao: Session):
        """É o caso mais comum da carteira, não a exceção."""
        grupo = _grupo(sessao)
        sessao.add(Empresa(grupo_id=grupo.id, razao_social="Única Ltda"))
        sessao.flush()

        assert len(grupo.empresas) == 1

    def test_o_banco_recusa_grupo_fundido_em_si_mesmo(self, sessao: Session):
        grupo = _grupo(sessao)
        grupo.fundido_em_id = grupo.id

        with pytest.raises(sa.exc.IntegrityError):
            sessao.flush()


class TestEmpresa:
    def test_cnpj_pode_faltar(self, sessao: Session):
        """A planilha de 2026 não traz CNPJ em nenhuma linha."""
        grupo = _grupo(sessao)
        sessao.add(Empresa(grupo_id=grupo.id, razao_social="Sem CNPJ Ltda"))
        sessao.flush()

        assert sessao.scalar(sa.select(sa.func.count()).select_from(Empresa)) == 1

    def test_o_mesmo_cnpj_nao_entra_duas_vezes(self, sessao: Session):
        grupo = _grupo(sessao)
        sessao.add(Empresa(grupo_id=grupo.id, razao_social="A", cnpj="11222333000181"))
        sessao.flush()
        sessao.add(Empresa(grupo_id=grupo.id, razao_social="B", cnpj="11222333000181"))

        with pytest.raises(sa.exc.IntegrityError):
            sessao.flush()

    def test_nasce_ativa(self, sessao: Session):
        grupo = _grupo(sessao)
        empresa = Empresa(grupo_id=grupo.id, razao_social="Ativa Ltda")
        sessao.add(empresa)
        sessao.flush()

        assert empresa.situacao is SituacaoEmpresa.ATIVA


class TestPessoaContato:
    def test_contato_precisa_pertencer_a_alguem(self, sessao: Session):
        """Contato solto não tem como ser encontrado nem respeitado."""
        sessao.add(PessoaContato(nome="Fulano"))

        with pytest.raises(sa.exc.IntegrityError):
            sessao.flush()

    def test_nao_contatar_comeca_desligado_e_registra_quando_e_por_que(self, sessao: Session):
        grupo = _grupo(sessao)
        contato = PessoaContato(grupo_id=grupo.id, nome="Beltrano", papel=PapelContato.DECISOR)
        sessao.add(contato)
        sessao.flush()

        assert contato.nao_contatar is False
        assert contato.nao_contatar_motivo is None


class TestOportunidade:
    def test_o_que_vem_da_carga_exige_chave_de_origem(self, sessao: Session):
        """Sem chave, a recarga duplicaria o registro — o banco não deixa."""
        grupo = _grupo(sessao)
        sessao.add(
            Oportunidade(
                grupo_id=grupo.id,
                nome="Sogamax",
                situacao=Situacao.RECUSADA,
                origem=Origem.CARGA_2026,
                chave_origem=None,
            )
        )

        with pytest.raises(sa.exc.IntegrityError):
            sessao.flush()

    def test_o_que_nasce_no_crm_dispensa_chave(self, sessao: Session):
        grupo = _grupo(sessao)
        oportunidade = Oportunidade(
            grupo_id=grupo.id, nome="Lead novo", situacao=Situacao.ENVIAR_PROPOSTA
        )
        sessao.add(oportunidade)
        sessao.flush()

        assert oportunidade.chave_origem is None
        assert oportunidade.origem is Origem.CRM

    def test_a_mesma_chave_de_origem_nao_entra_duas_vezes(self, sessao: Session):
        """É o que torna a carga repetível — a decisão de rodar em paralelo."""
        grupo = _grupo(sessao)
        for _ in range(2):
            sessao.add(
                Oportunidade(
                    grupo_id=grupo.id,
                    nome="Sogamax",
                    situacao=Situacao.RECUSADA,
                    origem=Origem.CARGA_2026,
                    chave_origem="sogamax|2026-01-01|bpo contabil|recorrente",
                )
            )
        with pytest.raises(sa.exc.IntegrityError):
            sessao.flush()

    def test_o_motivo_original_sobrevive_mesmo_sem_conversao(self, sessao: Session):
        """O verbatim é a matéria-prima da Matriz de Objeções."""
        grupo = _grupo(sessao)
        oportunidade = Oportunidade(
            grupo_id=grupo.id,
            nome="Tabor",
            situacao=Situacao.RECUSADA,
            motivo_recusa=None,
            motivo_recusa_original="Em formalização",
        )
        sessao.add(oportunidade)
        sessao.flush()

        assert oportunidade.motivo_recusa is None
        assert oportunidade.motivo_recusa_original == "Em formalização"

    def test_dinheiro_e_guardado_em_centavos(self, sessao: Session):
        grupo = _grupo(sessao)
        oportunidade = Oportunidade(
            grupo_id=grupo.id,
            nome="Preço",
            situacao=Situacao.ACEITA,
            data_colocacao=date(2026, 3, 26),
            preco_anual=Decimal("30000.00"),
        )
        sessao.add(oportunidade)
        sessao.flush()

        assert oportunidade.preco_anual == Decimal("30000.00")


class TestLead:
    def test_nasce_novo_e_aberto(self, sessao: Session):
        lead = Lead(nome="Contato da feira", tipo_canal=TipoCanal.SOCIOS)
        sessao.add(lead)
        sessao.flush()

        assert lead.situacao is SituacaoLead.NOVO
        assert lead.situacao.aberto is True

    def test_canais_que_ainda_nao_operam_ja_existem_na_lista(self, sessao: Session):
        """Tráfego pago e afiliados são desejo declarado, não operação."""
        lead = Lead(nome="Campanha futura", tipo_canal=TipoCanal.TRAFEGO_PAGO, campanha="Teste")
        sessao.add(lead)
        sessao.flush()

        assert lead.tipo_canal.em_operacao is False
        assert lead.campanha == "Teste"

    def test_converter_aponta_para_a_oportunidade(self, sessao: Session):
        grupo = _grupo(sessao)
        oportunidade = Oportunidade(
            grupo_id=grupo.id, nome="Convertido", situacao=Situacao.ENVIAR_PROPOSTA
        )
        sessao.add(oportunidade)
        sessao.flush()

        lead = Lead(
            nome="Virou proposta",
            situacao=SituacaoLead.CONVERTIDO,
            convertido_em_id=oportunidade.id,
        )
        sessao.add(lead)
        sessao.flush()

        assert lead.convertido_em is oportunidade
        assert lead.situacao.aberto is False
