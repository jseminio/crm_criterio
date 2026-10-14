"""Simula a Meta entregando uma mensagem de WhatsApp ao CRM local (14/10/2026).

    python scripts/simular_whatsapp.py                       "Olá, vi o anúncio de vocês", de um número de teste
    python scripts/simular_whatsapp.py --texto "SAIR"        pedido de saída: o lead fica "não contatar"
    python scripts/simular_whatsapp.py --de 5511987654321 --nome "Marina" --texto "Oi"
    python scripts/simular_whatsapp.py --assinatura-errada   vê a recusa aparecer em Integrações

Para testar o recebimento (fase 0 do SDR de IA) sem a Meta, que não alcança o CRM do computador. Monta a
entrega no formato da Meta, assina com a chave secreta salva em Configurações › Integrações › WhatsApp e
manda para o webhook. Passa por todas as travas de verdade: assinatura, número, repetição, "SAIR".

**Só manda para o CRM desta máquina** (127.0.0.1 ou localhost): nunca põe mensagem de teste no
servidor. Não mostra a chave secreta.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

CAMINHO = "/api/whatsapp/webhook"
LOCAIS = {"127.0.0.1", "localhost"}

EXPLICACAO = {
    200: "✓ Entregue. Abra SDR - Abordagens e conhecimento › SDR da IA › Leads e veja a conversa do lead.",
    401: "✗ Recusada: assinatura inválida (é o esperado com --assinatura-errada). A tela de Integrações mostra o motivo.",
    403: "✗ Recusada: falta a chave secreta do aplicativo em Configurações › Integrações › WhatsApp.",
    404: "✗ Recusada: o recebimento está desligado em Configurações › Integrações › WhatsApp.",
}


class Recusado(Exception):
    pass


def endereco_local(endereco: str) -> str:
    if urlparse(endereco).hostname not in LOCAIS:
        raise Recusado(f"Só mando para o CRM desta máquina (127.0.0.1 ou localhost), não para {endereco}.")
    return endereco.rstrip("/") + CAMINHO


def montar(numero_id: str, de: str, nome: str | None, texto: str, agora: int | None = None) -> dict:
    """Uma entrega no formato da Meta (webhook do WhatsApp Cloud API, campo `messages`)."""
    momento = str(agora or int(time.time()))
    return {"object": "whatsapp_business_account", "entry": [{"id": "simulacao", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "simulação", "phone_number_id": numero_id},
        "contacts": [{"wa_id": de, "profile": {"name": nome}}] if nome else [],
        "messages": [{"from": de, "id": f"wamid.simulacao.{uuid.uuid4().hex}", "timestamp": momento,
                      "type": "text", "text": {"body": texto}}],
    }}]}]}


def assinar(corpo: bytes, segredo: str) -> str:
    return "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


def _da_tela() -> tuple[str, str]:
    """A chave secreta e o ID do número salvos na tela (ou no ambiente), lidos do banco local."""
    from crm import configuracao
    from crm.db.sessao import criar_engine, criar_fabrica_de_sessao

    configuracao.registrar_fabrica(criar_fabrica_de_sessao(criar_engine()))
    return configuracao.valor("whatsapp.app_secret"), configuracao.valor("whatsapp.numero_id")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--texto", default="Olá, vi o anúncio de vocês")
    p.add_argument("--de", default="5511900000001", help="o número do lead, só dígitos com 55")
    p.add_argument("--nome", default="Lead de teste (simulação)")
    p.add_argument("--endereco", default="http://127.0.0.1:8000")
    p.add_argument("--assinatura-errada", action="store_true")
    a = p.parse_args()
    try:
        destino = endereco_local(a.endereco)
        if not a.de.isdigit():
            raise Recusado("--de: só os dígitos, com o 55 na frente (ex.: 5511987654321).")
        segredo, numero_id = _da_tela()
        if not numero_id:
            raise Recusado("Falta o ID do número de telefone em Configurações › Integrações › WhatsApp.")
        if not segredo and not a.assinatura_errada:
            raise Recusado("Falta a chave secreta do aplicativo em Configurações › Integrações › WhatsApp. "
                           "No teste local, qualquer valor serve.")
    except Recusado as motivo:
        print(f"✗ {motivo} Nada foi enviado.")
        return 1
    corpo = json.dumps(montar(numero_id, a.de, a.nome, a.texto)).encode()
    assinatura = assinar(corpo, "assinatura-errada" if a.assinatura_errada else segredo)
    pedido = urllib.request.Request(destino, data=corpo, method="POST",
                                    headers={"Content-Type": "application/json", "X-Hub-Signature-256": assinatura})
    try:
        status = urllib.request.urlopen(pedido, timeout=15).status
    except urllib.error.HTTPError as falha:
        status = falha.code
    except urllib.error.URLError:
        print(f"✗ O CRM não respondeu em {a.endereco}. Ele está rodando (./iniciar.sh)?")
        return 1
    print(f"Resposta {status}. {EXPLICACAO.get(status, '✗ Resposta inesperada: veja o terminal do iniciar.sh.')}")
    return 0 if status == 200 or (a.assinatura_errada and status == 401) else 1


if __name__ == "__main__":
    raise SystemExit(main())
