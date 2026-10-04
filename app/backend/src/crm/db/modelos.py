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
from crm.domain.base_de_conhecimento import BlocoDaBase, SituacaoDaFicha
from crm.domain.listas import (
    AutorDaMensagem,
    CanalDeAbordagem,
    DesfechoDaConversa,
    DestinoDoTransbordo,
    IndiceDeReajuste,
    LinhaServico,
    MotivoDeDescarte,
    MotivoDeTransbordo,
    Tom,
    MotivoRecusa,
    Origem,
    PapelContato,
    Situacao,
    SituacaoAbordagem,
    SituacaoContrato,
    SituacaoDoQuestionario,
    SituacaoEmpresa,
    TipoDeMatriz,
    SituacaoGrupo,
    SituacaoLead,
    Temperatura,
    TipoCanal,
    IniciativaDoEncerramento,
    MotivoDeEncerramento,
    TipoDeEventoDeContrato,
    TipoDeOcorrencia,
    SituacaoDaAprovacao,
)

__all__ = [
    "FichaDaBase",
    "GrupoEconomico",
    "Empresa",
    "PessoaContato",
    "Lead",
    "Oportunidade",
    "Contrato",
    "FichaDeConta",
    "Abordagem",
    "ExecucaoDoAgente",
    "ClassificacaoDoGrupo",
    "EventoDeContrato",
    "FusaoDeGrupos",
    "HistoricoDePreco",
    "ExecucaoDeCarga",
    "OcorrenciaDeCarga",
    "AnaliseDaCarteira",
    "RevisaoDaCarteira",
    "ConversaDoSdr",
    "MensagemDoSdr",
    "ParametrosDoSdr",
    "InvestimentoEmMidia",
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

    documentos_fiscais_mes: Mapped[int | None] = mapped_column(sa.Integer)
    lancamentos_contabeis_mes: Mapped[int | None] = mapped_column(sa.Integer)
    pagamentos_mes: Mapped[int | None] = mapped_column(sa.Integer)
    contas_bancarias: Mapped[int | None] = mapped_column(sa.Integer)
    conciliacoes_cartao_mes: Mapped[int | None] = mapped_column(sa.Integer)
    empregados_clt: Mapped[int | None] = mapped_column(sa.Integer)
    admissoes_desligamentos_mes: Mapped[int | None] = mapped_column(sa.Integer)
    cnpjs_no_escopo: Mapped[int | None] = mapped_column(sa.Integer)
    tomadores_de_servico: Mapped[int | None] = mapped_column(sa.Integer)
    """Os nove direcionadores da régua de porte (`crm.domain.porte`), agora também na carteira —
    não só na oportunidade. `None` é "não se aplica ao escopo contratado"."""

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
    """O porte **confirmado** do grupo — não o calculado. A régua só sugere (`crm.domain.porte`);
    este campo é o que a pessoa aceitou ou sobrepôs. Não entra no Score: por isso mora aqui, no
    grupo, e não numa nova linha de `ClassificacaoDoGrupo` a cada revisão."""
    porte_definido_por: Mapped[str | None] = mapped_column(sa.String(120))
    """120, não 10 como em `Oportunidade.porte_definido_por` — lá é iniciais; aqui é o mesmo
    campo de nome completo que `ClassificacaoDoGrupo.atribuido_por` e o painel de avaliação usam."""
    porte_definido_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    porte_justificativa: Mapped[str | None] = mapped_column(sa.String(500))
    """Por que o porte confirmado difere da sugestão do questionário (29/09/2026: obrigatória
    nesse caso). Vazia quando o porte seguiu a sugestão."""

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
    """Quem se fala. Ligada a uma ou mais empresas (`VinculoDeContato`), ou
    ainda a nenhuma — nunca ao grupo: as empresas de uma pessoa nem sempre são
    do mesmo grupo (Karine, 01/10/2026). O grupo mora na empresa.

    Desde 30/09/2026 (pedido de Karine): a pessoa é cadastrada antes da
    empresa e pode estar em várias empresas — base única de contatos, sem
    recadastrar a mesma pessoa a cada empresa nova.
    """

    __tablename__ = "pessoa_contato"

    id: Mapped[int] = mapped_column(primary_key=True)
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

    vinculos: Mapped[list[VinculoDeContato]] = relationship(
        back_populates="pessoa", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PessoaContato {self.id} {self.nome!r}>"


class VinculoDeContato(CarimboMixin, Base):
    """A pessoa numa empresa. Uma pessoa em várias empresas, uma empresa com
    vários contatos, e mais de um principal por empresa (pedido de Karine em
    30/09/2026). "Principal" é do vínculo: principal na Delta, não na Alfa.

    Cargo, e-mail e telefone continuam na pessoa, iguais em todas as empresas
    (suposição aprovada junto com a proposta).
    """

    __tablename__ = "vinculo_de_contato"

    id: Mapped[int] = mapped_column(primary_key=True)
    pessoa_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pessoa_contato.id", ondelete="CASCADE"), nullable=False, index=True
    )
    empresa_id: Mapped[int] = mapped_column(
        sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False, index=True
    )
    principal: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )

    pessoa: Mapped[PessoaContato] = relationship(back_populates="vinculos")
    empresa: Mapped[Empresa] = relationship()

    __table_args__ = (sa.UniqueConstraint("pessoa_id", "empresa_id", name="uq_vinculo_pessoa_empresa"),)

    def __repr__(self) -> str:
        return f"<VinculoDeContato pessoa={self.pessoa_id} empresa={self.empresa_id}>"


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
    interesse_descricao: Mapped[str | None] = mapped_column(sa.Text)
    """Só quando o interesse é "Outro": o que o lead pediu, com as palavras dele."""
    interesse_tema: Mapped[str | None] = mapped_column(sa.String(80))
    """O tema, quando o serviço de interesse tem temas (Consultoria)."""
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

    # --- Qualificação (SDR de IA, 27/09/2026) -------------------------------
    cnpj: Mapped[str | None] = mapped_column(sa.String(18))
    porte_estimado: Mapped[str | None] = mapped_column(sa.String(20))
    """Sugestão da régua de porte com o que o lead informou. **Não é o porte da
    oportunidade**: esse continua sendo confirmado por uma pessoa, com autor e
    data (`Oportunidade.porte_definido_por`)."""
    qualificado_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    descartado_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    motivo_descarte: Mapped[MotivoDeDescarte | None] = mapped_column(
        coluna_lista(MotivoDeDescarte, 60)
    )
    reuniao_marcada_para: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    nao_contatar: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    """Pedido de não ser contatado. Nenhuma mensagem da IA ou da equipe é
    registrada para este lead depois disso — a rota recusa."""
    nao_contatar_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    conversas: Mapped[list["ConversaDoSdr"]] = relationship(
        back_populates="lead", order_by="ConversaDoSdr.id"
    )

    def __repr__(self) -> str:
        return f"<Lead {self.id} {self.nome!r} {self.situacao.value}>"


class Oportunidade(CarimboMixin, Base):
    """Uma proposta, enviada ou por enviar. É a linha da planilha de 2026."""

    __tablename__ = "oportunidade"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("grupo_economico.id"), nullable=False, index=True
    )
    empresa_id: Mapped[int | None] = mapped_column(sa.ForeignKey("empresa.id"), index=True)
    """A empresa (o CNPJ) da oportunidade, escolhida na base de empresas; o grupo vem dela.
    Pedido de Karine em 01/10/2026. Nulo nas antigas cujo grupo tem mais de uma empresa."""
    nome: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)

    servico: Mapped[str | None] = mapped_column(sa.String(120))
    tipo_servico: Mapped[str | None] = mapped_column(sa.String(120))
    linha_servico: Mapped[LinhaServico | None] = mapped_column(coluna_lista(LinhaServico))
    servico_descricao: Mapped[str | None] = mapped_column(sa.Text)
    """Só quando o serviço é "Outro": o que o lead pediu, com as palavras dele."""
    servico_tema: Mapped[str | None] = mapped_column(sa.String(80))
    """O tema, quando o serviço tem temas (Consultoria). Campo do CRM: a
    planilha não tem essa coluna, e `tipo_servico` faz parte da identidade da
    proposta na carga, então não pode ser reaproveitado."""

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
    quantidade_parcelas: Mapped[int | None] = mapped_column(sa.SmallInteger)
    """Só em serviço recorrente (C1): o preço anual é mensal × parcelas, sem ajuste à mão.
    Pedido de Karine em 30/09/2026."""
    reajuste: Mapped[IndiceDeReajuste | None] = mapped_column(coluna_lista(IndiceDeReajuste))
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

    ficha: Mapped[dict[str, dict]] = mapped_column(
        sa.JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'"),
    )
    """O que se corrigiu da ficha na entrevista (E4, 02/10/2026): `{chave: {"valor", "por", "em"}}`,
    com a chave do questionário do site (`crm.proposta.ficha`). Vale sobre a resposta do
    questionário, que continua guardada em `QuestionarioRecebido.respostas`."""

    historico_de_preco: Mapped[list["HistoricoDePreco"]] = relationship(
        back_populates="oportunidade",
        order_by="HistoricoDePreco.id.desc()",
    )

    linha_planilha: Mapped[int | None] = mapped_column(sa.Integer)
    """Onde estava na aba quando foi importada. Serve para apontar a origem no
    relatório de conferência — **não** é identidade: número de linha se desloca.
    """

    grupo: Mapped[GrupoEconomico] = relationship(back_populates="oportunidades")
    empresa: Mapped[Empresa | None] = relationship()
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


NOTA = sa.Numeric(4, 2)  # nota de grupo é média das empresas: vem com casas decimais


class ClassificacaoDoGrupo(Base):
    """Uma leitura da classificação de um grupo em uma data — Etapa 3 (26/09/2026).

    **Snapshot imutável**: nova classificação = nova linha, nunca sobrescreve a anterior (é o que
    permite comparar o ISC de um mês com o do mês seguinte). Guarda as notas de entrada, o que o CRM
    calculou e **qual versão dos parâmetros** o produziu. A regra está em `crm.domain.classificacao`.

    **A nota de rentabilidade não é calculada pelo CRM ainda**: vem da planilha (defeito 7.2, margem e
    atrito, à espera de conferência). `rentabilidade_da_planilha` diz isso em cada linha.
    """

    __tablename__ = "classificacao_do_grupo"
    __table_args__ = (sa.UniqueConstraint("grupo_id", "referencia", "revisao", name="uq_classificacao_grupo_referencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), nullable=False, index=True)
    revisao: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=1, server_default="1")
    """Nova leitura da mesma referência (ex.: rentabilidade recalculada): revisão maior vence, a anterior fica."""
    referencia: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    """A data a que a leitura se refere (a da planilha), não a do carregamento."""
    fonte: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    versao_dos_parametros: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    atribuido_por: Mapped[str | None] = mapped_column(sa.String(120))
    """Quem mudou as notas humanas numa edição manual; `None` nas cargas de planilha."""
    motivo: Mapped[str | None] = mapped_column(sa.String(500))

    receita_mensal: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    margem: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 4))
    horas_por_mes: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2))
    rentabilidade_da_planilha: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())

    nota_receita: Mapped[Decimal] = mapped_column(NOTA, nullable=False)
    nota_rentabilidade: Mapped[Decimal] = mapped_column(NOTA, nullable=False)
    complexidade: Mapped[Decimal] = mapped_column(NOTA, nullable=False)
    disciplina: Mapped[Decimal] = mapped_column(NOTA, nullable=False)
    risco_tecnico: Mapped[Decimal] = mapped_column(NOTA, nullable=False)
    cross_sell: Mapped[Decimal] = mapped_column(NOTA, nullable=False)
    adimplencia: Mapped[Decimal] = mapped_column(NOTA, nullable=False)
    semaforo: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    churn: Mapped[int | None] = mapped_column(sa.SmallInteger)
    """Nota de churn 1 a 5. Antes escondida dentro da fórmula da planilha (defeito 7.1): aqui é campo."""

    score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 4), nullable=False)
    classe: Mapped[str] = mapped_column(sa.String(1), nullable=False, index=True)
    classe_efetiva: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    alerta_de_churn: Mapped[str | None] = mapped_column(sa.String(1))
    em_cobranca: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    eixo_de_acao: Mapped[str] = mapped_column(sa.String(60), nullable=False, index=True)

    respostas_da_avaliacao: Mapped[dict | None] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"))
    """O que foi marcado no painel Avaliar e produziu as notas humanas (29/09/2026). Sem isto o
    painel reabria em branco, e gravar de novo trocava as notas boas pelas do painel vazio."""

    grupo: Mapped[GrupoEconomico] = relationship()


PARAMETRO = sa.Numeric(6, 4)


class VersaoDeParametros(Base):
    """Os parâmetros do Score e da Rentabilidade — pesos, cortes e a matriz de horas/mix/taxa por
    Porte (Etapa 3, 28/09/2026, decisão de Eduardo: "podem variar", então saem do código e viram
    linha de banco).

    **Snapshot imutável, como `ClassificacaoDoGrupo`**: uma edição grava uma versão nova, a
    anterior nunca é tocada — é o que mantém `ClassificacaoDoGrupo.versao_dos_parametros` de uma
    classificação antiga apontando para algo estável mesmo depois dos pesos mudarem. A vigente é
    sempre a de `criado_em` mais recente. A regra de construção e validação está em
    `crm.domain.parametros`."""

    __tablename__ = "versao_de_parametros"

    id: Mapped[int] = mapped_column(primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False, index=True)
    autor: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    motivo: Mapped[str] = mapped_column(sa.String(500), nullable=False)

    # Pesos do Score — somam 100% (validado antes de gravar, não pelo banco).
    peso_receita: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    peso_rentabilidade: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    peso_cross_sell: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    peso_complexidade: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    peso_disciplina: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    peso_risco: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    peso_adimplencia: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    corte_a: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    corte_b: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    trava_de_adimplencia: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    churn_alto: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)

    # Rentabilidade: imposto, atrito e cortes de margem.
    imposto: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    teto_de_atrito: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    atrito_nota_1: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    atrito_nota_2: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    atrito_nota_3: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    atrito_nota_4: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    atrito_nota_5: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    corte_margem_2: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    corte_margem_3: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    corte_margem_4: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)
    corte_margem_5: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)

    # Matriz de horas por Porte (seção 2 da régua de porte).
    horas_micro: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    horas_pequeno: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    horas_medio: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    horas_grande: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    horas_extra_grande: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)

    # Taxa por hora, por cargo (R$/h) — não varia por Porte; o mix é que varia (tabela `MixDeEquipe`).
    taxa_socio_senior: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    taxa_socio_junior: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    taxa_supervisor: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    taxa_analista_senior: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    taxa_analista_pleno: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    taxa_analista_junior: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)

    mix: Mapped[list["MixDeEquipe"]] = relationship(back_populates="versao", cascade="all, delete-orphan")


class MixDeEquipe(Base):
    """Uma célula da "MATRIZ DE HORAS E MIX DE EQUIPE — por Porte do cliente": quanto do tempo de
    um cargo entra no atendimento de cada Porte. Junto com as taxas de `VersaoDeParametros`,
    produz o custo/hora ponderado — calculado sempre, nunca digitado solto (ver
    `crm.domain.parametros.custo_hora_por_porte`). Cinco Portes × seis cargos = 30 linhas por
    versão; a soma por Porte precisa fechar 100%."""

    __tablename__ = "mix_de_equipe"
    __table_args__ = (sa.UniqueConstraint("versao_id", "porte", "cargo", name="uq_mix_versao_porte_cargo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    versao_id: Mapped[int] = mapped_column(sa.ForeignKey("versao_de_parametros.id"), nullable=False, index=True)
    porte: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    cargo: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    mix_percentual: Mapped[Decimal] = mapped_column(PARAMETRO, nullable=False)

    versao: Mapped[VersaoDeParametros] = relationship(back_populates="mix")


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
    base_do_valor: Mapped[str | None] = mapped_column(sa.String(10))
    """"bruto" ou "liquido" (02/10/2026, aprovado por Eduardo): se o preço do contrato já inclui o
    imposto. O MRR soma em bruto; o líquido entra com o imposto dos Parâmetros. Vazio = não informado
    (soma como está, com aviso). Contrato que nasce de proposta do CRM é líquido."""

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


class AnaliseDaCarteira(Base):
    """Um parágrafo escrito pela IA descrevendo a carteira — Etapa 3 (27/09/2026).

    Só descreve os números já calculados (ISC, componentes, retrato, travados); nunca decide nada e
    nunca aparece sozinha sem alguém pedir ("Gerar análise"). Imutável: uma nova geração cria uma
    linha nova, a anterior fica no histórico."""

    __tablename__ = "analise_da_carteira"

    id: Mapped[int] = mapped_column(primary_key=True)
    gerada_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False, index=True)
    gerada_por: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    texto: Mapped[str] = mapped_column(sa.Text, nullable=False)
    modelo: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    tokens_entrada: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    tokens_saida: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    custo_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 4))
    """Estimado pela tabela de preços do código. Nulo para modelo sem preço conhecido."""



class PeriodoDeAvaliacao(Base):
    """Um ciclo de avaliação da carteira (29/09/2026, pedido de Eduardo).

    Aberto por alguém, recebe os rascunhos de cada grupo (`AvaliacaoEmAndamento`) e só muda a
    carteira no "Calcular carteira", que exige todos os grupos completos. A janela de rentabilidade
    (mínima e alvo) é do período: pode variar de um para outro. Um aberto por vez."""

    __tablename__ = "periodo_de_avaliacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    mes_de_referencia: Mapped[date] = mapped_column(sa.Date, nullable=False, unique=True)
    """O primeiro dia do mês civil do período."""
    aberto_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    aberto_por: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    margem_minima: Mapped[Decimal] = mapped_column(sa.Numeric(6, 4), nullable=False)
    margem_alvo: Mapped[Decimal] = mapped_column(sa.Numeric(6, 4), nullable=False)
    calculado_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    """Preenchido pelo "Calcular carteira": daí em diante o período está fechado."""
    calculado_por: Mapped[str | None] = mapped_column(sa.String(120))


class AvaliacaoEmAndamento(Base):
    """O rascunho da avaliação de um grupo num período. Cada setor grava o que tem; nada aqui
    mexe no Score até o "Calcular carteira". Aba presente em `respostas` = revista."""

    __tablename__ = "avaliacao_em_andamento"
    __table_args__ = (sa.UniqueConstraint("periodo_id", "grupo_id", name="uq_avaliacao_periodo_grupo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    periodo_id: Mapped[int] = mapped_column(sa.ForeignKey("periodo_de_avaliacao.id"), nullable=False, index=True)
    grupo_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), nullable=False, index=True)
    respostas: Mapped[dict] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    atualizado_por: Mapped[str] = mapped_column(sa.String(120), nullable=False)


class RevisaoDaCarteira(Base):
    """A revisão mensal do ISC — ritual da seção 6 do modelo de classificação (27/09/2026).

    Congela o ISC, os três componentes e o retrato da carteira (grupos, receita, travados) do momento
    em que alguém clica "Registrar revisão". Não recalcula nada sozinha: é o placar do mês, depois de
    quem revisa atualizar as notas que precisar. Uma por mês civil. `mes_de_referencia` pode ser
    corrigido depois (rótulo), mas os números congelados nunca mudam."""

    __tablename__ = "revisao_da_carteira"
    __table_args__ = (sa.UniqueConstraint("mes_de_referencia", name="uq_revisao_carteira_mes"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mes_de_referencia: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    """O primeiro dia do mês civil a que esta revisão se refere — editável, é só o rótulo."""
    registrada_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    registrada_por: Mapped[str] = mapped_column(sa.String(120), nullable=False)

    isc_valor: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    isc_zona: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    componente_classe: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    componente_semaforo: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    componente_churn: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)

    grupos: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    receita_total: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    grupos_travados: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    receita_travada: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    percentual_travado: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False)

    baseado_em_referencia: Mapped[date] = mapped_column(sa.Date, nullable=False)
    """A referência mais recente das classificações usadas para montar este retrato."""


class ConversaDoSdr(CarimboMixin, Base):
    """Uma conversa do SDR de IA com um lead — é o que alimenta o painel.

    Registrada pela integração do canal (WhatsApp ou e-mail) a cada mensagem.
    Decisão de Eduardo em 27/09/2026: o SDR de IA **envia sozinho**, sem
    aprovação por mensagem. As travas continuam no servidor: sem preço, nada
    para quem pediu para não ser contatado.
    """

    __tablename__ = "conversa_do_sdr"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(sa.ForeignKey("lead.id"), nullable=False, index=True)
    canal: Mapped[CanalDeAbordagem] = mapped_column(coluna_lista(CanalDeAbordagem), nullable=False)
    iniciada_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=agora, index=True
    )
    encerrada_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    desfecho: Mapped[DesfechoDaConversa | None] = mapped_column(coluna_lista(DesfechoDaConversa))
    """Nulo enquanto a conversa está em andamento."""

    motivo_transbordo: Mapped[MotivoDeTransbordo | None] = mapped_column(
        coluna_lista(MotivoDeTransbordo, 60)
    )
    destino_transbordo: Mapped[DestinoDoTransbordo | None] = mapped_column(
        coluna_lista(DestinoDoTransbordo, 60)
    )
    atendida_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    """Primeira mensagem da equipe depois do transbordo. Carimbada pelo servidor
    ao registrar essa mensagem — é o fim da espera do lead."""

    nota: Mapped[int | None] = mapped_column(sa.SmallInteger)
    """CSAT de 1 a 5, dado pelo lead ao fim da conversa."""

    lead: Mapped[Lead] = relationship(back_populates="conversas")
    mensagens: Mapped[list["MensagemDoSdr"]] = relationship(
        back_populates="conversa", order_by="MensagemDoSdr.id"
    )

    __table_args__ = (
        sa.CheckConstraint("nota IS NULL OR nota BETWEEN 1 AND 5", name="nota_de_1_a_5"),
    )

    def __repr__(self) -> str:
        return f"<ConversaDoSdr {self.id} lead={self.lead_id}>"


class MensagemDoSdr(Base):
    """Uma mensagem da conversa. Imutável: o registro do que foi dito."""

    __tablename__ = "mensagem_do_sdr"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        sa.ForeignKey("conversa_do_sdr.id"), nullable=False, index=True
    )
    autor: Mapped[AutorDaMensagem] = mapped_column(coluna_lista(AutorDaMensagem), nullable=False)
    enviada_em: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=agora
    )
    texto: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # Só nas mensagens da IA.
    intencao: Mapped[str | None] = mapped_column(sa.String(120))
    """O assunto que a IA reconheceu na mensagem do lead que ela respondeu."""
    confianca: Mapped[Decimal | None] = mapped_column(sa.Numeric(3, 2))
    """Certeza do modelo na intenção, de 0 a 1."""
    fallback: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    """A IA respondeu "não entendi" ou caiu na intenção padrão de erro."""
    termo_nao_reconhecido: Mapped[str | None] = mapped_column(sa.String(120))
    custo_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 4))

    # Só nas mensagens do lead.
    tom: Mapped[Tom | None] = mapped_column(coluna_lista(Tom))

    conversa: Mapped[ConversaDoSdr] = relationship(back_populates="mensagens")

    __table_args__ = (
        sa.CheckConstraint(
            "confianca IS NULL OR confianca BETWEEN 0 AND 1", name="confianca_de_0_a_1"
        ),
    )


class ParametrosDoSdr(CarimboMixin, Base):
    """Os valores do cálculo de custo poupado. Uma linha só.

    Sem eles o painel não inventa: mostra o custo poupado como "falta definir".
    """

    __tablename__ = "parametros_do_sdr"

    id: Mapped[int] = mapped_column(primary_key=True)
    custo_hora_sdr: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    """Quanto custa uma hora de um SDR humano: salário × encargos ÷ horas."""
    minutos_por_conversa: Mapped[int | None] = mapped_column(sa.SmallInteger)
    """Quanto um SDR humano levaria para fazer a mesma qualificação."""
    cotacao_dolar: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 4))
    """Converte o custo da IA, medido em dólar, para reais."""
    atualizado_por: Mapped[str | None] = mapped_column(sa.String(10))


class InvestimentoEmMidia(CarimboMixin, Base):
    """Quanto se investiu em mídia num mês, por canal de tráfego pago.

    Digitado à mão até existir integração com Meta Ads e Google Ads.
    """

    __tablename__ = "investimento_em_midia"

    id: Mapped[int] = mapped_column(primary_key=True)
    mes: Mapped[str] = mapped_column(sa.String(7), nullable=False, index=True)
    """`AAAA-MM`."""
    canal: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    """O mesmo texto de `Lead.canal` nos leads de tráfego pago ("Meta Ads")."""
    valor: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("mes", "canal", name="uq_investimento_mes_canal"),
        sa.CheckConstraint("valor >= 0", name="valor_nao_negativo"),
    )


class QuestionarioRecebido(CarimboMixin, Base):
    """Um questionário para proposta enviado pelo cliente no site e trazido pelo "Buscar
    questionários" (01/10/2026). Guarda a resposta inteira, como chegou: o que o CRM fez com ela
    está em `oportunidade_id` e `o_que_fez`."""

    __tablename__ = "questionario_recebido"

    id: Mapped[int] = mapped_column(primary_key=True)
    externo_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    """O `id` da linha no Supabase: buscar de novo nunca duplica."""
    recebido_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    versao: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    razao_social: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(sa.String(200))
    cnpj: Mapped[str] = mapped_column(sa.String(14), nullable=False, index=True)
    contato_nome: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    contato_cargo: Mapped[str | None] = mapped_column(sa.String(100))
    contato_celular: Mapped[str | None] = mapped_column(sa.String(30))
    contato_email: Mapped[str | None] = mapped_column(sa.String(200))
    respostas: Mapped[dict] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    avaliacao_do_site: Mapped[dict | None] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"))
    """O cálculo que o próprio formulário fez, em JavaScript. Só para comparação: vale o do CRM."""
    pdf_base64: Mapped[str | None] = mapped_column(sa.Text)
    """O PDF que o cliente viu, em base64 (texto, para o backup lógico levar junto)."""

    situacao: Mapped[SituacaoDoQuestionario] = mapped_column(
        coluna_lista(SituacaoDoQuestionario), nullable=False, index=True
    )
    o_que_fez: Mapped[str] = mapped_column(sa.Text, nullable=False)
    grupo_id: Mapped[int | None] = mapped_column(sa.ForeignKey("grupo_economico.id"), index=True)
    oportunidade_id: Mapped[int | None] = mapped_column(sa.ForeignKey("oportunidade.id"), index=True)
    oportunidade_em_aberto_id: Mapped[int | None] = mapped_column(sa.ForeignKey("oportunidade.id"))
    """Só em "Precisa de você": a oportunidade em aberto que já existia para o CNPJ."""
    cliente_novo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    porte_crm: Mapped[str | None] = mapped_column(sa.String(20))
    porte_site: Mapped[str | None] = mapped_column(sa.String(20))
    marcado_na_origem_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    """Quando o Supabase aceitou a marca de importado. Vazio = a marca falhou; na próxima busca ele
    volta e o CRM só tenta marcar de novo."""


class MatrizDeProposta(Base):
    """Um PowerPoint de proposta subido em Configurações › Propostas (01/10/2026). Trocar a matriz é subir
    outra: a anterior fica, para que uma proposta já gerada saia de novo exatamente igual.

    **Imutável de propósito**, como `HistoricoDePreco`: não herda o carimbo de alteração."""

    __tablename__ = "matriz_de_proposta"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoDeMatriz] = mapped_column(coluna_lista(TipoDeMatriz), nullable=False, index=True)
    nome_arquivo: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    conteudo_base64: Mapped[str] = mapped_column(sa.Text, nullable=False)
    """O .pptx em base64 (texto, para o backup lógico levar junto, como o PDF do questionário)."""
    enviada_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    enviada_por: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    faltando: Mapped[list[str]] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    """Marcadores obrigatórios que não estão no arquivo. Não vazio = matriz não usada até trocar."""
    desconhecidos: Mapped[list[str]] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    """Marcadores que o CRM não conhece (erro de digitação): também impedem o uso."""


class ConfiguracaoDeProposta(CarimboMixin, Base):
    """Uma linha só: o próximo número da sequência PROP CCE RJ, quem revisa e envia, e o preço de
    tabela dos três planos da matriz Financeiro. A alíquota é o imposto dos Parâmetros."""

    __tablename__ = "configuracao_de_proposta"

    id: Mapped[int] = mapped_column(primary_key=True)
    proximo_numero: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    revisores: Mapped[list[str]] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    plano_bpo: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    plano_plus: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    plano_cfo: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)


class Proposta(CarimboMixin, Base):
    """Uma proposta gerada em PowerPoint. O número (PROP CCE RJ 154.2026) é único e não volta: gerar
    de novo antes de enviar regrava a mesma proposta; depois de enviada, gerar abre número novo.
    `valores` guarda tudo o que foi preenchido, para baixar de novo exatamente igual."""

    __tablename__ = "proposta"
    __table_args__ = (sa.UniqueConstraint("ano", "numero", name="uq_proposta_ano_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    oportunidade_id: Mapped[int] = mapped_column(sa.ForeignKey("oportunidade.id"), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    ano: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    matriz_id: Mapped[int] = mapped_column(sa.ForeignKey("matriz_de_proposta.id"), nullable=False)
    valores: Mapped[dict] = mapped_column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    valor_liquido: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    """Total mensal líquido (Contábil + DP); vazio na matriz Financeiro, que mostra três planos."""
    valor_bruto: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    gerada_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    enviada_em: Mapped[date | None] = mapped_column(sa.Date)
    enviada_por: Mapped[str | None] = mapped_column(sa.String(60))



class PendenciaDaProposta(CarimboMixin, Base):
    """Um item de "o que falta para a proposta" (E4, 02/10/2026).

    Item **manual**: `descricao` escrita por alguém, fechado com `feita_em`. Item **automático**: o
    CRM confere sozinho (`crm.proposta.pendencias`) e fecha quando o dado chega; a linha só existe
    para guardar o responsável e o prazo que alguém lhe deu, pela `chave` da regra."""

    __tablename__ = "pendencia_da_proposta"
    __table_args__ = (sa.UniqueConstraint("oportunidade_id", "chave", name="uq_pendencia_oportunidade_chave"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    oportunidade_id: Mapped[int] = mapped_column(
        sa.ForeignKey("oportunidade.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chave: Mapped[str | None] = mapped_column(sa.String(40))
    """A regra automática (ex. "volumes", "porte"); vazio no item manual."""
    descricao: Mapped[str | None] = mapped_column(sa.String(300))
    responsavel: Mapped[str | None] = mapped_column(sa.String(60))
    prazo: Mapped[date | None] = mapped_column(sa.Date)
    criada_por: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    feita_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    feita_por: Mapped[str | None] = mapped_column(sa.String(60))


class Perfil(CarimboMixin, Base):
    """Um perfil de acesso (E1, 02/10/2026): as funcionalidades que ele libera em cada menu, como
    `"funil.converter"` (`crm.acesso.catalogo`). O Administrador tem tudo, inclusive o que vier depois."""

    __tablename__ = "perfil"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(sa.String(60), nullable=False, unique=True)
    administrador: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    permissoes: Mapped[list[str]] = mapped_column(
        sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list, server_default=sa.text("'[]'")
    )


class Usuario(CarimboMixin, Base):
    """Quem pode entrar no CRM: a conta Microsoft (o e-mail) e o perfil. A Microsoft confere quem é; o
    CRM decide o que pode. Desativar tira o acesso sem apagar o histórico de quem a pessoa foi."""

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(200), nullable=False, unique=True)
    """Sempre em minúsculas, como a conta Microsoft entra."""
    nome: Mapped[str | None] = mapped_column(sa.String(200))
    """O nome que a Microsoft informa na primeira entrada; até lá, vazio."""
    perfil_id: Mapped[int] = mapped_column(sa.ForeignKey("perfil.id"), nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())
    liberado_por: Mapped[str | None] = mapped_column(sa.String(200))

    perfil: Mapped[Perfil] = relationship()


class RegistroDeAlteracao(Base):
    """O histórico de alterações por usuário (E1, 02/10/2026): uma linha por campo que mudou, com quem,
    quando, antes e depois. Gravado sozinho a cada gravação no banco (`crm.acesso.auditoria`) quando há
    alguém identificado. **Não se edita nem se apaga**: não herda o carimbo de alteração."""

    __tablename__ = "registro_de_alteracao"
    __table_args__ = (sa.Index("ix_registro_de_alteracao_tabela_registro", "tabela", "registro_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quando: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=agora, index=True)
    usuario_email: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)
    usuario_nome: Mapped[str | None] = mapped_column(sa.String(200))
    acao: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    """criou · alterou · excluiu"""
    tabela: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    registro_id: Mapped[int | None] = mapped_column(sa.Integer)
    descricao: Mapped[str | None] = mapped_column(sa.String(200))
    """Como o registro aparece para as pessoas: o nome da oportunidade, a razão social…"""
    campo: Mapped[str | None] = mapped_column(sa.String(60))
    antes: Mapped[str | None] = mapped_column(sa.Text)
    depois: Mapped[str | None] = mapped_column(sa.Text)
    rota: Mapped[str | None] = mapped_column(sa.String(200))


class PedidoDeAprovacao(Base):
    """Evento de contrato acima da alçada esperando quem aprova (decisões de Eduardo, 02/10/2026).

    Contração e reajuste que reduzem o preço em mais de 10%, e aditivo que muda o escopo (ou reduz o
    preço em mais de 10%), registrados por quem não tem "aprovar eventos de contrato". O contrato só
    muda quando alguém aprova: aí nasce o `EventoDeContrato`, com a data pedida. Regras em
    `crm.domain.alcada`. Não se apaga: recusado fica com o porquê.
    """

    __tablename__ = "pedido_de_aprovacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    contrato_id: Mapped[int] = mapped_column(sa.ForeignKey("contrato.id"), nullable=False, index=True)
    tipo: Mapped[TipoDeEventoDeContrato] = mapped_column(coluna_lista(TipoDeEventoDeContrato), nullable=False)
    data_do_evento: Mapped[date] = mapped_column(sa.Date, nullable=False)
    descricao: Mapped[str | None] = mapped_column(sa.String(500))
    preco_mensal_anterior: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_mensal_novo: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual_anterior: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    preco_anual_novo: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    escopo_anterior: Mapped[str | None] = mapped_column(sa.String(200))
    escopo_novo: Mapped[str | None] = mapped_column(sa.String(200))
    motivo: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    """Por que pediu aprovação, como a tela mostra ("redução de 18,8% no preço mensal")."""
    pedido_por: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    pedido_em: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=agora, nullable=False)
    situacao: Mapped[SituacaoDaAprovacao] = mapped_column(
        coluna_lista(SituacaoDaAprovacao, 20), nullable=False, default=SituacaoDaAprovacao.AGUARDANDO, index=True
    )
    decidido_por: Mapped[str | None] = mapped_column(sa.String(200))
    decidido_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    motivo_da_recusa: Mapped[str | None] = mapped_column(sa.String(500))
    evento_id: Mapped[int | None] = mapped_column(sa.ForeignKey("evento_de_contrato.id"))
    """O evento que nasceu da aprovação."""

    contrato: Mapped[Contrato] = relationship()


class MetaDeIndicador(Base):
    """A meta e o alerta de um indicador, editáveis em Configurações › Metas (02/10/2026, aprovado
    por Eduardo). `chave`: "mrr" (em reais) ou "conversao" (em %). Sem a linha, valem os padrões
    do KPI oficial (`crm.domain.mrr`, `crm.domain.indicadores`). Quem muda fica no histórico."""

    __tablename__ = "meta_de_indicador"

    chave: Mapped[str] = mapped_column(sa.String(30), primary_key=True)
    meta: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    alerta: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    alterado_por: Mapped[str | None] = mapped_column(sa.String(200))
    alterado_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class JornadaDoCliente(CarimboMixin, Base):
    """Em que etapa do Funil do Sucesso do Cliente o grupo está (02/10/2026, aprovado por Eduardo) e
    quais itens do checklist já foram feitos. Regras em `crm.domain.sucesso`.

    Sem a linha, o grupo com contrato valendo está em **Contrato** — ou **Em curso**, se o contrato é
    anterior ao CRM (o cliente já foi implantado). A linha nasce na primeira marcação."""

    __tablename__ = "jornada_do_cliente"

    grupo_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), primary_key=True)
    etapa: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    itens_feitos: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    """As chaves dos itens marcados, de todas as etapas (`crm.domain.sucesso.CHECKLIST`)."""
    etapa_desde: Mapped[date] = mapped_column(sa.Date, nullable=False)
    em_curso_desde: Mapped[date | None] = mapped_column(sa.Date)
    """Quando o kickoff terminou: é daí que se contam as primeiras reuniões de resultado."""
    alterado_por: Mapped[str | None] = mapped_column(sa.String(200))


class ReuniaoDeResultado(CarimboMixin, Base):
    """Uma reunião de resultado feita com o cliente (02/10/2026, aprovado por Eduardo). O objetivo é
    apresentar os números do cliente para ele decidir; por isso guarda as decisões e os próximos
    passos. O dashboard é um link ou caminho, opcional: ainda não existe (Eduardo, 02/10/2026)."""

    __tablename__ = "reuniao_de_resultado"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    """mensal · trimestral · semestral (bimestral e anual, só antes de 03/10/2026)"""
    data: Mapped[date] = mapped_column(sa.Date, nullable=False)
    participantes: Mapped[str | None] = mapped_column(sa.String(300))
    pauta: Mapped[str | None] = mapped_column(sa.Text)
    dashboard: Mapped[str | None] = mapped_column(sa.String(400))
    decisoes: Mapped[str | None] = mapped_column(sa.Text)
    proximos_passos: Mapped[str | None] = mapped_column(sa.Text)
    registrada_por: Mapped[str | None] = mapped_column(sa.String(200))
    resumo: Mapped[str | None] = mapped_column(sa.Text)
    pendencias_do_cliente: Mapped[str | None] = mapped_column(sa.Text)
    pontos_sensiveis: Mapped[str | None] = mapped_column(sa.Text)
    transcricao: Mapped[str | None] = mapped_column(sa.Text)
    """A transcrição do Granola colada para montar a ata (02/10/2026). Dado de cliente: só no banco."""
    estrategia_e_desafios: Mapped[str | None] = mapped_column(sa.Text)
    """O que o cliente contou da estratégia e dos desafios dele (03/10/2026): de onde saem as vendas."""

    grupo: Mapped[GrupoEconomico] = relationship()
    ajustes: Mapped[list["AjusteTecnico"]] = relationship(back_populates="reuniao", order_by="AjusteTecnico.id")
    oportunidades: Mapped[list["OportunidadeDaReuniao"]] = relationship(
        back_populates="reuniao", order_by="OportunidadeDaReuniao.id")


class OportunidadeDaReuniao(CarimboMixin, Base):
    """Um novo negócio que a reunião de resultado achou (aprovado por Eduardo em 03/10/2026): a lacuna
    técnica do cliente e o serviço da Critério que a cobre. Marcada na ata, vira uma oportunidade no
    Funil comercial (`oportunidade_id`); sem marcar, fica só anotada."""

    __tablename__ = "oportunidade_da_reuniao"

    id: Mapped[int] = mapped_column(primary_key=True)
    reuniao_id: Mapped[int] = mapped_column(sa.ForeignKey("reuniao_de_resultado.id"), nullable=False, index=True)
    grupo_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), nullable=False, index=True)
    lacuna: Mapped[str] = mapped_column(sa.Text, nullable=False)
    servico: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    servico_tema: Mapped[str | None] = mapped_column(sa.String(80))
    valor: Mapped[Decimal | None] = mapped_column(DINHEIRO)
    recorrente: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    """Recorrente (C1): o valor é por mês. Projeto (C2): o valor é o total."""
    oportunidade_id: Mapped[int | None] = mapped_column(sa.ForeignKey("oportunidade.id"), index=True)

    reuniao: Mapped[ReuniaoDeResultado] = relationship(back_populates="oportunidades")
    oportunidade: Mapped["Oportunidade | None"] = relationship()


class ReuniaoDaCarteira(CarimboMixin, Base):
    """A bimestral interna, entre o Head do BPO e o CEO da Critério (Eduardo, 03/10/2026): overview da
    carteira para corrigir rotas de análise. Não é de um cliente."""

    __tablename__ = "reuniao_da_carteira"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    participantes: Mapped[str | None] = mapped_column(sa.String(300))
    resumo: Mapped[str | None] = mapped_column(sa.Text)
    correcoes_de_rota: Mapped[str | None] = mapped_column(sa.Text)
    registrada_por: Mapped[str | None] = mapped_column(sa.String(200))


class AjusteTecnico(CarimboMixin, Base):
    """Um ajuste que a reunião de resultado identificou e a área técnica precisa fazer (aprovado por
    Eduardo em 02/10/2026). Nasce da ata, com responsável e prazo escolhidos pelo gestor; aparece na
    Agenda do responsável, que marca feito. Não se apaga: reaberto volta a pendente."""

    __tablename__ = "ajuste_tecnico"

    id: Mapped[int] = mapped_column(primary_key=True)
    reuniao_id: Mapped[int] = mapped_column(sa.ForeignKey("reuniao_de_resultado.id"), nullable=False, index=True)
    grupo_id: Mapped[int] = mapped_column(sa.ForeignKey("grupo_economico.id"), nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(sa.Text, nullable=False)
    responsavel_email: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)
    responsavel_nome: Mapped[str | None] = mapped_column(sa.String(200))
    prazo: Mapped[date | None] = mapped_column(sa.Date)
    feito_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    feito_por: Mapped[str | None] = mapped_column(sa.String(200))
    observacao: Mapped[str | None] = mapped_column(sa.String(500))

    reuniao: Mapped[ReuniaoDeResultado] = relationship(back_populates="ajustes")
    grupo: Mapped[GrupoEconomico] = relationship()


class CadenciaDeReuniao(Base):
    """Quais reuniões de resultado cada classe tem, editável em Configurações › Metas (02/10/2026).
    Sem a linha, vale `crm.domain.sucesso.CADENCIA_PADRAO`."""

    __tablename__ = "cadencia_de_reuniao"

    classe: Mapped[str] = mapped_column(sa.String(1), primary_key=True)
    tipos: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    intencao: Mapped[str | None] = mapped_column(sa.Text)
    """O que a Critério quer com a classe (03/10/2026). Vazia: vale `INTENCAO_PADRAO`."""
    alterado_por: Mapped[str | None] = mapped_column(sa.String(200))
    alterado_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class FichaDaBase(CarimboMixin, Base):
    """Uma ficha da base de conhecimento do SDR de IA (03/10/2026): um assunto, o que a IA pode
    dizer, o que nunca diz e de onde veio. Só a aprovada e dentro da validade vale para a IA
    (`crm.domain.base_de_conhecimento.vale_para_a_ia`). Quem aprova e quando, carimbados pelo
    servidor."""

    __tablename__ = "ficha_da_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str | None] = mapped_column(sa.String(20), unique=True)
    """Só das fichas da carga inicial (P1, T9, S04...): é como a carga sabe o que já entrou."""
    titulo: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    bloco: Mapped[BlocoDaBase] = mapped_column(coluna_lista(BlocoDaBase), nullable=False, index=True)
    servico: Mapped[str | None] = mapped_column(sa.String(120))
    texto: Mapped[str | None] = mapped_column(sa.Text)
    """O que a IA pode dizer."""
    nunca_dizer: Mapped[str | None] = mapped_column(sa.Text)
    como_o_lead_pergunta: Mapped[str | None] = mapped_column(sa.Text)
    fonte: Mapped[str | None] = mapped_column(sa.String(300))
    dono: Mapped[str | None] = mapped_column(sa.String(120))
    depende_de_hipotese: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    situacao: Mapped[SituacaoDaFicha] = mapped_column(
        coluna_lista(SituacaoDaFicha), nullable=False, default=SituacaoDaFicha.RASCUNHO, index=True
    )
    validade: Mapped[date | None] = mapped_column(sa.Date)
    aprovada_por: Mapped[str | None] = mapped_column(sa.String(200))
    aprovada_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

QUANTIDADE = sa.Numeric(6, 2)


class PlanoDeMrr(Base):
    """As premissas do plano de MRR da aba Inteligência de Conversão (03/10/2026, aprovado por
    Eduardo). Uma linha só (`id` = 1); sem ela, valem as de `crm.domain.plano_de_mrr.PADRAO`. Só o
    Administrador muda, e cada campo alterado vai para o histórico de alterações."""

    __tablename__ = "plano_de_mrr"

    id: Mapped[int] = mapped_column(primary_key=True)
    meta_liquida: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    inicio: Mapped[date] = mapped_column(sa.Date, nullable=False)
    fim: Mapped[date] = mapped_column(sa.Date, nullable=False)
    inicio_da_projecao: Mapped[date] = mapped_column(sa.Date, nullable=False)
    ponto_de_partida: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    mrr_de_partida: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    churn_anual_pct: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    bpo_ticket: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    bpo_teto: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    contabil_vagas: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    atipico_vagas: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    escada_prazo_meses: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    plus_acrescimo: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    plus_pct: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    cfo_acrescimo: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    cfo_pct: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    alerta_bpo_por_mes: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    previsto_bpo_por_mes: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    otimista_bpo_por_mes: Mapped[Decimal] = mapped_column(QUANTIDADE, nullable=False)
    alerta_ticket_contabil: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    previsto_ticket_contabil: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    otimista_ticket_contabil: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    alerta_com_previstos: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    previsto_com_previstos: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    otimista_com_previstos: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    # As quatro fases (04/10/2026). Vazias: o previsto usa a taxa histórica do CRM, e sem ela, "sem dado".
    taxa_lead_reuniao_pct: Mapped[Decimal | None] = mapped_column(QUANTIDADE)
    taxa_reuniao_proposta_pct: Mapped[Decimal | None] = mapped_column(QUANTIDADE)
    taxa_conversao_pct: Mapped[Decimal | None] = mapped_column(QUANTIDADE)
    icp_alvo_pct: Mapped[Decimal | None] = mapped_column(QUANTIDADE)
    indicacoes_por_mes: Mapped[Decimal | None] = mapped_column(QUANTIDADE)
    primeiro_contato_horas: Mapped[Decimal | None] = mapped_column(QUANTIDADE)
    ciclo_alvo_dias: Mapped[Decimal | None] = mapped_column(QUANTIDADE)
    alterado_por: Mapped[str | None] = mapped_column(sa.String(200))
    alterado_em: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class ContratoPrevistoDoPlano(Base):
    """Um contrato contábil que o plano já conta num mês (o pipeline conhecido). O atípico ocupa
    mais de uma vaga do onboarding. Sem nome de cliente: a descrição é para quem edita o plano."""

    __tablename__ = "contrato_previsto_do_plano"

    id: Mapped[int] = mapped_column(primary_key=True)
    descricao: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    mes: Mapped[date] = mapped_column(sa.Date, nullable=False)
    valor: Mapped[Decimal] = mapped_column(DINHEIRO, nullable=False)
    atipico: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
