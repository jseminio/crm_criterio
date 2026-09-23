"""Rotas do backup lógico: baixar, conferir e restaurar os dados.

⚠️ **Só na própria máquina.** O arquivo tem todos os dados de cliente e a API não
tem login. As rotas recusam qualquer pedido que chegue por túnel ou proxy
reverso (cabeçalhos `X-Forwarded-*`/`Forwarded`) ou por um endereço que não seja
`localhost`. O acesso remoto (ngrok) continua vendo as outras telas, nunca esta.
"""

from __future__ import annotations

import io
from datetime import datetime
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
