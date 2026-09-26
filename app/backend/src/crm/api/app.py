"""A API do Critério CRM.

Serve o funil: grupos, oportunidades, leads e, a partir do início da Etapa 2
(23/09/2026), o contrato que nasce de uma oportunidade aceita. Implantação e
carteira classificada continuam de fora — ainda não passam por aqui.

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
from types import SimpleNamespace
from datetime import date
from typing import Iterator, Literal

import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from crm.api import esquemas as e
from crm.api.backup import roteador as roteador_de_backup
from crm.api.contatos import roteador as roteador_de_contatos
from crm.api.contatos import roteador_de_empresas
from crm.carga.persistencia import CAMPOS as CAMPOS_DA_CARGA
from crm.db.base import agora
from crm.db.grupos import FusaoInvalida, fundir_grupos
from crm.db.modelos import (
    Contrato,
    Empresa,
    EventoDeContrato,
    HistoricoDePreco,
    ExecucaoDeCarga,
    GrupoEconomico,
    Lead,
    OcorrenciaDeCarga,
    Oportunidade,
)
from crm.db.sessao import criar_engine, criar_fabrica_de_sessao, url_do_banco
from crm.domain import indicadores as regras_de_indicadores
from crm.domain.sugestoes_de_fusao import sugerir as sugerir_fusoes
from crm.domain.sugestoes_de_fusao import sugerir_clientes
from crm.domain import agenda as regras_da_agenda
from crm.domain import eventos_de_contrato as regras_de_eventos
from crm.domain import mrr as regras_de_mrr
from crm.domain import recortes as regras_de_recortes
from crm.domain.porte import DIRECIONADORES as DIRECIONADORES_DA_VOLUMETRIA
from crm.domain import porte as regras_de_porte
from crm.domain.listas import (
    ORIGEM_DA_MUDANCA_NO_CRM,
    IniciativaDoEncerramento,
    LinhaServico,
    MotivoDeEncerramento,
    MotivoRecusa,
    Origem,
    PapelContato,
    Situacao,
    SituacaoContrato,
    SituacaoGrupo,
    SituacaoLead,
    Temperatura,
    TipoCanal,
    TipoDeEventoDeContrato,
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
    api.include_router(roteador_de_backup(lambda: _fabrica.kw["bind"]))
    api.include_router(roteador_de_contatos(obter_sessao))
    api.include_router(roteador_de_empresas(obter_sessao))
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


def _resumo_de_contrato(contrato: Contrato, nome_do_grupo: str | None) -> e.ContratoResumo:
    resumo = e.ContratoResumo.model_validate(contrato)
    resumo.grupo_nome = nome_do_grupo
    return resumo


def _detalhe_de_contrato(contrato: Contrato, nome_do_grupo: str | None) -> e.ContratoDetalhe:
    detalhe = e.ContratoDetalhe.model_validate(contrato)
    detalhe.grupo_nome = nome_do_grupo
    return detalhe


def _registrar(api: FastAPI) -> None:
    # ------------------------------------------------------------------ listas
    @api.get("/api/listas", response_model=e.Listas, tags=["referência"])
    def listas(sessao: Session = Depends(obter_sessao)) -> e.Listas:
        """As listas controladas, para a tela montar os seletores.

        `servicos` não é enum do domínio — é texto livre da planilha, então
        vem do banco, não de código. `crm.carga.planilha_2026` já registra os
        oito valores reais nas 155 propostas de 2026.
        """
        servicos = sessao.scalars(
            sa.select(Oportunidade.servico)
            .where(Oportunidade.servico.is_not(None))
            .distinct()
            .order_by(Oportunidade.servico)
        ).all()
        return e.Listas(
            situacoes=_valores(Situacao),
            situacoes_de_lead=_valores(SituacaoLead),
            temperaturas=_valores(Temperatura),
            tipos_de_canal=_valores(TipoCanal),
            tipos_de_canal_em_operacao=[c.value for c in TipoCanal if c.em_operacao],
            motivos_de_recusa=_valores(MotivoRecusa),
            motivos_de_encerramento=_valores(MotivoDeEncerramento),
            iniciativas_de_encerramento=_valores(IniciativaDoEncerramento),
            papeis_de_contato=_valores(PapelContato),
            linhas_de_servico=_valores(LinhaServico),
            situacoes_de_grupo=_valores(SituacaoGrupo),
            captadores=sorted(_CAPTADORES),
            portes=[p.value for p in regras_de_porte.Porte],
            servicos=list(servicos),
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

    @api.get(
        "/api/grupos/sugestoes-de-fusao", response_model=list[e.SugestaoDeFusao], tags=["grupos"]
    )
    def sugestoes_de_fusao(sessao: Session = Depends(obter_sessao)) -> list[e.SugestaoDeFusao]:
        """Blocos de grupos que parecem ser o mesmo cliente. **Não funde nada**:
        quem confirma é uma pessoa, pelo `POST /api/grupos/{id}/fundir`."""
        quantas = (
            sa.select(sa.func.count(Oportunidade.id))
            .where(Oportunidade.grupo_id == GrupoEconomico.id)
            .scalar_subquery()
        )
        linhas = sessao.execute(
            sa.select(GrupoEconomico, quantas).where(GrupoEconomico.fundido_em_id.is_(None))
        ).all()
        resumos: dict[int, e.GrupoResumo] = {}
        for grupo, quantidade in linhas:
            r = e.GrupoResumo.model_validate(grupo)
            r.quantas_oportunidades = quantidade or 0
            resumos[grupo.id] = r
        por_nome = list(sugerir_fusoes(resumos.values()))

        # Prospect que já é cliente: cruza pelo nome das empresas de cada grupo.
        empresas_do_grupo: dict[int, list[str]] = {}
        for gid, razao in sessao.execute(sa.select(Empresa.grupo_id, Empresa.razao_social)):
            empresas_do_grupo.setdefault(gid, []).append(razao)

        def com_empresas(r: e.GrupoResumo) -> SimpleNamespace:
            return SimpleNamespace(id=r.id, nome=r.nome, quantas_oportunidades=r.quantas_oportunidades,
                                   empresas=empresas_do_grupo.get(r.id, []))

        # Alvos: clientes da carteira (têm empresa cadastrada). Candidatos: grupos **sem** empresa,
        # sejam prospects ou clientes não recorrentes (proposta aceita, sem contrato): é onde ficam
        # os nomes digitados pelo comercial ("ASM retomada… - 3AW") que duplicam um cliente da carteira.
        todos = [com_empresas(r) for r in resumos.values()]
        clientes = [g for g, r in zip(todos, resumos.values()) if r.situacao is SituacaoGrupo.CLIENTE and g.empresas]
        prospects = [g for g, r in zip(todos, resumos.values())
                     if not g.empresas and r.situacao in (SituacaoGrupo.PROSPECT, SituacaoGrupo.CLIENTE)]
        ja_juntos = [set(s.ids) for s in por_nome]
        do_cliente = [
            s for s in sugerir_clientes(prospects, clientes)
            if not any(set(s.ids) <= bloco for bloco in ja_juntos)  # já veio numa sugestão por nome
        ]
        return [
            e.SugestaoDeFusao(
                confianca=s.confianca,
                motivo=s.motivo,
                principal_id=s.principal_id,
                grupos=[resumos[i] for i in s.ids],
            )
            for s in [*por_nome, *do_cliente]
        ]

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
        servico: list[str] | None = None,
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
        if servico:
            consulta = consulta.where(Oportunidade.servico.in_(servico))
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
        servico: list[str] | None = Query(default=None),
        limite: int = Query(default=100, le=1000),
        salto: int = 0,
    ) -> e.Pagina[e.OportunidadeResumo]:
        """A visão em lista, com os filtros que o funil precisa."""
        consulta = _consulta_de_oportunidades(
            situacao, captador, tipo_canal, temperatura, grupo_id, busca,
            data_tipo, data_de, data_ate, servico,
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
        servico: list[str] | None = Query(default=None),
    ) -> list[e.ColunaDoFunil]:
        """O kanban: uma coluna por situação, na ordem do funil.

        Devolve **todas** as situações, inclusive as vazias. Coluna que some
        quando zera faz a tela dançar e esconde que o estado existe.
        """
        consulta = _consulta_de_oportunidades(
            None, captador, tipo_canal, temperatura, None, busca,
            data_tipo, data_de, data_ate, servico,
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
        servico: list[str] | None = Query(default=None),
    ) -> e.IndicadoresResposta:
        """Os números do funil, com os mesmos filtros do kanban.

        Só entra o que os dados sustentam sem definição pendente. O que não dá
        para calcular volta com o motivo e o que falta — ver
        `crm.domain.indicadores`.
        """
        consulta = _consulta_de_oportunidades(
            None, captador, tipo_canal, temperatura, None, busca,
            data_tipo, data_de, data_ate, servico,
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
            ciclo_medio=e.CicloMedioDeVendasResposta.model_validate(resultado.ciclo_medio),
            taxa_de_conversao=e.TaxaDeConversaoResposta.model_validate(
                resultado.taxa_de_conversao
            ),
            cobertura=e.CoberturaResposta.model_validate(resultado.cobertura),
            dependencia_de_canal=e.DependenciaDeCanalResposta.model_validate(
                resultado.dependencia_de_canal
            ),
            ticket_recorrente=e.TicketRecorrenteResposta.model_validate(
                resultado.ticket_recorrente
            ),
        )

    def _filtradas(
        sessao: Session,
        captador, tipo_canal, temperatura, busca, data_tipo, data_de, data_ate, servico,
    ) -> list[Oportunidade]:
        consulta = _consulta_de_oportunidades(
            None, captador, tipo_canal, temperatura, None, busca,
            data_tipo, data_de, data_ate, servico,
        )
        return [linha[0] for linha in sessao.execute(consulta).all()]

    @api.get("/api/mrr", response_model=e.MrrResposta, tags=["contratos"])
    def mrr(
        sessao: Session = Depends(obter_sessao),
        de: date | None = None,
        ate: date | None = None,
        hoje: date | None = None,
    ) -> e.MrrResposta:
        """MRR dos contratos registrados no CRM e o que o moveu no período.

        Sem `de`/`ate`, vale o mês corrente até hoje. `hoje` existe para teste.
        **Parcial**: a carteira anterior ao CRM não está aqui (Etapa 3). Ver
        `crm.domain.mrr`.
        """
        dia = hoje or date.today()
        fim = ate or dia
        inicio = de or fim.replace(day=1)
        if fim > dia:
            raise HTTPException(422, "só há MRR até hoje")
        if inicio > fim:
            raise HTTPException(422, "o início do período não pode ser depois do fim")
        contratos = list(sessao.scalars(sa.select(Contrato)))
        da_carteira = sum(1 for c in contratos if c.anterior_ao_crm)
        mov = regras_de_mrr.movimento(contratos, inicio, fim, dia)
        return e.MrrResposta(
            atual=e.MrrAtualResposta.model_validate(regras_de_mrr.mrr_atual(contratos)),
            movimento=e.MovimentoDeMrrResposta(
                de=mov.de, ate=mov.ate, mrr_inicio=mov.mrr_inicio, novo=mov.novo,
                expansao=mov.expansao, reajuste=mov.reajuste, contracao=mov.contracao,
                churn_cliente=mov.churn_cliente, churn_criterio=mov.churn_criterio,
                churn=mov.churn, mrr_fim=mov.mrr_fim, variacao=mov.variacao,
                nrr=mov.nrr, grr=mov.grr,
            ),
            contratos_registrados=len(contratos),
            contratos_da_carteira_anterior=da_carteira,
            cobertura_completa=da_carteira > 0,
            aviso=(
                "Inclui a carteira anterior ao CRM, carregada da planilha de saúde da carteira "
                f"({da_carteira} contratos, sem data de assinatura), mais o que foi registrado depois. "
                "Confira contra o MRR oficial antes de comparar com a meta: a fonte é outra."
                if da_carteira
                else "Só entram os contratos registrados no CRM. A carteira anterior ao CRM ainda "
                "não foi carregada (Etapa 3): este MRR é parcial e não se compara com a meta."
            ),
        )

    @api.get("/api/agenda", response_model=e.AgendaResposta, tags=["follow-up"])
    def agenda(
        sessao: Session = Depends(obter_sessao),
        captador: list[str] | None = Query(default=None),
        hoje: date | None = None,
    ) -> e.AgendaResposta:
        """A fila de follow-up: oportunidades em aberto e leads no funil, por
        urgência. `hoje` existe para teste; sem ele vale a data do servidor."""
        dia = hoje or date.today()
        consulta = _consulta_de_oportunidades(None, captador, None, None, None, None)
        em_aberto = [
            (linha[0], linha[1])
            for linha in sessao.execute(consulta).all()
            if not linha[0].situacao.decidida
        ]
        consulta_de_leads = sa.select(Lead).where(
            Lead.situacao.in_([s for s in SituacaoLead if s.aberto])
        )
        if captador:
            consulta_de_leads = consulta_de_leads.where(Lead.captador.in_(captador))
        leads = list(sessao.scalars(consulta_de_leads))
        # Contrato em vigor com data de fim: o vencimento é a hora de decidir a renovação.
        # Sem `captador`: contrato não tem captador, e o filtro é "só as minhas".
        em_vigor = [] if captador else [
            (c, c.grupo.nome)
            for c in sessao.scalars(
                sa.select(Contrato).where(
                    Contrato.situacao == SituacaoContrato.ATIVO, Contrato.data_fim.is_not(None)
                )
            )
        ]
        itens = regras_da_agenda.montar(oportunidades=em_aberto, leads=leads, hoje=dia, contratos=em_vigor)
        contagens = {b: 0 for b in regras_da_agenda.BALDES}
        for i in itens:
            contagens[i.balde] += 1
        return e.AgendaResposta(
            hoje=dia,
            contagens=contagens,
            itens=[e.ItemDaAgendaResposta.model_validate(i) for i in itens],
        )

    @api.get(
        "/api/indicadores/recortes",
        response_model=list[e.LinhaDeRecorteResposta],
        tags=["funil"],
    )
    def recortes(
        dimensao: Literal["servico", "tipo_canal", "captador"],
        sessao: Session = Depends(obter_sessao),
        captador: list[str] | None = Query(default=None),
        tipo_canal: list[TipoCanal] | None = Query(default=None),
        temperatura: list[Temperatura] | None = Query(default=None),
        busca: str | None = None,
        data_tipo: Literal["colocacao", "aceite"] | None = None,
        data_de: date | None = None,
        data_ate: date | None = None,
        servico: list[str] | None = Query(default=None),
    ) -> list[e.LinhaDeRecorteResposta]:
        """Propostas, conversão e ticket por serviço, canal ou captador, com os
        mesmos filtros do funil."""
        itens = _filtradas(sessao, captador, tipo_canal, temperatura, busca, data_tipo, data_de, data_ate, servico)
        return [e.LinhaDeRecorteResposta.model_validate(l) for l in regras_de_recortes.recortar(itens, dimensao)]

    @api.get(
        "/api/indicadores/cenarios-de-ticket",
        response_model=e.CenariosDeTicketResposta | None,
        tags=["funil"],
    )
    def cenarios_de_ticket(
        sessao: Session = Depends(obter_sessao),
        captador: list[str] | None = Query(default=None),
        tipo_canal: list[TipoCanal] | None = Query(default=None),
        temperatura: list[Temperatura] | None = Query(default=None),
        busca: str | None = None,
        data_tipo: Literal["colocacao", "aceite"] | None = None,
        data_de: date | None = None,
        data_ate: date | None = None,
        servico: list[str] | None = Query(default=None),
    ) -> e.CenariosDeTicketResposta | None:
        """Ticket conservador, base e otimista dos contratos recorrentes, com o
        atípico à parte. `null` quando há menos de 4 contratos: sem base."""
        itens = _filtradas(sessao, captador, tipo_canal, temperatura, busca, data_tipo, data_de, data_ate, servico)
        c = regras_de_recortes.cenarios_de_ticket(itens)
        return e.CenariosDeTicketResposta.model_validate(c) if c else None

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
        # Estes dois não são colunas da oportunidade que se copiam por `setattr`:
        # o motivo vai para a linha do histórico, e a origem tem validação própria.
        motivo_do_preco = mudancas.pop("motivo_do_preco", None)
        origem_da_volumetria = mudancas.pop("origem_da_volumetria", None)
        preco_antes = (oportunidade.preco_mensal, oportunidade.preco_anual)

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
        # Histórico de preço: só quando o valor mudou de fato (a tela manda o
        # rascunho inteiro a cada salvar). Guarda antes e depois; nada é apagado.
        preco_depois = (oportunidade.preco_mensal, oportunidade.preco_anual)
        if preco_depois != preco_antes:
            sessao.add(
                HistoricoDePreco(
                    oportunidade_id=oportunidade.id,
                    origem=ORIGEM_DA_MUDANCA_NO_CRM,
                    motivo=(motivo_do_preco or "").strip() or None,
                    preco_mensal_anterior=preco_antes[0],
                    preco_mensal_novo=preco_depois[0],
                    preco_anual_anterior=preco_antes[1],
                    preco_anual_novo=preco_depois[1],
                )
            )

        # Origem da volumetria: só para direcionador da régua e só para campo
        # preenchido. A origem de um campo que voltou a ficar vazio é descartada.
        campos_validos = {d.campo for d in DIRECIONADORES_DA_VOLUMETRIA}
        if origem_da_volumetria is not None:
            invalidos = sorted(set(origem_da_volumetria) - campos_validos)
            if invalidos:
                raise HTTPException(422, f"origem só vale para direcionadores da volumetria: {', '.join(invalidos)}")
            oportunidade.origem_da_volumetria = {k: v.value for k, v in origem_da_volumetria.items()}
        if origem_da_volumetria is not None or any(c in mudancas for c in campos_validos):
            oportunidade.origem_da_volumetria = {
                k: v
                for k, v in (oportunidade.origem_da_volumetria or {}).items()
                if getattr(oportunidade, k, None) is not None
            }

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

        # Proposta aceita faz do grupo um cliente — recorrente (contrato) ou não (consultoria
        # pontual). Decisão de Eduardo, 26/09/2026.
        if oportunidade.situacao is Situacao.ACEITA and oportunidade.grupo.situacao is SituacaoGrupo.PROSPECT:
            oportunidade.grupo.situacao = SituacaoGrupo.CLIENTE
        sessao.flush()
        return _detalhe_de(oportunidade, oportunidade.grupo.nome)

    @api.post(
        "/api/oportunidades/{oportunidade_id}/converter-em-contrato",
        response_model=e.ContratoDetalhe,
        status_code=201,
        tags=["contratos"],
    )
    def converter_em_contrato(
        oportunidade_id: int,
        corpo: e.ConversaoEmContrato,
        sessao: Session = Depends(obter_sessao),
    ) -> e.ContratoDetalhe:
        """Fecha o ciclo: a oportunidade aceita vira contrato — começo da
        Etapa 2 (23/09/2026). Só o registro; sem Clicksign, sem renovação
        automática (decisão de Eduardo — ver `crm.db.modelos.Contrato`).
        """
        oportunidade = sessao.get(Oportunidade, oportunidade_id)
        if oportunidade is None:
            raise HTTPException(404, "oportunidade não encontrada")
        if oportunidade.situacao is not Situacao.ACEITA:
            raise HTTPException(422, "só uma oportunidade aceita vira contrato")

        contrato_existente = sessao.scalar(
            sa.select(Contrato).where(Contrato.oportunidade_id == oportunidade_id)
        )
        if contrato_existente is not None:
            raise HTTPException(409, "esta oportunidade já tem contrato")

        contrato = Contrato(
            grupo_id=oportunidade.grupo_id,
            oportunidade_id=oportunidade.id,
            escopo=corpo.escopo or oportunidade.servico,
            preco_mensal=corpo.preco_mensal or oportunidade.preco_mensal,
            preco_anual=corpo.preco_anual or oportunidade.preco_anual,
            # A vigência começa na assinatura (decisão de 25/09/2026): o contrato
            # nasce sem data de início; quem assina é que a preenche.
            data_inicio=corpo.data_inicio,
            signatario=corpo.signatario,
            situacao=SituacaoContrato.AGUARDANDO_ASSINATURA,
        )
        sessao.add(contrato)
        sessao.flush()

        return _detalhe_de_contrato(contrato, oportunidade.grupo.nome)

    @api.get("/api/contratos", response_model=e.Pagina[e.ContratoResumo], tags=["contratos"])
    def listar_contratos(
        sessao: Session = Depends(obter_sessao),
        situacao: list[SituacaoContrato] | None = Query(default=None),
        grupo_id: int | None = None,
        limite: int = Query(default=100, le=1000),
        salto: int = 0,
    ) -> e.Pagina[e.ContratoResumo]:
        consulta = sa.select(Contrato, GrupoEconomico.nome).join(
            GrupoEconomico, Contrato.grupo_id == GrupoEconomico.id
        )
        if situacao:
            consulta = consulta.where(Contrato.situacao.in_(situacao))
        if grupo_id is not None:
            consulta = consulta.where(Contrato.grupo_id == grupo_id)

        total = sessao.scalar(sa.select(sa.func.count()).select_from(consulta.subquery()))
        linhas = sessao.execute(
            consulta.order_by(Contrato.data_inicio.desc().nulls_last(), Contrato.id.desc())
            .offset(salto)
            .limit(limite)
        ).all()
        return e.Pagina(
            total=total or 0,
            itens=[_resumo_de_contrato(c, nome) for c, nome in linhas],
        )

    @api.get(
        "/api/contratos/{contrato_id}", response_model=e.ContratoDetalhe, tags=["contratos"]
    )
    def ver_contrato(
        contrato_id: int, sessao: Session = Depends(obter_sessao)
    ) -> e.ContratoDetalhe:
        contrato = sessao.get(Contrato, contrato_id)
        if contrato is None:
            raise HTTPException(404, "contrato não encontrado")
        return _detalhe_de_contrato(contrato, contrato.grupo.nome)

    @api.patch(
        "/api/contratos/{contrato_id}", response_model=e.ContratoDetalhe, tags=["contratos"]
    )
    def editar_contrato(
        contrato_id: int,
        corpo: e.ContratoEdicao,
        sessao: Session = Depends(obter_sessao),
    ) -> e.ContratoDetalhe:
        contrato = sessao.get(Contrato, contrato_id)
        if contrato is None:
            raise HTTPException(404, "contrato não encontrado")

        mudancas = corpo.model_dump(exclude_unset=True)

        # Depois de assinado, preço, fim e encerramento só mudam por evento: é o
        # que deixa o antes e o depois registrados. A tela manda o rascunho inteiro,
        # então só conta como mudança o que de fato difere do valor atual.
        assinado = contrato.situacao in (SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO)
        if assinado:
            for campo, evento in (("preco_mensal", "Reajuste, Expansão ou Contração"),
                                  ("preco_anual", "Reajuste, Expansão ou Contração")):
                if campo in mudancas and mudancas[campo] != getattr(contrato, campo):
                    raise HTTPException(422, f"contrato assinado: para mudar o preço, registre um evento ({evento})")
            if "data_fim" in mudancas and contrato.data_fim is not None and mudancas["data_fim"] != contrato.data_fim:
                raise HTTPException(422, "contrato assinado: para mudar a data de fim, registre uma Renovação")
        if mudancas.get("situacao") is SituacaoContrato.ENCERRADO and contrato.situacao is not SituacaoContrato.ENCERRADO:
            raise HTTPException(422, "para encerrar, registre um evento de Encerramento com o motivo")

        for campo, valor in mudancas.items():
            setattr(contrato, campo, valor)
        # A vigência começa na assinatura: sem a data, o contrato não vira Ativo.
        # (Contrato da carteira anterior ao CRM não tem a data e não precisa dela.)
        if (
            "situacao" in mudancas
            and contrato.situacao is SituacaoContrato.ATIVO
            and contrato.data_inicio is None
            and not contrato.anterior_ao_crm
        ):
            raise HTTPException(422, "para ativar o contrato, informe a data da assinatura (início da vigência)")
        sessao.flush()
        return _detalhe_de_contrato(contrato, contrato.grupo.nome)

    @api.post(
        "/api/contratos/{contrato_id}/eventos",
        response_model=e.ContratoDetalhe,
        status_code=201,
        tags=["contratos"],
    )
    def registrar_evento_de_contrato(
        contrato_id: int,
        corpo: e.EventoDeContratoNovo,
        sessao: Session = Depends(obter_sessao),
    ) -> e.ContratoDetalhe:
        """Registra um aditivo, reajuste, expansão, contração, renovação ou
        encerramento. Valida, grava o evento com o antes e o depois e aplica o
        efeito no contrato — tudo na mesma transação. Não há rota para editar
        nem apagar um evento: errou, registra outro."""
        contrato = sessao.get(Contrato, contrato_id)
        if contrato is None:
            raise HTTPException(404, "contrato não encontrado")
        pedido = regras_de_eventos.Pedido(
            tipo=corpo.tipo,
            data_do_evento=corpo.data_do_evento or date.today(),
            descricao=(corpo.descricao or "").strip() or None,
            motivo_categoria=corpo.motivo_categoria,
            iniciativa=corpo.iniciativa,
            escopo_novo=corpo.escopo_novo,
            preco_mensal_novo=corpo.preco_mensal_novo,
            preco_anual_novo=corpo.preco_anual_novo,
            data_fim_nova=corpo.data_fim_nova,
        )
        if (corpo.motivo_categoria is not None or corpo.iniciativa is not None) and corpo.tipo is not TipoDeEventoDeContrato.ENCERRAMENTO:
            raise HTTPException(422, "a categoria do motivo e a iniciativa só valem no Encerramento")
        try:
            efeito = regras_de_eventos.efeito_do_evento(contrato, pedido)
        except regras_de_eventos.ErroDeEvento as erro:
            raise HTTPException(erro.status, str(erro)) from erro

        sessao.add(
            EventoDeContrato(
                contrato_id=contrato.id,
                tipo=pedido.tipo,
                data_do_evento=pedido.data_do_evento,
                descricao=pedido.descricao,
                motivo_categoria=pedido.motivo_categoria,
                iniciativa=pedido.iniciativa,
                preco_mensal_anterior=contrato.preco_mensal,
                preco_mensal_novo=efeito.get("preco_mensal"),
                preco_anual_anterior=contrato.preco_anual,
                preco_anual_novo=efeito.get("preco_anual"),
                escopo_anterior=contrato.escopo,
                escopo_novo=efeito.get("escopo"),
                data_fim_anterior=contrato.data_fim,
                data_fim_nova=efeito.get("data_fim") if pedido.tipo is not TipoDeEventoDeContrato.ENCERRAMENTO else pedido.data_do_evento,
            )
        )
        for campo, valor in efeito.items():
            setattr(contrato, campo, valor)
        sessao.flush()
        sessao.refresh(contrato)
        return _detalhe_de_contrato(contrato, contrato.grupo.nome)

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
