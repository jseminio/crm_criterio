"""Fundir grupos econômicos — a contrapartida do caminho 2.

Eduardo escolheu em 20/09/2026 **carregar cada proposta como grupo próprio e
reagrupar depois**. Isso desbloqueia a carga, mas só funciona se reagrupar for
barato. É o que este módulo faz.

A fusão **não apaga** o grupo absorvido: a arquitetura proíbe exclusão física,
e o histórico de quem era quem é exatamente o que se quer preservar quando uma
empresa muda de mão.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Empresa, GrupoEconomico, Oportunidade
from crm.domain.listas import SituacaoGrupo

__all__ = ["fundir_grupos", "FusaoInvalida", "ResultadoDaFusao"]


class FusaoInvalida(ValueError):
    """A fusão pedida não faz sentido e não será tentada."""


class ResultadoDaFusao:
    """O que a fusão moveu, para o relatório e para quem desfizer depois."""

    def __init__(self, principal: GrupoEconomico, absorvido: GrupoEconomico,
                 empresas: int, oportunidades: int, contatos: int):
        self.principal = principal
        self.absorvido = absorvido
        self.empresas = empresas
        self.oportunidades = oportunidades
        self.contatos = contatos

    @property
    def texto(self) -> str:
        return (
            f"{self.absorvido.nome!r} foi fundido em {self.principal.nome!r}: "
            f"{self.empresas} empresa(s), {self.oportunidades} oportunidade(s) e "
            f"{self.contatos} contato(s) movidos"
        )

    def __repr__(self) -> str:
        return f"<ResultadoDaFusao {self.absorvido.id}→{self.principal.id}>"


def fundir_grupos(
    sessao: Session, principal: GrupoEconomico, absorvido: GrupoEconomico
) -> ResultadoDaFusao:
    """Move tudo de `absorvido` para `principal` e marca a origem da fusão.

    Recusa três casos, cada um por um motivo diferente:

    - **fundir um grupo nele mesmo** — não é operação, é engano de digitação;
    - **absorver um grupo já fundido** — a cadeia ficaria ambígua, e quem
      consultasse o histórico não saberia qual fusão valeu;
    - **absorver um grupo que é o destino do principal** — fecharia um ciclo e
      deixaria os dois sem raiz.
    """
    if principal.id == absorvido.id:
        raise FusaoInvalida("um grupo não se funde em si mesmo")
    if absorvido.fundido_em_id is not None:
        raise FusaoInvalida(
            f"{absorvido.nome!r} já foi fundido antes — desfaça aquela fusão primeiro"
        )
    if principal.fundido_em_id == absorvido.id:
        raise FusaoInvalida(
            f"{principal.nome!r} já aponta para {absorvido.nome!r}; fundir "
            f"no sentido inverso criaria um ciclo"
        )

    # Lido antes de qualquer alteração: a promoção abaixo depende do que o
    # absorvido era, e daqui a três linhas ele já não será mais isso.
    absorvido_era = absorvido.situacao

    empresas = sessao.execute(
        sa.update(Empresa)
        .where(Empresa.grupo_id == absorvido.id)
        .values(grupo_id=principal.id)
    ).rowcount
    oportunidades = sessao.execute(
        sa.update(Oportunidade)
        .where(Oportunidade.grupo_id == absorvido.id)
        .values(grupo_id=principal.id)
    ).rowcount
    contatos = sessao.execute(
        sa.text(
            "UPDATE pessoa_contato SET grupo_id = :novo WHERE grupo_id = :velho"
        ),
        {"novo": principal.id, "velho": absorvido.id},
    ).rowcount

    absorvido.fundido_em_id = principal.id
    absorvido.situacao = SituacaoGrupo.FUNDIDO

    # Um prospect que absorve um cliente vira cliente: a relação mais avançada
    # manda. Sem isso, fundir rebaixaria a carteira em silêncio — e o grupo
    # sumiria dos relatórios de cliente sem ninguém ter decidido isso.
    if absorvido_era is SituacaoGrupo.CLIENTE and principal.situacao is SituacaoGrupo.PROSPECT:
        principal.situacao = SituacaoGrupo.CLIENTE

    # A data de entrada do conjunto é a mais antiga das duas: é quando a
    # Critério começou a atender aquele cliente, não quando descobriu o vínculo.
    if absorvido.data_entrada is not None and (
        principal.data_entrada is None or absorvido.data_entrada < principal.data_entrada
    ):
        principal.data_entrada = absorvido.data_entrada

    sessao.flush()
    return ResultadoDaFusao(principal, absorvido, empresas, oportunidades, contatos)
