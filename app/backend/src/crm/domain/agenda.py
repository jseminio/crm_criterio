"""A fila de follow-up: o que precisa de uma próxima ação, e quando.

Etapa 2, "follow-up e lembretes" (25/09/2026). O achado que desenhou este módulo:
das 50 propostas em aberto, **nenhuma tinha próxima ação** (a cobertura do processo
marcava 0%). Uma agenda só de datas ficaria vazia. Por isso a fila tem um balde
próprio para quem **não tem próxima ação**, e é por ele que o trabalho começa.

Baldes, na ordem em que pedem atenção:

1. **atrasada** — a data da próxima ação já passou;
2. **hoje**;
3. **proximos_7_dias**;
4. **depois** — data além de 7 dias;
5. **sem_data** — tem a ação escrita, mas sem data;
6. **sem_acao** — em aberto e sem próxima ação. Não é falha de ninguém: é onde a
   cobertura do processo sobe.

Só entra o que está **em aberto**: oportunidade não decidida, lead ainda no funil e
**contrato em vigor com data de fim** — o vencimento é a hora de decidir a renovação
(a data usada é a do fim, sem prazo de aviso inventado).
Lembrete aqui é **tela**, não notificação: a API do WhatsApp segue pendente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Protocol

from crm.domain.listas import Temperatura

__all__ = ["BALDES", "ItemDaAgenda", "montar"]

BALDES = ("atrasada", "hoje", "proximos_7_dias", "depois", "sem_data", "sem_acao")
_ORDEM_DA_TEMPERATURA = {Temperatura.QUENTE: 0, Temperatura.MORNO: 1, Temperatura.FRIO: 2}


class _Aberto(Protocol):
    id: int
    proxima_acao: str | None
    proxima_acao_em: date | None
    temperatura: Temperatura | None
    captador: str | None


@dataclass(frozen=True)
class ItemDaAgenda:
    tipo: str  # "oportunidade" | "lead" | "contrato"
    id: int
    titulo: str
    subtitulo: str | None
    situacao: str
    temperatura: str | None
    captador: str | None
    valor_anual: Decimal | None
    proxima_acao: str | None
    proxima_acao_em: date | None
    balde: str
    dias_de_atraso: int
    """Positivo quando a data passou; zero nos demais casos."""
    dias_desde_o_envio: int | None
    """Idade da proposta (hoje − data de colocação). `None` para lead e para proposta sem data."""


def _balde(acao: str | None, quando: date | None, hoje: date) -> str:
    tem_acao = bool(acao and acao.strip())
    if quando is None:
        return "sem_data" if tem_acao else "sem_acao"
    if quando < hoje:
        return "atrasada"
    if quando == hoje:
        return "hoje"
    return "proximos_7_dias" if quando <= hoje + timedelta(days=7) else "depois"


def montar(
    *,
    oportunidades: Iterable[tuple[object, str | None]],
    leads: Iterable[object],
    hoje: date,
    contratos: Iterable[tuple[object, str | None]] = (),
) -> list[ItemDaAgenda]:
    """`oportunidades` é uma lista de (oportunidade em aberto, nome do grupo).

    Quem chama já filtrou o que está em aberto; aqui só se classifica e ordena.
    """
    itens: list[ItemDaAgenda] = []
    for o, grupo in oportunidades:
        balde = _balde(o.proxima_acao, o.proxima_acao_em, hoje)
        itens.append(
            ItemDaAgenda(
                tipo="oportunidade",
                id=o.id,
                titulo=grupo or o.nome,
                subtitulo=o.nome if grupo and o.nome != grupo else None,
                situacao=o.situacao.value,
                temperatura=o.temperatura.value if o.temperatura else None,
                captador=o.captador,
                valor_anual=o.preco_anual,
                proxima_acao=(o.proxima_acao or "").strip() or None,
                proxima_acao_em=o.proxima_acao_em,
                balde=balde,
                dias_de_atraso=(hoje - o.proxima_acao_em).days if balde == "atrasada" else 0,
                dias_desde_o_envio=(hoje - o.data_colocacao).days if o.data_colocacao else None,
            )
        )
    for l in leads:
        balde = _balde(l.proxima_acao, l.proxima_acao_em, hoje)
        itens.append(
            ItemDaAgenda(
                tipo="lead",
                id=l.id,
                titulo=l.empresa_texto or l.nome,
                subtitulo=l.nome if l.empresa_texto else None,
                situacao=l.situacao.value,
                temperatura=l.temperatura.value if l.temperatura else None,
                captador=l.captador,
                valor_anual=None,
                proxima_acao=(l.proxima_acao or "").strip() or None,
                proxima_acao_em=l.proxima_acao_em,
                balde=balde,
                dias_de_atraso=(hoje - l.proxima_acao_em).days if balde == "atrasada" else 0,
                dias_desde_o_envio=None,
            )
        )

    for c, grupo in contratos:
        if c.data_fim is None:
            continue
        balde = _balde("Vencimento do contrato", c.data_fim, hoje)
        itens.append(
            ItemDaAgenda(
                tipo="contrato",
                id=c.id,
                titulo=grupo or f"Contrato {c.id}",
                subtitulo=c.escopo,
                situacao=c.situacao.value,
                temperatura=None,
                captador=None,
                valor_anual=c.preco_anual,
                proxima_acao="Vencimento do contrato: decidir a renovação",
                proxima_acao_em=c.data_fim,
                balde=balde,
                dias_de_atraso=(hoje - c.data_fim).days if balde == "atrasada" else 0,
                dias_desde_o_envio=None,
            )
        )

    def chave(i: ItemDaAgenda):
        temp = _ORDEM_DA_TEMPERATURA.get(Temperatura(i.temperatura), 3) if i.temperatura else 3
        return (
            BALDES.index(i.balde),
            -i.dias_de_atraso,
            i.proxima_acao_em or date.max,
            temp,
            -(i.valor_anual or Decimal(0)),
            i.titulo.lower(),
        )

    return sorted(itens, key=chave)
