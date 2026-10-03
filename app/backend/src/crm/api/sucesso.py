"""Funil do Sucesso do Cliente (aprovado por Eduardo em 02/10/2026): a etapa de cada grupo cliente,
o checklist da implantação e as reuniões de resultado com cadência pela classe. Regras em
`crm.domain.sucesso`."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from crm.agente.ata import MODELO_PADRAO as MODELO_DA_ATA, ClienteDaApi, escrever_ata
from crm.agente.config import ler_configuracao
from crm.agente.erros import mensagem_de_falha
from crm.agente.sdr import AgenteFalhou, Uso
from crm.api.acesso import quem_fez
from crm.api.ajustes import AjusteResposta, resposta_do_ajuste, responsaveis_possiveis
from crm.api.classificacao import parametros_vigentes
from crm.db.base import agora
from crm.db.modelos import (
    AjusteTecnico, CadenciaDeReuniao, ClassificacaoDoGrupo, Contrato, Empresa, GrupoEconomico, JornadaDoCliente,
    Oportunidade, OportunidadeDaReuniao, ReuniaoDaCarteira, ReuniaoDeResultado,
)
from crm.domain import mrr as regras_de_mrr
from crm.domain import sucesso as regra
from crm.domain.listas import _CAPTADORES  # noqa: PLC2701 — única fonte da lista
from crm.domain.listas import LinhaServico, Origem, Situacao, SituacaoContrato, TipoCanal
from crm.domain.servicos import (
    CATALOGO, OUTRO, linha_do_servico, problema_na_descricao, problema_no_tema, servico_do_catalogo,
)

__all__ = ["ServicosDaAta", "roteador_do_sucesso", "servicos_da_ata_reais"]

_VALENDO = (SituacaoContrato.AGUARDANDO_ASSINATURA, SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO)
_CLASSES = ("A", "B", "C")
_ABERTAS = (Situacao.ENVIAR_PROPOSTA, Situacao.EM_AVALIACAO, Situacao.ON_HOLD)
"""Venda aberta: ainda não decidida (aceita, recusada ou perdida)."""


class EtapaResposta(BaseModel):
    chave: str
    nome: str
    participantes: str | None


class ItemResposta(BaseModel):
    chave: str
    rotulo: str


class TipoResposta(BaseModel):
    chave: str
    nome: str
    meses: int
    participantes: str
    pauta: list[str]


class DevidaResposta(BaseModel):
    tipo: str
    ultima: date | None
    proxima: date | None
    atrasada: bool
    dias_de_atraso: int | None


class GrupoNoFunil(BaseModel):
    grupo_id: int
    nome: str
    etapa: str
    classe: str | None
    itens_feitos: list[str]
    etapa_desde: date | None
    """Vazia para o cliente anterior ao CRM, que já entra em curso."""
    em_curso_desde: date | None
    """Do fim do kickoff; para o cliente anterior ao CRM, o início do funil (02/10/2026)."""
    situacao: str | None
    """Só em curso: "em_dia", "atrasada" (alguma reunião vencida ou nunca registrada) ou "sem_classe"
    (sem leitura do Score, não há cadência para cobrar)."""
    reunioes: list[DevidaResposta]
    ajustes_pendentes: int = 0
    ajustes_atrasados: int = 0
    """Pendentes com prazo vencido."""
    ajustes_feitos: int = 0
    mrr_bruto: Decimal = Decimal("0")
    """Soma dos contratos ativos, em bruto (o líquido com o imposto dos Parâmetros), como o MRR."""
    vendas_abertas: int = 0
    """Oportunidades abertas no Funil comercial a partir das reuniões e ainda não decididas."""
    vendas_por_mes: Decimal = Decimal("0")
    """Das abertas, as recorrentes: valor por mês."""
    vendas_em_projeto: Decimal = Decimal("0")
    """Das abertas, as de projeto: valor total. Não se soma com o mensal."""


class CarteiraResposta(BaseModel):
    """A bimestral interna da carteira (Head do BPO e CEO)."""

    nome: str
    participantes: str
    pauta: list[str]
    ultima: date | None
    proxima: date
    atrasada: bool
    dias_de_atraso: int | None


class FunilDoSucesso(BaseModel):
    etapas: list[EtapaResposta]
    checklist: dict[str, list[ItemResposta]]
    tipos: list[TipoResposta]
    tipos_antigos: dict[str, str]
    """Nome dos tipos que só aparecem no histórico (bimestral e anual, antes de 03/10/2026)."""
    cadencia: dict[str, list[str]]
    intencao: dict[str, str]
    carteira: CarteiraResposta
    grupos: list[GrupoNoFunil]


class ReuniaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    data: date
    participantes: str | None
    pauta: str | None
    dashboard: str | None
    resumo: str | None
    decisoes: str | None
    pendencias_do_cliente: str | None
    pontos_sensiveis: str | None
    proximos_passos: str | None
    estrategia_e_desafios: str | None = None
    tem_transcricao: bool
    registrada_por: str | None
    criado_em: datetime
    ajustes: list[AjusteResposta]
    oportunidades: list["OportunidadeDaReuniaoResposta"] = []


class OportunidadeDaReuniaoResposta(BaseModel):
    id: int
    lacuna: str
    servico: str
    servico_tema: str | None
    valor: Decimal | None
    recorrente: bool
    oportunidade_id: int | None
    """A oportunidade no Funil comercial; vazia quando ficou só anotada."""
    situacao: str | None
    """A situação dela no Funil comercial, agora."""


ReuniaoResposta.model_rebuild()


class NovoAjuste(BaseModel):
    descricao: str = Field(min_length=3)
    responsavel_email: str = Field(min_length=3, max_length=200)
    prazo: date | None = None


class NovaOportunidade(BaseModel):
    lacuna: str = Field(min_length=3)
    servico: str = Field(min_length=2, max_length=120)
    servico_tema: str | None = Field(default=None, max_length=80)
    valor: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    abrir_no_funil: bool = False


class NovaReuniao(BaseModel):
    tipo: str
    data: date
    participantes: str | None = Field(default=None, max_length=300)
    pauta: str | None = None
    dashboard: str | None = Field(default=None, max_length=400)
    resumo: str | None = None
    decisoes: str | None = None
    pendencias_do_cliente: str | None = None
    pontos_sensiveis: str | None = None
    proximos_passos: str | None = None
    transcricao: str | None = None
    estrategia_e_desafios: str | None = None
    ajustes: list[NovoAjuste] = []
    oportunidades: list[NovaOportunidade] = []


class PedidoDeAta(BaseModel):
    tipo: str
    data: date
    participantes: str | None = Field(default=None, max_length=300)
    transcricao: str = Field(min_length=50, max_length=400_000)


class AjusteSugerido(BaseModel):
    descricao: str
    prazo: date | None
    responsavel_citado: str | None = None
    """O nome como a ata citou."""
    responsavel_email: str | None = None
    """Quem é, entre os que recebem ajustes; vazio se ninguém foi citado ou se não deu para saber quem."""
    trecho: str | None = None


class OportunidadeSugerida(BaseModel):
    lacuna: str
    servico: str | None
    """Do catálogo; vazio se a IA citou um serviço que não existe (a pessoa escolhe)."""
    servico_tema: str | None
    valor: Decimal | None
    recorrente: bool
    trecho: str | None


class RascunhoDaAtaResposta(BaseModel):
    resumo: str
    decisoes_do_cliente: list[str]
    ajustes: list[AjusteSugerido]
    pendencias_do_cliente: list[str]
    pontos_sensiveis: list[str]
    estrategia_e_desafios: str = ""
    oportunidades: list[OportunidadeSugerida] = []
    custo_usd: str | None


@dataclass(frozen=True)
class ServicosDaAta:
    """O que a ata usa de fora do banco: o teste troca por um cliente falso, sem chave nem rede."""

    cliente: Callable[[], ClienteDaApi]
    modelo: str = MODELO_DA_ATA


def servicos_da_ata_reais() -> ServicosDaAta:
    """A chave lida do `.env` a cada uso, como a análise da carteira."""
    config = ler_configuracao()

    def cliente() -> ClienteDaApi:
        if not config.chave:
            raise AgenteFalhou(
                "A chave da API da Anthropic não está no .env (ANTHROPIC_API_KEY). "
                "Coloque a chave e tente de novo; nada foi gerado."
            )
        import anthropic

        return anthropic.Anthropic(api_key=config.chave)

    return ServicosDaAta(cliente=cliente)


class MarcarItem(BaseModel):
    item: str
    feito: bool


class CadenciaResposta(BaseModel):
    cadencia: dict[str, list[str]]
    intencao: dict[str, str]
    alterado_por: str | None = None
    alterado_em: datetime | None = None


class CadenciaEdicao(BaseModel):
    cadencia: dict[str, list[str]] = {}
    intencao: dict[str, str] = {}
    """Texto vazio volta ao padrão."""


class NovaReuniaoDaCarteira(BaseModel):
    data: date
    participantes: str | None = Field(default=None, max_length=300)
    resumo: str | None = None
    correcoes_de_rota: str | None = None


class ReuniaoDaCarteiraResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data: date
    participantes: str | None
    resumo: str | None
    correcoes_de_rota: str | None
    registrada_por: str | None


class CarteiraComReunioes(BaseModel):
    devida: CarteiraResposta
    reunioes: list[ReuniaoDaCarteiraResposta]


def _texto(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def cadencia_vigente(sessao: Session) -> dict[str, list[str]]:
    """Só tipos que se registram hoje: um tipo antigo gravado (bimestral, anual) não é cobrado."""
    validos = {t.chave for t in regra.TIPOS_DE_REUNIAO}
    gravadas = {c.classe: [t for t in c.tipos if t in validos] for c in sessao.scalars(sa.select(CadenciaDeReuniao))}
    return {cl: gravadas.get(cl) or list(regra.CADENCIA_PADRAO[cl]) for cl in _CLASSES}


def intencao_vigente(sessao: Session) -> dict[str, str]:
    gravadas = {c.classe: c.intencao for c in sessao.scalars(sa.select(CadenciaDeReuniao)) if c.intencao}
    return {cl: gravadas.get(cl) or regra.INTENCAO_PADRAO[cl] for cl in _CLASSES}


def _carteira(sessao: Session, hoje: date) -> CarteiraResposta:
    ultima = sessao.scalar(sa.select(sa.func.max(ReuniaoDaCarteira.data)))
    d = regra.devida_da_carteira(ultima, hoje)
    t = regra.REUNIAO_DA_CARTEIRA
    return CarteiraResposta(nome=t.nome, participantes=t.participantes, pauta=list(t.pauta), ultima=d.ultima,
                            proxima=d.proxima, atrasada=d.atrasada, dias_de_atraso=d.dias_de_atraso)


def _captador(nome: str | None) -> str | None:
    """A sigla de captador de quem registrou, pelas iniciais do primeiro e do último nome ("Eduardo
    Luiz" → EL), se for uma das siglas conhecidas; senão fica vazio, para escolher no Funil comercial."""
    partes = (nome or "").split()
    if len(partes) < 2:
        return None
    sigla = (partes[0][0] + partes[-1][0]).upper()
    return sigla if sigla in _CAPTADORES else None


def _valor_da_venda(o: Oportunidade) -> Decimal:
    return (o.preco_mensal if o.linha_servico is LinhaServico.C1 else o.preco_anual) or Decimal("0")


def _resposta_da_reuniao(reuniao: ReuniaoDeResultado) -> ReuniaoResposta:
    return ReuniaoResposta(
        id=reuniao.id, tipo=reuniao.tipo, data=reuniao.data, participantes=reuniao.participantes,
        pauta=reuniao.pauta, dashboard=reuniao.dashboard, resumo=reuniao.resumo, decisoes=reuniao.decisoes,
        pendencias_do_cliente=reuniao.pendencias_do_cliente, pontos_sensiveis=reuniao.pontos_sensiveis,
        proximos_passos=reuniao.proximos_passos, estrategia_e_desafios=reuniao.estrategia_e_desafios,
        tem_transcricao=bool(reuniao.transcricao),
        registrada_por=reuniao.registrada_por, criado_em=reuniao.criado_em,
        ajustes=[resposta_do_ajuste(a) for a in reuniao.ajustes],
        oportunidades=[OportunidadeDaReuniaoResposta(
            id=o.id, lacuna=o.lacuna, servico=o.servico, servico_tema=o.servico_tema, valor=o.valor,
            recorrente=o.recorrente, oportunidade_id=o.oportunidade_id,
            situacao=o.oportunidade.situacao.value if o.oportunidade else None,
        ) for o in reuniao.oportunidades],
    )


def _servicos_para_a_ia() -> list[str]:
    nomes = []
    for sv in CATALOGO:
        nomes.append(f"{sv.nome} (temas: {', '.join(t.nome for t in sv.temas)})" if sv.temas else sv.nome)
    return [*nomes, OUTRO]


def _sugerida(o: dict) -> OportunidadeSugerida:
    """O serviço só fica se for do catálogo (ou "Outro"); o tema, só se for dele."""
    do_catalogo = servico_do_catalogo(o.get("servico"))
    nome = do_catalogo.nome if do_catalogo else (OUTRO if (o.get("servico") or "").strip() == OUTRO else None)
    tema = o.get("tema") if do_catalogo and o.get("tema") in [t.nome for t in do_catalogo.temas] else None
    return OportunidadeSugerida(
        lacuna=o["lacuna"], servico=nome, servico_tema=tema, valor=Decimal(o["valor"]) if o.get("valor") else None,
        recorrente=linha_do_servico(nome) is LinhaServico.C1, trecho=o.get("trecho"),
    )


def roteador_do_sucesso(
    obter_sessao: Callable[[], Iterator[Session]],
    servicos_da_ata: Callable[[], ServicosDaAta] = servicos_da_ata_reais,
) -> APIRouter:
    r = APIRouter(prefix="/api/sucesso", tags=["sucesso"])

    def _grupos(sessao: Session, so: int | None = None) -> list[tuple[GrupoEconomico, bool]]:
        """Grupos não fundidos com contrato valendo, e se algum deles é anterior ao CRM."""
        consulta = (
            sa.select(GrupoEconomico, sa.func.max(sa.cast(Contrato.anterior_ao_crm, sa.Integer)))
            .join(Contrato, Contrato.grupo_id == GrupoEconomico.id)
            .where(GrupoEconomico.fundido_em_id.is_(None), Contrato.situacao.in_(_VALENDO))
            .group_by(GrupoEconomico.id)
            .order_by(GrupoEconomico.nome)
        )
        if so is not None:
            consulta = consulta.where(GrupoEconomico.id == so)
        return [(g, bool(anterior)) for g, anterior in sessao.execute(consulta)]

    def _classes(sessao: Session) -> dict[int, str]:
        """A classe da leitura mais recente de cada grupo (referência maior, depois revisão maior)."""
        classes: dict[int, str] = {}
        for grupo_id, classe in sessao.execute(
            sa.select(ClassificacaoDoGrupo.grupo_id, ClassificacaoDoGrupo.classe)
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc())
        ):
            classes.setdefault(grupo_id, classe)
        return classes

    def _ultimas(sessao: Session) -> dict[int, dict[str, date]]:
        ultimas: dict[int, dict[str, date]] = {}
        for grupo_id, tipo, dia in sessao.execute(
            sa.select(ReuniaoDeResultado.grupo_id, ReuniaoDeResultado.tipo, sa.func.max(ReuniaoDeResultado.data))
            .group_by(ReuniaoDeResultado.grupo_id, ReuniaoDeResultado.tipo)
        ):
            ultimas.setdefault(grupo_id, {})[tipo] = dia
        return ultimas

    def _ajustes(sessao: Session, hoje: date) -> dict[int, tuple[int, int, int]]:
        """Grupo → (pendentes, pendentes com prazo vencido, feitos)."""
        contagem: dict[int, list[int]] = {}
        for grupo_id, prazo, feito_em in sessao.execute(
            sa.select(AjusteTecnico.grupo_id, AjusteTecnico.prazo, AjusteTecnico.feito_em)
        ):
            c = contagem.setdefault(grupo_id, [0, 0, 0])
            if feito_em is not None:
                c[2] += 1
            else:
                c[0] += 1
                c[1] += prazo is not None and prazo < hoje
        return {g: (p, a, f) for g, (p, a, f) in contagem.items()}

    def _mrr(sessao: Session, so: int | None = None) -> dict[int, Decimal]:
        """Grupo → MRR bruto (contratos ativos), como a Receita soma."""
        consulta = sa.select(Contrato).where(Contrato.situacao == SituacaoContrato.ATIVO)
        if so is not None:
            consulta = consulta.where(Contrato.grupo_id == so)
        imposto = parametros_vigentes(sessao)[1].imposto
        soma: dict[int, Decimal] = {}
        for c in regras_de_mrr.em_bruto(sessao.scalars(consulta), imposto):
            if c.preco_mensal and c.preco_mensal > 0:
                soma[c.grupo_id] = soma.get(c.grupo_id, Decimal("0")) + c.preco_mensal
        return soma

    def _vendas(sessao: Session) -> dict[int, tuple[int, Decimal, Decimal]]:
        """Grupo → (abertas, por mês, em projeto), das oportunidades nascidas nas reuniões."""
        vendas: dict[int, list] = {}
        for o in sessao.scalars(
            sa.select(Oportunidade).join(OportunidadeDaReuniao, OportunidadeDaReuniao.oportunidade_id == Oportunidade.id)
            .where(Oportunidade.situacao.in_(_ABERTAS)).distinct()
        ):
            v = vendas.setdefault(o.grupo_id, [0, Decimal("0"), Decimal("0")])
            v[0] += 1
            v[1 if o.linha_servico is LinhaServico.C1 else 2] += _valor_da_venda(o)
        return {g: (n, m, p) for g, (n, m, p) in vendas.items()}

    def _no_funil(
        g: GrupoEconomico, anterior: bool, jornada: JornadaDoCliente | None, classe: str | None,
        ultimas: dict[str, date], cadencia: dict[str, list[str]], hoje: date,
        ajustes: tuple[int, int, int] = (0, 0, 0), mrr: Decimal = Decimal("0"),
        vendas: tuple[int, Decimal, Decimal] = (0, Decimal("0"), Decimal("0")),
    ) -> GrupoNoFunil:
        etapa = jornada.etapa if jornada else ("em_curso" if anterior else "contrato")
        # Quem entrou em curso pelo kickoff conta dali; o cliente anterior ao CRM, do início do funil.
        em_curso_desde = (jornada.em_curso_desde if jornada else None) or (
            regra.INICIO_DO_FUNIL if etapa == "em_curso" else None)
        devidas: list[regra.ReuniaoDevida] = []
        situacao = None
        if etapa == "em_curso":
            if classe is None:
                situacao = "sem_classe"
            else:
                devidas = regra.devidas(cadencia.get(classe, []), ultimas, em_curso_desde, hoje)
                situacao = "atrasada" if any(d.atrasada for d in devidas) else "em_dia"
        return GrupoNoFunil(
            grupo_id=g.id, nome=g.nome, etapa=etapa, classe=classe,
            itens_feitos=list(jornada.itens_feitos) if jornada else [],
            etapa_desde=jornada.etapa_desde if jornada else None, em_curso_desde=em_curso_desde,
            situacao=situacao, reunioes=[DevidaResposta(**d.__dict__) for d in devidas],
            ajustes_pendentes=ajustes[0], ajustes_atrasados=ajustes[1], ajustes_feitos=ajustes[2],
            mrr_bruto=mrr, vendas_abertas=vendas[0], vendas_por_mes=vendas[1], vendas_em_projeto=vendas[2],
        )

    def _um(sessao: Session, grupo_id: int, hoje: date) -> GrupoNoFunil:
        achados = _grupos(sessao, grupo_id)
        if not achados:
            raise HTTPException(404, "Grupo sem contrato valendo: não está no Funil do Sucesso do Cliente")
        g, anterior = achados[0]
        return _no_funil(
            g, anterior, sessao.get(JornadaDoCliente, grupo_id), _classes(sessao).get(grupo_id),
            _ultimas(sessao).get(grupo_id, {}), cadencia_vigente(sessao), hoje,
            _ajustes(sessao, hoje).get(grupo_id, (0, 0, 0)), _mrr(sessao, grupo_id).get(grupo_id, Decimal("0")),
            _vendas(sessao).get(grupo_id, (0, Decimal("0"), Decimal("0"))),
        )

    def _jornada(sessao: Session, grupo_id: int, hoje: date) -> tuple[JornadaDoCliente, GrupoNoFunil]:
        """A linha da jornada, criada na primeira marcação com a etapa que o grupo já mostrava."""
        atual = _um(sessao, grupo_id, hoje)
        jornada = sessao.get(JornadaDoCliente, grupo_id)
        if jornada is None:
            jornada = JornadaDoCliente(grupo_id=grupo_id, etapa=atual.etapa, itens_feitos=[], etapa_desde=hoje)
            sessao.add(jornada)
        return jornada, atual

    @r.get("/funil", response_model=FunilDoSucesso)
    def funil(hoje: date | None = None, sessao: Session = Depends(obter_sessao)) -> FunilDoSucesso:
        """`hoje` existe para teste; sem ele vale a data do servidor."""
        dia = hoje or date.today()
        jornadas = {j.grupo_id: j for j in sessao.scalars(sa.select(JornadaDoCliente))}
        classes, ultimas, cadencia = _classes(sessao), _ultimas(sessao), cadencia_vigente(sessao)
        ajustes, mrr, vendas = _ajustes(sessao, dia), _mrr(sessao), _vendas(sessao)
        return FunilDoSucesso(
            etapas=[EtapaResposta(chave=c, nome=n, participantes=p) for c, n, p in regra.ETAPAS],
            checklist={e: [ItemResposta(chave=c, rotulo=r_) for c, r_ in itens] for e, itens in regra.CHECKLIST.items()},
            tipos=[TipoResposta(chave=t.chave, nome=t.nome, meses=t.meses, participantes=t.participantes, pauta=list(t.pauta))
                   for t in regra.TIPOS_DE_REUNIAO],
            tipos_antigos=dict(regra.TIPOS_ANTIGOS),
            cadencia=cadencia,
            intencao=intencao_vigente(sessao),
            carteira=_carteira(sessao, dia),
            grupos=[_no_funil(g, anterior, jornadas.get(g.id), classes.get(g.id), ultimas.get(g.id, {}), cadencia, dia,
                              ajustes.get(g.id, (0, 0, 0)), mrr.get(g.id, Decimal("0")),
                              vendas.get(g.id, (0, Decimal("0"), Decimal("0"))))
                    for g, anterior in _grupos(sessao)],
        )

    @r.patch("/grupos/{grupo_id}/itens", response_model=GrupoNoFunil)
    def marcar(grupo_id: int, corpo: MarcarItem, sessao: Session = Depends(obter_sessao)) -> GrupoNoFunil:
        """Marca ou desmarca um item do checklist da etapa em que o grupo está."""
        hoje = date.today()
        jornada, atual = _jornada(sessao, grupo_id, hoje)
        da_etapa = {c for c, _ in regra.CHECKLIST.get(atual.etapa, ())}
        if corpo.item not in da_etapa:
            raise HTTPException(422, "Este item não é da etapa em que o grupo está")
        feitos = [i for i in jornada.itens_feitos if i != corpo.item]
        if corpo.feito:
            feitos.append(corpo.item)
        jornada.itens_feitos = feitos
        jornada.alterado_por = quem_fez("") or None
        sessao.flush()
        return _um(sessao, grupo_id, hoje)

    @r.post("/grupos/{grupo_id}/concluir-etapa", response_model=GrupoNoFunil)
    def concluir(grupo_id: int, sessao: Session = Depends(obter_sessao)) -> GrupoNoFunil:
        """Passa o grupo para a etapa seguinte, com o checklist da atual completo. Ao concluir o kickoff,
        o grupo entra em curso e as reuniões de resultado começam a contar a partir de hoje."""
        hoje = date.today()
        jornada, atual = _jornada(sessao, grupo_id, hoje)
        seguinte = regra.proxima_etapa(atual.etapa)
        if seguinte is None:
            raise HTTPException(422, "O grupo já está em curso: não há etapa seguinte")
        faltam = [rotulo for c, rotulo in regra.CHECKLIST.get(atual.etapa, ()) if c not in jornada.itens_feitos]
        if faltam:
            raise HTTPException(422, f"Faltam {len(faltam)} itens do checklist: {'; '.join(faltam)}")
        jornada.etapa, jornada.etapa_desde = seguinte, hoje
        if seguinte == "em_curso":
            jornada.em_curso_desde = hoje
        jornada.alterado_por = quem_fez("") or None
        sessao.flush()
        return _um(sessao, grupo_id, hoje)

    @r.get("/grupos/{grupo_id}/reunioes", response_model=list[ReuniaoResposta])
    def reunioes(grupo_id: int, sessao: Session = Depends(obter_sessao)) -> list[ReuniaoResposta]:
        """Da mais recente para a mais antiga, com os ajustes de cada uma. A transcrição não vem: só se
        ela existe (é longa, e quem consulta quer a ata)."""
        return [_resposta_da_reuniao(x) for x in sessao.scalars(
            sa.select(ReuniaoDeResultado).where(ReuniaoDeResultado.grupo_id == grupo_id)
            .order_by(ReuniaoDeResultado.data.desc(), ReuniaoDeResultado.id.desc())
        )]

    @r.post("/grupos/{grupo_id}/ata", response_model=RascunhoDaAtaResposta)
    def montar_ata(grupo_id: int, corpo: PedidoDeAta, sessao: Session = Depends(obter_sessao)) -> RascunhoDaAtaResposta:
        """Rascunho da ata pela IA a partir da transcrição do Granola. **Não grava nada**: a tela mostra
        para o gestor revisar, escolher os responsáveis e registrar a reunião."""
        tipo = regra.tipo(corpo.tipo)
        if tipo is None:
            raise HTTPException(422, "Tipo de reunião desconhecido")
        grupo = _um(sessao, grupo_id, date.today())
        pessoas = [(u.email, u.nome) for u in responsaveis_possiveis(sessao)]
        servicos = servicos_da_ata()
        uso = Uso(modelo=servicos.modelo)
        try:
            rascunho = escrever_ata(
                servicos.cliente(), servicos.modelo, cliente=grupo.nome, tipo=tipo.nome,
                data=corpo.data.strftime("%d/%m/%Y"), participantes=_texto(corpo.participantes),
                transcricao=corpo.transcricao.strip(), uso=uso,
                responsaveis=[n or e for e, n in pessoas], servicos=_servicos_para_a_ia(),
            )
        except Exception as falha:  # noqa: BLE001 — a mensagem é para a pessoa, sem dado do cliente
            raise HTTPException(502, mensagem_de_falha(falha)) from falha
        return RascunhoDaAtaResposta(
            resumo=rascunho.resumo, decisoes_do_cliente=rascunho.decisoes_do_cliente,
            ajustes=[AjusteSugerido(
                descricao=a["descricao"], prazo=a["prazo"], responsavel_citado=a.get("responsavel"),
                responsavel_email=regra.achar_responsavel(a.get("responsavel"), pessoas), trecho=a.get("trecho"),
            ) for a in rascunho.ajustes],
            pendencias_do_cliente=rascunho.pendencias_do_cliente, pontos_sensiveis=rascunho.pontos_sensiveis,
            estrategia_e_desafios=rascunho.estrategia_e_desafios,
            oportunidades=[_sugerida(o) for o in rascunho.oportunidades],
            custo_usd=f"{uso.custo_usd:.4f}" if uso.custo_usd is not None else None,
        )

    @r.post("/grupos/{grupo_id}/reunioes", response_model=GrupoNoFunil, status_code=201)
    def registrar(grupo_id: int, corpo: NovaReuniao, sessao: Session = Depends(obter_sessao)) -> GrupoNoFunil:
        """Registra uma reunião já feita. Só para o grupo em curso; a data não pode ser futura."""
        hoje = date.today()
        if regra.tipo(corpo.tipo) is None:
            raise HTTPException(422, "Tipo de reunião desconhecido")
        if corpo.data > hoje:
            raise HTTPException(422, "A data da reunião não pode ser futura: registre depois de feita")
        if _um(sessao, grupo_id, hoje).etapa != "em_curso":
            raise HTTPException(422, "As reuniões de resultado começam quando o grupo entra em curso, depois do kickoff")
        possiveis = {u.email.lower(): u for u in responsaveis_possiveis(sessao)} if corpo.ajustes else {}
        for a in corpo.ajustes:
            if a.responsavel_email.lower() not in possiveis:
                raise HTTPException(422, f"Responsável sem acesso aos ajustes: {a.responsavel_email}. "
                                         "Libere em Configurações › Perfis e acesso (perfil Área técnica).")
        for n, o in enumerate(corpo.oportunidades, 1):
            servico = o.servico.strip()
            if servico != OUTRO and servico_do_catalogo(servico) is None:
                raise HTTPException(422, f"Oportunidade {n}: serviço fora do catálogo ({servico}). Use \"Outro\".")
            problema = problema_no_tema(servico, o.servico_tema, exigir=True) or (
                problema_na_descricao(servico, o.lacuna) if servico == OUTRO else None)
            if problema:
                raise HTTPException(422, f"Oportunidade {n}: {problema}")
        reuniao = ReuniaoDeResultado(
            grupo_id=grupo_id, tipo=corpo.tipo, data=corpo.data, participantes=_texto(corpo.participantes),
            pauta=_texto(corpo.pauta), dashboard=_texto(corpo.dashboard), resumo=_texto(corpo.resumo),
            decisoes=_texto(corpo.decisoes), pendencias_do_cliente=_texto(corpo.pendencias_do_cliente),
            pontos_sensiveis=_texto(corpo.pontos_sensiveis), proximos_passos=_texto(corpo.proximos_passos),
            transcricao=_texto(corpo.transcricao), estrategia_e_desafios=_texto(corpo.estrategia_e_desafios),
            registrada_por=quem_fez("") or None,
        )
        sessao.add(reuniao)
        sessao.flush()
        for a in corpo.ajustes:
            u = possiveis[a.responsavel_email.lower()]
            sessao.add(AjusteTecnico(
                reuniao_id=reuniao.id, grupo_id=grupo_id, descricao=a.descricao.strip(),
                responsavel_email=u.email, responsavel_nome=u.nome, prazo=a.prazo,
            ))
        if corpo.oportunidades:
            _abrir_vendas(sessao, reuniao, corpo.oportunidades, hoje)
        sessao.flush()
        return _um(sessao, grupo_id, hoje)

    def _abrir_vendas(sessao: Session, reuniao: ReuniaoDeResultado, pedidas: list[NovaOportunidade], hoje: date) -> None:
        """Anota cada oportunidade na ata; a marcada vira oportunidade no Funil comercial, em "Enviar
        proposta", canal Carteira, com o captador de quem registrou (aprovado por Eduardo em 03/10/2026).
        Recorrente leva o valor no preço mensal; projeto, no preço anual (o total)."""
        grupo = sessao.get(GrupoEconomico, reuniao.grupo_id)
        empresas = list(sessao.scalars(sa.select(Empresa.id).where(Empresa.grupo_id == grupo.id).limit(2)))
        captador = _captador(quem_fez(""))
        nome_do_tipo = regra.nome_do_tipo(reuniao.tipo).lower()
        for o in pedidas:
            servico, tema = o.servico.strip(), _texto(o.servico_tema)
            linha = linha_do_servico(servico)
            anotada = OportunidadeDaReuniao(
                reuniao_id=reuniao.id, grupo_id=grupo.id, lacuna=o.lacuna.strip(), servico=servico,
                servico_tema=tema, valor=o.valor, recorrente=linha is LinhaServico.C1,
            )
            if o.abrir_no_funil:
                aberta = Oportunidade(
                    grupo_id=grupo.id, empresa_id=empresas[0] if len(empresas) == 1 else None, nome=grupo.nome,
                    servico=servico, servico_tema=tema, linha_servico=linha,
                    servico_descricao=o.lacuna.strip() if servico == OUTRO else None,
                    situacao=Situacao.ENVIAR_PROPOSTA, tipo_canal=TipoCanal.CARTEIRA, canal="Reunião de resultado",
                    captador=captador, data_colocacao=hoje,
                    preco_mensal=o.valor if linha is LinhaServico.C1 else None,
                    preco_anual=None if linha is LinhaServico.C1 else o.valor,
                    observacao=f"Aberta na reunião {nome_do_tipo} de {reuniao.data:%d/%m/%Y}. Lacuna: {o.lacuna.strip()}",
                    origem=Origem.CRM,
                )
                sessao.add(aberta)
                sessao.flush()
                anotada.oportunidade_id = aberta.id
            sessao.add(anotada)

    def _cadencia_resposta(sessao: Session) -> CadenciaResposta:
        mudadas = [c for c in sessao.scalars(sa.select(CadenciaDeReuniao)) if c.alterado_em]
        ultima = max(mudadas, key=lambda c: c.alterado_em, default=None)
        return CadenciaResposta(
            cadencia=cadencia_vigente(sessao), intencao=intencao_vigente(sessao),
            alterado_por=ultima.alterado_por if ultima else None, alterado_em=ultima.alterado_em if ultima else None,
        )

    @r.get("/cadencia", response_model=CadenciaResposta)
    def ver_cadencia(sessao: Session = Depends(obter_sessao)) -> CadenciaResposta:
        return _cadencia_resposta(sessao)

    @r.put("/cadencia", response_model=CadenciaResposta)
    def mudar_cadencia(corpo: CadenciaEdicao, sessao: Session = Depends(obter_sessao)) -> CadenciaResposta:
        """Só muda as classes que vieram. Cada classe precisa de ao menos uma reunião. A intenção vazia
        volta ao texto padrão."""
        validos = [t.chave for t in regra.TIPOS_DE_REUNIAO]
        for classe in [*corpo.cadencia, *corpo.intencao]:
            if classe not in _CLASSES:
                raise HTTPException(422, f"Classe desconhecida: {classe}")
        vigente = cadencia_vigente(sessao)
        for classe in _CLASSES:
            if classe not in corpo.cadencia and classe not in corpo.intencao:
                continue
            tipos = corpo.cadencia.get(classe, vigente[classe])
            if not tipos:
                raise HTTPException(422, f"Classe {classe}: escolha ao menos uma reunião")
            if any(t not in validos for t in tipos):
                raise HTTPException(422, f"Classe {classe}: tipo de reunião desconhecido")
            ordenados = [t for t in validos if t in tipos]
            linha = sessao.get(CadenciaDeReuniao, classe)
            intencao = _texto(corpo.intencao[classe]) if classe in corpo.intencao else (linha.intencao if linha else None)
            if intencao == regra.INTENCAO_PADRAO[classe]:
                intencao = None
            if linha is None:
                linha = CadenciaDeReuniao(classe=classe, tipos=ordenados)
                sessao.add(linha)
            elif list(linha.tipos) == ordenados and linha.intencao == intencao:
                continue
            linha.tipos, linha.intencao = ordenados, intencao
            linha.alterado_por = quem_fez("") or None
            linha.alterado_em = agora()
        sessao.flush()
        return _cadencia_resposta(sessao)

    @r.get("/carteira", response_model=CarteiraComReunioes)
    def carteira(sessao: Session = Depends(obter_sessao)) -> CarteiraComReunioes:
        """A bimestral interna da carteira: quando vence e as já feitas, da mais recente."""
        return CarteiraComReunioes(
            devida=_carteira(sessao, date.today()),
            reunioes=[ReuniaoDaCarteiraResposta.model_validate(x) for x in sessao.scalars(
                sa.select(ReuniaoDaCarteira).order_by(ReuniaoDaCarteira.data.desc(), ReuniaoDaCarteira.id.desc()))],
        )

    @r.post("/carteira/reunioes", response_model=CarteiraComReunioes, status_code=201)
    def registrar_da_carteira(corpo: NovaReuniaoDaCarteira, sessao: Session = Depends(obter_sessao)) -> CarteiraComReunioes:
        if corpo.data > date.today():
            raise HTTPException(422, "A data da reunião não pode ser futura: registre depois de feita")
        sessao.add(ReuniaoDaCarteira(
            data=corpo.data, participantes=_texto(corpo.participantes) or regra.REUNIAO_DA_CARTEIRA.participantes,
            resumo=_texto(corpo.resumo), correcoes_de_rota=_texto(corpo.correcoes_de_rota),
            registrada_por=quem_fez("") or None,
        ))
        sessao.flush()
        return carteira(sessao)

    return r
