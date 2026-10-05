"""A API de produção não sobe sem login: e-mail e senha ou Microsoft (05/10/2026)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import servir_producao as sp  # noqa: E402

COM_LOGIN = {"CRM_ENTRA_TENANT_ID": "t", "CRM_ENTRA_CLIENT_ID": "c"}
SEGREDO = "s" * 32
COM_SENHA = {"CRM_ADMIN_EMAIL": "admin@crmcs.com.br", "CRM_ADMIN_SENHA_INICIAL": "Admin@123", "CRM_SEGREDO_SESSAO": SEGREDO}
ESPERADO = {"host": "127.0.0.1", "port": 8000, "workers": 1, "proxy_headers": True, "forwarded_allow_ips": "127.0.0.1"}


@pytest.mark.parametrize("ambiente", [{}, {"CRM_ENTRA_TENANT_ID": "t"}, {"CRM_ENTRA_CLIENT_ID": "c"},
                                      {"CRM_ENTRA_TENANT_ID": " ", "CRM_ENTRA_CLIENT_ID": " "}, {"CRM_ADMIN_EMAIL": " "}])
def test_sem_login_nao_sobe(ambiente):
    with pytest.raises(SystemExit, match="Nada foi iniciado"):
        sp.parametros(ambiente)


def test_com_login_escuta_so_na_maquina_e_num_processo():
    assert sp.parametros(COM_LOGIN) == ESPERADO


def test_com_email_e_senha_sobe():
    assert sp.parametros(COM_SENHA) == ESPERADO
    assert sp.parametros({**COM_SENHA, **COM_LOGIN}) == ESPERADO  # a senha vence; a Microsoft fica guardada


@pytest.mark.parametrize("falta, frase", [
    ({"CRM_SEGREDO_SESSAO": ""}, "falta CRM_SEGREDO_SESSAO"),
    ({"CRM_SEGREDO_SESSAO": "s" * 31}, "pelo menos 32 caracteres"),
    ({"CRM_ADMIN_SENHA_INICIAL": ""}, "Falta CRM_ADMIN_SENHA_INICIAL"),
    ({"CRM_ADMIN_EMAIL": "sem-arroba"}, "não parece um e-mail"),
])
def test_email_e_senha_incompleto_nao_sobe_e_nao_mostra_o_segredo(falta, frase):
    with pytest.raises(SystemExit, match="Nada foi iniciado") as saida:
        sp.parametros({**COM_SENHA, **COM_LOGIN, **falta})
    texto = str(saida.value)
    assert frase in texto
    assert "Admin@123" not in texto and "s" * 31 not in texto


def test_host_e_porta_pelo_ambiente():
    p = sp.parametros({**COM_LOGIN, "CRM_HOST": "0.0.0.0", "CRM_PORTA": "9000"})
    assert (p["host"], p["port"]) == ("0.0.0.0", 9000)
