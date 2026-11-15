"""Do formulário do site ao lead do CRM — LP "Reforma Tributária para empresas de serviços" (15/11/2026).

Lógica pura, sem banco: confere o que a página mandou e devolve os campos do lead, no mesmo molde dos leads do
Meta (`crm.domain.leads_do_meta`). Nome, WhatsApp, e-mail e empresa vão para os campos; o perfil da simulação, a
estimativa, a página, a origem e a prova do consentimento vão para a observação, uma linha por item.

O texto que vem de fora nunca quebra linha: cada valor vira uma linha só, sem caractere de controle, com tamanho
limitado. Assim ninguém escreve na observação uma linha que pareça do CRM.

Recusa diz **qual campo** falhou, nunca o valor: a mensagem vai para o navegador e para o log.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from crm.domain.listas import TipoCanal

__all__ = [
    "CANAL", "ISCA", "MEIOS_PAGOS", "ORGANICO", "EnvioDoSite", "Recusa", "anotacao_da_nova_entrada",
    "campos_do_lead", "conferir", "normalizar_whatsapp", "tipo_de_canal",
]

CANAL = "Site — LP Reforma Tributária"
ORGANICO = "Orgânico"
ISCA = "website"
"""O campo invisível da página: gente não o vê e não o preenche; robô que preenche tudo, sim."""
MEIOS_PAGOS = frozenset({"cpc", "ppc", "cpm", "cpv", "paid", "pago", "paid_social", "paidsocial", "paid-social",
                         "ads", "display", "anuncio", "anúncio"})
"""`utm_medium` que diz anúncio pago. **Hipótese em teste**: a classificação do lead do site espera Eduardo."""

_FUSO = ZoneInfo("America/Sao_Paulo")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]{2,}$")
_LIMITES = {
    "nome": 200, "empresa": 200, "email": 200, "versao_consentimento": 40,
    "e1": 120, "e2": 120, "e3": 120, "e4": 120, "e5": 120, "resultado": 500, "pagina": 300,
    "utm_source": 120, "utm_medium": 120, "utm_campaign": 200, "utm_term": 120, "utm_content": 120,
}


class Recusa(ValueError):
    """O envio não vale. `campo` é o nome do campo; o valor nunca entra na mensagem."""

    def __init__(self, campo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


@dataclass(frozen=True)
class EnvioDoSite:
    nome: str
    whatsapp: str
    """Só dígitos, DDD + número (10 ou 11), sem o 55."""
    email: str | None
    empresa: str | None
    versao_consentimento: str | None
    faturamento: str | None
    regime: str | None
    folha: str | None
    clientes: str | None
    segmento: str | None
    resultado: str | None
    pagina: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_term: str | None
    utm_content: str | None


def _linha(valor: object, campo: str) -> str | None:
    """Texto de uma linha só: sem controle, espaços juntados, cortado no limite do campo."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise Recusa(campo, f"O campo {campo} precisa ser texto.")
    limpo = "".join(" " if unicodedata.category(c).startswith(("C", "Z")) else c for c in valor)
    limpo = " ".join(limpo.split())
    return limpo[:_LIMITES.get(campo, 200)] or None


def normalizar_whatsapp(valor: object) -> str:
    """WhatsApp brasileiro com DDD: só dígitos, 10 ou 11 (aceita o 55 na frente), DDD de 11 a 99 e, com 11
    dígitos, celular começando com 9. Devolve DDD + número, sem o 55."""
    if not isinstance(valor, str) or not valor.isascii() or not valor.isdigit():
        raise Recusa("whatsapp", "Informe o WhatsApp só com números, com DDD.")
    digitos = valor
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        raise Recusa("whatsapp", "O WhatsApp precisa ter DDD e 8 ou 9 dígitos.")
    if not 11 <= int(digitos[:2]) <= 99:
        raise Recusa("whatsapp", "O DDD do WhatsApp não existe.")
    if len(digitos) == 11 and digitos[2] != "9":
        raise Recusa("whatsapp", "Celular com 9 dígitos começa com 9.")
    return digitos


def conferir(corpo: object) -> EnvioDoSite:
    """Confere o corpo JSON da página. Recusa com o campo que falhou."""
    if not isinstance(corpo, dict):
        raise Recusa("corpo", "O envio precisa ser um objeto JSON.")
    nome = _linha(corpo.get("nome"), "nome")
    if not nome:
        raise Recusa("nome", "Informe o nome.")
    whatsapp = normalizar_whatsapp(corpo.get("whatsapp"))
    email = _linha(corpo.get("email"), "email")
    if email and (not _EMAIL.fullmatch(email) or len(email) > 200):
        raise Recusa("email", "O e-mail não parece válido.")
    if corpo.get("consentimento") is not True:
        raise Recusa("consentimento", "É preciso aceitar o uso dos dados para receber o contato.")
    return EnvioDoSite(
        nome=nome, whatsapp=whatsapp, email=email.lower() if email else None,
        empresa=_linha(corpo.get("empresa"), "empresa"),
        versao_consentimento=_linha(corpo.get("versao_consentimento"), "versao_consentimento"),
        faturamento=_linha(corpo.get("e1"), "e1"), regime=_linha(corpo.get("e2"), "e2"),
        folha=_linha(corpo.get("e3"), "e3"), clientes=_linha(corpo.get("e4"), "e4"),
        segmento=_linha(corpo.get("e5"), "e5"), resultado=_linha(corpo.get("resultado"), "resultado"),
        pagina=_linha(corpo.get("pagina"), "pagina"),
        **{k: _linha(corpo.get(k), k) for k in ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")},
    )


def tipo_de_canal(envio: EnvioDoSite) -> TipoCanal | None:
    """**Provisório, à espera de Eduardo:** anúncio pago (pelo `utm_medium`) entra como Tráfego pago; o resto
    fica sem tipo de canal, com o canal "Site — LP Reforma Tributária" dizendo de onde veio."""
    return TipoCanal.TRAFEGO_PAGO if (envio.utm_medium or "").casefold() in MEIOS_PAGOS else None


def _quando(momento: datetime) -> str:
    return momento.astimezone(_FUSO).strftime("%d/%m/%Y %H:%M")


def _linhas_da_observacao(envio: EnvioDoSite, momento: datetime) -> list[str]:
    itens = [
        ("Faixa de faturamento", envio.faturamento), ("Regime", envio.regime), ("Segmento", envio.segmento),
        ("Folha", envio.folha), ("Clientes", envio.clientes), ("Estimativa", envio.resultado),
        ("Página", envio.pagina),
    ]
    linhas = [f"{rotulo}: {valor}" for rotulo, valor in itens if valor]
    utm = " / ".join(v for v in (envio.utm_source, envio.utm_medium) if v)
    if utm:
        linhas.append(f"Origem UTM: {utm}")
    versao = f", versão {envio.versao_consentimento}" if envio.versao_consentimento else ""
    linhas.append(f"Consentimento LGPD: aceito{versao}, em {_quando(momento)}")
    linhas.append(f"(enviado pelo simulador do site, {_quando(momento)})")
    return linhas


def campos_do_lead(envio: EnvioDoSite, momento: datetime) -> dict:
    """Os campos de `crm.db.modelos.Lead` para um envio do site."""
    return {
        "nome": envio.nome,
        "telefone": envio.whatsapp,
        "email": envio.email,
        "empresa_texto": envio.empresa,
        "tipo_canal": tipo_de_canal(envio),
        "canal": CANAL,
        "campanha": (envio.utm_campaign or ORGANICO)[:120],
        "campanha_midia": ((envio.utm_content or envio.utm_term) or None) and (envio.utm_content or envio.utm_term)[:120],
        "utm_source": envio.utm_source,
        "utm_medium": envio.utm_medium,
        "utm_campaign": envio.utm_campaign,
        "observacao": "\n".join(_linhas_da_observacao(envio, momento)),
    }


def anotacao_da_nova_entrada(envio: EnvioDoSite, momento: datetime) -> str:
    """O bloco que se acrescenta à observação do lead que já tem este WhatsApp (proposta à espera de Eduardo)."""
    cabeca = [f"— Nova entrada pelo site em {_quando(momento)}:", f"Nome informado: {envio.nome}"]
    if envio.empresa:
        cabeca.append(f"Empresa informada: {envio.empresa}")
    if envio.email:
        cabeca.append(f"E-mail informado: {envio.email}")
    if envio.utm_campaign:
        cabeca.append(f"Campanha: {envio.utm_campaign}")
    return "\n".join(cabeca + _linhas_da_observacao(envio, momento))
