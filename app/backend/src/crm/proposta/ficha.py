"""A ficha da oportunidade (E4, 02/10/2026): as nove seções do questionário do site, cada resposta
dizendo de onde veio.

A definição espelha o formulário publicado ("BPO Full 2026 v6", `app/site/questionario/index.html`,
constante `SECOES`): mudou o formulário, muda esta lista. Quem responde primeiro é o cliente, no
questionário; o que se corrige no CRM vale como **Entrevista**, com quem e quando, e a resposta
original continua guardada no questionário recebido.

Contagem: só entram as perguntas visíveis para as respostas atuais (o formulário esconde, por
exemplo, "fornecedor atual" de quem tem operação interna). A seção 6 (Folha) só está no escopo se o
serviço "Folha / DP" foi pedido, a 7 (Financeiro) só com "Financeiro". A seção 9 (acessos e
documentos) é levantada no kick-off da implantação: aparece, mas não conta como pendência da
proposta (decisão de Eduardo em 02/10/2026).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

__all__ = ["CAMPOS", "SECOES", "Campo", "CampoMontado", "Ficha", "SecaoMontada", "campo", "montar", "valor_do_questionario"]

SIM_NAO = ("Sim", "Não")
Respostas = dict[str, Any]


def _tem(campo: str, *valores: str) -> Callable[[Respostas], bool]:
    def condicao(r: Respostas) -> bool:
        v = r.get(campo)
        return any((x in v) if isinstance(v, list) else v == x for x in valores)
    return condicao


@dataclass(frozen=True)
class Campo:
    chave: str
    """Nome no questionário; `vol.x` e `sistemas.x` são as partes de dentro desses dois blocos."""
    secao: int
    rotulo: str
    tipo: str = "texto"
    """texto · texto_longo · numero · data · uma (escolha única) · varias (múltipla escolha)."""
    opcoes: tuple[str, ...] = ()
    mostra: Callable[[Respostas], bool] | None = None
    sub: bool = False


SECOES: dict[int, str] = {
    1: "Empresa, escopo e responsáveis",
    2: "Sistemas, dados e integrações",
    3: "Volumes mensais para dimensionamento",
    4: "Contábil e gerencial",
    5: "Fiscal e obrigações",
    6: "Folha de pagamento e departamento pessoal",
    7: "Financeiro",
    8: "Dores, expectativas, transição e decisão",
    9: "Acessos, documentos e estrutura — para a implantação",
}

_TERCEIRIZADA = _tem("operacao", "Terceirizada", "Mista")
_VOLUMES = (
    ("notas_emitidas", "Notas fiscais emitidas (serviço / produto)"), ("notas_recebidas", "Notas fiscais recebidas"),
    ("lancamentos", "Lançamentos contábeis"), ("pagamentos", "Pagamentos efetuados"),
    ("contas_bancarias", "Contas bancárias"), ("conciliacoes_cartao", "Conciliações de cartão"),
    ("empregados_clt", "Empregados CLT"), ("pjs_estagiarios", "PJs / estagiários"), ("admissoes", "Admissões"),
    ("desligamentos", "Desligamentos"), ("cnpjs", "CNPJs (empresas do grupo que a Critério atenderá)"),
    ("tomadores", "Tomadores de serviço (clientes atendidos)"), ("filiais_estabelecimentos", "Filiais / estabelecimentos"),
)
_SISTEMAS = (("erp", "ERP / financeiro"), ("contabil", "Contábil / fiscal"), ("folha", "Folha / eSocial"), ("ponto", "Ponto / RH"))

CAMPOS: tuple[Campo, ...] = (
    # 1 · Empresa, escopo e responsáveis
    Campo("razao_social", 1, "Razão social"),
    Campo("cnpj", 1, "CNPJ principal"),
    Campo("nome_fantasia", 1, "Nome fantasia"),
    Campo("atividade", 1, "Atividade / segmento"),
    Campo("faturamento_anual", 1, "Faturamento anual"),
    Campo("regime_tributario", 1, "Regime tributário", "varias",
          ("Simples Nacional", "Lucro Presumido", "Lucro Real", "MEI", "Outro")),
    Campo("cnpjs_escopo", 1, "CNPJs no escopo", "texto_longo"),
    Campo("filiais_localidades", 1, "Filiais / localidades"),
    Campo("contato_nome", 1, "Contato"),
    Campo("contato_cargo", 1, "Cargo"),
    Campo("contato_celular", 1, "Celular"),
    Campo("contato_email", 1, "E-mail"),
    Campo("servicos", 1, "Serviços no escopo", "varias", ("Contábil", "Fiscal", "Folha / DP", "Financeiro")),
    Campo("operacao", 1, "Operação atual", "uma", ("Interna", "Terceirizada", "Mista")),
    Campo("fornecedor_atual", 1, "Fornecedor atual / prazo de aviso prévio", mostra=_TERCEIRIZADA),
    Campo("equipe_interna", 1, "Equipe interna dedicada hoje (nº de pessoas)", "numero"),
    Campo("valor_fornecedor", 1, "Valor mensal pago ao fornecedor atual", mostra=_TERCEIRIZADA),
    # 2 · Sistemas, dados e integrações
    *(Campo(f"sistemas.{k}", 2, f"Sistema {nome} (e como troca dados)") for k, nome in _SISTEMAS),
    Campo("implantacao_historico", 2, "Implantação / histórico", "texto_longo"),
    # 3 · Volumes mensais
    *(Campo(f"vol.{k}", 3, nome, "numero") for k, nome in _VOLUMES),
    # 4 · Contábil e gerencial
    Campo("fechamento", 4, "Fechamento atual e prazo desejado para balancete / demonstrações (dias úteis)", "texto_longo"),
    Campo("plano_contas", 4, "O plano de contas contempla natureza de serviço, centro de custo e projeto?", "uma", ("Não", "Sim")),
    Campo("plano_contas_qtd", 4, "Quantidades", mostra=_tem("plano_contas", "Sim"), sub=True),
    Campo("folha_rateio", 4, "A folha deve ser rateada por centro de custo, projeto ou natureza?", "uma", SIM_NAO),
    Campo("folha_rateio_formal", 4, "Regra formalizada?", "uma", SIM_NAO, _tem("folha_rateio", "Sim"), True),
    Campo("relatorios", 4, "Relatórios necessários", "varias",
          ("DRE por centro/projeto", "Balanço", "Fluxo de caixa", "Consolidação", "Outros")),
    Campo("relatorios_outros", 4, "Outros relatórios", mostra=_tem("relatorios", "Outros"), sub=True),
    Campo("auditada", 4, "A empresa é auditada?", "uma", SIM_NAO),
    Campo("auditoria_det", 4, "Empresa, frequência e exigências de fechamento", "texto_longo", mostra=_tem("auditada", "Sim"), sub=True),
    # 5 · Fiscal e obrigações
    Campo("tributos", 5, "Tributos e operações", "varias", ("ISS", "ICMS", "IPI", "Retenções")),
    Campo("municipios_ufs", 5, "Municípios/UFs com atividade"),
    Campo("exterior", 5, "Há remessas/retornos, importação/exportação ou pagamentos ao exterior?", "uma", SIM_NAO),
    Campo("exterior_det", 5, "Descreva", mostra=_tem("exterior", "Sim"), sub=True),
    Campo("obrigacoes_especificas", 5, "Obrigações específicas, benefícios fiscais ou certidões exigidas por clientes", "texto_longo"),
    Campo("passivos", 5, "Existem parcelamentos, passivos, autos de infração ou processos tributários?", "uma", SIM_NAO),
    Campo("passivos_tipos", 5, "Quais?", "varias", ("Parcelamento", "Auto de infração", "Processo tributário", "Outro passivo"),
          _tem("passivos", "Sim"), True),
    Campo("passivos_det", 5, "Descreva", "texto_longo", mostra=_tem("passivos", "Sim"), sub=True),
    Campo("parcelamento_situacao", 5, "Se houver parcelamento", "uma", ("Em dia", "Em atraso, ou já quebrado antes"),
          _tem("passivos", "Sim"), True),
    Campo("obrig_esforco", 5, "Declarações/obrigações que demandam tratamento especial ou maior esforço", "texto_longo"),
    Campo("obrig_atraso", 5, "Alguma obrigação acessória foi entregue com atraso nos últimos 3 meses?", "uma", SIM_NAO),
    Campo("obrig_atraso_det", 5, "Quais", mostra=_tem("obrig_atraso", "Sim"), sub=True),
    # 6 · Folha e DP
    Campo("colab_distribuicao", 6, "Distribuição dos colaboradores por UF/localidade e modalidade", "texto_longo"),
    Campo("sindicatos", 6, "Sindicatos e CCTs aplicáveis; colaboradores sujeitos a CCT de outra localidade?", "texto_longo"),
    Campo("calendario_folha", 6, "Corte do ponto, fechamento e pagamento da folha; adiantamento ou folha complementar?", "texto_longo"),
    Campo("eventos", 6, "Eventos variáveis", "varias",
          ("HE/banco de horas", "Noturno", "Sobreaviso", "Periculosidade", "Comissão", "Outros")),
    Campo("eventos_outros", 6, "Outros eventos", mostra=_tem("eventos", "Outros"), sub=True),
    Campo("ponto_beneficios", 6, "Sistema de ponto e conferência manual; benefícios administrados no escopo", "texto_longo"),
    Campo("tomadores_upload", 6, "Tomadores exigem upload de folha/encargos ou condicionam faturamento?", "uma", SIM_NAO),
    Campo("tomadores_upload_det", 6, "Quantos, quais dados e prazo", mostra=_tem("tomadores_upload", "Sim"), sub=True),
    Campo("pendencias_esocial", 6, "Pendências de eSocial/SST, histórico de folha a migrar ou ocorrências trabalhistas", "texto_longo"),
    # 7 · Financeiro
    Campo("fin_escopo", 7, "Escopo desejado", "varias",
          ("Contas a pagar", "Contas a receber", "Faturamento", "Cobrança", "Conciliação", "Fluxo de caixa")),
    Campo("fin_aprovacoes", 7, "Aprovações, alçadas, bancos e prazos críticos; pagamentos/recebimentos no exterior?", "texto_longo"),
    Campo("fin_relatorios", 7, "Relatórios e periodicidade; principais processos ainda manuais", "texto_longo"),
    Campo("fin_inadimplencia", 7, "Inadimplência, capital de giro e volumes mensais (boletos, cobranças)", "texto_longo"),
    # 8 · Dores, expectativas, transição e decisão
    Campo("dores", 8, "Erros, atrasos ou retrabalhos dos últimos 12 meses que mais impactaram", "texto_longo"),
    Campo("proatividade", 8, "O que o novo parceiro deve antecipar ou fazer de forma mais proativa?", "texto_longo"),
    Campo("criterio_1", 8, "Critério de sucesso 1"),
    Campo("criterio_2", 8, "Critério de sucesso 2"),
    Campo("criterio_3", 8, "Critério de sucesso 3"),
    Campo("slas", 8, "SLAs esperados (folha, balancete, obrigações e relatórios)", "texto_longo"),
    Campo("data_inicio", 8, "Data desejada de início", "data"),
    Campo("decisores", 8, "Decisor final, influenciadores e usuários do serviço", "texto_longo"),
    Campo("ponto_focal", 8, "Ponto focal da implantação e quem concede acessos", "texto_longo"),
    Campo("documentos", 8, "Documentos disponíveis", "varias",
          ("Balancete", "Folha", "Obrigações", "Relatórios gerenciais", "Contrato atual", "Balanço de Abertura",
           "Balancete de encerramento", "Plano de contas", "Histórico contábil", "Outros")),
    Campo("historico_exercicios", 8, "Histórico contábil: nº de exercícios", "numero",
          mostra=_tem("documentos", "Histórico contábil"), sub=True),
    Campo("documentos_outros", 8, "Outros documentos", mostra=_tem("documentos", "Outros"), sub=True),
    # 9 · Acessos, documentos e estrutura (implantação)
    Campo("reestruturacao", 9, "Reestruturação societária, fusão, cisão ou entrada de sócio em curso?", "uma", SIM_NAO),
    Campo("reestruturacao_det", 9, "Descreva e informe o prazo estimado", "texto_longo", mostra=_tem("reestruturacao", "Sim"), sub=True),
    Campo("certificado", 9, "Certificado digital", "uma", ("e-CNPJ A1", "e-CNPJ A3", "Não possui")),
    Campo("certificado_titular", 9, "Titular", mostra=lambda r: bool(r.get("certificado")) and r.get("certificado") != "Não possui", sub=True),
    Campo("certificado_validade", 9, "Validade", "data", mostra=lambda r: bool(r.get("certificado")) and r.get("certificado") != "Não possui", sub=True),
    Campo("procuracao", 9, "Procuração eletrônica para a contabilidade", "uma", SIM_NAO),
    Campo("procuracao_det", 9, "Escopo e validade", mostra=_tem("procuracao", "Sim"), sub=True),
    Campo("domicilios", 9, "Domicílios eletrônicos em uso e quem os acompanha", "texto_longo"),
    Campo("saldos", 9, "Saldos a migrar", "varias", ("Férias", "13º", "Banco de horas", "Provisões", "Outros")),
    Campo("saldos_outros", 9, "Outros saldos", mostra=_tem("saldos", "Outros"), sub=True),
    Campo("saldos_onde", 9, "Disponíveis em (sistema ou arquivo)",
          mostra=lambda r: isinstance(r.get("saldos"), list) and len(r["saldos"]) > 0, sub=True),
)
_POR_CHAVE = {c.chave: c for c in CAMPOS}


def valor_do_questionario(respostas: Respostas | None, chave: str) -> Any:
    """A resposta do cliente, já no formato da ficha: texto, número em texto, lista ou `None`."""
    r = respostas or {}
    if chave.startswith("vol."):
        v = (r.get("vol") or {}).get(chave[4:])
    elif chave.startswith("sistemas."):
        s = (r.get("sistemas") or {}).get(chave[9:]) or {}
        troca = ", ".join(x for x in (s.get("troca") or []) if isinstance(x, str))
        v = " · ".join(x for x in (s.get("sistema"), troca) if x) or None
    else:
        v = r.get(chave)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        v = str(v)
    return v


def _respondida(v: Any) -> bool:
    return v not in (None, "", []) and not (isinstance(v, str) and not v.strip())


@dataclass(frozen=True)
class CampoMontado:
    campo: Campo
    valor: Any
    origem: str | None
    """"Questionário", "Entrevista" ou `None` (sem resposta)."""
    por: str | None
    em: datetime | None

    @property
    def respondida(self) -> bool:
        return _respondida(self.valor)


@dataclass(frozen=True)
class SecaoMontada:
    numero: int
    titulo: str
    no_escopo: bool
    conta_pendencia: bool
    campos: list[CampoMontado]

    @property
    def total(self) -> int:
        return len(self.campos)

    @property
    def respondidas(self) -> int:
        return sum(1 for c in self.campos if c.respondida)


@dataclass(frozen=True)
class Ficha:
    secoes: list[SecaoMontada]

    @property
    def total(self) -> int:
        """Só o que conta para a proposta: seções no escopo, sem a 9."""
        return sum(s.total for s in self.secoes if s.conta_pendencia)

    @property
    def respondidas(self) -> int:
        return sum(s.respondidas for s in self.secoes if s.conta_pendencia)


def _quando(texto: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(texto) if isinstance(texto, str) else None
    except ValueError:
        return None


def montar(respostas: Respostas | None, correcoes: dict[str, dict] | None, recebido_em: datetime | None) -> Ficha:
    """`correcoes` é `Oportunidade.ficha`: `{chave: {"valor", "por", "em"}}`, o que foi corrigido na
    entrevista. Vale sobre a resposta do questionário, inclusive para decidir o que aparece."""
    correcoes = correcoes or {}
    efetivas: Respostas = {}
    for c in CAMPOS:
        efetivas[c.chave] = correcoes[c.chave].get("valor") if c.chave in correcoes else valor_do_questionario(respostas, c.chave)
    servicos = efetivas.get("servicos") or []
    escopo = {6: "Folha / DP" in servicos, 7: "Financeiro" in servicos}

    secoes = []
    for numero, titulo in SECOES.items():
        campos = []
        for c in (c for c in CAMPOS if c.secao == numero):
            if c.mostra is not None and not c.mostra(efetivas):
                continue
            if c.chave in correcoes:
                k = correcoes[c.chave]
                campos.append(CampoMontado(c, k.get("valor"), "Entrevista", k.get("por"), _quando(k.get("em"))))
            else:
                v = valor_do_questionario(respostas, c.chave)
                campos.append(CampoMontado(c, v, "Questionário" if _respondida(v) else None, None,
                                           recebido_em if _respondida(v) else None))
        no_escopo = escopo.get(numero, True)
        secoes.append(SecaoMontada(numero, titulo, no_escopo, no_escopo and numero != 9, campos))
    return Ficha(secoes)


def campo(chave: str) -> Campo | None:
    return _POR_CHAVE.get(chave)
