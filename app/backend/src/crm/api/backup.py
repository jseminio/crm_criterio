"""Rotas do backup lógico: baixar, conferir e restaurar os dados.

⚠️ **Só na própria máquina.** O arquivo tem todos os dados de cliente e a API não
tem login. As rotas recusam qualquer pedido que chegue por túnel ou proxy
reverso (cabeçalhos `X-Forwarded-*`/`Forwarded`) ou por um endereço que não seja
`localhost`. O acesso remoto (ngrok) continua vendo as outras telas, nunca esta.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Callable

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from crm.backup import ErroDeBackup, ResumoDeBackup, exportar, importar, verificar

_LOCAIS = {"localhost", "127.0.0.1", "[::1]", "::1"}
_LIMITE = 200 * 1024 * 1024  # 200 MB


class ResumoResposta(BaseModel):
    criado_em: str
    revisao_do_esquema: str | None
    tabelas: dict[str, int]
    total: int


def _resumo(r: ResumoDeBackup) -> ResumoResposta:
    return ResumoResposta(
        criado_em=r.criado_em, revisao_do_esquema=r.revisao_do_esquema, tabelas=r.tabelas, total=r.total
    )


def somente_local(request: Request) -> None:
    proibidos = ("x-forwarded-for", "x-forwarded-host", "forwarded", "x-real-ip")
    if any(h in request.headers for h in proibidos):
        raise HTTPException(403, "O backup só funciona direto na máquina do CRM, nunca por túnel ou rede.")
    host = (request.headers.get("host") or "").rsplit(":", 1)[0] if not request.headers.get("host", "").startswith("[") else "[::1]"
    if host not in _LOCAIS:
        raise HTTPException(403, "O backup só funciona direto na máquina do CRM, nunca por túnel ou rede.")


def roteador(obter_engine: Callable[[], sa.Engine]) -> APIRouter:
    r = APIRouter(prefix="/api/backup", tags=["backup"], dependencies=[Depends(somente_local)])

    @r.get("/exportar")
    def baixar() -> Response:
        buf = io.BytesIO()
        exportar(obter_engine(), buf)
        nome = f"crm-{datetime.now():%Y%m%d-%H%M%S}.zip"
        return Response(
            buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{nome}"', "Cache-Control": "no-store"},
        )

    async def _corpo(request: Request) -> io.BytesIO:
        dados = await request.body()
        if not dados:
            raise HTTPException(400, "Nenhum arquivo enviado.")
        if len(dados) > _LIMITE:
            raise HTTPException(413, "Arquivo grande demais para importar pela tela; use o comando backup.py.")
        return io.BytesIO(dados)

    @r.post("/verificar", response_model=ResumoResposta)
    async def conferir(request: Request) -> ResumoResposta:
        try:
            return _resumo(verificar(await _corpo(request)))
        except ErroDeBackup as erro:
            raise HTTPException(422, str(erro)) from erro

    @r.post("/importar", response_model=ResumoResposta)
    async def restaurar(request: Request, substituir: bool = Query(False)) -> ResumoResposta:
        if substituir and request.headers.get("x-confirmacao") != "SUBSTITUIR":
            raise HTTPException(400, "Substituir apaga os dados atuais e exige confirmação explícita.")
        try:
            return _resumo(importar(obter_engine(), await _corpo(request), substituir=substituir))
        except ErroDeBackup as erro:
            raise HTTPException(409, str(erro)) from erro

    return r



# ---------------------------------------------------------------- migrar do CRM local (10/10/2026)

def administrador_ou_local(request: Request) -> None:
    """A migração roda na nuvem, por proxy, com login: só o Administrador (aprovado por Eduardo em 10/10/2026).
    Sem login (a máquina do CRM), vale a regra de sempre do backup: só direto no localhost."""
    from crm.acesso.auditoria import usuario_atual

    u = usuario_atual.get()
    if u is not None:
        if not u.administrador:
            raise HTTPException(403, "Migrar do CRM local é só do Administrador.")
        return
    somente_local(request)


class LinhaDaPreviaResposta(BaseModel):
    tabela: str
    no_arquivo: int
    na_nuvem: int
    acao: str


class PreviaDaMigracaoResposta(BaseModel):
    criado_em: str
    revisao_do_arquivo: str | None
    revisao_da_nuvem: str | None
    pode_migrar: bool
    motivo: str | None
    registros_que_entram: int
    registros_que_saem: int
    linhas: list[LinhaDaPreviaResposta]


class MigracaoFeitaResposta(BaseModel):
    registros: int
    backup_de_antes: str


async def _corpo_da_migracao(request: Request) -> io.BytesIO:
    dados = await request.body()
    if not dados:
        raise HTTPException(400, "Nenhum arquivo enviado.")
    if len(dados) > _LIMITE:
        raise HTTPException(413, "Arquivo grande demais para a migração pela tela.")
    return io.BytesIO(dados)


def roteador_da_migracao(obter_engine: Callable[[], sa.Engine], pasta_do_backup: Callable[[], "Path"]) -> APIRouter:
    from crm.backup.migracao import migrar, previa

    r = APIRouter(prefix="/api/migracao", tags=["backup"], dependencies=[Depends(administrador_ou_local)])

    @r.post("/previa", response_model=PreviaDaMigracaoResposta)
    async def ver_previa(request: Request) -> PreviaDaMigracaoResposta:
        """O que a migração faria, tabela por tabela. Não grava nada."""
        try:
            p = previa(obter_engine(), await _corpo_da_migracao(request))
        except ErroDeBackup as erro:
            raise HTTPException(422, str(erro)) from erro
        return PreviaDaMigracaoResposta(
            criado_em=p.criado_em, revisao_do_arquivo=p.revisao_do_arquivo, revisao_da_nuvem=p.revisao_da_nuvem,
            pode_migrar=p.pode_migrar, motivo=p.motivo, registros_que_entram=p.registros_que_entram,
            registros_que_saem=p.registros_que_saem,
            linhas=[LinhaDaPreviaResposta(**vars(l)) for l in p.linhas],
        )

    @r.post("/migrar", response_model=MigracaoFeitaResposta)
    async def fazer(request: Request) -> MigracaoFeitaResposta:
        """Substitui os dados de negócio pelos do arquivo e preserva os da nuvem (usuários, perfis, integrações,
        manutenção, WhatsApp). Irreversível: pede a confirmação MIGRAR e grava o backup da nuvem antes."""
        if request.headers.get("x-confirmacao") != "MIGRAR":
            raise HTTPException(400, "Migrar substitui os dados da nuvem e exige a confirmação explícita.")
        try:
            resumo, antes = migrar(obter_engine(), await _corpo_da_migracao(request), pasta_do_backup=pasta_do_backup())
        except ErroDeBackup as erro:
            raise HTTPException(409, str(erro)) from erro
        return MigracaoFeitaResposta(registros=resumo.total, backup_de_antes=antes.name)

    return r
