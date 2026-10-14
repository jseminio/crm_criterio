"""Do lead do formulário do Google Ads ao lead do CRM — 14/10/2026 (decisão de Eduardo: formulário do Google).

Lógica pura, no mesmo molde de `crm.domain.leads_do_meta`. Os campos padrão do Google chegam pelo tipo
(FULL_NAME, EMAIL, PHONE_NUMBER, COMPANY_NAME…); as perguntas personalizadas, pelo texto da pergunta e vão para a
observação, com a data. O gclid vem junto: é ele que permite devolver a conversão ao Google.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from crm.domain.listas import TipoCanal

__all__ = ["CANAL", "SEM_CAMPANHA", "campos_do_lead"]

CANAL = "Google Ads"
SEM_CAMPANHA = "Formulário do Google"
_FUSO = ZoneInfo("America/Sao_Paulo")

_NOME, _PRIMEIRO, _ULTIMO = ("FULL_NAME",), ("FIRST_NAME",), ("LAST_NAME",)
_EMAIL = ("EMAIL", "WORK_EMAIL")
_TELEFONE = ("PHONE_NUMBER", "WORK_PHONE")
_EMPRESA = ("COMPANY_NAME",)
_JA_USADOS = set(_NOME + _PRIMEIRO + _ULTIMO + _EMAIL + _TELEFONE + _EMPRESA)
_ROTULOS = {"JOB_TITLE": "Cargo", "CITY": "Cidade", "REGION": "Estado", "COUNTRY": "País",
            "POSTAL_CODE": "CEP", "STREET_ADDRESS": "Endereço"}


def _primeira(respostas: dict[str, str], chaves: tuple[str, ...]) -> str | None:
    return next((respostas[k].strip() for k in chaves if (respostas.get(k) or "").strip()), None)


def _pergunta(chave: str) -> str:
    if chave in _ROTULOS:
        return _ROTULOS[chave]
    if chave.isupper():  # outro campo padrão do Google: "JOB_TITLE" → "Job title"
        texto = chave.replace("_", " ").lower()
        return texto[:1].upper() + texto[1:]
    return chave.strip().rstrip("?").strip()


def _corta(valor: str | None, tamanho: int) -> str | None:
    return valor[:tamanho] if valor else None


def campos_do_lead(lead) -> dict:
    """Os campos de `crm.db.modelos.Lead` para um `crm.anuncios.google.LeadDoGoogle`."""
    r = lead.respostas
    nome = _primeira(r, _NOME) or " ".join(
        p for p in (_primeira(r, _PRIMEIRO), _primeira(r, _ULTIMO)) if p) or "Lead do Google sem nome"
    outras = [f"{_pergunta(k)}: {v}" for k, v in r.items() if k not in _JA_USADOS]
    quando = lead.criado_em.astimezone(_FUSO).strftime("%d/%m/%Y %H:%M")
    origem = f"respondido no formulário do Google Ads, {quando}"
    observacao = "\n".join(outras + [f"({origem})"]) if outras else f"({origem[:1].upper()}{origem[1:]})"
    return {
        "nome": nome[:200],
        "email": _corta(_primeira(r, _EMAIL), 200),
        "telefone": _corta(_primeira(r, _TELEFONE), 30),
        "empresa_texto": _corta(_primeira(r, _EMPRESA), 200),
        "tipo_canal": TipoCanal.TRAFEGO_PAGO,
        "canal": CANAL,
        "campanha": (lead.campanha or SEM_CAMPANHA)[:120],
        "gclid": _corta(lead.gclid, 255),
        "observacao": observacao,
        "google_lead_id": lead.id[:40],
        "criado_em": lead.criado_em,
    }
