"""Endereço da empresa pelo CNPJ, no cadastro público da Receita (BrasilAPI).

O questionário do site não pergunta o endereço; Karine decidiu (01/10/2026) buscá-lo
sozinho pelo CNPJ ao importar. Só o CNPJ — dado público — sai do CRM. Falha de rede ou
CNPJ não achado não impede a importação: o endereço fica em branco e o "o que fez" avisa.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Callable

__all__ = ["BuscaDeEndereco", "endereco_pelo_cnpj"]

#: Recebe os 14 dígitos do CNPJ; devolve os campos de endereço da empresa, ou None.
BuscaDeEndereco = Callable[[str], "dict[str, str | None] | None"]

_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
# A BrasilAPI recusa (403) o agente padrão do Python; um nome próprio é aceito.
_AGENTE = "CRM-Criterio/1.0"


def _limpo(v: object) -> str | None:
    texto = " ".join(str(v or "").split())
    return texto or None


def endereco_pelo_cnpj(cnpj: str, *, tempo_limite: float = 8.0) -> dict[str, str | None] | None:
    """Logradouro, número, complemento, bairro, município, UF e CEP — no formato que a empresa
    guarda (CEP só com os 8 dígitos). None quando não acha ou a rede falha."""
    digitos = re.sub(r"\D", "", cnpj or "")
    if len(digitos) != 14:
        return None
    pedido = urllib.request.Request(_URL.format(cnpj=digitos), headers={"User-Agent": _AGENTE, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
            d = json.load(resposta)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    logradouro = " ".join(p for p in (_limpo(d.get("descricao_tipo_de_logradouro")), _limpo(d.get("logradouro"))) if p) or None
    numero = _limpo(d.get("numero"))
    if numero and numero.isdigit():
        numero = str(int(numero))  # "00190" -> "190"
    cep = re.sub(r"\D", "", str(d.get("cep") or "")) or None
    uf = (_limpo(d.get("uf")) or "").upper() or None
    endereco = {
        "logradouro": logradouro, "numero": numero, "complemento": _limpo(d.get("complemento")),
        "bairro": _limpo(d.get("bairro")), "municipio": _limpo(d.get("municipio")), "uf": uf,
        "cep": cep.zfill(8) if cep else None,
    }
    return endereco if any(endereco.values()) else None
