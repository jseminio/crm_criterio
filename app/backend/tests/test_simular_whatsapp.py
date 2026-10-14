"""O simulador da Meta para testar o recebimento no CRM local (14/10/2026)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import simular_whatsapp as sim  # noqa: E402

from crm.agente.recebimento import assinatura_valida  # noqa: E402


@pytest.mark.parametrize("endereco", ["http://127.0.0.1:8000", "http://localhost:8000/"])
def test_so_manda_para_o_crm_local(endereco):
    assert sim.endereco_local(endereco).endswith("/api/whatsapp/webhook")


@pytest.mark.parametrize("endereco", ["https://crmcs.criterioconsultores.com.br", "http://10.0.0.5:8000", "http://localhost.evil.com"])
def test_recusa_o_servidor(endereco):
    with pytest.raises(sim.Recusado, match="Só mando para o CRM desta máquina"):
        sim.endereco_local(endereco)


def test_a_entrega_tem_o_formato_da_meta_e_a_assinatura_confere():
    entrega = sim.montar("1098765432", "5511987654321", "Marina", "SAIR", agora=1760450040)
    valor = entrega["entry"][0]["changes"][0]["value"]
    assert entrega["object"] == "whatsapp_business_account" and valor["metadata"]["phone_number_id"] == "1098765432"
    (m,) = valor["messages"]
    assert (m["from"], m["type"], m["text"]["body"], m["timestamp"]) == ("5511987654321", "text", "SAIR", "1760450040")
    corpo = json.dumps(entrega).encode()
    assert assinatura_valida(corpo, sim.assinar(corpo, "segredo"), "segredo")


def test_cada_entrega_tem_um_id_novo():
    a, b = (sim.montar("1", "551199", None, "oi")["entry"][0]["changes"][0]["value"]["messages"][0]["id"] for _ in range(2))
    assert a != b
