"""Conexão com o banco, lida do ambiente.

**Nenhuma credencial mora no código.** A regra do projeto é explícita: segredo
só em `.env` ou cofre, nunca em código, JSON, nota ou log. Este módulo lê a
variável e não guarda nem imprime o que leu.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

__all__ = [
    "url_do_banco",
    "ler_ambiente",
    "criar_engine",
    "criar_fabrica_de_sessao",
    "sessao",
    "VARIAVEL",
    "PARTES",
    "ARQUIVO_ENV",
    "BancoNaoConfigurado",
]

VARIAVEL = "CRM_DATABASE_URL"

#: As partes da conexão, para quem não quer montar um endereço à mão.
#:
#: Existe porque senha com caractere especial quebra dentro de uma URL — o "#"
#: inicia a âncora e **descarta tudo depois dele**, em silêncio, e a
#: autenticação falha sem dizer por quê. Aqui a senha é escrita crua e quem
#: codifica é o código.
PARTES = {
    "host": "CRM_DB_HOST",
    "porta": "CRM_DB_PORT",
    "banco": "CRM_DB_NAME",
    "usuario": "CRM_DB_USER",
    "senha": "CRM_DB_PASSWORD",
}

PADROES = {"host": "localhost", "porta": "5432", "banco": "criterio_crm"}

#: Só para teste e exploração local. Não serve de produção: não persiste.
URL_DE_MEMORIA = "sqlite+pysqlite:///:memory:"


class BancoNaoConfigurado(RuntimeError):
    """Levantada quando ninguém disse onde está o banco.

    Falha visível, como mandam as regras do projeto: cair aqui com uma mensagem clara é melhor
    do que escrever dados de cliente num SQLite improvisado que ninguém sabe que
    existe.
    """


#: Onde procurar o arquivo de ambiente: a raiz do backend.
ARQUIVO_ENV = Path(__file__).resolve().parents[3] / ".env"


def _ambiente(arquivo: Path | None = None) -> dict[str, str]:
    """Junta as variáveis do processo com as do `.env`. O processo vence."""
    valores = dict(_todas_do_arquivo(arquivo))
    valores.update(os.environ)
    return valores


def ler_ambiente() -> dict[str, str]:
    """As variáveis do processo e do `.env` do backend, o processo vencendo.

    Para os outros módulos lerem a própria configuração (agente SDR, envio)
    do mesmo `.env`, sem cada um reimplementar a leitura.
    """
    return _ambiente()


def _todas_do_arquivo(arquivo: Path | None = None) -> dict[str, str]:
    """Lê todas as atribuições do `.env`, quando ele existir.

    **Nenhum valor lido aqui entra em log ou em mensagem de erro.**
    Formato: uma atribuição por linha, `#` comenta, aspas são opcionais.
    """
    arquivo = arquivo or ARQUIVO_ENV
    if not arquivo.is_file():
        return {}
    try:
        conteudo = arquivo.read_text(encoding="utf-8")
    except OSError:
        return {}
    valores: dict[str, str] = {}
    for linha in conteudo.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#") or "=" not in limpa:
            continue
        chave, _, valor = limpa.partition("=")
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if valor:
            valores[chave.strip()] = valor
    return valores


def _montar_das_partes(valores: dict[str, str]) -> str | None:
    """Monta a URL a partir de host, porta, banco, usuário e senha.

    **A senha é codificada aqui**, com `safe=""`, para que nenhum caractere
    especial — `#`, `@`, `/`, `?`, `:`, `%`, espaço — mude o significado do
    endereço. Quem escreve o `.env` escreve a senha como ela é.
    """
    usuario = valores.get(PARTES["usuario"])
    senha = valores.get(PARTES["senha"])
    if not usuario or not senha:
        return None
    host = valores.get(PARTES["host"], PADROES["host"])
    porta = valores.get(PARTES["porta"], PADROES["porta"])
    banco = valores.get(PARTES["banco"], PADROES["banco"])
    return (
        f"postgresql+psycopg://{quote(usuario, safe='')}:{quote(senha, safe='')}"
        f"@{host}:{porta}/{banco}"
    )


def _ler_do_arquivo(arquivo: Path | None = None) -> str | None:
    """Lê `CRM_DATABASE_URL` do `.env`, quando ele existir.

    Evita que cada comando precise exportar a variável à mão — e, principalmente,
    evita que alguém a cole numa linha de comando, onde ela ficaria no histórico
    do shell. O `.env` é ignorado pelo git.

    **O valor lido nunca é registrado em log nem devolvido em mensagem de erro.**
    Formato aceito: uma atribuição por linha, `#` comenta, aspas são opcionais.
    """
    arquivo = arquivo or ARQUIVO_ENV
    if not arquivo.is_file():
        return None
    try:
        conteudo = arquivo.read_text(encoding="utf-8")
    except OSError:
        return None
    for linha in conteudo.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#") or "=" not in limpa:
            continue
        chave, _, valor = limpa.partition("=")
        if chave.strip() != VARIAVEL:
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        return valor or None
    return None


def url_do_banco(padrao: str | None = None) -> str:
    """Devolve a URL de conexão, nesta ordem de precedência:

    1. `CRM_DATABASE_URL` no ambiente — é assim que provedor de nuvem entrega;
    2. `CRM_DATABASE_URL` no `.env`;
    3. as partes `CRM_DB_*`, montadas e codificadas aqui — o caminho recomendado
       em desenvolvimento, porque não exige acertar escape de endereço;
    4. `padrao`, que só o teste passa. Produção nunca adivinha um destino.
    """
    valores = _ambiente()
    url = valores.get(VARIAVEL) or _montar_das_partes(valores) or padrao
    if not url:
        raise BancoNaoConfigurado(
            f"Não sei onde está o banco. Preencha {ARQUIVO_ENV} com "
            f"{PARTES['usuario']} e {PARTES['senha']} — a senha vai crua, o "
            f"código codifica — ou defina {VARIAVEL} com o endereço inteiro. "
            f"Modelo em .env.example. Segredo nunca vai para o código."
        )
    return url


def criar_engine(url: str | None = None, *, echo: bool = False) -> sa.Engine:
    """Cria a engine. `echo=True` mostra o SQL — só para depurar, nunca em uso real."""
    destino = url or url_do_banco()
    parametros: dict = {"echo": echo, "future": True}
    if destino.startswith("postgresql"):
        # Devolve conexão morta ao pool antes que o servidor a derrube.
        parametros["pool_pre_ping"] = True
    return sa.create_engine(destino, **parametros)


def criar_fabrica_de_sessao(engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def sessao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    """Abre uma sessão que confirma no fim ou desfaz por inteiro no erro."""
    sessao_aberta = fabrica()
    try:
        yield sessao_aberta
        sessao_aberta.commit()
    except Exception:
        sessao_aberta.rollback()
        raise
    finally:
        sessao_aberta.close()
