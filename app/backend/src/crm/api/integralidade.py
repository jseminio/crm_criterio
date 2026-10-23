"""Integralidade do cadastro (amostra e lista de campos aprovadas por Eduardo em 13/10/2026).

Um campo entra na conta só se alimenta um indicador ou uma decisão. Dois níveis: **obrigatório** (sem ele um
número da liderança fica errado ou some) vale 2 pontos; **prioritário** (melhora a análise) vale 1. Campo
condicional só é devido quando se aplica (a data de envio, depois de "Enviar proposta"; o motivo, na Perdida).

- **Pendente** = pontos dos campos devidos e vazios ÷ pontos de todos os campos devidos.
- **Dois cortes** (decisão de Eduardo em 15/10/2026, no lugar do "só daqui para frente" de 13/10): **Novos**, os
  registros criados desde `DATA_DE_CORTE`, em % pendente (a disciplina da equipe); e **Passado**, o que veio antes (a
  Carga 2026 e a carteira anterior ao CRM), em pendências que faltam e as já consertadas desde o retrato guardado na
  publicação (`guardar_retrato`). A lista traz todos os registros com pendência, dos dois cortes, para consertar aos
  poucos (`por_registro`, `planilha`).
- **Quem responde:** na oportunidade, o captador; no cliente, contrato, encerramento, empresa e contato, o
  responsável de CS do grupo — ou, enquanto o grupo não é cliente, o captador da oportunidade mais recente.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from crm.api import sucesso
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, Oportunidade, PessoaContato, VinculoDeContato
from crm.domain.listas import LinhaServico, Origem, Situacao, SituacaoContrato, TipoDeEventoDeContrato

__all__ = ["DATA_DE_CORTE", "PESO", "CADASTROS", "Campo", "Resultado", "calcular", "CHAVE_DO_RETRATO", "Retrato",
           "ler_retrato", "guardar_retrato", "RegistroPendente", "por_registro", "planilha", "CHAVES", "lacunas",
           "Lacuna", "roteador_de_lacunas"]

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
    registro_id: int | None = None
    """O id do registro no seu cadastro: junta os campos de um mesmo registro na lista de pendências."""
    grupo_id: int | None = None
    """O grupo do registro (18/10/2026): a composição abre o card dele e o card mostra as lacunas."""
    empresa_id: int | None = None
    """No contato, a empresa do vínculo (o card do contato é o da empresa); na empresa, ela mesma."""
    contrato_id: int | None = None
    """No contrato, ele mesmo; no encerramento, o contrato encerrado (é no card dele que a lacuna aparece)."""

    @property
    def pontos(self) -> int:
        return PESO[self.obrigatorio]

    @property
    def chave(self) -> str:
        """O nome estável do campo, que a tela usa para achar e destacar o campo no card (18/10/2026)."""
        return CHAVES[(self.cadastro, self.campo)]


CHAVES: dict[tuple[str, str], str] = {
    ("Oportunidade", "Serviço"): "servico",
    ("Oportunidade", "Valor (parcela ou valor único)"): "valor",
    ("Oportunidade", "Captador"): "captador",
    ("Oportunidade", "Tipo de canal"): "tipo_canal",
    ("Oportunidade", "Data de originação"): "data_colocacao",
    ("Oportunidade", "Data de envio da proposta"): "data_envio_proposta",
    ("Oportunidade", "Motivo de perda"): "motivo_recusa",
    ("Oportunidade", "Contrato cadastrado"): "contrato",
    ("Oportunidade", "Temperatura"): "temperatura",
    ("Oportunidade", "Próxima ação com data"): "proxima_acao",
    ("Oportunidade", "Porte"): "porte",
    ("Contrato", "Data de assinatura"): "data_inicio",
    ("Contrato", "Valor (parcela ou valor único)"): "valor",
    ("Contrato", "Bruto ou líquido"): "base_do_valor",
    ("Contrato", "CNPJ (empresa)"): "empresa_id",
    ("Contrato", "Signatário"): "signatario",
    ("Contrato", "Fim da vigência"): "data_fim",
    ("Encerramento", "Data da saída"): "data_da_saida",
    ("Encerramento", "Motivo"): "motivo_categoria",
    ("Encerramento", "Iniciativa"): "iniciativa",
    ("Encerramento", "Descrição"): "descricao",
    ("Cliente", "Responsável de CS"): "responsavel_cs",
    ("Cliente", "Classificação (classe e semáforo)"): "classificacao",
    ("Cliente", "Porte"): "porte",
    ("Empresa", "CNPJ"): "cnpj",
    ("Empresa", "Regime tributário"): "regime_tributario",
    ("Empresa", "Endereço (logradouro, município e CEP)"): "endereco",
    ("Contato", "Telefone ou e-mail"): "contato",
    ("Contato", "Vínculo com a empresa"): "vinculo",
    ("Contato", "Cargo"): "cargo",
    ("Contato", "Papel (decisor, influenciador…)"): "papel",
}
"""Todo campo da conta tem a sua chave: `tests/test_integralidade.py` derruba a suíte se faltar alguma."""


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
               itens: Iterator[tuple[str, bool, bool]], registro_id: int | None = None, *, grupo_id: int | None = None,
               empresa_id: int | None = None, contrato_id: int | None = None) -> None:
        for campo, obrigatorio, preenchido in itens:
            campos.append(Campo(cadastro, registro, responsavel, campo, obrigatorio, preenchido, legado, registro_id,
                                grupo_id, empresa_id, contrato_id))

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
        devido("Oportunidade", f"{grupos[o.grupo_id].nome} · {o.servico or o.nome}", o.captador or None, legado, regras(), o.id,
               grupo_id=o.grupo_id)

    # Contrato e encerramento: o responsável de CS do grupo.
    for c in contratos:
        def regras(c=c):
            if c.situacao in _ASSINADO and not c.anterior_ao_crm:
                yield "Data de assinatura", True, c.data_inicio is not None
            yield "Valor (parcela ou valor único)", True, _tem(c.preco_mensal) or _tem(c.preco_anual)
            yield "Bruto ou líquido", True, c.base_do_valor is not None
            yield "CNPJ (empresa)", True, c.empresa_id is not None
            yield "Signatário", False, _tem(c.signatario)
            if c.recorrente is not True:  # recorrente não tem fim de vigência (Eduardo, 23/10/2026)
                yield "Fim da vigência", False, c.data_fim is not None
        nome = f"{grupos[c.grupo_id].nome} · {c.escopo or 'contrato'}"
        dono = dono_do_grupo(c.grupo_id)
        devido("Contrato", nome, dono, c.anterior_ao_crm or not _desde_o_corte(c.criado_em), regras(), c.id,
               grupo_id=c.grupo_id, contrato_id=c.id)
        for ev in c.eventos:
            if ev.tipo is not TipoDeEventoDeContrato.ENCERRAMENTO:
                continue
            def regras_do_encerramento(ev=ev):
                yield "Data da saída", True, ev.data_da_saida is not None
                yield "Motivo", True, ev.motivo_categoria is not None
                yield "Iniciativa", True, ev.iniciativa is not None
                yield "Descrição", False, _tem(ev.descricao)
            devido("Encerramento", nome, dono, not _desde_o_corte(ev.registrado_em), regras_do_encerramento(), ev.id,
                   grupo_id=c.grupo_id, contrato_id=c.id)

    # Cliente (grupo com contrato valendo).
    for g in sorted(clientes & set(grupos)):
        grupo = grupos[g]
        def regras(grupo=grupo):
            yield "Responsável de CS", True, _tem(grupo.responsavel_cs)
            yield "Classificação (classe e semáforo)", True, grupo.id in classes
            yield "Porte", False, _tem(grupo.porte)
        devido("Cliente", grupo.nome, dono_do_grupo(g), not _desde_o_corte(grupo.criado_em), regras(), grupo.id,
               grupo_id=grupo.id)

    # Empresa (CNPJ).
    for e in sessao.scalars(sa.select(Empresa).order_by(Empresa.id)):
        if e.grupo_id not in grupos:
            continue
        def regras(e=e):
            yield "CNPJ", True, _tem(e.cnpj)
            yield "Regime tributário", False, _tem(e.regime_tributario)
            yield "Endereço (logradouro, município e CEP)", False, _tem(e.logradouro) and _tem(e.municipio) and _tem(e.cep)
        devido("Empresa", e.razao_social, dono_do_grupo(e.grupo_id), not _desde_o_corte(e.criado_em), regras(), e.id,
               grupo_id=e.grupo_id, empresa_id=e.id)

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
               not _desde_o_corte(p.criado_em), regras(), p.id,
               grupo_id=grupo_id, empresa_id=vinculos[0].empresa_id if vinculos else None)

    return Resultado(campos)


# ------------------------------------------------------------ o Passado: retrato e lista para consertar
CHAVE_DO_RETRATO = "integralidade.retrato_do_passado"
"""Linha de `configuracao_do_sistema` com o retrato do Passado no dia da publicação (decisão de Eduardo em 15/10/2026):
quantas pendências havia, para a tela mostrar quantas já foram consertadas. Não é campo da tela de Integrações."""


@dataclass(frozen=True)
class Retrato:
    em: date
    pendencias: int
    obrigatorios: int


def ler_retrato(sessao: Session) -> Retrato | None:
    from crm.db.modelos import ConfiguracaoDoSistema

    linha = sessao.get(ConfiguracaoDoSistema, CHAVE_DO_RETRATO)
    if linha is None or not linha.valor:
        return None
    d = json.loads(linha.valor)
    return Retrato(date.fromisoformat(d["em"]), int(d["pendencias"]), int(d["obrigatorios"]))


def guardar_retrato(sessao: Session, hoje: date) -> Retrato | None:
    """Guarda o retrato uma vez: se já existe, não mexe (devolve None)."""
    from crm.db.modelos import ConfiguracaoDoSistema

    if ler_retrato(sessao) is not None:
        return None
    faltam = [c for c in calcular(sessao).legado if not c.preenchido]
    retrato = Retrato(hoje, len(faltam), sum(c.obrigatorio for c in faltam))
    sessao.add(ConfiguracaoDoSistema(chave=CHAVE_DO_RETRATO, alterado_por="manutenção", valor=json.dumps(
        {"em": hoje.isoformat(), "pendencias": retrato.pendencias, "obrigatorios": retrato.obrigatorios})))
    sessao.flush()
    return retrato


@dataclass(frozen=True)
class RegistroPendente:
    """Um registro com o que falta nele: a linha da lista para consertar (15/10/2026)."""

    corte: str
    """"Novos" (criados desde o corte) ou "Passado"."""
    cadastro: str
    registro: str
    responsavel: str | None
    faltam: tuple[tuple[str, bool], ...]
    """(campo, obrigatório)."""
    chaves: tuple[str, ...] = ()
    """A chave de cada campo de `faltam`, na mesma ordem: a tela abre o card já no campo (18/10/2026)."""
    registro_id: int | None = None
    grupo_id: int | None = None
    empresa_id: int | None = None
    contrato_id: int | None = None


def por_registro(campos: list[Campo]) -> list[RegistroPendente]:
    """Junta as pendências por registro, do responsável com mais pendências para o com menos; "Sem responsável" no fim."""
    juntos: dict[tuple, list[Campo]] = {}
    for c in campos:
        if not c.preenchido:
            juntos.setdefault((c.legado, c.cadastro, c.registro_id, c.registro, c.responsavel), []).append(c)
    por_dono: dict[str | None, int] = {}
    for (_, _, _, _, dono), lista in juntos.items():
        por_dono[dono] = por_dono.get(dono, 0) + len(lista)
    def ordem(chave):
        legado, cadastro, _, registro, dono = chave
        return (dono is None, -por_dono[dono], dono or "", CADASTROS.index(cadastro), registro)
    def registro(k) -> RegistroPendente:
        lista = sorted(juntos[k], key=lambda c: not c.obrigatorio)
        primeiro = lista[0]
        return RegistroPendente("Passado" if k[0] else "Novos", k[1], k[3], k[4],
                                tuple((c.campo, c.obrigatorio) for c in lista), tuple(c.chave for c in lista),
                                primeiro.registro_id, primeiro.grupo_id, primeiro.empresa_id, primeiro.contrato_id)
    return [registro(k) for k in sorted(juntos, key=ordem)]


def lacunas(campos: list[Campo], *, grupo_id: int | None = None, cadastro: str | None = None,
            registro_id: int | None = None) -> list[Campo]:
    """Os campos devidos e vazios de um grupo ou de um registro, dos dois cortes: o que o card destaca (18/10/2026)."""
    return [c for c in campos if not c.preenchido
            and (grupo_id is None or c.grupo_id == grupo_id)
            and (cadastro is None or c.cadastro == cadastro)
            and (registro_id is None or c.registro_id == registro_id)]


def planilha(registros: list[RegistroPendente]) -> bytes:
    """Uma linha por campo em falta, para distribuir o trabalho."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Pendências"
    ws.append(["Corte", "Responsável", "Cadastro", "Registro", "Campo em falta", "Nível"])
    for celula in ws[1]:
        celula.font = Font(bold=True)
    for r in registros:
        for campo, obrigatorio in r.faltam:
            ws.append([r.corte, r.responsavel or "Sem responsável", r.cadastro, r.registro, campo,
                       "Obrigatório" if obrigatorio else "Prioritário"])
    for col, largura in zip("ABCDEF", (10, 16, 14, 60, 40, 13)):
        ws.column_dimensions[col].width = largura
    ws.auto_filter.ref = ws.dimensions
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


# ------------------------------------------------------------ as lacunas no card (18/10/2026)
class Lacuna(BaseModel):
    cadastro: str
    registro_id: int | None
    registro: str
    campo: str
    chave: str
    obrigatorio: bool
    grupo_id: int | None
    empresa_id: int | None
    contrato_id: int | None


def roteador_de_lacunas(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    """O que falta num grupo ou num registro (amostra aprovada por Eduardo em 18/10/2026): todo card destaca os campos
    devidos e vazios, com a mesma regra da Integralidade do cadastro, nos dois cortes."""
    r = APIRouter(tags=["integralidade"])

    @r.get("/api/lacunas", response_model=list[Lacuna])
    def listar_lacunas(
        grupo_id: int | None = None,
        cadastro: Literal["Oportunidade", "Contrato", "Encerramento", "Cliente", "Empresa", "Contato"] | None = None,
        registro_id: int | None = None,
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> list[Lacuna]:
        if grupo_id is None and registro_id is None:
            raise HTTPException(422, "informe o grupo ou o registro")
        faltam = lacunas(calcular(sessao).campos, grupo_id=grupo_id, cadastro=cadastro, registro_id=registro_id)
        return [Lacuna(cadastro=c.cadastro, registro_id=c.registro_id, registro=c.registro, campo=c.campo, chave=c.chave,
                       obrigatorio=c.obrigatorio, grupo_id=c.grupo_id, empresa_id=c.empresa_id, contrato_id=c.contrato_id)
                for c in sorted(faltam, key=lambda c: (CADASTROS.index(c.cadastro), c.registro, not c.obrigatorio))]

    return r
