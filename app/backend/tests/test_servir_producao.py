"""A API de produção não sobe sem o login da Microsoft (05/10/2026)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import servir_producao as sp  # noqa: E402

COM_LOGIN = {"CRM_ENTRA_TENANT_ID": "t", "CRM_ENTRA_CLIENT_ID": "c"}


@pytest.mark.parametrize("ambiente", [{}, {"CRM_ENTRA_TENANT_ID": "t"}, {"CRM_ENTRA_CLIENT_ID": "c"},
                                      {"CRM_ENTRA_TENANT_ID": " ", "CRM_ENTRA_CLIENT_ID": " "}])
def test_sem_login_nao_sobe(ambiente):
    with pytest.raises(SystemExit, match="Nada foi iniciado"):
        sp.parametros(ambiente)


def test_com_login_escuta_so_na_maquina_e_num_processo():
    p = sp.parametros(COM_LOGIN)
    assert p == {"host": "127.0.0.1", "port": 8000, "workers": 1, "proxy_headers": True,
                 "forwarded_allow_ips": "127.0.0.1"}


def test_host_e_porta_pelo_ambiente():
    p = sp.parametros({**COM_LOGIN, "CRM_HOST": "0.0.0.0", "CRM_PORTA": "9000"})
    assert (p["host"], p["port"]) == ("0.0.0.0", 9000)
