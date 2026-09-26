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

from crm.db.base import agora
from crm.db.modelos import Contrato, Empresa, FusaoDeGrupos, GrupoEconomico, Oportunidade, PessoaContato
from crm.domain.listas import SituacaoGrupo

__all__ = ["fundir_grupos", "desfazer_fusao", "FusaoInvalida", "ResultadoDaFusao"]

#: As tabelas que a fusão move do absorvido para o principal, e a coluna que aponta o grupo.
#: (Ficha de conta e abordagem do agente SDR ainda não são movidas: têm regra própria.)
_MOVIDOS = ((Empresa, "empresa"), (Oportunidade, "oportunidade"), (PessoaContato, "pessoa_contato"), (Contrato, "contrato"))


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
        self.fusao_id: int | None = None
        """O registro que permite desfazer."""

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

    # Guarda os ids **antes** de mover: é o que permite desfazer devolvendo exatamente estes itens.
    movidos: dict[str, list[int]] = {}
    for modelo, chave in _MOVIDOS:
        ids = list(sessao.scalars(sa.select(modelo.id).where(modelo.grupo_id == absorvido.id)))
        movidos[chave] = ids
        if ids:
            sessao.execute(sa.update(modelo).where(modelo.id.in_(ids)).values(grupo_id=principal.id))
    empresas, oportunidades, contatos = (len(movidos[k]) for k in ("empresa", "oportunidade", "pessoa_contato"))
    principal_situacao_antes, principal_entrada_antes = principal.situacao, principal.data_entrada

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

    registro = FusaoDeGrupos(
        principal_id=principal.id, absorvido_id=absorvido.id, movidos=movidos,
        absorvido_situacao_antes=absorvido_era.value,
        principal_situacao_antes=principal_situacao_antes.value, principal_situacao_depois=principal.situacao.value,
        principal_data_entrada_antes=principal_entrada_antes, principal_data_entrada_depois=principal.data_entrada,
    )
    sessao.add(registro)
    sessao.flush()
    resultado = ResultadoDaFusao(principal, absorvido, empresas, oportunidades, contatos)
    resultado.fusao_id = registro.id
    return resultado


def desfazer_fusao(sessao: Session, fusao: FusaoDeGrupos) -> FusaoDeGrupos:
    """Devolve ao grupo absorvido exatamente o que a fusão tirou dele, e o reabre.

    - Recusa fusão já desfeita.
    - Move de volta **por id**: o que foi criado no principal depois da fusão fica onde está, e o
      que uma fusão posterior levou para outro grupo também volta (pelo id, esteja onde estiver).
    - Reabre o absorvido com a situação que ele tinha.
    - Restaura o principal (situação e data de entrada) **só se ainda estiverem como a fusão os
      deixou**: se alguém os mudou depois, a mudança de propósito é respeitada.
    """
    if fusao.desfeita_em is not None:
        raise FusaoInvalida("esta fusão já foi desfeita")
    absorvido = sessao.get(GrupoEconomico, fusao.absorvido_id)
    principal = sessao.get(GrupoEconomico, fusao.principal_id)
    if absorvido is None or principal is None:
        raise FusaoInvalida("um dos grupos da fusão não existe mais")
    if absorvido.fundido_em_id != principal.id:
        raise FusaoInvalida("o grupo absorvido não está mais fundido neste principal")

    for modelo, chave in _MOVIDOS:
        ids = (fusao.movidos or {}).get(chave, [])
        if ids:
            sessao.execute(sa.update(modelo).where(modelo.id.in_(ids)).values(grupo_id=absorvido.id))

    absorvido.fundido_em_id = None
    absorvido.situacao = SituacaoGrupo(fusao.absorvido_situacao_antes)
    if principal.situacao.value == fusao.principal_situacao_depois:
        principal.situacao = SituacaoGrupo(fusao.principal_situacao_antes)
    if principal.data_entrada == fusao.principal_data_entrada_depois:
        principal.data_entrada = fusao.principal_data_entrada_antes
    fusao.desfeita_em = agora()
    sessao.flush()
    return fusao
