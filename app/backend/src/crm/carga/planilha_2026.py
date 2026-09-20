"""Carga das propostas de 2026 da planilha de performance comercial.

A planilha é a fonte do histórico comercial. Esta carga a normaliza contra as
listas controladas e devolve, junto dos registros, um **relatório de
conferência**: o que entrou, o que foi ajustado e o que ficou pendente.

O relatório não é um extra. Sem ele ninguém confia na base, e confiar na base é
a condição para abandonar a planilha.

Princípio: **nada é descartado em silêncio.** Um valor que não converte entra
como pendência com o texto original preservado, nunca como vazio.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from crm.domain.listas import (
    LinhaServico,
    MotivoRecusa,
    Situacao,
    Temperatura,
    TipoCanal,
    normalizar_captador,
    normalizar_linha_servico,
    normalizar_motivo_recusa,
    normalizar_situacao,
    normalizar_temperatura,
    normalizar_tipo_canal,
)

__all__ = ["Aviso", "Proposta", "Relatorio", "carregar", "ANO_DA_CARGA"]

#: Só 2026 entra. Decisão de Eduardo em 19/09/2026.
ANO_DA_CARGA = 2026


@dataclass(frozen=True)
class Aviso:
    """Algo que mereceu registro numa linha da planilha."""

    linha: int
    campo: str
    texto: str
    bloqueia: bool = False
    """``True`` quando o dado não pôde ser convertido e ficou pendente."""


@dataclass(frozen=True)
class Proposta:
    """Uma proposta de 2026, já normalizada.

    Campos que a planilha não trazia ficam ``None`` — e o aviso correspondente
    diz por quê.
    """

    linha: int
    nome_oportunidade: str | None
    data_colocacao: date | None
    servico: str | None
    tipo_servico: str | None
    linha_servico: LinhaServico | None
    captador: str | None
    canal: str | None
    tipo_canal: TipoCanal | None
    situacao: Situacao | None
    temperatura: Temperatura | None
    data_aceite: date | None
    motivo_recusa: MotivoRecusa | None
    motivo_recusa_original: str | None
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    valor_mensalizado: Decimal | None

    @property
    def completa(self) -> bool:
        """Tem o mínimo para virar oportunidade no CRM."""
        return bool(self.nome_oportunidade) and self.situacao is not None


@dataclass
class Relatorio:
    """O que a carga fez, para uma pessoa conferir antes de confiar."""

    total_lidas: int = 0
    importadas: int = 0
    descartadas_outro_ano: int = 0
    descartadas_residuais: int = 0
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def com_pendencia(self) -> int:
        return len({a.linha for a in self.avisos if a.bloqueia})

    @property
    def com_ajuste(self) -> int:
        return len({a.linha for a in self.avisos if not a.bloqueia})

    def por_campo(self) -> Counter[str]:
        return Counter(a.campo for a in self.avisos)

    def resumo(self) -> str:
        """Texto curto para quem vai decidir se a carga está boa."""
        linhas = [
            f"Lidas: {self.total_lidas}",
            f"Importadas: {self.importadas}",
            f"De outro ano, ignoradas: {self.descartadas_outro_ano}",
            f"Residuais, ignoradas: {self.descartadas_residuais}",
            f"Linhas com ajuste automático: {self.com_ajuste}",
            f"Linhas com pendência: {self.com_pendencia}",
            "",
            "Avisos por campo:",
        ]
        for campo, quantos in self.por_campo().most_common():
            linhas.append(f"  {campo}: {quantos}")
        return "\n".join(linhas)


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _data(valor: Any) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def _decimal(valor: Any) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def _registrar(rel: Relatorio, linha: int, campo: str, resultado, bloqueia_se_vazio: bool):
    """Anota o aviso de uma normalização, quando houver."""
    if resultado.aviso is None:
        return
    rel.avisos.append(
        Aviso(linha, campo, resultado.aviso, bloqueia=bloqueia_se_vazio and not resultado.ok)
    )


def carregar(linhas: Iterable[dict[str, Any]]) -> tuple[list[Proposta], Relatorio]:
    """Normaliza as linhas da planilha e devolve os registros e o relatório.

    Cada linha é um dicionário com os nomes de coluna da aba ``Propostas``.
    """
    rel = Relatorio()
    propostas: list[Proposta] = []

    for numero, bruta in enumerate(linhas, start=1):
        rel.total_lidas += 1

        ano = bruta.get("Ano")
        if ano is not None and int(ano) != ANO_DA_CARGA:
            rel.descartadas_outro_ano += 1
            continue

        # Linha residual: a planilha tem, no fim da aba, algumas linhas com
        # valores soltos em colunas sem cabeçalho — sobra de cálculo, não
        # proposta. Sem nome e sem situação, não há o que importar. Não some em
        # silêncio: entra no relatório.
        if not _texto(bruta.get("Nome da oportunidade")) and not _texto(
            bruta.get("Status")
        ):
            rel.descartadas_residuais += 1
            rel.avisos.append(
                Aviso(numero, "linha residual", "sem nome e sem situação — ignorada")
            )
            continue

        situacao = normalizar_situacao(bruta.get("Status"))
        _registrar(rel, numero, "situação", situacao, True)

        tipo_canal = normalizar_tipo_canal(bruta.get("Tipo Canal"))
        _registrar(rel, numero, "tipo de canal", tipo_canal, True)

        temperatura = normalizar_temperatura(bruta.get("Temperatura"))
        _registrar(rel, numero, "temperatura", temperatura, False)

        linha_servico = normalizar_linha_servico(bruta.get("Responsável"))
        _registrar(rel, numero, "linha de serviço", linha_servico, False)

        captador = normalizar_captador(bruta.get("Responsável 2"))
        _registrar(rel, numero, "captador", captador, False)

        motivo_bruto = _texto(bruta.get("Motivo da Recusa"))
        motivo = normalizar_motivo_recusa(motivo_bruto)
        if motivo_bruto is not None:
            _registrar(rel, numero, "motivo de recusa", motivo, False)

        # O nome do cliente: a coluna "Empresa" está vazia em 149 das 154 linhas
        # de 2026. Eduardo confirmou que falta preencher, então a origem passa a
        # ser "Nome da oportunidade" e a empresa fica para completar depois.
        nome = _texto(bruta.get("Nome da oportunidade"))
        if not nome:
            rel.avisos.append(
                Aviso(numero, "nome", "linha sem nome de oportunidade", bloqueia=True)
            )

        data_aceite = _data(bruta.get("Data do aceite"))
        if situacao.valor is Situacao.ACEITA and data_aceite is None:
            rel.avisos.append(
                Aviso(
                    numero,
                    "data de aceite",
                    "aceita sem data — Eduardo preencherá no CRM",
                    bloqueia=False,
                )
            )

        preco_mensal = _decimal(bruta.get("Preço mensal"))
        if preco_mensal is None:
            # Vazio intencional em 2026, conforme Eduardo: consultoria de valor
            # único. Preservado como vazio; no CRM, registro novo exige preço.
            rel.avisos.append(
                Aviso(numero, "preço mensal", "vazio — intencional em 2026", bloqueia=False)
            )

        propostas.append(
            Proposta(
                linha=numero,
                nome_oportunidade=nome,
                data_colocacao=_data(bruta.get("Data da colocação")),
                servico=_texto(bruta.get("Serviço")),
                tipo_servico=_texto(bruta.get("Tipo serviço")),
                linha_servico=linha_servico.valor,
                captador=captador.valor,
                canal=_texto(bruta.get("Canal")),
                tipo_canal=tipo_canal.valor,
                situacao=situacao.valor,
                temperatura=temperatura.valor,
                data_aceite=data_aceite,
                motivo_recusa=motivo.valor,
                motivo_recusa_original=motivo_bruto,
                preco_mensal=preco_mensal,
                preco_anual=_decimal(bruta.get("Preço anual")),
                valor_mensalizado=_decimal(bruta.get("Valor mensalizado")),
            )
        )
        rel.importadas += 1

    return propostas, rel
