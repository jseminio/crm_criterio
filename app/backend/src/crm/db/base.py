"""Fundação do mapeamento objeto-relacional.

Concentra as decisões que valem para **toda** tabela: convenção de nomes de
restrição, carimbo de criação e alteração, e a forma de guardar as listas
controladas. Decidir uma vez aqui evita decidir de novo em cada entidade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["Base", "CarimboMixin", "coluna_lista", "agora"]


def agora() -> datetime:
    """Instante atual em UTC, sempre com fuso explícito.

    Data sem fuso é dívida silenciosa: funciona até o servidor mudar de região.
    A apresentação converte para o horário de Brasília; o armazenamento é UTC.
    """
    return datetime.now(timezone.utc)


#: Nomes previsíveis para índices e restrições.
#:
#: Sem isso o banco inventa os nomes, e o Alembic não consegue remover no futuro
#: uma restrição que ele mesmo criou — a migração quebra na hora de voltar atrás.
CONVENCAO_DE_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Raiz de todas as entidades."""

    metadata = sa.MetaData(naming_convention=CONVENCAO_DE_NOMES)


class CarimboMixin:
    """Quando o registro nasceu e quando mudou pela última vez.

    Não substitui a procedência exigida pela arquitetura — quem decidiu, com que
    evidência, em que papel. Isso é por entidade, onde o dado tem dono. Aqui é
    só o carimbo técnico.
    """

    criado_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=agora, nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=agora, onupdate=agora, nullable=False
    )


def coluna_lista(enum: type[Enum], tamanho: int = 40) -> sa.Enum:
    """Guarda um item de lista controlada como texto legível.

    Duas decisões embutidas, ambas deliberadas:

    **Texto, não tipo nativo do banco.** Um ``ENUM`` do PostgreSQL exige
    ``ALTER TYPE`` para ganhar um valor novo. As listas de `crm.domain.listas`
    são **proposta ainda não aprovada** por Eduardo: vão mudar. Texto muda com
    um ``UPDATE``.

    **Sem restrição de verificação no banco.** A validação já existe em
    ``normalizar_*``, e repeti-la aqui criaria a segunda cópia da mesma regra.
    O deck da carteira dá a diretriz da casa: *modelo único = manutenção única;
    dois modelos = duas atualizações, duas chances de divergir*. A porta de
    entrada do dado é a camada de domínio, e é lá que a lista vive.

    Guarda o ``value`` — "Enviar proposta", não "ENVIAR_PROPOSTA" — para que
    uma consulta direta ao banco seja legível por quem não conhece o código.
    """
    return sa.Enum(
        enum,
        native_enum=False,
        length=tamanho,
        create_constraint=False,
        values_callable=lambda e: [membro.value for membro in e],
    )
