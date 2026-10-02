"""Funil do Sucesso do Cliente (aprovado por Eduardo em 02/10/2026): a etapa de cada grupo cliente,
o checklist da implantação e as reuniões de resultado com cadência pela classe. Regras em
`crm.domain.sucesso`."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime

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
from crm.db.base import agora
from crm.db.modelos import (
    AjusteTecnico, CadenciaDeReuniao, ClassificacaoDoGrupo, Contrato, GrupoEconomico, JornadaDoCliente,
    ReuniaoDeResultado,
)
from crm.domain import sucesso as regra
from crm.domain.listas import SituacaoContrato

__all__ = ["ServicosDaAta", "roteador_do_sucesso", "servicos_da_ata_reais"]

_VALENDO = (SituacaoContrato.AGUARDANDO_ASSINATURA, SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO)
_CLASSES = ("A", "B", "C")


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


class FunilDoSucesso(BaseModel):
    etapas: list[EtapaResposta]
    checklist: dict[str, list[ItemResposta]]
    tipos: list[TipoResposta]
    cadencia: dict[str, list[str]]
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
    tem_transcricao: bool
    registrada_por: str | None
    criado_em: datetime
    ajustes: list[AjusteResposta]


class NovoAjuste(BaseModel):
    descricao: str = Field(min_length=3)
    responsavel_email: str = Field(min_length=3, max_length=200)
    prazo: date | None = None


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
    ajustes: list[NovoAjuste] = []


class PedidoDeAta(BaseModel):
    tipo: str
    data: date
    participantes: str | None = Field(default=None, max_length=300)
    transcricao: str = Field(min_length=50, max_length=400_000)


class AjusteSugerido(BaseModel):
    descricao: str
    prazo: date | None


class RascunhoDaAtaResposta(BaseModel):
    resumo: str
    decisoes_do_cliente: list[str]
    ajustes: list[AjusteSugerido]
    pendencias_do_cliente: list[str]
    pontos_sensiveis: list[str]
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
    alterado_por: str | None = None
    alterado_em: datetime | None = None


class CadenciaEdicao(BaseModel):
    cadencia: dict[str, list[str]]


def _texto(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def cadencia_vigente(sessao: Session) -> dict[str, list[str]]:
    gravadas = {c.classe: list(c.tipos) for c in sessao.scalars(sa.select(CadenciaDeReuniao))}
    return {cl: gravadas.get(cl, list(regra.CADENCIA_PADRAO[cl])) for cl in _CLASSES}


def _resposta_da_reuniao(reuniao: ReuniaoDeResultado) -> ReuniaoResposta:
    return ReuniaoResposta(
        id=reuniao.id, tipo=reuniao.tipo, data=reuniao.data, participantes=reuniao.participantes,
        pauta=reuniao.pauta, dashboard=reuniao.dashboard, resumo=reuniao.resumo, decisoes=reuniao.decisoes,
        pendencias_do_cliente=reuniao.pendencias_do_cliente, pontos_sensiveis=reuniao.pontos_sensiveis,
        proximos_passos=reuniao.proximos_passos, tem_transcricao=bool(reuniao.transcricao),
        registrada_por=reuniao.registrada_por, criado_em=reuniao.criado_em,
        ajustes=[resposta_do_ajuste(a) for a in reuniao.ajustes],
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

    def _no_funil(
        g: GrupoEconomico, anterior: bool, jornada: JornadaDoCliente | None, classe: str | None,
        ultimas: dict[str, date], cadencia: dict[str, list[str]], hoje: date,
        ajustes: tuple[int, int, int] = (0, 0, 0),
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
        )

    def _um(sessao: Session, grupo_id: int, hoje: date) -> GrupoNoFunil:
        achados = _grupos(sessao, grupo_id)
        if not achados:
            raise HTTPException(404, "Grupo sem contrato valendo: não está no Funil do Sucesso do Cliente")
        g, anterior = achados[0]
        return _no_funil(
            g, anterior, sessao.get(JornadaDoCliente, grupo_id), _classes(sessao).get(grupo_id),
            _ultimas(sessao).get(grupo_id, {}), cadencia_vigente(sessao), hoje,
            _ajustes(sessao, hoje).get(grupo_id, (0, 0, 0)),
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
        ajustes = _ajustes(sessao, dia)
        return FunilDoSucesso(
            etapas=[EtapaResposta(chave=c, nome=n, participantes=p) for c, n, p in regra.ETAPAS],
            checklist={e: [ItemResposta(chave=c, rotulo=r_) for c, r_ in itens] for e, itens in regra.CHECKLIST.items()},
            tipos=[TipoResposta(chave=t.chave, nome=t.nome, meses=t.meses, participantes=t.participantes, pauta=list(t.pauta))
                   for t in regra.TIPOS_DE_REUNIAO],
            cadencia=cadencia,
            grupos=[_no_funil(g, anterior, jornadas.get(g.id), classes.get(g.id), ultimas.get(g.id, {}), cadencia, dia,
                              ajustes.get(g.id, (0, 0, 0)))
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
        servicos = servicos_da_ata()
        uso = Uso(modelo=servicos.modelo)
        try:
            rascunho = escrever_ata(
                servicos.cliente(), servicos.modelo, cliente=grupo.nome, tipo=tipo.nome,
                data=corpo.data.strftime("%d/%m/%Y"), participantes=_texto(corpo.participantes),
                transcricao=corpo.transcricao.strip(), uso=uso,
            )
        except Exception as falha:  # noqa: BLE001 — a mensagem é para a pessoa, sem dado do cliente
            raise HTTPException(502, mensagem_de_falha(falha)) from falha
        return RascunhoDaAtaResposta(
            resumo=rascunho.resumo, decisoes_do_cliente=rascunho.decisoes_do_cliente,
            ajustes=[AjusteSugerido(descricao=a["descricao"], prazo=a["prazo"]) for a in rascunho.ajustes],
            pendencias_do_cliente=rascunho.pendencias_do_cliente, pontos_sensiveis=rascunho.pontos_sensiveis,
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
        reuniao = ReuniaoDeResultado(
            grupo_id=grupo_id, tipo=corpo.tipo, data=corpo.data, participantes=_texto(corpo.participantes),
            pauta=_texto(corpo.pauta), dashboard=_texto(corpo.dashboard), resumo=_texto(corpo.resumo),
            decisoes=_texto(corpo.decisoes), pendencias_do_cliente=_texto(corpo.pendencias_do_cliente),
            pontos_sensiveis=_texto(corpo.pontos_sensiveis), proximos_passos=_texto(corpo.proximos_passos),
            transcricao=_texto(corpo.transcricao), registrada_por=quem_fez("") or None,
        )
        sessao.add(reuniao)
        sessao.flush()
        for a in corpo.ajustes:
            u = possiveis[a.responsavel_email.lower()]
            sessao.add(AjusteTecnico(
                reuniao_id=reuniao.id, grupo_id=grupo_id, descricao=a.descricao.strip(),
                responsavel_email=u.email, responsavel_nome=u.nome, prazo=a.prazo,
            ))
        sessao.flush()
        return _um(sessao, grupo_id, hoje)

    def _cadencia_resposta(sessao: Session) -> CadenciaResposta:
        mudadas = [c for c in sessao.scalars(sa.select(CadenciaDeReuniao)) if c.alterado_em]
        ultima = max(mudadas, key=lambda c: c.alterado_em, default=None)
        return CadenciaResposta(
            cadencia=cadencia_vigente(sessao),
            alterado_por=ultima.alterado_por if ultima else None, alterado_em=ultima.alterado_em if ultima else None,
        )

    @r.get("/cadencia", response_model=CadenciaResposta)
    def ver_cadencia(sessao: Session = Depends(obter_sessao)) -> CadenciaResposta:
        return _cadencia_resposta(sessao)

    @r.put("/cadencia", response_model=CadenciaResposta)
    def mudar_cadencia(corpo: CadenciaEdicao, sessao: Session = Depends(obter_sessao)) -> CadenciaResposta:
        """Só muda as classes que vieram. Cada classe precisa de ao menos uma reunião."""
        validos = [t.chave for t in regra.TIPOS_DE_REUNIAO]
        for classe, tipos in corpo.cadencia.items():
            if classe not in _CLASSES:
                raise HTTPException(422, f"Classe desconhecida: {classe}")
            if not tipos:
                raise HTTPException(422, f"Classe {classe}: escolha ao menos uma reunião")
            if any(t not in validos for t in tipos):
                raise HTTPException(422, f"Classe {classe}: tipo de reunião desconhecido")
            ordenados = [t for t in validos if t in tipos]
            linha = sessao.get(CadenciaDeReuniao, classe)
            if linha is None:
                linha = CadenciaDeReuniao(classe=classe, tipos=ordenados)
                sessao.add(linha)
            elif list(linha.tipos) == ordenados:
                continue
            linha.tipos = ordenados
            linha.alterado_por = quem_fez("") or None
            linha.alterado_em = agora()
        sessao.flush()
        return _cadencia_resposta(sessao)

    return r
