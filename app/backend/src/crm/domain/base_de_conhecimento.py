"""A base de conhecimento do SDR de IA — 03/10/2026.

Lógica pura, sem banco nem rede. Amostra aprovada por Eduardo em 03/10/2026.

A base é feita de **fichas curtas**, uma por assunto, e cada uma diz o que a
IA pode dizer, o que nunca diz e como o lead costuma perguntar. Só a ficha
**aprovada e dentro da validade** vale para a IA — e o bloco Referências
nunca vale: é material de consulta da equipe (fontes, estudos, benchmarks).

O conteúdo da carga inicial vem de `sdr-ia-limites-de-atuacao.md` (passo 1,
proposta em validação) e do catálogo de serviços (rascunho). Por isso nada
nasce aprovado: regras entram "Em revisão", serviços e o resto como
"Rascunho".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Protocol

from crm.domain.abordagem import fala_de_preco
from crm.domain.servicos import CATALOGO

__all__ = [
    "BlocoDaBase",
    "SituacaoDaFicha",
    "VALIDADE_PADRAO",
    "VALIDADE_DE_HIPOTESE",
    "FichaInicial",
    "FICHAS_INICIAIS",
    "validade_ao_aprovar",
    "vencida",
    "vale_para_a_ia",
    "problemas_para_aprovar",
    "ResumoDoBloco",
    "resumir",
]


class BlocoDaBase(Enum):
    """Os nove blocos da base. A ordem é a da tela."""

    REGRAS = "Regras de atuação"
    TRANSBORDO = "Transbordo"
    SERVICOS = "Serviços"
    OBJECOES = "Objeções"
    TOM = "Tom de voz"
    CRITERIO = "Quem é a Critério"
    QUALIFICACAO = "Qualificação"
    PERGUNTAS = "Perguntas frequentes"
    REFERENCIAS = "Referências"

    @property
    def vai_para_a_ia(self) -> bool:
        return self is not BlocoDaBase.REFERENCIAS


class SituacaoDaFicha(Enum):
    RASCUNHO = "Rascunho"
    EM_REVISAO = "Em revisão"
    APROVADA = "Aprovada"
    ARQUIVADA = "Arquivada"


#: Ficha comum vale seis meses; a que depende de hipótese em validação (ICP,
#: preço, fronteiras entre BPO Financeiro, BPO Plus e CFO as a Service), 60 dias.
VALIDADE_PADRAO = timedelta(days=182)
VALIDADE_DE_HIPOTESE = timedelta(days=60)


def validade_ao_aprovar(hoje: date, depende_de_hipotese: bool) -> date:
    return hoje + (VALIDADE_DE_HIPOTESE if depende_de_hipotese else VALIDADE_PADRAO)


class FichaLida(Protocol):
    bloco: BlocoDaBase
    situacao: SituacaoDaFicha
    titulo: str
    texto: str | None
    fonte: str | None
    dono: str | None
    validade: date | None


def vencida(ficha: FichaLida, hoje: date) -> bool:
    return (
        ficha.situacao is SituacaoDaFicha.APROVADA
        and ficha.validade is not None
        and ficha.validade < hoje
    )


def vale_para_a_ia(ficha: FichaLida, hoje: date) -> bool:
    return (
        ficha.bloco.vai_para_a_ia
        and ficha.situacao is SituacaoDaFicha.APROVADA
        and not vencida(ficha, hoje)
    )


def problemas_para_aprovar(ficha: FichaLida) -> list[str]:
    """O que falta para a ficha poder ser aprovada. Lista vazia: pode."""
    problemas: list[str] = []
    if ficha.situacao is SituacaoDaFicha.ARQUIVADA:
        problemas.append("A ficha está arquivada: reabra antes de aprovar")
    if not (ficha.titulo or "").strip():
        problemas.append("Falta o título")
    if not (ficha.texto or "").strip():
        problemas.append("Falta o que a IA pode dizer")
    if not (ficha.fonte or "").strip():
        problemas.append("Falta a fonte")
    if not (ficha.dono or "").strip():
        problemas.append("Falta o dono")
    if ficha.bloco.vai_para_a_ia and fala_de_preco(ficha.texto):
        problemas.append(
            "O texto fala de preço: a IA não informa preço (a mesma trava das mensagens)"
        )
    return problemas


@dataclass(frozen=True)
class ResumoDoBloco:
    bloco: str
    total: int
    """Fichas não arquivadas."""
    valem: int
    """Aprovadas e dentro da validade — o que a IA usa."""
    em_revisao: int
    rascunhos: int
    vencidas: int
    vai_para_a_ia: bool


def resumir(fichas: list[FichaLida], hoje: date) -> list[ResumoDoBloco]:
    """Um resumo por bloco, todos os blocos, na ordem da tela — inclusive os vazios."""
    resumo = []
    for bloco in BlocoDaBase:
        do_bloco = [
            f for f in fichas if f.bloco is bloco and f.situacao is not SituacaoDaFicha.ARQUIVADA
        ]
        resumo.append(
            ResumoDoBloco(
                bloco=bloco.value,
                total=len(do_bloco),
                valem=sum(
                    1 for f in do_bloco
                    if f.situacao is SituacaoDaFicha.APROVADA and not vencida(f, hoje)
                ),
                em_revisao=sum(1 for f in do_bloco if f.situacao is SituacaoDaFicha.EM_REVISAO),
                rascunhos=sum(1 for f in do_bloco if f.situacao is SituacaoDaFicha.RASCUNHO),
                vencidas=sum(1 for f in do_bloco if vencida(f, hoje)),
                vai_para_a_ia=bloco.vai_para_a_ia,
            )
        )
    return resumo


# ----------------------------------------------------------- carga inicial
@dataclass(frozen=True)
class FichaInicial:
    codigo: str
    """Chave da carga: a ficha com este código já existe? Então não entra de novo."""
    titulo: str
    bloco: BlocoDaBase
    texto: str
    situacao: SituacaoDaFicha
    fonte: str
    nunca_dizer: str | None = None
    como_o_lead_pergunta: str | None = None
    servico: str | None = None
    dono: str | None = None
    depende_de_hipotese: bool = False


_DOC = "sdr-ia-limites-de-atuacao.md"
_REVISAO = SituacaoDaFicha.EM_REVISAO
_RASCUNHO = SituacaoDaFicha.RASCUNHO
_R, _T, _V = BlocoDaBase.REGRAS, BlocoDaBase.TRANSBORDO, BlocoDaBase.TOM

_FRASE_DO_VALOR = (
    "O valor depende do volume da sua operação. Quem monta a proposta é a nossa equipe, "
    "depois de entender a sua rotina. Posso passar o seu contato?"
)
_FRASE_DO_ESPECIALISTA = (
    "Essa é uma análise que nossos especialistas fazem com os números da sua empresa. "
    "Vou passar a sua pergunta para eles."
)


def _regra(codigo, titulo, texto, nunca, pergunta=None, hipotese=False) -> FichaInicial:
    return FichaInicial(
        codigo, titulo, _R, texto, _REVISAO, f"{_DOC}, seção 3 (03/10/2026)",
        nunca_dizer=nunca, como_o_lead_pergunta=pergunta, dono="Eduardo",
        depende_de_hipotese=hipotese,
    )


def _gatilho(codigo, titulo, texto, quando, pergunta=None) -> FichaInicial:
    return FichaInicial(
        codigo, titulo, _T, texto, _REVISAO, f"{_DOC}, seção 4 (03/10/2026)",
        nunca_dizer=quando, como_o_lead_pergunta=pergunta, dono="Eduardo",
    )


_REGRAS = (
    _regra("P1", "Não informa preço, faixa de valor, desconto ou condição comercial", _FRASE_DO_VALOR,
           "Qualquer número de honorário, faixa, desconto ou mensalidade.",
           '"Quanto custa?" · "Qual a mensalidade?" · "Tem desconto?"'),
    _regra("P2", "Não envia mensagem para lead que pediu para não ser contatado",
           "A IA não escreve para lead marcado como não contatar. O lead ainda pode escrever.",
           "Qualquer mensagem iniciada pela IA para quem pediu para não ser contatado."),
    _regra("P3", "Não opina sobre o caso concreto do lead", _FRASE_DO_ESPECIALISTA,
           "Opinião sobre regime tributário, crédito, passivo, enquadramento ou questão jurídica do lead.",
           '"Vale a pena sair do Simples?" · "Tenho crédito de PIS/Cofins?"'),
    _regra("P4", "Não promete prazo, resultado ou economia",
           "Isso entra na proposta, depois do levantamento.",
           "Prazo de entrega, economia de imposto, crédito a recuperar ou resultado garantido.",
           '"Em quanto tempo vocês resolvem?" · "Quanto eu economizo?"'),
    _regra("P5", "Não cita, compara ou critica concorrente",
           "Posso explicar como a Critério trabalha, e você compara com o que tem hoje.",
           "Nome de concorrente, comparação ou crítica ao contador atual do lead.",
           '"Vocês são melhores que a minha contabilidade?"'),
    _regra("P6", "Não anuncia a régua do ICP nem as fronteiras entre os produtos",
           "A IA pergunta o porte e o faturamento em aberto e segue o roteiro do serviço.",
           "A régua do ICP (faixa de faturamento atendida) e a diferença entre BPO Financeiro, "
           "BPO Plus e CFO as a Service: são hipóteses em validação.",
           '"Vocês atendem empresa do meu tamanho?"', hipotese=True),
    _regra("P7", "Não apresenta o Módulo de Cenários como software",
           "Usamos uma ferramenta própria para montar os cenários do seu negócio.",
           "Que o Módulo de Cenários é vendido à parte, licenciado ou usado pelo cliente sozinho.",
           '"Vocês vendem o sistema de cenários?"'),
    _regra("P8", "Não diz que a Critério cobra os inadimplentes do cliente",
           "Entregamos o relatório de inadimplência para a sua equipe agir.",
           "Que a Critério faz cobrança ativa dos clientes do lead.",
           '"Vocês cobram os meus clientes atrasados?"'),
    _regra("P9", "Não nomeia clientes da Critério",
           "Atendemos empresas do seu porte e segmento; a equipe pode conversar sobre experiências parecidas.",
           "Nome ou detalhe de qualquer cliente da Critério.",
           '"Quem são os seus clientes?"'),
    _regra("P10", "Não pede dado sensível",
           "Não precisamos disso agora. Na proposta, a equipe combina o envio por um canal seguro.",
           "Pedido de senha, certificado digital, extrato, folha nominal ou documento pessoal."),
    _regra("P11", "Não responde a assunto fora da Critério",
           "Eu ajudo com os serviços da Critério. Sobre isso, não consigo ajudar.",
           "Respostas de assistente geral sobre temas que não são da Critério."),
    _regra("P12", "Não afirma nada que não esteja numa ficha aprovada",
           "Quero te responder com precisão. Vou confirmar com a equipe.",
           "Qualquer fato, número ou promessa sem ficha aprovada que o sustente."),
)

_GATILHOS = (
    _gatilho("T1", "Lead pede uma pessoa", "Claro. Vou passar a conversa para a nossa equipe.",
             "Motivo: Pediu para falar com uma pessoa. Destino: o do serviço.",
             '"Quero falar com alguém" · "Você é um robô?"'),
    _gatilho("T2", "Lead insiste no valor depois da resposta da P1", _FRASE_DO_VALOR,
             "Motivo: Perguntou o preço. Destino: o do serviço."),
    _gatilho("T3", "Grupo com vários CNPJs ou conta grande",
             "Pelo tamanho da operação, quem conduz é um dos nossos sócios.",
             "Motivo: Grupo com vários CNPJs. Destino: Sócios · conta grande."),
    _gatilho("T4", "Pergunta técnica do caso concreto", _FRASE_DO_ESPECIALISTA,
             "Motivo: Dúvida técnica fora do roteiro. Destino: Técnico fiscal, ou o do serviço."),
    _gatilho("T5", "Não existe ficha para a pergunta",
             "Quero te responder com precisão. Vou confirmar com a equipe.",
             "Motivo: Dúvida técnica fora do roteiro. Destino: o do serviço."),
    _gatilho("T6", "Lead irritado ou reclamando",
             "Peço desculpas pelo transtorno. Vou passar a conversa para a nossa equipe agora.",
             "Motivo: Lead irritado. Destino: o do serviço. A IA se desculpa uma vez só."),
    _gatilho("T7", "Integração ou agenda fora do ar",
             "Tive um problema para marcar. A equipe vai falar com você.",
             "Motivo: Sistema externo fora do ar. Destino: Comercial · BPO (C1)."),
    _gatilho("T8", "Serviço sem roteiro",
             "Esse serviço é desenhado caso a caso. Vou passar para quem conduz.",
             'Vale para "Outro", Representante Legal, BPO Plus e CFO as a Service. Motivo: Outro '
             '(proposta: "Serviço sem roteiro"). Destino: Sócios.'),
    _gatilho("T9", "Urgência com prazo legal",
             "Pelo prazo, vou passar agora para um especialista.",
             'Fiscalização, autuação, multa ou prazo de entrega vencendo. Motivo: Outro (proposta: '
             '"Urgência com prazo legal"). Destino: Técnico fiscal.',
             '"Recebi uma intimação da Receita, vence sexta."'),
    _gatilho("T10", "Lead frio pergunta como conseguimos o contato",
             "Vou passar para a nossa equipe, que te explica.",
             "Pendência: o texto da base legal do lead frio ainda está em preparação. Até lá, passa "
             "para Comercial · BPO (C1).",
             '"Como vocês conseguiram meu número?"'),
    _gatilho("T11", "Lead já é cliente da Critério",
             "Vou te encaminhar para a equipe que já cuida da sua empresa.",
             "Motivo: Outro. Destino: Sucesso do Cliente (proposta de destino novo)."),
)

_TOM = (
    FichaInicial("V1", "Apresentação", _V,
                 "Na primeira mensagem, a IA se apresenta como assistente virtual da Critério.",
                 _REVISAO, f"{_DOC}, seções 2 e 5 (03/10/2026)", dono="Eduardo",
                 nunca_dizer="Que é uma pessoa, ou deixar o lead acreditar nisso."),
    FichaInicial("V2", "Vocabulário", _V,
                 'Vende tempo e capacidade de decisão: "Tempo para Crescer", a passagem do '
                 '"Empresário Operador" para o "Empresário Gestor". Diz "Balanço de Abertura".',
                 _REVISAO, f"{_DOC}, seção 5 (03/10/2026)", dono="Eduardo",
                 nunca_dizer='"terceirização de tarefas", "software" (para o serviço), "custo operacional", '
                             '"overhead", "Open Balance", "garantimos", "sem risco", "o mais barato".'),
    FichaInicial("V3", "Estilo", _V,
                 'Português do Brasil, cordial e profissional. Trata o lead por "você", frases curtas, '
                 "no máximo uma pergunta por mensagem sempre que possível.",
                 _REVISAO, f"{_DOC}, seção 5 (03/10/2026)", dono="Eduardo",
                 nunca_dizer="Emojis, gírias, textos longos."),
)

_FSCP_FIXO = "Mapeamento dos processos e controles para fechamento das informações contábeis."


def _servicos() -> tuple[FichaInicial, ...]:
    """Uma ficha por serviço do catálogo, como rascunho: o catálogo ainda é rascunho."""
    fichas = []
    for i, s in enumerate(CATALOGO, start=1):
        para_quem = _FSCP_FIXO if s.nome == "FSCP" else s.para_quem
        texto = para_quem
        if s.fora_do_perfil:
            texto += "\nFora do perfil: " + "; ".join(s.fora_do_perfil) + "."
        fonte = "Catálogo de serviços, rascunho de 27/09/2026"
        if s.nome == "FSCP":
            fonte += ". Texto trocado pela terminologia fixa da Critério (o catálogo diz outra coisa)"
        fichas.append(FichaInicial(
            f"S{i:02d}", s.nome, BlocoDaBase.SERVICOS, texto, _RASCUNHO, fonte,
            servico=s.nome, nunca_dizer="Preço, prazo ou condição comercial.",
        ))
    return tuple(fichas)


_OUTROS = (
    FichaInicial("C1", "Quem é a Critério", BlocoDaBase.CRITERIO,
                 "Consultoria do Rio de Janeiro, com cerca de 30 anos, que cuida da contabilidade, do "
                 "fiscal, do pessoal e do financeiro das empresas, e apoia decisões com consultoria "
                 "tributária, M&A e valuation.",
                 _RASCUNHO, "Contexto da Critério (rascunho de 03/10/2026, a revisar)"),
    FichaInicial("Q1", "Como a IA qualifica", BlocoDaBase.QUALIFICACAO,
                 "A IA identifica o serviço, faz as perguntas do roteiro desse serviço no catálogo e "
                 "pergunta o faturamento em aberto, deixando o lead responder com as palavras dele.",
                 _RASCUNHO, f"{_DOC}, seção 6 (03/10/2026); régua de porte",
                 nunca_dizer="Faixas de faturamento com valores: a trava de preço barra a mensagem.",
                 depende_de_hipotese=True),
)

_REFERENCIAS = (
    FichaInicial("R1", "Speed-to-lead · estudo MIT/InsideSales (2007)", BlocoDaBase.REFERENCIAS,
                 "Lead contatado em até 5 minutos teve 21 vezes mais chance de qualificar do que após "
                 "30 minutos. Seis empresas, mais de 15 mil leads. Estudo antigo: serve de direção, não de meta.",
                 _RASCUNHO, "https://ainora.lt/blog/lead-response-time-5-minutes-study-2026 (consultado em 03/10/2026)"),
    FichaInicial("R2", "Leadster · dados do próprio fornecedor", BlocoDaBase.REFERENCIAS,
                 "635 conversas de dez/2025 a jan/2026: primeira resposta em 0,8 minuto (mediana) e 79,2% "
                 "de qualificado para reunião. Dado do fornecedor, não auditado. Implantação em três "
                 "fases: mapeamento, ativação e otimização contínua.",
                 _RASCUNHO, "https://leadster.com.br/blog/sdr-com-ia/ (consultado em 03/10/2026)"),
    FichaInicial("R3", "HubSpot · base de conhecimento com IA", BlocoDaBase.REFERENCIAS,
                 "Começar pelas perguntas mais frequentes; aprovar antes de publicar; sinalizar fichas "
                 "pouco usadas ou com muito fallback; medir deflexão, fallback e uso.",
                 _RASCUNHO, "https://br.hubspot.com/blog/service/exemplos-bases-de-conhecimento-com-ia (consultado em 03/10/2026)"),
    FichaInicial("R4", "Política do WhatsApp Business para IA", BlocoDaBase.REFERENCIAS,
                 "Desde 15/01/2026 a API do WhatsApp Business proíbe assistentes de IA de uso geral. Bot "
                 "da própria empresa, que atende os clientes dela, continua permitido. Revalidar antes de "
                 "ligar o canal.",
                 _RASCUNHO, "https://gptmaker.ai/proibicao-de-chatbots-no-whatsapp-business/ (consultado em 03/10/2026)"),
    FichaInicial("R5", "Avaliação da base · golden dataset", BlocoDaBase.REFERENCIAS,
                 "Conjunto de perguntas reais com a resposta esperada e a ficha que a sustenta. A medida "
                 "principal é a fidelidade: a resposta precisa estar ancorada na ficha.",
                 _RASCUNHO, "https://dev.to/matheuscamarques/o-fim-do-testado-no-olho-como-automatizar-a-avaliacao-do-seu-rag-ick (consultado em 03/10/2026)"),
    FichaInicial("R6", "Tabela de metas de mercado sem fonte", BlocoDaBase.REFERENCIAS,
                 "Recebida em 03/10/2026: deflexão acima de 70%, alucinação abaixo de 2%, handoff de 15% a "
                 "25%, fallback abaixo de 10%. Sem fonte: não usar como meta. As metas do SDR são as "
                 "aprovadas em 27/09/2026.",
                 _RASCUNHO, "Material colado em chat, sem fonte (03/10/2026)"),
)

FICHAS_INICIAIS: tuple[FichaInicial, ...] = (
    *_REGRAS, *_GATILHOS, *_TOM, *_servicos(), *_OUTROS, *_REFERENCIAS,
)
