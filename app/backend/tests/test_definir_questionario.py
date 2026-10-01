"""Comando que grava a configuração da busca de questionários no .env (01/10/2026)."""

import importlib.util
from pathlib import Path

ESPEC = importlib.util.spec_from_file_location("definir_questionario", Path(__file__).parent.parent / "scripts" / "definir_questionario.py")
modulo = importlib.util.module_from_spec(ESPEC)
ESPEC.loader.exec_module(modulo)


def test_grava_preservando_o_resto_e_trocando_o_que_existia():
    antes = "# comentário\nCRM_DB_USER=criterio_crm\nCRM_QUESTIONARIO_URL=https://velho/functions/v1/x\n"
    depois = modulo.gravar(antes, {"CRM_QUESTIONARIO_URL": "https://abc.supabase.co", "CRM_QUESTIONARIO_CHAVE": "sb_secret_x"})
    assert depois == ("# comentário\nCRM_DB_USER=criterio_crm\nCRM_QUESTIONARIO_URL=https://abc.supabase.co\n"
                      "CRM_QUESTIONARIO_CHAVE=sb_secret_x\n")


def test_url_do_projeto():
    assert modulo.url_valida(" https://abcdefghijkl.supabase.co/ ") == "https://abcdefghijkl.supabase.co"
    assert modulo.url_valida("https://criterio-questionario-proposta.lovable.app/questionario?v=2") is None
    assert modulo.url_valida("https://abc.supabase.co/functions/v1/questionarios-crm") is None
