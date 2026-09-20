"""Fundir grupos — o que torna o caminho 2 viável.

Carregar cada proposta como grupo próprio só é uma boa decisão se reagrupar for
barato e não destruir nada. É isso que estes testes cobram.
"""

from __future__ import annotations

from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.grupos import FusaoInvalida, fundir_grupos
from crm.db.modelos import Empresa, GrupoEconomico, Oportunidade, PessoaContato
from crm.domain.listas import Origem, Situacao, SituacaoGrupo


def _grupo(sessao: Session, nome: str, **campos) -> GrupoEconomico:
    grupo = GrupoEconomico(nome=nome, **campos)
    sessao.add(grupo)
    sessao.flush()
    return grupo


def _oportunidade(sessao: Session, grupo: GrupoEconomico, nome: str) -> Oportunidade:
    oportunidade = Oportunidade(
        grupo_id=grupo.id,
        nome=nome,
        situacao=Situacao.ACEITA,
        origem=Origem.CARGA_2026,
        chave_origem=f"{nome}|2026-01-01|bpo|recorrente",
    )
    sessao.add(oportunidade)
    sessao.flush()
    return oportunidade


class TestFusao:
    def test_move_empresas_oportunidades_e_contatos(self, sessao: Session):
        principal = _grupo(sessao, "Grupo Alfa")
        absorvido = _grupo(sessao, "Alfa Participações")
        sessao.add(Empresa(grupo_id=absorvido.id, razao_social="Alfa Part. Ltda"))
        sessao.add(PessoaContato(grupo_id=absorvido.id, nome="Decisor"))
        _oportunidade(sessao, absorvido, "Alfa")
        sessao.flush()

        resultado = fundir_grupos(sessao, principal, absorvido)

        assert (resultado.empresas, resultado.oportunidades, resultado.contatos) == (1, 1, 1)
        assert "fundido em" in resultado.texto

    def test_o_grupo_absorvido_nao_e_apagado(self, sessao: Session):
        """A arquitetura proíbe exclusão física: o histórico continua legível."""
        principal = _grupo(sessao, "Grupo Beta")
        absorvido = _grupo(sessao, "Beta Filial")

        fundir_grupos(sessao, principal, absorvido)

        ainda_existe = sessao.get(GrupoEconomico, absorvido.id)
        assert ainda_existe is not None
        assert ainda_existe.situacao is SituacaoGrupo.FUNDIDO
        assert ainda_existe.fundido_em_id == principal.id
        assert principal.absorvidos == [ainda_existe]

    def test_prospect_que_absorve_cliente_vira_cliente(self, sessao: Session):
        """Sem isto, reagrupar rebaixaria a carteira sem ninguém ter decidido."""
        principal = _grupo(sessao, "Gama", situacao=SituacaoGrupo.PROSPECT)
        absorvido = _grupo(sessao, "Gama Antiga", situacao=SituacaoGrupo.CLIENTE)

        fundir_grupos(sessao, principal, absorvido)

        assert principal.situacao is SituacaoGrupo.CLIENTE

    def test_cliente_que_absorve_prospect_continua_cliente(self, sessao: Session):
        principal = _grupo(sessao, "Delta", situacao=SituacaoGrupo.CLIENTE)
        absorvido = _grupo(sessao, "Delta Nova", situacao=SituacaoGrupo.PROSPECT)

        fundir_grupos(sessao, principal, absorvido)

        assert principal.situacao is SituacaoGrupo.CLIENTE

    def test_a_data_de_entrada_do_conjunto_e_a_mais_antiga(self, sessao: Session):
        """É quando a Critério começou a atender, não quando descobriu o vínculo."""
        principal = _grupo(sessao, "Épsilon", data_entrada=date(2024, 5, 1))
        absorvido = _grupo(sessao, "Épsilon Antiga", data_entrada=date(2019, 2, 1))

        fundir_grupos(sessao, principal, absorvido)

        assert principal.data_entrada == date(2019, 2, 1)

    def test_data_mais_recente_no_absorvido_nao_sobrescreve(self, sessao: Session):
        principal = _grupo(sessao, "Zeta", data_entrada=date(2018, 1, 1))
        absorvido = _grupo(sessao, "Zeta Nova", data_entrada=date(2025, 1, 1))

        fundir_grupos(sessao, principal, absorvido)

        assert principal.data_entrada == date(2018, 1, 1)


class TestFusoesRecusadas:
    def test_nao_funde_um_grupo_nele_mesmo(self, sessao: Session):
        grupo = _grupo(sessao, "Sozinho")

        with pytest.raises(FusaoInvalida, match="si mesmo"):
            fundir_grupos(sessao, grupo, grupo)

    def test_nao_absorve_quem_ja_foi_fundido(self, sessao: Session):
        """A cadeia ficaria ambígua e ninguém saberia qual fusão valeu."""
        primeiro = _grupo(sessao, "Primeiro")
        segundo = _grupo(sessao, "Segundo")
        terceiro = _grupo(sessao, "Terceiro")
        fundir_grupos(sessao, primeiro, segundo)

        with pytest.raises(FusaoInvalida, match="já foi fundido"):
            fundir_grupos(sessao, terceiro, segundo)

    def test_nao_fecha_ciclo(self, sessao: Session):
        """Desfazer uma fusão trocando a ordem deixaria os dois grupos sem raiz."""
        maior = _grupo(sessao, "Maior")
        menor = _grupo(sessao, "Menor")
        fundir_grupos(sessao, maior, menor)

        # `menor` já aponta para `maior`. Fundir na ordem inversa faria `maior`
        # apontar de volta — e nenhum dos dois seria o grupo verdadeiro.
        with pytest.raises(FusaoInvalida, match="ciclo"):
            fundir_grupos(sessao, menor, maior)


class TestIntegridade:
    def test_oportunidade_nao_aponta_para_grupo_inexistente(self, sessao: Session):
        """Confirma que a chave estrangeira está ligada — o SQLite a ignora por padrão."""
        sessao.add(
            Oportunidade(grupo_id=9999, nome="Órfã", situacao=Situacao.ENVIAR_PROPOSTA)
        )

        with pytest.raises(sa.exc.IntegrityError):
            sessao.flush()
