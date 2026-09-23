"""A conexão com o banco — e a recusa de adivinhar onde ele está."""

from __future__ import annotations

import pytest

from crm.db.sessao import VARIAVEL, BancoNaoConfigurado, criar_engine, url_do_banco


class TestUrlDoBanco:
    def test_le_do_ambiente(self, monkeypatch):
        monkeypatch.setenv(VARIAVEL, "postgresql+psycopg://alguem@localhost/crm")

        assert url_do_banco() == "postgresql+psycopg://alguem@localhost/crm"

    def test_sem_variavel_falha_de_forma_visivel(self):
        """Falha visível: melhor parar com mensagem clara do que gravar dado de cliente
        num SQLite improvisado que ninguém sabe que existe."""
        with pytest.raises(BancoNaoConfigurado, match=VARIAVEL):
            url_do_banco()

    def test_a_mensagem_de_erro_ensina_o_caminho_certo(self):
        with pytest.raises(BancoNaoConfigurado, match=r"\.env"):
            url_do_banco()

    def test_o_padrao_so_vale_quando_pedido(self):
        """Existe para o teste, nunca para produção adivinhar um destino."""
        assert url_do_banco("sqlite+pysqlite:///:memory:") == "sqlite+pysqlite:///:memory:"

    def test_o_ambiente_vence_o_padrao(self, monkeypatch):
        monkeypatch.setenv(VARIAVEL, "postgresql+psycopg://real/crm")

        assert url_do_banco("sqlite+pysqlite:///:memory:").startswith("postgresql")


class TestEngine:
    def test_cria_sem_tocar_no_banco(self):
        engine = criar_engine("sqlite+pysqlite:///:memory:")

        assert engine.dialect.name == "sqlite"


class TestArquivoEnv:
    """Ler do `.env` evita que a URL, que carrega senha, passe pela linha de
    comando e fique no histórico do shell."""

    def _escrever(self, tmp_path, conteudo: str):
        arquivo = tmp_path / ".env"
        arquivo.write_text(conteudo, encoding="utf-8")
        return arquivo

    def test_le_a_variavel_do_arquivo(self, tmp_path, monkeypatch):
        from crm.db import sessao as modulo

        arquivo = self._escrever(tmp_path, f"{VARIAVEL}=postgresql+psycopg://a@localhost/crm\n")
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)

        assert modulo.url_do_banco() == "postgresql+psycopg://a@localhost/crm"

    def test_ignora_comentario_e_linha_vazia(self, tmp_path, monkeypatch):
        from crm.db import sessao as modulo

        arquivo = self._escrever(
            tmp_path,
            f"# comentário\n\nOUTRA=coisa\n{VARIAVEL}=postgresql+psycopg://b@localhost/crm\n",
        )
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)

        assert modulo.url_do_banco().endswith("/crm")

    def test_tira_as_aspas(self, tmp_path, monkeypatch):
        from crm.db import sessao as modulo

        arquivo = self._escrever(tmp_path, f'{VARIAVEL}="postgresql+psycopg://c@localhost/crm"\n')
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)

        assert modulo.url_do_banco() == "postgresql+psycopg://c@localhost/crm"

    def test_o_ambiente_vence_o_arquivo(self, tmp_path, monkeypatch):
        """Para o teste e a produção poderem sobrescrever sem editar arquivo."""
        from crm.db import sessao as modulo

        monkeypatch.setenv(VARIAVEL, "postgresql+psycopg://ambiente@localhost/crm")
        arquivo = self._escrever(tmp_path, f"{VARIAVEL}=postgresql+psycopg://arquivo@localhost/crm\n")
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)

        assert "ambiente" in modulo.url_do_banco()

    def test_arquivo_ausente_nao_quebra(self, tmp_path, monkeypatch):
        from crm.db import sessao as modulo

        monkeypatch.setattr(modulo, "ARQUIVO_ENV", tmp_path / "nao-existe")

        with pytest.raises(BancoNaoConfigurado):
            modulo.url_do_banco()

    def test_a_mensagem_de_erro_nao_vaza_conteudo_do_arquivo(self, tmp_path, monkeypatch):
        """Erro que imprime credencial vira credencial em log."""
        from crm.db import sessao as modulo

        arquivo = self._escrever(tmp_path, "OUTRA=senha-secreta-nao-pode-aparecer\n")
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)

        with pytest.raises(BancoNaoConfigurado) as erro:
            modulo.url_do_banco()

        assert "senha-secreta" not in str(erro.value)


class TestMontagemPelasPartes:
    """Senha crua no `.env`, codificada pelo código.

    É a correção de uma falha real: `#` dentro de uma URL inicia a âncora e
    descarta tudo depois dele, então a senha chegava truncada ao servidor e a
    autenticação falhava sem dizer por quê.
    """

    def _partes(self, monkeypatch, **extras):
        from crm.db import sessao as modulo

        monkeypatch.setenv(modulo.PARTES["usuario"], "criterio_crm")
        for chave, valor in extras.items():
            monkeypatch.setenv(modulo.PARTES[chave], valor)
        return modulo

    def test_senha_com_cerquilha_sobrevive(self, monkeypatch):
        import sqlalchemy as sa

        modulo = self._partes(monkeypatch, senha="#abc123")

        assert sa.engine.make_url(modulo.url_do_banco()).password == "#abc123"

    def test_senha_com_arroba_nao_confunde_o_servidor(self, monkeypatch):
        import sqlalchemy as sa

        modulo = self._partes(monkeypatch, senha="senha@forte")
        url = sa.engine.make_url(modulo.url_do_banco())

        assert url.host == "localhost"
        assert url.password == "senha@forte"

    def test_senha_com_barra_nao_vira_caminho(self, monkeypatch):
        import sqlalchemy as sa

        modulo = self._partes(monkeypatch, senha="a/b/c")
        url = sa.engine.make_url(modulo.url_do_banco())

        assert url.database == "criterio_crm"
        assert url.password == "a/b/c"

    def test_usa_os_padroes_quando_so_ha_usuario_e_senha(self, monkeypatch):
        import sqlalchemy as sa

        modulo = self._partes(monkeypatch, senha="x")
        url = sa.engine.make_url(modulo.url_do_banco())

        assert (url.host, url.port, url.database) == ("localhost", 5432, "criterio_crm")

    def test_sem_senha_nao_monta_nada(self, monkeypatch):
        """Metade da configuração é pior que nenhuma: falha visível."""
        modulo = self._partes(monkeypatch)

        with pytest.raises(BancoNaoConfigurado):
            modulo.url_do_banco()

    def test_a_url_inteira_tem_precedencia(self, monkeypatch):
        """É assim que provedor de nuvem entrega — e ela manda."""
        import sqlalchemy as sa

        modulo = self._partes(monkeypatch, senha="local")
        monkeypatch.setenv(VARIAVEL, "postgresql+psycopg://u:p@nuvem:5432/banco")

        assert sa.engine.make_url(modulo.url_do_banco()).host == "nuvem"

    def test_as_partes_funcionam_pelo_arquivo(self, tmp_path, monkeypatch):
        import sqlalchemy as sa

        from crm.db import sessao as modulo

        arquivo = tmp_path / ".env"
        arquivo.write_text(
            "CRM_DB_USER=criterio_crm\nCRM_DB_PASSWORD=#898085aA@\n", encoding="utf-8"
        )
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)
        url = sa.engine.make_url(modulo.url_do_banco())

        assert url.password == "#898085aA@"
        assert url.host == "localhost"
