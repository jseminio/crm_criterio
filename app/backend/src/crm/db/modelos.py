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

from crm.db.base import Base, CarimboMixin, agora, coluna_lista
from crm.domain.listas import (
    CanalDeAbordagem,
    LinhaServico,
    MotivoRecusa,
    Origem,
    PapelContato,
    Situacao,
    SituacaoAbordagem,
    SituacaoContrato,
    SituacaoEmpresa,
    SituacaoGrupo,
    SituacaoLead,
    Temperatura,
    TipoCanal,
    IniciativaDoEncerramento,
    MotivoDeEncerramento,
    TipoDeEventoDeContrato,
    TipoDeOcorrencia,
)

__all__ = [
    "GrupoEconomico",
    "Empresa",
    "PessoaContato",
    "Lead",
    "Oportunidade",
    "Contrato",
    "FichaDeConta",
    "Abordagem",
    "ExecucaoDoAgente",
    "EventoDeContrato",
    "FusaoDeGrupos",
    "HistoricoDePreco",
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
    logradouro: Mapped[str | None] = mapped_column(sa.String(200))
    numero: Mapped[str | None] = mapped_column(sa.String(20))
    complemento: Mapped[str | None] = mapped_column(sa.String(100))
    bairro: Mapped[str | None] = mapped_column(sa.String(100))
    municipio: Mapped[str | None] = mapped_column(sa.String(100))
    uf: Mapped[str | None] = mapped_column(sa.String(2))
    cep: Mapped[str | None] = mapped_column(sa.String(8))
    """Só os oito dígitos, sem hífen — mesma regra do CNPJ. Endereço da empresa
    (o CNPJ), não do grupo: entrou em 25/09/2026, pedido de Eduardo, para
    receber os dados preenchidos à mão na planilha de lacunas de contato."""
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

    origem_da_volumetria: Mapped[dict[str, str]] = mapped_column(
        sa.JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'"),
    )
    """De onde veio cada direcionador da volumetria: `{campo: "Entrevista" | "Questionário"}`.

    Só existe para campo preenchido — o servidor descarta a origem de um campo que
    voltou a ficar vazio. Pedido do E4 (planejamento): cada campo sabe se veio da
    entrevista ou do questionário.
    """

    historico_de_preco: Mapped[list["HistoricoDePreco"]] = relationship(
        back_populates="oportunidade",
        order_by="HistoricoDePreco.id.desc()",
    )

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


class FusaoDeGrupos(Base):
    """O registro de uma fusão de grupos, para poder **desfazê-la** (pedido de Eduardo, 26/09/2026).

    Guarda, por id, tudo que a fusão moveu do grupo absorvido para o principal, e o estado do
    principal antes e depois. Desfazer devolve exatamente esses itens: o que foi criado no
    principal depois da fusão fica onde está. **Imutável, exceto por `desfeita_em`**, que só vai
    de nulo para uma data (uma fusão não é desfeita duas vezes).
    """

    __tablename__ = "fusao_de_grupos"

    id: Mapped[int] = mapped_column(primary_key=True)
    principal_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), nullable=False, index=True)
    absorvido_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), nullable=False, index=True)
    feita_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    desfeita_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    reconstruida: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    """Registro refeito depois, a partir de um backup, para fusões feitas antes de o registro existir."""

    movidos: Mapped[dict] = mapped_column(
        sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict, server_default=sa.text("'{}'")
    )
    """{"empresa": [ids], "oportunidade": [ids], "pessoa_contato": [ids], "contrato": [ids]}"""
    absorvido_situacao_antes: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    principal_situacao_antes: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    principal_situacao_depois: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    principal_data_entrada_antes: Mapped[date | None] = mapped_column(sa.Date)
    principal_data_entrada_depois: Mapped[date | None] = mapped_column(sa.Date)


class HistoricoDePreco(Base):
    """Uma mudança de preço, guardada como aconteceu — E4 (reajuste).

    Cada linha diz o preço **antes** e **depois**, quando, de onde veio (CRM ou
    recarga da planilha) e, se alguém disse, por quê ("reajuste anual",
    "renegociação"). Sem isto, reajustar apagava o preço anterior.

    **Imutável de propósito**, como `ExecucaoDeCarga`: não herda o carimbo de
    alteração. Um histórico que se reescreve deixa de ser histórico. Ainda não há
    login, então não há "quem mudou" — entra com o E1.
    """

    __tablename__ = "historico_de_preco"

    id: Mapped[int] = mapped_column(primary_key=True)
    oportunidade_id: Mapped[int] = mapped_column(
        sa.ForeignKey("oportunidade.id"), nullable=False, index=True
    )
    registrado_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=agora, nullable=False
    )
    origem: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    motivo: Mapped[str | None] = mapped_column(sa.String(200))

    preco_mensal_anterior: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_mensal_novo: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual_anterior: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual_novo: Mapped[Decimal | None] = mapped_column(DINHEIRO)

    oportunidade: Mapped["Oportunidade"] = relationship(back_populates="historico_de_preco")


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

    empresa_id: Mapped[int | None] = mapped_column(sa.ForeignKey("empresa.id"), index=True)
    """O CNPJ a que o contrato se refere. Nulo quando o contrato é do grupo inteiro (o que
    nasce da conversão de uma oportunidade, que ainda não conhece o CNPJ)."""
    anterior_ao_crm: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    """Contrato da carteira que já existia **antes** do CRM (carga de 26/09/2026, a partir da
    planilha de saúde da carteira). A data de assinatura dele é desconhecida, e **não se
    inventa uma**: pode ficar Ativo sem `data_inicio`, e no MRR conta como existente desde
    sempre — nunca como "novo" de um período."""

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
    empresa: Mapped["Empresa | None"] = relationship()
    eventos: Mapped[list["EventoDeContrato"]] = relationship(
        back_populates="contrato", order_by="EventoDeContrato.id.desc()"
    )

    def __repr__(self) -> str:
        return f"<Contrato {self.id} grupo={self.grupo_id} {self.situacao.value}>"


#: JSON genérico, JSONB no PostgreSQL — mesma razão de `Oportunidade.campos_do_crm`.
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


class FichaDeConta(CarimboMixin, Base):
    """O que o agente SDR sabe de uma conta antes do primeiro contato.

    **Nunca é sobrescrita**: cada preparo grava uma ficha nova, e a abordagem
    aponta a que usou. Assim dá para ver depois em que o rascunho se baseou.
    """

    __tablename__ = "ficha_de_conta"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), nullable=False, index=True
    )
    historico: Mapped[str] = mapped_column(sa.Text, nullable=False)
    """O resumo do que a Critério já fez com a conta, do CRM e do contexto
    informado na abordagem."""
    pesquisa: Mapped[list[dict]] = mapped_column(
        _JSON, nullable=False, default=list, server_default=sa.text("'[]'")
    )
    """Fatos públicos, cada um `{"fato": ..., "fonte": url}`. Fato sem fonte
    não entra — é a regra que a conferência cobra antes da aprovação."""
    quem_decide: Mapped[str | None] = mapped_column(sa.String(300))
    modelo: Mapped[str] = mapped_column(sa.String(60), nullable=False)


class Abordagem(CarimboMixin, Base):
    """O primeiro contato com uma conta âncora: ficha, rascunho e aprovação.

    Plano de go-to-market de 26/09/2026. O agente SDR prepara; **só Eduardo
    aprova**, e só a aprovação dispara o envio. O agente não tem ferramenta de
    envio — a separação é do código, não de uma instrução ao modelo.
    """

    __tablename__ = "abordagem"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), nullable=False, index=True
    )
    mes: Mapped[str] = mapped_column(sa.String(7), nullable=False, index=True)
    """Mês de abordagem do plano, `AAAA-MM`."""
    quem_apresenta: Mapped[str | None] = mapped_column(sa.String(120))
    """Quem abre a conversa. Sem ele a abordagem fica bloqueada: o plano manda
    o primeiro contato vir de quem trouxe a conta."""
    contexto: Mapped[str | None] = mapped_column(sa.Text)
    """O histórico que não está no CRM (propostas de antes de 2026, conversas),
    escrito por uma pessoa. Entra na ficha como fato da Critério."""

    canal: Mapped[CanalDeAbordagem] = mapped_column(
        coluna_lista(CanalDeAbordagem), nullable=False, default=CanalDeAbordagem.EMAIL
    )
    destinatario: Mapped[str | None] = mapped_column(sa.String(200))
    """E-mail ou telefone, conforme o canal."""
    assunto: Mapped[str | None] = mapped_column(sa.String(300))
    mensagem: Mapped[str | None] = mapped_column(sa.Text)
    versao: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=0, server_default=sa.text("0")
    )

    situacao: Mapped[SituacaoAbordagem] = mapped_column(
        coluna_lista(SituacaoAbordagem),
        nullable=False,
        default=SituacaoAbordagem.A_PREPARAR,
        index=True,
    )
    erro: Mapped[str | None] = mapped_column(sa.Text)

    ficha_id: Mapped[int | None] = mapped_column(sa.ForeignKey("ficha_de_conta.id"))

    aprovada_por: Mapped[str | None] = mapped_column(sa.String(10))
    aprovada_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    enviada_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    """Carimbados pelo **servidor**, nunca pelo navegador — mesma regra de
    `Oportunidade.porte_definido_em`."""
    diagnostico_agendado_em: Mapped[date | None] = mapped_column(sa.Date)

    grupo: Mapped[GrupoEconomico] = relationship()
    ficha: Mapped[FichaDeConta | None] = relationship()

    def __repr__(self) -> str:
        return f"<Abordagem {self.id} grupo={self.grupo_id} {self.situacao.value}>"


class ExecucaoDoAgente(Base):
    """Uma chamada do agente SDR: quanto usou, quanto custou, se deu certo.

    Imutável, como `ExecucaoDeCarga`: é o registro do custo do agente, e custo
    que muda depois de anotado deixa de ser prova do que se gastou.
    """

    __tablename__ = "execucao_do_agente"

    id: Mapped[int] = mapped_column(primary_key=True)
    abordagem_id: Mapped[int] = mapped_column(
        sa.ForeignKey("abordagem.id"), nullable=False, index=True
    )
    iniciada_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, index=True
    )
    terminada_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    modelo: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    tokens_entrada: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    tokens_saida: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    buscas_web: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    custo_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 4))
    """Estimado pela tabela de preços do código. Nulo para modelo sem preço
    conhecido — nunca zero, que pareceria "saiu de graça"."""
    deu_certo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    erro: Mapped[str | None] = mapped_column(sa.Text)


class EventoDeContrato(Base):
    """Algo que aconteceu com o contrato depois de assinado: aditivo, reajuste,
    expansão, contração, renovação ou encerramento.

    Guarda o **antes e o depois** do que o evento mudou. **Imutável** (não herda o
    carimbo de alteração): errou, registra outro evento — o histórico não se
    reescreve. Ainda não registra *quem* (sem login; entra com o E1).
    Regras em `crm.domain.eventos_de_contrato`.
    """

    __tablename__ = "evento_de_contrato"

    id: Mapped[int] = mapped_column(primary_key=True)
    contrato_id: Mapped[int] = mapped_column(
        sa.ForeignKey("contrato.id"), nullable=False, index=True
    )
    tipo: Mapped[TipoDeEventoDeContrato] = mapped_column(
        coluna_lista(TipoDeEventoDeContrato), nullable=False, index=True
    )
    data_do_evento: Mapped[date] = mapped_column(sa.Date, nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=agora, nullable=False
    )
    descricao: Mapped[str | None] = mapped_column(sa.String(500))
    """No encerramento, detalha a `motivo_categoria` (obrigatório só em "Outro")."""
    motivo_categoria: Mapped[MotivoDeEncerramento | None] = mapped_column(
        coluna_lista(MotivoDeEncerramento, tamanho=60), index=True
    )
    """Só no encerramento. Nulo em qualquer outro evento."""
    iniciativa: Mapped[IniciativaDoEncerramento | None] = mapped_column(
        coluna_lista(IniciativaDoEncerramento), index=True
    )
    """Quem decidiu encerrar: `Cliente` ou `Critério`. Só no encerramento."""

    preco_mensal_anterior: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_mensal_novo: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual_anterior: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual_novo: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    escopo_anterior: Mapped[str | None] = mapped_column(sa.String(200))
    escopo_novo: Mapped[str | None] = mapped_column(sa.String(200))
    data_fim_anterior: Mapped[date | None] = mapped_column(sa.Date)
    data_fim_nova: Mapped[date | None] = mapped_column(sa.Date)

    contrato: Mapped[Contrato] = relationship(back_populates="eventos")


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
