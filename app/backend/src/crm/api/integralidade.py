"""Integralidade do cadastro (amostra e lista de campos aprovadas por Eduardo em 13/10/2026).

Um campo entra na conta só se alimenta um indicador ou uma decisão. Dois níveis: **obrigatório** (sem ele um
número da liderança fica errado ou some) vale 2 pontos; **prioritário** (melhora a análise) vale 1. Campo
condicional só é devido quando se aplica (a data de envio, depois de "Enviar proposta"; o motivo, na Perdida).

- **Pendente** = pontos dos campos devidos e vazios ÷ pontos de todos os campos devidos.
- **Daqui para frente:** o número principal conta só os registros criados desde `DATA_DE_CORTE`; o legado (antes
  dela, a Carga 2026 e a carteira anterior ao CRM) vai num número à parte.
- **Quem responde:** na oportunidade, o captador; no cliente, contrato, encerramento, empresa e contato, o
  responsável de CS do grupo — ou, enquanto o grupo não é cliente, o captador da oportunidade mais recente.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from crm.api import sucesso
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, Oportunidade, PessoaContato, VinculoDeContato
from crm.domain.listas import LinhaServico, Origem, Situacao, SituacaoContrato, TipoDeEventoDeContrato

__all__ = ["DATA_DE_CORTE", "PESO", "CADASTROS", "Campo", "Resultado", "calcular"]

DATA_DE_CORTE = date(2026, 10, 14)
"""Primeiro dia da cobrança (a publicação): o que nasceu antes é legado (decisão de Eduardo em 13/10/2026)."""

PESO = {True: 2, False: 1}
"""Obrigatório vale 2; prioritário, 1 (13/10/2026)."""

CADASTROS = ("Oportunidade", "Contrato", "Encerramento", "Cliente", "Empresa", "Contato")

_ABERTAS = {Situacao.ENVIAR_PROPOSTA, Situacao.EM_AVALIACAO, Situacao.ON_HOLD}
_ASSINADO = {SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO, SituacaoContrato.ENCERRADO}


@dataclass(frozen=True)
class Campo:
    """Um campo devido num registro."""

    cadastro: str
    registro: str
    responsavel: str | None
    campo: str
    obrigatorio: bool
    preenchido: bool
    legado: bool

    @property
    def pontos(self) -> int:
        return PESO[self.obrigatorio]


@dataclass(frozen=True)
class Resultado:
    campos: list[Campo]

    def _de(self, legado: bool) -> list[Campo]:
        return [c for c in self.campos if c.legado is legado]

    @staticmethod
    def pendente_pct(campos: list[Campo]) -> Decimal | None:
        devidos = sum(c.pontos for c in campos)
        if devidos == 0:
            return None
        return (Decimal(sum(c.pontos for c in campos if not c.preenchido)) / devidos * 100).quantize(Decimal("0.1"))

    @property
    def novos(self) -> list[Campo]:
        return self._de(False)

    @property
    def legado(self) -> list[Campo]:
        return self._de(True)


def _desde_o_corte(quando: datetime | date | None) -> bool:
    if quando is None:
        return False
    dia = quando.date() if isinstance(quando, datetime) else quando
    return dia >= DATA_DE_CORTE


def _tem(valor) -> bool:
    return valor is not None and (not isinstance(valor, str) or valor.strip() != "")


def calcular(sessao: Session) -> Resultado:
    grupos = {g.id: g for g in sessao.scalars(sa.select(GrupoEconomico).where(GrupoEconomico.fundido_em_id.is_(None)))}
    oportunidades = [o for o in sessao.scalars(sa.select(Oportunidade).order_by(Oportunidade.id)) if o.grupo_id in grupos]
    contratos = [c for c in sessao.scalars(sa.select(Contrato).options(selectinload(Contrato.eventos))) if c.grupo_id in grupos]
    clientes = {g.id for g, _ in sucesso._grupos(sessao)}
    classes = sucesso._classes(sessao)

    captador_recente: dict[int, str] = {}
    for o in sorted(oportunidades, key=lambda o: (o.data_colocacao or date.min, o.id)):
        if _tem(o.captador):
            captador_recente[o.grupo_id] = o.captador

    def dono_do_grupo(g: int) -> str | None:
        if g in clientes:
            return grupos[g].responsavel_cs or None
        return captador_recente.get(g)

    grupos_com_contrato = {c.grupo_id for c in contratos}
    campos: list[Campo] = []

    def devido(cadastro: str, registro: str, responsavel: str | None, legado: bool,
               itens: Iterator[tuple[str, bool, bool]]) -> None:
        for campo, obrigatorio, preenchido in itens:
            campos.append(Campo(cadastro, registro, responsavel, campo, obrigatorio, preenchido, legado))

    # Oportunidade: o captador responde.
    for o in oportunidades:
        def regras(o=o):
            yield "Serviço", True, _tem(o.servico)
            yield "Valor (parcela ou valor único)", True, _tem(o.preco_mensal) or _tem(o.preco_anual)
            yield "Captador", True, _tem(o.captador)
            yield "Tipo de canal", True, o.tipo_canal is not None
            yield "Data de originação", True, o.data_colocacao is not None
            if o.situacao is not Situacao.ENVIAR_PROPOSTA:
                yield "Data de envio da proposta", True, o.data_envio_proposta is not None
            if o.situacao is Situacao.PERDIDA:
                yield "Motivo de perda", True, o.motivo_recusa is not None
            if (o.situacao is Situacao.ACEITA and o.linha_servico is not LinhaServico.C2
                    and o.preco_mensal is not None and o.preco_mensal > 0):
                yield "Contrato cadastrado", True, o.grupo_id in grupos_com_contrato
            if o.situacao in _ABERTAS:
                yield "Temperatura", False, o.temperatura is not None
                yield "Próxima ação com data", False, _tem(o.proxima_acao) and o.proxima_acao_em is not None
            yield "Porte", False, _tem(o.porte)
        legado = not _desde_o_corte(o.criado_em) or o.origem is Origem.CARGA_2026
        devido("Oportunidade", f"{grupos[o.grupo_id].nome} · {o.servico or o.nome}", o.captador or None, legado, regras())

    # Contrato e encerramento: o responsável de CS do grupo.
    for c in contratos:
        def regras(c=c):
            if c.situacao in _ASSINADO and not c.anterior_ao_crm:
                yield "Data de assinatura", True, c.data_inicio is not None
            yield "Valor (parcela ou valor único)", True, _tem(c.preco_mensal) or _tem(c.preco_anual)
            yield "Bruto ou líquido", True, c.base_do_valor is not None
            yield "CNPJ (empresa)", True, c.empresa_id is not None
            yield "Signatário", False, _tem(c.signatario)
            yield "Fim da vigência", False, c.data_fim is not None
        nome = f"{grupos[c.grupo_id].nome} · {c.escopo or 'contrato'}"
        dono = dono_do_grupo(c.grupo_id)
        devido("Contrato", nome, dono, c.anterior_ao_crm or not _desde_o_corte(c.criado_em), regras())
        for ev in c.eventos:
            if ev.tipo is not TipoDeEventoDeContrato.ENCERRAMENTO:
                continue
            def regras_do_encerramento(ev=ev):
                yield "Data da saída", True, ev.data_da_saida is not None
                yield "Motivo", True, ev.motivo_categoria is not None
                yield "Iniciativa", True, ev.iniciativa is not None
                yield "Descrição", False, _tem(ev.descricao)
            devido("Encerramento", nome, dono, not _desde_o_corte(ev.registrado_em), regras_do_encerramento())

    # Cliente (grupo com contrato valendo).
    for g in sorted(clientes & set(grupos)):
        grupo = grupos[g]
        def regras(grupo=grupo):
            yield "Responsável de CS", True, _tem(grupo.responsavel_cs)
            yield "Classificação (classe e semáforo)", True, grupo.id in classes
            yield "Porte", False, _tem(grupo.porte)
        devido("Cliente", grupo.nome, dono_do_grupo(g), not _desde_o_corte(grupo.criado_em), regras())

    # Empresa (CNPJ).
    for e in sessao.scalars(sa.select(Empresa).order_by(Empresa.id)):
        if e.grupo_id not in grupos:
            continue
        def regras(e=e):
            yield "CNPJ", True, _tem(e.cnpj)
            yield "Regime tributário", False, _tem(e.regime_tributario)
            yield "Endereço (logradouro, município e CEP)", False, _tem(e.logradouro) and _tem(e.municipio) and _tem(e.cep)
        devido("Empresa", e.razao_social, dono_do_grupo(e.grupo_id), not _desde_o_corte(e.criado_em), regras())

    # Contato: pelo vínculo com a empresa (o primeiro, ou o principal).
    pessoas = sessao.scalars(
        sa.select(PessoaContato).options(selectinload(PessoaContato.vinculos).selectinload(VinculoDeContato.empresa))
        .order_by(PessoaContato.id)
    )
    for p in pessoas:
        vinculos = sorted(p.vinculos, key=lambda v: (not v.principal, v.id))
        grupo_id = vinculos[0].empresa.grupo_id if vinculos else None
        if grupo_id is not None and grupo_id not in grupos:
            continue
        def regras(p=p, vinculos=vinculos):
            yield "Telefone ou e-mail", True, _tem(p.telefone) or _tem(p.email)
            yield "Vínculo com a empresa", True, bool(vinculos)
            yield "Cargo", False, _tem(p.cargo)
            yield "Papel (decisor, influenciador…)", False, p.papel is not None
        registro = p.nome + (f" · {grupos[grupo_id].nome}" if grupo_id is not None else "")
        devido("Contato", registro, dono_do_grupo(grupo_id) if grupo_id is not None else None,
               not _desde_o_corte(p.criado_em), regras())

    return Resultado(campos)
