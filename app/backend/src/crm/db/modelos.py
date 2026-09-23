"""As entidades do E2, E3 e do começo da Etapa 2: cliente, contato, lead,
oportunidade e contrato.

E2/E3 cobrem o que a proposta aprovada em 20/09/2026 prometeu para sexta — a
carteira existindo e o funil funcionando. `Contrato` entrou em 23/09/2026,
começo da Etapa 2 ("fechar o ciclo") — decisão de Eduardo, com o Bruno já
alinhado. Implantação e carteira classificada continuam **fora**: a primeira
depende da aprovação do `MP-SC-01`, que não é deste projeto; a segunda é
Etapa 3.

Três princípios da arquitetura aparecem no código:

1. **O cliente é um grupo, a operação é por empresa.** Oportunidade e relação
   pendem do grupo; CNPJ e regime pendem da empresa.
2. **Exclusão nunca é física.** Nada some: muda de situação e guarda o rastro.
3. **Quem decide fica registrado.** Onde há julgamento humano, há autor e data.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm.db.base import Base, CarimboMixin, coluna_lista
from crm.domain.listas import (
    LinhaServico,
    MotivoRecusa,
    Origem,
    PapelContato,
    Situacao,
    SituacaoContrato,
    SituacaoEmpresa,
    SituacaoGrupo,
    SituacaoLead,
    Temperatura,
    TipoCanal,
    TipoDeOcorrencia,
)

__all__ = [
    "GrupoEconomico",
    "Empresa",
    "PessoaContato",
    "Lead",
    "Oportunidade",
    "Contrato",
    "ExecucaoDeCarga",
    "OcorrenciaDeCarga",
]

#: Dinheiro é guardado em centavos exatos.
#:
#: A planilha traz valores com até dez casas decimais — resíduo de fórmula, não
#: preço. Quem arredonda é a carga, **avisando**, e não o banco em silêncio.
DINHEIRO = sa.Numeric(14, 2)


class GrupoEconomico(CarimboMixin, Base):
    """A unidade de cliente. Pode ter uma empresa só — é o caso mais comum."""

    __tablename__ = "grupo_economico"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)
    situacao: Mapped[SituacaoGrupo] = mapped_column(
        coluna_lista(SituacaoGrupo), nullable=False, default=SituacaoGrupo.PROSPECT
    )
    responsavel_cs: Mapped[str | None] = mapped_column(sa.String(10))
    data_entrada: Mapped[date | None] = mapped_column(sa.Date)
    origem: Mapped[Origem] = mapped_column(
        coluna_lista(Origem), nullable=False, default=Origem.CRM
    )
    observacao: Mapped[str | None] = mapped_column(sa.Text)

    fundido_em_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), index=True
    )
    """Para quem este grupo foi quando se descobriu que era parte de outro.

    A carga de 2026 cria **um grupo por proposta** — caminho 2, escolhido por
    Eduardo em 20/09/2026. O reagrupamento vem depois, no uso, e é esta coluna
    que o registra sem apagar nada.
    """

    fundido_em: Mapped["GrupoEconomico | None"] = relationship(
        remote_side="GrupoEconomico.id", back_populates="absorvidos"
    )
    absorvidos: Mapped[list["GrupoEconomico"]] = relationship(
        back_populates="fundido_em"
    )
    empresas: Mapped[list["Empresa"]] = relationship(
        back_populates="grupo", cascade="save-update"
    )
    oportunidades: Mapped[list["Oportunidade"]] = relationship(
        back_populates="grupo", cascade="save-update"
    )
    contratos: Mapped[list["Contrato"]] = relationship(
        back_populates="grupo", cascade="save-update"
    )

    __table_args__ = (
        sa.CheckConstraint(
            "fundido_em_id IS NULL OR fundido_em_id <> id",
            name="nao_funde_em_si_mesmo",
        ),
    )

    def __repr__(self) -> str:
        return f"<GrupoEconomico {self.id} {self.nome!r} {self.situacao.value}>"


class Empresa(CarimboMixin, Base):
    """Um CNPJ. É dele que pendem nota fiscal, folha e obrigação acessória."""

    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), nullable=False, index=True
    )
    razao_social: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(sa.String(200))
    cnpj: Mapped[str | None] = mapped_column(sa.String(14), unique=True, index=True)
    """Só os catorze dígitos, sem pontuação. Nulo até alguém preencher.

    A planilha de 2026 não traz CNPJ em nenhuma linha. Exigir aqui impediria a
    carga inteira de existir.
    """

    regime_tributario: Mapped[str | None] = mapped_column(sa.String(40))
    inscricao_estadual: Mapped[str | None] = mapped_column(sa.String(20))
    inscricao_municipal: Mapped[str | None] = mapped_column(sa.String(20))
    municipio: Mapped[str | None] = mapped_column(sa.String(100))
    uf: Mapped[str | None] = mapped_column(sa.String(2))
    situacao: Mapped[SituacaoEmpresa] = mapped_column(
        coluna_lista(SituacaoEmpresa), nullable=False, default=SituacaoEmpresa.ATIVA
    )

    grupo: Mapped[GrupoEconomico] = relationship(back_populates="empresas")

    def __repr__(self) -> str:
        return f"<Empresa {self.id} {self.razao_social!r}>"


class PessoaContato(CarimboMixin, Base):
    """Quem se fala. Ligada ao grupo ou a uma empresa dele."""

    __tablename__ = "pessoa_contato"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), index=True
    )
    empresa_id: Mapped[int | None] = mapped_column(sa.ForeignKey("empresa.id"), index=True)
    nome: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    cargo: Mapped[str | None] = mapped_column(sa.String(100))
    email: Mapped[str | None] = mapped_column(sa.String(200), index=True)
    telefone: Mapped[str | None] = mapped_column(sa.String(30))
    papel: Mapped[PapelContato | None] = mapped_column(coluna_lista(PapelContato))
    observacao: Mapped[str | None] = mapped_column(sa.Text)

    nao_contatar: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    """Pedido de não ser contatado. **Respeitado por toda lista de campanha.**

    Eduardo decidiu em 19/09/2026 não submeter o uso de lead perdido em campanha
    à validação jurídica. Esta coluna é a medida técnica que sobrou — não é
    parecer, e não substitui um.
    """

    nao_contatar_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    nao_contatar_motivo: Mapped[str | None] = mapped_column(sa.String(200))

    __table_args__ = (
        sa.CheckConstraint(
            "grupo_id IS NOT NULL OR empresa_id IS NOT NULL",
            name="contato_pertence_a_alguem",
        ),
    )

    def __repr__(self) -> str:
        return f"<PessoaContato {self.id} {self.nome!r}>"


class Lead(CarimboMixin, Base):
    """Interesse que chegou e ainda não virou proposta.

    **Não existe na planilha de 2026** — ela começa na proposta já enviada. Todo
    lead nasce no CRM, e é aqui que o funil deixa de ter começo invisível.
    """

    __tablename__ = "lead"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)
    empresa_texto: Mapped[str | None] = mapped_column(sa.String(200))
    """O nome da empresa como a pessoa falou, antes de existir cadastro."""

    email: Mapped[str | None] = mapped_column(sa.String(200))
    telefone: Mapped[str | None] = mapped_column(sa.String(30))

    tipo_canal: Mapped[TipoCanal | None] = mapped_column(coluna_lista(TipoCanal))
    canal: Mapped[str | None] = mapped_column(sa.String(120))
    """Segunda camada da origem: quem, com nome, dentro do tipo de canal."""

    captador: Mapped[str | None] = mapped_column(sa.String(10))
    interesse: Mapped[str | None] = mapped_column(sa.String(200))
    temperatura: Mapped[Temperatura | None] = mapped_column(coluna_lista(Temperatura))
    situacao: Mapped[SituacaoLead] = mapped_column(
        coluna_lista(SituacaoLead), nullable=False, default=SituacaoLead.NOVO
    )

    campanha: Mapped[str | None] = mapped_column(sa.String(120))
    campanha_midia: Mapped[str | None] = mapped_column(sa.String(120))
    """Preenchidos quando a origem é tráfego pago ou afiliado.

    Nenhum dos dois canais opera hoje: são desejo declarado por Eduardo. As
    colunas existem para que o indicador de origem meça a saída da dependência
    de sócios desde o primeiro lead.
    """

    proxima_acao: Mapped[str | None] = mapped_column(sa.String(200))
    proxima_acao_em: Mapped[date | None] = mapped_column(sa.Date, index=True)
    observacao: Mapped[str | None] = mapped_column(sa.Text)

    convertido_em_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("oportunidade.id"), index=True
    )
    convertido_em: Mapped["Oportunidade | None"] = relationship(back_populates="lead")

    def __repr__(self) -> str:
        return f"<Lead {self.id} {self.nome!r} {self.situacao.value}>"


class Oportunidade(CarimboMixin, Base):
    """Uma proposta, enviada ou por enviar. É a linha da planilha de 2026."""

    __tablename__ = "oportunidade"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)

    servico: Mapped[str | None] = mapped_column(sa.String(120))
    tipo_servico: Mapped[str | None] = mapped_column(sa.String(120))
    linha_servico: Mapped[LinhaServico | None] = mapped_column(coluna_lista(LinhaServico))

    tipo_canal: Mapped[TipoCanal | None] = mapped_column(coluna_lista(TipoCanal))
    canal: Mapped[str | None] = mapped_column(sa.String(120))
    captador: Mapped[str | None] = mapped_column(sa.String(10), index=True)

    situacao: Mapped[Situacao] = mapped_column(coluna_lista(Situacao), nullable=False)
    temperatura: Mapped[Temperatura | None] = mapped_column(coluna_lista(Temperatura))

    data_colocacao: Mapped[date | None] = mapped_column(sa.Date, index=True)
    data_aceite: Mapped[date | None] = mapped_column(sa.Date)

    motivo_recusa: Mapped[MotivoRecusa | None] = mapped_column(coluna_lista(MotivoRecusa))
    motivo_recusa_original: Mapped[str | None] = mapped_column(sa.String(200))
    """O texto exato da planilha, preservado mesmo quando a conversão falhou.

    É a matéria-prima da Matriz de Objeções: o verbatim é o que ensina.
    """

    preco_mensal: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    valor_mensalizado: Mapped[Decimal | None] = mapped_column(DINHEIRO)

    proxima_acao: Mapped[str | None] = mapped_column(sa.String(200))
    proxima_acao_em: Mapped[date | None] = mapped_column(sa.Date, index=True)
    observacao: Mapped[str | None] = mapped_column(sa.Text)

    complexidade: Mapped[int | None] = mapped_column(sa.SmallInteger)
    risco_tecnico: Mapped[int | None] = mapped_column(sa.SmallInteger)
    """Nota 1 a 5, mesma escala do `modelo-classificacao-carteira.md` — para
    servir sem conversão quando a classificação viva (Etapa 3) chegar.

    Decisão de 22/09/2026 (`regua-de-porte-e-plano-de-teste.md`, seção 7):
    preenchidos **na oportunidade, antes da proposta**, não só na carteira —
    senão, quando a precificação automática entrar, não há histórico para
    calibrar nada.
    """

    documentos_fiscais_mes: Mapped[int | None] = mapped_column(sa.Integer)
    lancamentos_contabeis_mes: Mapped[int | None] = mapped_column(sa.Integer)
    pagamentos_mes: Mapped[int | None] = mapped_column(sa.Integer)
    contas_bancarias: Mapped[int | None] = mapped_column(sa.Integer)
    conciliacoes_cartao_mes: Mapped[int | None] = mapped_column(sa.Integer)
    empregados_clt: Mapped[int | None] = mapped_column(sa.Integer)
    admissoes_desligamentos_mes: Mapped[int | None] = mapped_column(sa.Integer)
    cnpjs_no_escopo: Mapped[int | None] = mapped_column(sa.Integer)
    tomadores_de_servico: Mapped[int | None] = mapped_column(sa.Integer)
    """Os nove direcionadores da régua de porte (`crm.domain.porte`). `None`
    é "não se aplica ao escopo contratado" — fica fora da média, nunca vira
    zero. Ver a régua para as faixas de cada um."""

    servicos_contratados_alem_do_primeiro: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=0, server_default=sa.text("0")
    )
    tem_consolidacao_de_grupo: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    e_auditada: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )

    porte: Mapped[str | None] = mapped_column(sa.String(20))
    """O porte **confirmado** — não o calculado. A régua só sugere (ver
    `crm.domain.porte`); este campo é o que a pessoa aceitou ou sobrepôs."""

    porte_definido_por: Mapped[str | None] = mapped_column(sa.String(10))
    porte_definido_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    """Quem confirmou ou sobrepôs o porte, e quando — é este par que vira
    material para recalibrar a régua depois. Sem autor, uma sobreposição é
    só um número diferente, sem ninguém para explicar por quê."""

    origem: Mapped[Origem] = mapped_column(
        coluna_lista(Origem), nullable=False, default=Origem.CRM
    )
    chave_origem: Mapped[str | None] = mapped_column(sa.String(400), unique=True, index=True)
    """Identidade estável do registro na planilha, para recarregar sem duplicar.

    Nome + data de colocação + serviço + tipo de serviço. Testada contra as 157
    propostas de 2026: **156 chaves distintas**. A única colisão restante são
    duas linhas idênticas em todos os campos — defeito da planilha, aguardando
    confirmação de quem digitou.

    Nula no que nasce no CRM: aí a identidade é a chave primária.
    """

    campos_do_crm: Mapped[list[str]] = mapped_column(
        # JSONB no PostgreSQL: o tipo json não tem operador de igualdade, então o
        # Alembic não consegue comparar o valor padrão e o `alembic check` quebra.
        # JSON genérico nos demais bancos, para o teste rodar em SQLite.
        sa.JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
        server_default=sa.text("'[]'"),
    )
    """Campos que uma pessoa mudou **aqui**, e que a carga não pode sobrescrever.

    Enquanto o CRM roda em paralelo com a planilha, os dois editam a mesma
    oportunidade. Sem esta memória, a recarga apagava o que se preenchia na tela:
    a planilha não tem nenhuma data de aceite, então preencher a data e rodar a
    carga de novo a desfazia. Tipo JSON genérico, para valer igual nos dois bancos.
    """

    linha_planilha: Mapped[int | None] = mapped_column(sa.Integer)
    """Onde estava na aba quando foi importada. Serve para apontar a origem no
    relatório de conferência — **não** é identidade: número de linha se desloca.
    """

    grupo: Mapped[GrupoEconomico] = relationship(back_populates="oportunidades")
    lead: Mapped[Lead | None] = relationship(back_populates="convertido_em")

    __table_args__ = (
        sa.CheckConstraint(
            "origem <> 'Carga 2026' OR chave_origem IS NOT NULL",
            name="carga_exige_chave_de_origem",
        ),
        sa.CheckConstraint(
            "complexidade IS NULL OR complexidade BETWEEN 1 AND 5",
            name="complexidade_de_1_a_5",
        ),
        sa.CheckConstraint(
            "risco_tecnico IS NULL OR risco_tecnico BETWEEN 1 AND 5",
            name="risco_tecnico_de_1_a_5",
        ),
    )

    def __repr__(self) -> str:
        return f"<Oportunidade {self.id} {self.nome!r} {self.situacao.value}>"


class Contrato(CarimboMixin, Base):
    """Nasce de uma oportunidade aceita — começo da Etapa 2 (E2 "fechar o
    ciclo"), 23/09/2026.

    **Só o registro, ainda.** Sem Clicksign (decisão de Eduardo: a assinatura
    eletrônica fica para depois), sem evento de contrato (aditivo, reajuste,
    expansão — é a camada seguinte, ainda não construída), sem renovação
    automática (`anexo-tecnico.md` marca vigência/renovação como "a
    confirmar" — não é para inventar aqui).
    """

    __tablename__ = "contrato"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), nullable=False, index=True
    )
    oportunidade_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("oportunidade.id"), unique=True, index=True
    )
    """A oportunidade aceita que originou o contrato. Nula se o contrato
    nascer direto na tela, sem passar pelo funil."""

    escopo: Mapped[str | None] = mapped_column(sa.String(200))
    preco_mensal: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual: Mapped[Decimal | None] = mapped_column(DINHEIRO)

    data_inicio: Mapped[date | None] = mapped_column(sa.Date)
    data_fim: Mapped[date | None] = mapped_column(sa.Date)

    situacao: Mapped[SituacaoContrato] = mapped_column(
        coluna_lista(SituacaoContrato),
        nullable=False,
        default=SituacaoContrato.AGUARDANDO_ASSINATURA,
    )
    documento_assinado: Mapped[str | None] = mapped_column(sa.String(400))
    """Link ou referência do documento — sem upload no CRM ainda. Texto
    livre (ex.: caminho no SharePoint), não um arquivo guardado aqui."""

    signatario: Mapped[str | None] = mapped_column(sa.String(200))
    observacao: Mapped[str | None] = mapped_column(sa.Text)

    grupo: Mapped[GrupoEconomico] = relationship(back_populates="contratos")
    oportunidade: Mapped["Oportunidade | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Contrato {self.id} grupo={self.grupo_id} {self.situacao.value}>"


class ExecucaoDeCarga(Base):
    """Uma rodada da carga da planilha, guardada como foi.

    Existe para o relatório de conferência sobreviver ao script. Sem isto ele
    aparecia na tela do terminal e sumia — e confiar na base, que é a condição
    para abandonar a planilha, dependia de alguém ter guardado a saída.

    **Imutável de propósito**: não herda o carimbo de alteração. Um relatório
    que muda depois de escrito deixa de ser evidência do que aconteceu.
    """

    __tablename__ = "execucao_de_carga"

    id: Mapped[int] = mapped_column(primary_key=True)
    executada_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, index=True
    )
    arquivo: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    """Só o nome do arquivo, sem o caminho: o caminho revela a estrutura de
    pastas de quem rodou e não ajuda a conferir nada."""

    # O que a leitura da planilha viu
    lidas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    de_outro_ano: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    residuais: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    importadas: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # O que a gravação fez
    criadas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    atualizadas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    inalteradas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    ignoradas_incompletas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    ignoradas_duplicatas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    grupos_criados: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    grupos_reaproveitados: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    ocorrencias: Mapped[list["OcorrenciaDeCarga"]] = relationship(
        back_populates="execucao", cascade="all, delete-orphan"
    )

    @property
    def gravadas(self) -> int:
        """Quantas oportunidades desta planilha estão no CRM depois da rodada."""
        return self.criadas + self.atualizadas + self.inalteradas


class OcorrenciaDeCarga(Base):
    """Uma linha do relatório: algo que a carga viu, ajustou ou alterou."""

    __tablename__ = "ocorrencia_de_carga"

    id: Mapped[int] = mapped_column(primary_key=True)
    execucao_id: Mapped[int] = mapped_column(
        sa.ForeignKey("execucao_de_carga.id"), nullable=False, index=True
    )
    tipo: Mapped[TipoDeOcorrencia] = mapped_column(
        coluna_lista(TipoDeOcorrencia), nullable=False, index=True
    )
    linha: Mapped[int | None] = mapped_column(sa.Integer)
    """A linha da aba da planilha, para quem confere ir direto ao lugar."""
    campo: Mapped[str | None] = mapped_column(sa.String(60))
    texto: Mapped[str] = mapped_column(sa.Text, nullable=False)

    execucao: Mapped[ExecucaoDeCarga] = relationship(back_populates="ocorrencias")
