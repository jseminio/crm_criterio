"""Configuração pela tela (07/10/2026): o que está na tela vale mais que a variável de ambiente.

Ordem de precedência de cada campo do catálogo: **tela** (tabela `configuracao_do_sistema`) →
variável de ambiente antiga (`.env` ou painel do servidor) → padrão do catálogo.

Os módulos que já liam o ambiente (`crm.agente.config`, `crm.questionario.fonte`) passam a ler
`ambiente_efetivo()`: o mesmo dicionário de variáveis, com os valores da tela por cima. Assim nada
muda para eles, e sem banco registrado (os testes de unidade) vale só o ambiente, como antes.

A leitura do banco fica em memória por alguns segundos (`VALIDADE`) e se renova na hora em que a tela
grava: trocar a chave não exige reiniciar a API.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.configuracao.catalogo import CAMPOS, GRUPOS, Campo, Grupo
from crm.configuracao.cofre import SegredoIlegivel, cifrar, decifrar
from crm.db.sessao import ler_ambiente

__all__ = [
    "VALIDADE", "Linha", "registrar_fabrica", "invalidar", "ambiente_efetivo", "valor", "linhas",
    "gravar", "copiar_do_ambiente", "GRUPOS", "CAMPOS", "Campo", "Grupo",
]

_log = logging.getLogger(__name__)
VALIDADE = 10.0
"""Segundos que a leitura do banco vale em memória."""

_trava = threading.Lock()
_fabrica: Callable[[], Session] | None = None
_cache: tuple[float, dict[str, str]] | None = None


def registrar_fabrica(fabrica: Callable[[], Session] | None) -> None:
    """A API registra a fábrica de sessão ao subir; sem ela, vale só o ambiente."""
    global _fabrica
    with _trava:
        _fabrica = fabrica
    invalidar()


def invalidar() -> None:
    global _cache
    with _trava:
        _cache = None


def _ler(sessao: Session) -> dict[str, str]:
    from crm.db.modelos import ConfiguracaoDoSistema

    valores: dict[str, str] = {}
    for linha in sessao.scalars(sa.select(ConfiguracaoDoSistema)):
        if not linha.valor:
            continue
        try:
            valores[linha.chave] = decifrar(linha.valor) if linha.cifrado else linha.valor
        except SegredoIlegivel:
            continue  # a tela mostra "cadastre de novo"; aqui vale o ambiente
    return valores


def _da_tela() -> dict[str, str]:
    global _cache
    with _trava:
        fabrica, cache = _fabrica, _cache
    if fabrica is None:
        return {}
    if cache is not None and time.monotonic() - cache[0] < VALIDADE:
        return cache[1]
    try:
        with fabrica() as sessao:
            valores = _ler(sessao)
    except Exception:  # noqa: BLE001 — sem a tabela (antes da migração) ou sem banco: vale o ambiente
        _log.warning("configuração da tela indisponível; usando só o ambiente", exc_info=True)
        return {}
    with _trava:
        _cache = (time.monotonic(), valores)
    return valores


def ambiente_efetivo() -> dict[str, str]:
    """As variáveis de ambiente, com o que está na tela por cima (pela variável de cada campo)."""
    ambiente = dict(ler_ambiente())
    for chave, valor_da_tela in _da_tela().items():
        campo = CAMPOS.get(chave)
        if campo is not None and campo.variavel:
            ambiente[campo.variavel] = valor_da_tela
    return ambiente


def valor(chave: str) -> str:
    """O valor efetivo de um campo: tela, ambiente, padrão."""
    campo = CAMPOS[chave]
    da_tela = _da_tela().get(chave)
    if da_tela:
        return da_tela
    if campo.variavel:
        do_ambiente = (ler_ambiente().get(campo.variavel) or "").strip()
        if do_ambiente:
            return do_ambiente
    return campo.padrao


@dataclass(frozen=True)
class Linha:
    """Um campo como a tela o vê. Segredo nunca vem em `valor`: só os 4 últimos em `final`."""

    campo: Campo
    origem: str
    """"tela", "servidor" (variável de ambiente), "padrão" ou "vazio"."""
    valor: str | None
    final: str | None
    ilegivel: bool
    alterado_por: str | None
    alterado_em: datetime | None


def _final(segredo: str) -> str:
    return segredo[-4:] if len(segredo) >= 8 else "…"


def linhas(sessao: Session) -> dict[str, Linha]:
    from crm.db.modelos import ConfiguracaoDoSistema

    no_banco = {l.chave: l for l in sessao.scalars(sa.select(ConfiguracaoDoSistema))}
    ambiente = ler_ambiente()
    resultado: dict[str, Linha] = {}
    for campo in CAMPOS.values():
        linha = no_banco.get(campo.chave)
        efetivo, origem, ilegivel = None, "vazio", False
        if linha is not None and linha.valor:
            try:
                efetivo, origem = (decifrar(linha.valor) if linha.cifrado else linha.valor), "tela"
            except SegredoIlegivel:
                ilegivel = True
        if efetivo is None and campo.variavel and (ambiente.get(campo.variavel) or "").strip():
            efetivo, origem = ambiente[campo.variavel].strip(), "servidor"
        if efetivo is None and campo.padrao:
            efetivo, origem = campo.padrao, "padrão"
        resultado[campo.chave] = Linha(
            campo=campo, origem=origem,
            valor=None if campo.segredo else efetivo,
            final=_final(efetivo) if campo.segredo and efetivo else None,
            ilegivel=ilegivel,
            alterado_por=linha.alterado_por if linha is not None else None,
            alterado_em=linha.alterado_em if linha is not None else None,
        )
    return resultado


def gravar(sessao: Session, chave: str, novo: str | None, quem: str | None) -> None:
    """Grava um campo (sem commit). Vazio ou `None` apaga o valor da tela: volta a valer o ambiente."""
    from crm.db.base import agora
    from crm.db.modelos import ConfiguracaoDoSistema

    campo = CAMPOS[chave]
    novo = (novo or "").strip() or None
    linha = sessao.get(ConfiguracaoDoSistema, chave)
    if linha is None:
        linha = ConfiguracaoDoSistema(chave=chave)
        sessao.add(linha)
    linha.valor = cifrar(novo) if (novo and campo.segredo) else novo
    linha.cifrado = bool(novo and campo.segredo)
    linha.alterado_por = quem
    linha.alterado_em = agora()
    invalidar()


def copiar_do_ambiente(sessao: Session, quem: str) -> list[str]:
    """Copia para a tela o que está nas variáveis de ambiente e ainda não está na tela. Não sobrescreve
    nada: o que já foi salvo na tela continua valendo. Devolve as chaves copiadas."""
    from crm.db.modelos import ConfiguracaoDoSistema

    ambiente = ler_ambiente()
    copiadas = []
    for campo in CAMPOS.values():
        do_ambiente = (ambiente.get(campo.variavel) or "").strip() if campo.variavel else ""
        if not do_ambiente:
            continue
        linha = sessao.get(ConfiguracaoDoSistema, campo.chave)
        if linha is not None and linha.valor:
            continue
        gravar(sessao, campo.chave, do_ambiente, quem)
        copiadas.append(campo.chave)
    return copiadas
