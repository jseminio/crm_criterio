"""Uma rodada da busca das notas do Granola (amostra aprovada por Eduardo em 23/10/2026).

Para cada uma das duas pastas, lista as notas criadas desde a data configurada e traz as que o CRM ainda não tem
(pelo ID do Granola). Cada nota nova é casada pelos e-mails de quem participou, tirando o dono da nota, quem tem o
domínio dele e os usuários do CRM:

- **reunião com o lead:** o contato (ou o lead) com aquele e-mail aponta a oportunidade **em aberto**. Uma só →
  "A usar" na aba Granola dela. Nenhuma ou mais de uma → "Precisa de você";
- **Reunião de Resultado:** o contato aponta o grupo. Um só → "A usar" no Funil do Sucesso. Senão → "Precisa de você".

Nada é aplicado à proposta nem à ata: a nota só chega. Do lead, a transcrição nem é pedida ao Granola.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import httpx2 as httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Empresa, Lead, NotaDoGranola, Oportunidade, PessoaContato, Usuario, VinculoDeContato
from crm.domain.granola import SituacaoDaNota, TipoDaNota, emails_de_fora, participantes_em_texto
from crm.domain.listas import Situacao
from crm.granola import cliente as g

__all__ = ["EM_ABERTO", "Rodada", "buscar_uma_vez", "casar_lead", "casar_resultado"]

EM_ABERTO = (Situacao.ENVIAR_PROPOSTA, Situacao.EM_AVALIACAO, Situacao.ON_HOLD)


@dataclass
class Rodada:
    lidas: int = 0
    novas: int = 0
    a_usar: int = 0
    precisam: int = 0
    aviso: str | None = None
    """Uma pasta que a chave não enxerga: a outra entra assim mesmo."""


def _grupos_dos_contatos(sessao: Session, emails: set[str]) -> set[int]:
    if not emails:
        return set()
    return set(sessao.scalars(
        sa.select(Empresa.grupo_id).join(VinculoDeContato, VinculoDeContato.empresa_id == Empresa.id)
        .join(PessoaContato, PessoaContato.id == VinculoDeContato.pessoa_id)
        .where(sa.func.lower(PessoaContato.email).in_(emails))
    ))


def casar_lead(sessao: Session, emails: set[str]) -> tuple[int | None, str | None]:
    """A oportunidade em aberto dos participantes, ou o motivo de não achar uma só."""
    if not emails:
        return None, "Nenhum participante de fora da Critério na nota."
    grupos = _grupos_dos_contatos(sessao, emails)
    ids: set[int] = set()
    if grupos:
        ids |= set(sessao.scalars(sa.select(Oportunidade.id).where(
            Oportunidade.grupo_id.in_(grupos), Oportunidade.situacao.in_(EM_ABERTO))))
    do_lead = set(sessao.scalars(sa.select(Lead.oportunidade_id).where(
        sa.func.lower(Lead.email).in_(emails), Lead.oportunidade_id.is_not(None))))
    if do_lead:
        ids |= set(sessao.scalars(sa.select(Oportunidade.id).where(
            Oportunidade.id.in_(do_lead), Oportunidade.situacao.in_(EM_ABERTO))))
    if len(ids) == 1:
        return ids.pop(), None
    if ids:
        return None, f"Os participantes têm {len(ids)} oportunidades em aberto."
    if grupos or do_lead:
        return None, "O contato não tem oportunidade em aberto."
    return None, "Nenhum participante é contato do CRM."


def casar_resultado(sessao: Session, emails: set[str]) -> tuple[int | None, str | None]:
    """O grupo dos participantes, ou o motivo de não achar um só."""
    if not emails:
        return None, "Nenhum participante de fora da Critério na nota."
    grupos = _grupos_dos_contatos(sessao, emails)
    if len(grupos) == 1:
        return grupos.pop(), None
    if grupos:
        return None, f"Os participantes são de {len(grupos)} grupos."
    return None, "Nenhum participante é contato do CRM."


def buscar_uma_vez(sessao: Session, http: httpx.Client, config: g.ConfiguracaoDoGranola, hoje: date,
                   esperar: Callable[[float], None] = time.sleep) -> Rodada:
    """Uma rodada, sem commit. Falha do Granola sobe como `FalhaNoGranola`; quem chamou desfaz o que entrou."""
    pastas = g.listar_pastas(http, config, esperar)
    desde = g.desde_efetivo(config, hoje)
    da_casa = set(sessao.scalars(sa.select(sa.func.lower(Usuario.email))))
    rodada = Rodada()
    conhecidas = set(sessao.scalars(sa.select(NotaDoGranola.granola_id)))
    faltam = []
    for tipo, nome in ((TipoDaNota.LEAD, config.pasta_lead), (TipoDaNota.RESULTADO, config.pasta_resultado)):
        pasta = g.achar_pasta(pastas, nome)
        if pasta is None:
            faltam.append(nome)
            continue
        resumidas = g.listar_notas(http, config, pasta, desde, esperar)
        rodada.lidas += len(resumidas)
        for r in sorted(resumidas, key=lambda n: n.criada_em):
            if r.id in conhecidas:
                continue
            nota = g.ler_nota(http, config, r.id, com_transcricao=tipo is TipoDaNota.RESULTADO, esperar=esperar)
            emails = emails_de_fora((e for _, e in nota.pessoas if e), nota.dono_email, da_casa)
            if tipo is TipoDaNota.LEAD:
                destino, motivo = casar_lead(sessao, emails)
                ligacao = {"oportunidade_id": destino}
            else:
                destino, motivo = casar_resultado(sessao, emails)
                ligacao = {"grupo_id": destino}
            situacao = SituacaoDaNota.A_USAR if destino else SituacaoDaNota.PRECISA_DE_VOCE
            sessao.add(NotaDoGranola(
                granola_id=nota.id, tipo=tipo, situacao=situacao, titulo=nota.titulo[:300], data=nota.data,
                participantes=participantes_em_texto(nota.pessoas), link=(nota.link or None) and nota.link[:400],
                resumo=nota.resumo or None, transcricao=nota.transcricao if tipo is TipoDaNota.RESULTADO else None,
                motivo=motivo, **ligacao,
            ))
            conhecidas.add(nota.id)
            rodada.novas += 1
            if destino:
                rodada.a_usar += 1
            else:
                rodada.precisam += 1
    sessao.flush()
    if faltam:
        rodada.aviso = (f"A chave não enxerga a pasta {' nem a pasta '.join(repr(n) for n in faltam)}. Crie a pasta no "
                        "Granola ou escolha outra.")
    return rodada
