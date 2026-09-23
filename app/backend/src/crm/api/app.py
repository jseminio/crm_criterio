"""A API do Critério CRM.

Serve o funil: grupos, oportunidades e leads. É o que o E3 precisa e nada além
— contrato, implantação e carteira classificada não passam por aqui.

⚠️ **Esta API não tem autenticação.** O E1, que traz o login pela conta
corporativa Microsoft, foi adiado por decisão de Eduardo em 20/09/2026 para que
o CRM ficasse de pé até sexta. Enquanto isso ela roda **só na máquina dele, com
um único usuário**, e escuta apenas em `localhost`.

Isso está declarado na proposta aprovada, seção 2, com o alcance: a Karine não
usa o CRM até o E1. **Não publique esta API em rede nenhuma antes do login
existir.**
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import Iterator, Literal

import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from crm.api import esquemas as e
from crm.carga.persistencia import CAMPOS as CAMPOS_DA_CARGA
from crm.db.base import agora
from crm.db.grupos import FusaoInvalida, fundir_grupos
from crm.db.modelos import (
    ExecucaoDeCarga,
    GrupoEconomico,
    Lead,
    OcorrenciaDeCarga,
    Oportunidade,
)
from crm.db.sessao import criar_engine, criar_fabrica_de_sessao, url_do_banco
from crm.domain import indicadores as regras_de_indicadores
from crm.domain import porte as regras_de_porte
from crm.domain.listas import (
    LinhaServico,
    MotivoRecusa,
    Origem,
    Situacao,
    SituacaoGrupo,
    SituacaoLead,
    Temperatura,
    TipoCanal,
    TipoDeOcorrencia,
)
from crm.domain.listas import _CAPTADORES  # noqa: PLC2701 — única fonte da lista

__all__ = ["criar_app", "app"]

#: De onde a tela é servida durante o desenvolvimento.
ORIGENS_PERMITIDAS = ["http://localhost:5173", "http://127.0.0.1:5173"]

_fabrica: sessionmaker[Session] | None = None


def obter_sessao() -> Iterator[Session]:
    """Uma sessão por requisição, confirmada no fim ou desfeita por inteiro."""
    assert _fabrica is not None, "a aplicação não foi iniciada"
    sessao = _fabrica()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()


def criar_app(fabrica: sessionmaker[Session] | None = None) -> FastAPI:
    """Monta a aplicação. `fabrica` existe para o teste usar seu próprio banco."""

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        global _fabrica
        _fabrica = fabrica or criar_fabrica_de_sessao(criar_engine(url_do_banco()))
        yield

    api = FastAPI(
        title="Critério CRM",
        version="0.1.0",
        summary="Funil comercial. Sem autenticação — ver o aviso no módulo.",
        lifespan=ciclo_de_vida,
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=ORIGENS_PERMITIDAS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _registrar(api)
    return api


def _valores(enum) -> list[str]:
    return [membro.value for membro in enum]


def _resumo_de(oportunidade: Oportunidade, nome_do_grupo: str | None) -> e.OportunidadeResumo:
    resumo = e.OportunidadeResumo.model_validate(oportunidade)
    resumo.grupo_nome = nome_do_grupo
    return resumo


def _detalhe_de(oportunidade: Oportunidade, nome_do_grupo: str | None) -> e.OportunidadeDetalhe:
    """O detalhe, com a sugestão da régua de porte calculada na hora — ela
    nunca é gravada, então recalcula a cada leitura (ver `crm.domain.porte`)."""
    detalhe = e.OportunidadeDetalhe.model_validate(oportunidade)
    detalhe.grupo_nome = nome_do_grupo
    volumetria = regras_de_porte.Volumetria(
        documentos_fiscais_mes=oportunidade.documentos_fiscais_mes,
        lancamentos_contabeis_mes=oportunidade.lancamentos_contabeis_mes,
        pagamentos_mes=oportunidade.pagamentos_mes,
        contas_bancarias=oportunidade.contas_bancarias,
        conciliacoes_cartao_mes=oportunidade.conciliacoes_cartao_mes,
        empregados_clt=oportunidade.empregados_clt,
        admissoes_desligamentos_mes=oportunidade.admissoes_desligamentos_mes,
        cnpjs_no_escopo=oportunidade.cnpjs_no_escopo,
        tomadores_de_servico=oportunidade.tomadores_de_servico,
        servicos_contratados_alem_do_primeiro=oportunidade.servicos_contratados_alem_do_primeiro,
        tem_consolidacao_de_grupo=oportunidade.tem_consolidacao_de_grupo,
        e_auditada=oportunidade.e_auditada,
    )
    sugestao = regras_de_porte.sugerir_porte(volumetria)
    detalhe.sugestao_de_porte = e.SugestaoDePorteResposta(
        calculavel=sugestao.calculavel,
        pontuacao=sugestao.pontuacao,
        porte=sugestao.porte.value if sugestao.porte else None,
        horas_base=sugestao.horas_base,
        direcionadores_aplicados=sugestao.direcionadores_aplicados,
    )
    return detalhe


def _registrar(api: FastAPI) -> None:
    # ------------------------------------------------------------------ listas
    @api.get("/api/listas", response_model=e.Listas, tags=["referência"])
    def listas() -> e.Listas:
        """As listas controladas, para a tela montar os seletores."""
        return e.Listas(
            situacoes=_valores(Situacao),
            situacoes_de_lead=_valores(SituacaoLead),
            temperaturas=_valores(Temperatura),
            tipos_de_canal=_valores(TipoCanal),
            tipos_de_canal_em_operacao=[c.value for c in TipoCanal if c.em_operacao],
            motivos_de_recusa=_valores(MotivoRecusa),
            linhas_de_servico=_valores(LinhaServico),
            situacoes_de_grupo=_valores(SituacaoGrupo),
            captadores=sorted(_CAPTADORES),
            portes=[p.value for p in regras_de_porte.Porte],
        )

    # ------------------------------------------------------------------ grupos
    @api.get("/api/grupos", response_model=e.Pagina[e.GrupoResumo], tags=["grupos"])
    def listar_grupos(
        sessao: Session = Depends(obter_sessao),
        busca: str | None = None,
        incluir_fundidos: bool = False,
        limite: int = Query(default=50, le=500),
        salto: int = 0,
    ) -> e.Pagina[e.GrupoResumo]:
        quantas = (
            sa.select(sa.func.count(Oportunidade.id))
            .where(Oportunidade.grupo_id == GrupoEconomico.id)
            .scalar_subquery()
        )
        consulta = sa.select(GrupoEconomico, quantas)
        if not incluir_fundidos:
            consulta = consulta.where(GrupoEconomico.fundido_em_id.is_(None))
        if busca:
            consulta = consulta.where(GrupoEconomico.nome.ilike(f"%{busca}%"))

        total = sessao.scalar(
            sa.select(sa.func.count()).select_from(consulta.subquery())
        )
        linhas = sessao.execute(
            consulta.order_by(quantas.desc(), GrupoEconomico.nome)
            .offset(salto)
            .limit(limite)
        ).all()

        itens = []
        for grupo, quantidade in linhas:
            resumo = e.GrupoResumo.model_validate(grupo)
            resumo.quantas_oportunidades = quantidade or 0
            itens.append(resumo)
        return e.Pagina(total=total or 0, itens=itens)

    @api.post("/api/grupos/{grupo_id}/fundir", response_model=e.GrupoResumo, tags=["grupos"])
    def fundir(
        grupo_id: int, corpo: e.Fusao, sessao: Session = Depends(obter_sessao)
    ) -> e.GrupoResumo:
        """Absorve outro grupo neste. O absorvido **não é apagado**."""
        principal = sessao.get(GrupoEconomico, grupo_id)
        absorvido = sessao.get(GrupoEconomico, corpo.absorvido_id)
        if principal is None or absorvido is None:
            raise HTTPException(404, "grupo não encontrado")
        try:
            fundir_grupos(sessao, principal, absorvido)
        except FusaoInvalida as erro:
            raise HTTPException(409, str(erro)) from erro
        return e.GrupoResumo.model_validate(principal)

    # ----------------------------------------------------------- oportunidades
    def _consulta_de_oportunidades(
        situacao: list[Situacao] | None,
        captador: list[str] | None,
        tipo_canal: list[TipoCanal] | None,
        temperatura: list[Temperatura] | None,
        grupo_id: int | None,
        busca: str | None,
        data_tipo: Literal["colocacao", "aceite"] | None = None,
        data_de: date | None = None,
        data_ate: date | None = None,
    ):
        consulta = sa.select(Oportunidade, GrupoEconomico.nome).join(
            GrupoEconomico, Oportunidade.grupo_id == GrupoEconomico.id
        )
        if situacao:
            consulta = consulta.where(Oportunidade.situacao.in_(situacao))
        if captador:
            consulta = consulta.where(Oportunidade.captador.in_(captador))
        if tipo_canal:
            consulta = consulta.where(Oportunidade.tipo_canal.in_(tipo_canal))
        if temperatura:
            consulta = consulta.where(Oportunidade.temperatura.in_(temperatura))
        if grupo_id is not None:
            consulta = consulta.where(Oportunidade.grupo_id == grupo_id)
        if busca:
            consulta = consulta.where(
                sa.or_(
                    Oportunidade.nome.ilike(f"%{busca}%"),
                    GrupoEconomico.nome.ilike(f"%{busca}%"),
                )
            )
        if data_de or data_ate:
            # Corte de período, pedido por Eduardo em 22/09/2026 para medir o
            # efeito de um teste de prospecção num recorte de tempo. O campo é
            # escolhido por quem filtra: colocação (quando a proposta foi
            # enviada) é o padrão, aceite (quando foi decidida) é a opção —
            # os dois existem em `Oportunidade`, e cada um mede uma pergunta
            # diferente.
            campo = Oportunidade.data_aceite if data_tipo == "aceite" else Oportunidade.data_colocacao
            if data_de:
                consulta = consulta.where(campo >= data_de)
            if data_ate:
                consulta = consulta.where(campo <= data_ate)
        return consulta

    @api.get(
        "/api/oportunidades",
        response_model=e.Pagina[e.OportunidadeResumo],
        tags=["funil"],
    )
    def listar_oportunidades(
        sessao: Session = Depends(obter_sessao),
        situacao: list[Situacao] | None = Query(default=None),
        captador: list[str] | None = Query(default=None),
        tipo_canal: list[TipoCanal] | None = Query(default=None),
        temperatura: list[Temperatura] | None = Query(default=None),
        grupo_id: int | None = None,
        busca: str | None = None,
        data_tipo: Literal["colocacao", "aceite"] | None = None,
        data_de: date | None = None,
        data_ate: date | None = None,
        limite: int = Query(default=100, le=1000),
        salto: int = 0,
    ) -> e.Pagina[e.OportunidadeResumo]:
        """A visão em lista, com os filtros que o funil precisa."""
        consulta = _consulta_de_oportunidades(
            situacao, captador, tipo_canal, temperatura, grupo_id, busca,
            data_tipo, data_de, data_ate,
        )
        total = sessao.scalar(sa.select(sa.func.count()).select_from(consulta.subquery()))
        linhas = sessao.execute(
            consulta.order_by(
                Oportunidade.data_colocacao.desc().nulls_last(), Oportunidade.id.desc()
            )
            .offset(salto)
            .limit(limite)
        ).all()
        return e.Pagina(
            total=total or 0,
            itens=[_resumo_de(o, nome) for o, nome in linhas],
        )

    @api.post(
        "/api/oportunidades",
        response_model=e.OportunidadeDetalhe,
        status_code=201,
        tags=["funil"],
    )
    def criar_oportunidade(
        corpo: e.OportunidadeNova, sessao: Session = Depends(obter_sessao)
    ) -> e.OportunidadeDetalhe:
        """A proposta nasce direto no CRM — sem passar pela planilha nem por
        um lead. Decisão de Eduardo em 22/09/2026 (E4).

        O grupo existente é reaproveitado pelo nome; se não houver, nasce um
        novo — mesmo padrão de `converter_lead`.
        """
        if corpo.grupo_id is not None:
            grupo = sessao.get(GrupoEconomico, corpo.grupo_id)
            if grupo is None:
                raise HTTPException(404, "grupo não encontrado")
        else:
            nome_do_grupo = corpo.nome_do_grupo or corpo.nome
            grupo = sessao.scalar(
                sa.select(GrupoEconomico).where(
                    sa.func.lower(GrupoEconomico.nome) == nome_do_grupo.casefold(),
                    GrupoEconomico.fundido_em_id.is_(None),
                )
            )
            if grupo is None:
                grupo = GrupoEconomico(
                    nome=nome_do_grupo, situacao=SituacaoGrupo.PROSPECT, origem=Origem.CRM
                )
                sessao.add(grupo)
                sessao.flush()

        oportunidade = Oportunidade(
            grupo_id=grupo.id,
            nome=corpo.nome,
            servico=corpo.servico,
            tipo_servico=corpo.tipo_servico,
            situacao=Situacao.ENVIAR_PROPOSTA,
            temperatura=corpo.temperatura,
            tipo_canal=corpo.tipo_canal,
            canal=corpo.canal,
            captador=corpo.captador,
            data_colocacao=corpo.data_colocacao or date.today(),
            preco_mensal=corpo.preco_mensal,
            preco_anual=corpo.preco_anual,
            origem=Origem.CRM,
        )
        sessao.add(oportunidade)
        sessao.flush()

        return _detalhe_de(oportunidade, grupo.nome)

    @api.get("/api/funil", response_model=list[e.ColunaDoFunil], tags=["funil"])
    def funil(
        sessao: Session = Depends(obter_sessao),
        captador: list[str] | None = Query(default=None),
        tipo_canal: list[TipoCanal] | None = Query(default=None),
        temperatura: list[Temperatura] | None = Query(default=None),
        busca: str | None = None,
        data_tipo: Literal["colocacao", "aceite"] | None = None,
        data_de: date | None = None,
        data_ate: date | None = None,
    ) -> list[e.ColunaDoFunil]:
        """O kanban: uma coluna por situação, na ordem do funil.

        Devolve **todas** as situações, inclusive as vazias. Coluna que some
        quando zera faz a tela dançar e esconde que o estado existe.
        """
        consulta = _consulta_de_oportunidades(
            None, captador, tipo_canal, temperatura, None, busca,
            data_tipo, data_de, data_ate,
        )
        linhas = sessao.execute(
            consulta.order_by(Oportunidade.data_colocacao.desc().nulls_last())
        ).all()

        por_situacao: dict[Situacao, list] = {s: [] for s in Situacao}
        for oportunidade, nome in linhas:
            por_situacao[oportunidade.situacao].append((oportunidade, nome))

        colunas = []
        for situacao, itens in por_situacao.items():
            colunas.append(
                e.ColunaDoFunil(
                    situacao=situacao,
                    quantas=len(itens),
                    valor_mensal=sum((o.preco_mensal or 0) for o, _ in itens),
                    valor_anual=sum((o.preco_anual or 0) for o, _ in itens),
                    oportunidades=[_resumo_de(o, nome) for o, nome in itens],
                )
            )
        return colunas

    @api.get("/api/indicadores", response_model=e.IndicadoresResposta, tags=["funil"])
    def indicadores(
        sessao: Session = Depends(obter_sessao),
        captador: list[str] | None = Query(default=None),
        tipo_canal: list[TipoCanal] | None = Query(default=None),
        temperatura: list[Temperatura] | None = Query(default=None),
        busca: str | None = None,
        data_tipo: Literal["colocacao", "aceite"] | None = None,
        data_de: date | None = None,
        data_ate: date | None = None,
    ) -> e.IndicadoresResposta:
        """Os números do funil, com os mesmos filtros do kanban.

        Só entra o que os dados sustentam sem definição pendente. O que não dá
        para calcular volta com o motivo e o que falta — ver
        `crm.domain.indicadores`.
        """
        consulta = _consulta_de_oportunidades(
            None, captador, tipo_canal, temperatura, None, busca,
            data_tipo, data_de, data_ate,
        )
        oportunidades = [linha[0] for linha in sessao.execute(consulta).all()]
        resultado = regras_de_indicadores.calcular(oportunidades)

        def recorte(r: regras_de_indicadores.Recorte) -> e.RecorteResposta:
            return e.RecorteResposta(
                quantas=r.quantas,
                valor_mensal=r.valor_mensal,
                valor_anual=r.valor_anual,
                sem_preco_mensal=r.sem_preco_mensal,
                com_preco_mensal=r.com_preco_mensal,
            )

        return e.IndicadoresResposta(
            em_aberto=recorte(resultado.em_aberto),
            aceitas=recorte(resultado.aceitas),
            aceitas_com_data_de_aceite=resultado.aceitas_com_data_de_aceite,
            ciclo_medio=e.PendenciaResposta.model_validate(resultado.ciclo_medio),
            taxa_de_conversao=e.TaxaDeConversaoResposta.model_validate(
                resultado.taxa_de_conversao
            ),
        )

    @api.get(
        "/api/oportunidades/{oportunidade_id}",
        response_model=e.OportunidadeDetalhe,
        tags=["funil"],
    )
    def ver_oportunidade(
        oportunidade_id: int, sessao: Session = Depends(obter_sessao)
    ) -> e.OportunidadeDetalhe:
        oportunidade = sessao.get(Oportunidade, oportunidade_id)
        if oportunidade is None:
            raise HTTPException(404, "oportunidade não encontrada")
        return _detalhe_de(oportunidade, oportunidade.grupo.nome)

    @api.patch(
        "/api/oportunidades/{oportunidade_id}",
        response_model=e.OportunidadeDetalhe,
        tags=["funil"],
    )
    def editar_oportunidade(
        oportunidade_id: int,
        corpo: e.OportunidadeEdicao,
        sessao: Session = Depends(obter_sessao),
    ) -> e.OportunidadeDetalhe:
        """Altera só o que veio no corpo. Campo ausente não é campo vazio."""
        oportunidade = sessao.get(Oportunidade, oportunidade_id)
        if oportunidade is None:
            raise HTTPException(404, "oportunidade não encontrada")

        mudancas = corpo.model_dump(exclude_unset=True)

        # Lembra o que foi mudado AQUI e a planilha também controla, para a
        # recarga não desfazer. Só conta o que de fato mudou de valor: abrir o
        # painel e salvar sem alterar nada não deve travar o campo.
        editados = {
            campo
            for campo, valor in mudancas.items()
            if campo in CAMPOS_DA_CARGA and getattr(oportunidade, campo) != valor
        }
        # Mesma disciplina para o porte: a tela manda o rascunho inteiro a
        # cada salvar, `porte` incluso mesmo sem ninguém ter mexido nele — só
        # carimba o servidor quando o valor realmente mudou.
        porte_mudou = "porte" in mudancas and oportunidade.porte != mudancas["porte"]

        for campo, valor in mudancas.items():
            setattr(oportunidade, campo, valor)
        if editados:
            # Nova lista, não mutação: o SQLAlchemy não enxerga alteração no
            # lugar de um valor JSON.
            oportunidade.campos_do_crm = sorted(
                set(oportunidade.campos_do_crm or []) | editados
            )

        # O instante da confirmação/sobreposição de porte é do servidor, não
        # do navegador de quem preenche — é este par (quem + quando) que vira
        # material para recalibrar a régua depois.
        if porte_mudou:
            oportunidade.porte_definido_em = agora()

        # Aceita sem data de aceite é o defeito mais comum da planilha de 2026.
        # Aqui não se repete: a API recusa, em vez de deixar passar e virar
        # indicador errado depois.
        if (
            oportunidade.situacao is Situacao.ACEITA
            and oportunidade.data_aceite is None
            and "situacao" in mudancas
        ):
            raise HTTPException(422, "para marcar como aceita, informe a data do aceite")

        sessao.flush()
        return _detalhe_de(oportunidade, oportunidade.grupo.nome)

    # ------------------------------------------------------------- conferência
    def _contagens(sessao: Session, ids: list[int]) -> dict[int, dict[TipoDeOcorrencia, int]]:
        """Quantas ocorrências de cada tipo, por rodada, numa consulta só."""
        contagem: dict[int, dict[TipoDeOcorrencia, int]] = {i: {} for i in ids}
        if not ids:
            return contagem
        linhas = sessao.execute(
            sa.select(
                OcorrenciaDeCarga.execucao_id, OcorrenciaDeCarga.tipo, sa.func.count()
            )
            .where(OcorrenciaDeCarga.execucao_id.in_(ids))
            .group_by(OcorrenciaDeCarga.execucao_id, OcorrenciaDeCarga.tipo)
        ).all()
        for execucao_id, tipo, quantas in linhas:
            contagem[execucao_id][tipo] = quantas
        return contagem

    def _resumo_da_execucao(
        execucao: ExecucaoDeCarga, contagem: dict[TipoDeOcorrencia, int]
    ) -> dict:
        dados = e.ExecucaoResumo.model_validate(execucao).model_dump()
        dados["pendencias"] = contagem.get(TipoDeOcorrencia.PENDENCIA, 0)
        dados["ajustes"] = contagem.get(TipoDeOcorrencia.AJUSTE, 0)
        dados["mudancas"] = contagem.get(TipoDeOcorrencia.MUDANCA, 0)
        return dados

    @api.get("/api/cargas", response_model=list[e.ExecucaoResumo], tags=["conferência"])
    def listar_cargas(
        sessao: Session = Depends(obter_sessao),
        limite: int = Query(default=50, le=200),
    ) -> list[e.ExecucaoResumo]:
        """As rodadas da carga, da mais recente para a mais antiga."""
        execucoes = sessao.scalars(
            sa.select(ExecucaoDeCarga)
            .order_by(ExecucaoDeCarga.executada_em.desc(), ExecucaoDeCarga.id.desc())
            .limit(limite)
        ).all()
        contagens = _contagens(sessao, [x.id for x in execucoes])
        return [
            e.ExecucaoResumo(**_resumo_da_execucao(x, contagens[x.id])) for x in execucoes
        ]

    @api.get("/api/cargas/{carga_id}", response_model=e.ExecucaoDetalhe, tags=["conferência"])
    def ver_carga(carga_id: int, sessao: Session = Depends(obter_sessao)) -> e.ExecucaoDetalhe:
        execucao = sessao.get(ExecucaoDeCarga, carga_id)
        if execucao is None:
            raise HTTPException(404, "carga não encontrada")
        contagem = _contagens(sessao, [carga_id])[carga_id]
        por_campo = sessao.execute(
            sa.select(
                OcorrenciaDeCarga.tipo, OcorrenciaDeCarga.campo, sa.func.count().label("q")
            )
            .where(OcorrenciaDeCarga.execucao_id == carga_id)
            .group_by(OcorrenciaDeCarga.tipo, OcorrenciaDeCarga.campo)
            .order_by(sa.desc("q"))
        ).all()
        return e.ExecucaoDetalhe(
            **_resumo_da_execucao(execucao, contagem),
            por_campo=[
                e.ResumoPorCampo(tipo=tipo, campo=campo, quantas=quantas)
                for tipo, campo, quantas in por_campo
            ],
        )

    @api.get(
        "/api/cargas/{carga_id}/ocorrencias",
        response_model=e.Pagina[e.OcorrenciaResposta],
        tags=["conferência"],
    )
    def listar_ocorrencias(
        carga_id: int,
        sessao: Session = Depends(obter_sessao),
        tipo: TipoDeOcorrencia | None = None,
        campo: str | None = None,
        limite: int = Query(default=200, le=1000),
        salto: int = 0,
    ) -> e.Pagina[e.OcorrenciaResposta]:
        """As linhas do relatório, na ordem da planilha, para ir direto ao lugar."""
        if sessao.get(ExecucaoDeCarga, carga_id) is None:
            raise HTTPException(404, "carga não encontrada")
        consulta = sa.select(OcorrenciaDeCarga).where(
            OcorrenciaDeCarga.execucao_id == carga_id
        )
        if tipo is not None:
            consulta = consulta.where(OcorrenciaDeCarga.tipo == tipo)
        if campo is not None:
            consulta = consulta.where(OcorrenciaDeCarga.campo == campo)
        total = sessao.scalar(sa.select(sa.func.count()).select_from(consulta.subquery()))
        itens = sessao.scalars(
            consulta.order_by(
                OcorrenciaDeCarga.linha.asc().nulls_last(), OcorrenciaDeCarga.id
            )
            .offset(salto)
            .limit(limite)
        ).all()
        return e.Pagina(
            total=total or 0,
            itens=[e.OcorrenciaResposta.model_validate(i) for i in itens],
        )

    # ------------------------------------------------------------------- leads
    @api.get("/api/leads", response_model=e.Pagina[e.LeadResumo], tags=["leads"])
    def listar_leads(
        sessao: Session = Depends(obter_sessao),
        situacao: list[SituacaoLead] | None = Query(default=None),
        apenas_abertos: bool = False,
        busca: str | None = None,
        limite: int = Query(default=100, le=1000),
        salto: int = 0,
    ) -> e.Pagina[e.LeadResumo]:
        consulta = sa.select(Lead)
        if situacao:
            consulta = consulta.where(Lead.situacao.in_(situacao))
        if apenas_abertos:
            consulta = consulta.where(
                Lead.situacao.in_([s for s in SituacaoLead if s.aberto])
            )
        if busca:
            consulta = consulta.where(
                sa.or_(
                    Lead.nome.ilike(f"%{busca}%"), Lead.empresa_texto.ilike(f"%{busca}%")
                )
            )
        total = sessao.scalar(sa.select(sa.func.count()).select_from(consulta.subquery()))
        itens = sessao.scalars(
            consulta.order_by(
                Lead.proxima_acao_em.asc().nulls_last(), Lead.id.desc()
            )
            .offset(salto)
            .limit(limite)
        ).all()
        return e.Pagina(
            total=total or 0, itens=[e.LeadResumo.model_validate(i) for i in itens]
        )

    @api.post("/api/leads", response_model=e.LeadResumo, status_code=201, tags=["leads"])
    def criar_lead(corpo: e.LeadNovo, sessao: Session = Depends(obter_sessao)) -> e.LeadResumo:
        """Cadastra um lead. É a porta de entrada que a planilha nunca teve."""
        lead = Lead(**corpo.model_dump(exclude_unset=True))
        sessao.add(lead)
        sessao.flush()
        return e.LeadResumo.model_validate(lead)

    @api.patch("/api/leads/{lead_id}", response_model=e.LeadResumo, tags=["leads"])
    def editar_lead(
        lead_id: int, corpo: e.LeadEdicao, sessao: Session = Depends(obter_sessao)
    ) -> e.LeadResumo:
        lead = sessao.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(404, "lead não encontrado")

        mudancas = corpo.model_dump(exclude_unset=True)

        # "Convertido" significa que existe uma oportunidade apontada por este
        # lead. Marcá-lo à mão deixaria o estado sem a oportunidade que o
        # sustenta — e a origem, que viaja na conversão, nunca chegaria ao funil.
        if mudancas.get("situacao") is SituacaoLead.CONVERTIDO:
            raise HTTPException(
                422, "para converter um lead, use a conversão em oportunidade"
            )
        # E um lead já convertido tem a situação decidida pela oportunidade.
        if lead.convertido_em_id is not None and "situacao" in mudancas:
            raise HTTPException(409, "este lead já virou oportunidade")

        for campo, valor in mudancas.items():
            setattr(lead, campo, valor)
        sessao.flush()
        return e.LeadResumo.model_validate(lead)

    @api.post(
        "/api/leads/{lead_id}/converter",
        response_model=e.OportunidadeDetalhe,
        status_code=201,
        tags=["leads"],
    )
    def converter_lead(
        lead_id: int, corpo: e.ConversaoDeLead, sessao: Session = Depends(obter_sessao)
    ) -> e.OportunidadeDetalhe:
        """Transforma o lead em oportunidade, carregando a origem consigo.

        A origem viaja de propósito: é ela que responde de onde vêm os negócios
        que fecham, e sem isso o indicador de canal mede só a entrada.
        """
        lead = sessao.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(404, "lead não encontrado")
        if lead.convertido_em_id is not None:
            raise HTTPException(409, "este lead já virou oportunidade")

        if corpo.grupo_id is not None:
            grupo = sessao.get(GrupoEconomico, corpo.grupo_id)
            if grupo is None:
                raise HTTPException(404, "grupo não encontrado")
        else:
            grupo = GrupoEconomico(
                nome=corpo.nome_do_grupo or lead.empresa_texto or lead.nome,
                situacao=SituacaoGrupo.PROSPECT,
                origem=Origem.CRM,
            )
            sessao.add(grupo)
            sessao.flush()

        oportunidade = Oportunidade(
            grupo_id=grupo.id,
            nome=corpo.nome or lead.nome,
            servico=corpo.servico,
            tipo_servico=corpo.tipo_servico,
            situacao=Situacao.ENVIAR_PROPOSTA,
            temperatura=lead.temperatura,
            tipo_canal=lead.tipo_canal,
            canal=lead.canal,
            captador=lead.captador,
            origem=Origem.CRM,
        )
        sessao.add(oportunidade)
        sessao.flush()

        lead.convertido_em_id = oportunidade.id
        lead.situacao = SituacaoLead.CONVERTIDO
        sessao.flush()

        return _detalhe_de(oportunidade, grupo.nome)


app = criar_app()
