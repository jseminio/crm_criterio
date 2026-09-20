"""A conexão com o banco — e a recusa de adivinhar onde ele está."""

from __future__ import annotations

import pytest

from crm.db.sessao import VARIAVEL, BancoNaoConfigurado, criar_engine, url_do_banco


class TestUrlDoBanco:
    def test_le_do_ambiente(self, monkeypatch):
        monkeypatch.setenv(VARIAVEL, "postgresql+psycopg://alguem@localhost/crm")

        assert url_do_banco() == "postgresql+psycopg://alguem@localhost/crm"

    def test_sem_variavel_falha_de_forma_visivel(self, monkeypatch):
        """RN-16: melhor parar com mensagem clara do que gravar dado de cliente
        num SQLite improvisado que ninguém sabe que existe."""
        monkeypatch.delenv(VARIAVEL, raising=False)

        with pytest.raises(BancoNaoConfigurado, match=VARIAVEL):
            url_do_banco()

    def test_a_mensagem_de_erro_ensina_o_caminho_certo(self, monkeypatch):
        monkeypatch.delenv(VARIAVEL, raising=False)

        with pytest.raises(BancoNaoConfigurado, match=r"\.env"):
            url_do_banco()

    def test_o_padrao_so_vale_quando_pedido(self, monkeypatch):
        """Existe para o teste, nunca para produção adivinhar um destino."""
        monkeypatch.delenv(VARIAVEL, raising=False)

        assert url_do_banco("sqlite+pysqlite:///:memory:") == "sqlite+pysqlite:///:memory:"

    def test_o_ambiente_vence_o_padrao(self, monkeypatch):
        monkeypatch.setenv(VARIAVEL, "postgresql+psycopg://real/crm")

        assert url_do_banco("sqlite+pysqlite:///:memory:").startswith("postgresql")


class TestEngine:
    def test_cria_sem_tocar_no_banco(self):
        engine = criar_engine("sqlite+pysqlite:///:memory:")

        assert engine.dialect.name == "sqlite"
