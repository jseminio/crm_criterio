"""Do lead do formulário do Meta ao lead do CRM — 14/10/2026 (amostra aprovada por Eduardo).

Lógica pura: as respostas do formulário viram os campos do lead. Nome, e-mail, telefone e empresa vão para os
campos; o resto (as perguntas próprias da Critério, como faixa de faturamento) vai para a observação, com a data.
Lead orgânico (preencheu sem vir do anúncio) entra com a campanha "Orgânico (formulário)".
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from crm.domain.listas import TipoCanal

__all__ = ["CANAL", "ORGANICO", "campos_do_lead"]

CANAL = "Meta Ads"
ORGANICO = "Orgânico (formulário)"
_FUSO = ZoneInfo("America/Sao_Paulo")

_NOME = ("full_name", "nome_completo", "nome")
_PRIMEIRO, _ULTIMO = ("first_name",), ("last_name",)
_EMAIL = ("email", "e-mail", "work_email")
_TELEFONE = ("phone_number", "telefone", "whatsapp", "work_phone_number")
_EMPRESA = ("company_name", "empresa", "nome_da_empresa")
_JA_USADOS = set(_NOME + _PRIMEIRO + _ULTIMO + _EMAIL + _TELEFONE + _EMPRESA)


def _primeira(respostas: dict[str, str], chaves: tuple[str, ...]) -> str | None:
    por_chave = {k.strip().lower(): v.strip() for k, v in respostas.items()}
    return next((por_chave[k] for k in chaves if por_chave.get(k)), None)


def _pergunta(chave: str) -> str:
    """"faixa_de_faturamento_mensal?" → "Faixa de faturamento mensal"."""
    texto = chave.replace("_", " ").strip().rstrip("?").strip()
    return texto[:1].upper() + texto[1:] if texto else chave


def campos_do_lead(lead) -> dict:
    """Os campos de `crm.db.modelos.Lead` para um `LeadDoMeta`."""
    r = lead.respostas
    nome = _primeira(r, _NOME) or " ".join(
        p for p in (_primeira(r, _PRIMEIRO), _primeira(r, _ULTIMO)) if p) or "Lead do Meta sem nome"
    outras = [f"{_pergunta(k)}: {v}" for k, v in r.items() if k.strip().lower() not in _JA_USADOS]
    quando = lead.criado_em.astimezone(_FUSO).strftime("%d/%m/%Y %H:%M")
    origem = f"respondido no formulário do Meta{f' “{lead.formulario}”' if lead.formulario else ''}, {quando}"
    observacao = "\n".join(outras + [f"({origem})"]) if outras else f"({origem[:1].upper()}{origem[1:]})"
    return {
        "nome": nome[:200],
        "email": (_primeira(r, _EMAIL) or None) and _primeira(r, _EMAIL)[:200],
        "telefone": (_primeira(r, _TELEFONE) or None) and _primeira(r, _TELEFONE)[:30],
        "empresa_texto": (_primeira(r, _EMPRESA) or None) and _primeira(r, _EMPRESA)[:200],
        "tipo_canal": TipoCanal.TRAFEGO_PAGO,
        "canal": CANAL,
        "campanha": (ORGANICO if lead.organico or not lead.campanha else lead.campanha)[:120],
        "campanha_midia": (lead.anuncio or None) and lead.anuncio[:120],
        "observacao": observacao,
        "meta_lead_id": lead.id[:40],
        "criado_em": lead.criado_em,
    }
