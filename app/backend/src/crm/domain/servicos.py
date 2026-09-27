"""O catálogo de serviços da Critério — 27/09/2026.

Lista aprovada por Eduardo em 27/09/2026, com a regra das linhas: **C1 é
recorrente, C2 não é recorrente**. A linha deixa de ser digitada: sai do
serviço, no passado (planilha e dados já carregados) e daqui para frente.

O catálogo aparece no pop-up da Nova oportunidade e na qualificação do lead,
e é o roteiro que o SDR de IA segue. Por isso **não tem preço**: a IA não
informa preço, e o catálogo não dá número para ela repetir.

⚠️ Os textos de "para quem é", "fora do perfil" e "passa para" são
**rascunho**, aprovado para construir e ainda a revisar com Eduardo.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from crm.domain.listas import DestinoDoTransbordo, LinhaServico

__all__ = [
    "Pergunta", "Servico", "CATALOGO", "OUTRO", "DESCRICAO_MINIMA",
    "linha_do_servico", "servico_do_catalogo", "problema_na_descricao",
]

#: O serviço fora do catálogo (27/09/2026). A pessoa descreve o que o lead pediu,
#: com as palavras dele, e a linha fica **sem definir** ("Ainda não sei") até
#: Eduardo decidir se o serviço entra no catálogo. Não tem roteiro: o SDR de IA
#: passa a conversa para a equipe.
OUTRO = "Outro"
DESCRICAO_MINIMA = 10


@dataclass(frozen=True)
class Pergunta:
    texto: str
    direcionador: str | None = None
    """Campo da régua de porte (`crm.domain.porte.DIRECIONADORES`) que a
    pergunta preenche, quando preenche um."""


@dataclass(frozen=True)
class Servico:
    nome: str
    linha: LinhaServico
    para_quem: str
    perguntas: tuple[Pergunta, ...]
    fora_do_perfil: tuple[str, ...]
    transbordo: DestinoDoTransbordo
    nome_por_extenso: str | None = None
    nomes_antigos: tuple[str, ...] = field(default=())
    """Como a planilha escrevia o serviço antes do catálogo."""
    rascunho: bool = True


_DOCS = Pergunta("Documentos fiscais por mês (emitidas + recebidas)", "documentos_fiscais_mes")
_LANC = Pergunta("Lançamentos contábeis por mês", "lancamentos_contabeis_mes")
_CLT = Pergunta("Empregados CLT", "empregados_clt")
_ADM = Pergunta("Admissões + desligamentos por mês", "admissoes_desligamentos_mes")
_CNPJ = Pergunta("CNPJs no escopo", "cnpjs_no_escopo")
_TOMADORES = Pergunta("Tomadores de serviço", "tomadores_de_servico")
_REGIME = Pergunta("Regime tributário")

C1, C2 = LinhaServico.C1, LinhaServico.C2
BPO = DestinoDoTransbordo.COMERCIAL_C1
CONSULTORIA = DestinoDoTransbordo.CONSULTORIA_C2

CATALOGO: tuple[Servico, ...] = (
    Servico(
        "BPO Contábil, Fiscal e Dep. Pessoal", C1,
        "Empresa que quer terceirizar contabilidade, fiscal e folha juntos, com um fornecedor só.",
        (_DOCS, _LANC, _CLT, _ADM, _CNPJ, _REGIME),
        ("MEI", "Porte abaixo do mínimo", "Quer só a folha: é Dep. Pessoal"),
        BPO,
        nomes_antigos=("BPO Contábil",),
    ),
    Servico(
        "BPO Contábil e Fiscal", C1,
        "Empresa que quer terceirizar contabilidade e fiscal, e mantém a folha em outro lugar.",
        (_DOCS, _LANC, _CNPJ, _TOMADORES, _REGIME),
        ("MEI", "Porte abaixo do mínimo"),
        BPO,
    ),
    Servico(
        "Dep. Pessoal", C1,
        "Empresa que quer terceirizar só a folha e as rotinas trabalhistas.",
        (_CLT, _ADM, _CNPJ, Pergunta("Sindicato ou convenção da categoria")),
        ("Nenhum empregado CLT",),
        BPO,
    ),
    Servico(
        "BPO Financeiro", C1,
        "Empresa que quer terceirizar contas a pagar, a receber e conciliação.",
        (
            Pergunta("Pagamentos por mês", "pagamentos_mes"),
            Pergunta("Contas bancárias", "contas_bancarias"),
            Pergunta("Conciliações de cartão por mês", "conciliacoes_cartao_mes"),
        ),
        ("Movimento tão pequeno que não justifica rotina mensal",),
        BPO,
    ),
    Servico(
        "Endereço Fiscal", C1,
        "Empresa que precisa de endereço fiscal ou sede em cidade onde não tem escritório.",
        (
            Pergunta("Cidade e UF do endereço"),
            Pergunta("A empresa já tem CNPJ ou vai abrir"),
            Pergunta("Recebe correspondência física"),
        ),
        (),
        BPO,
    ),
    Servico(
        "Representante Legal", C1,
        "A escrever com Eduardo: o que o serviço cobre e para quem é.",
        (Pergunta("A escrever com Eduardo"),),
        (),
        DestinoDoTransbordo.SOCIOS,
        nomes_antigos=("Representação",),
    ),
    Servico(
        "Consultoria", C2,
        "Projeto com começo e fim: planejamento tributário, reorganização, diagnóstico.",
        (
            Pergunta("Qual é o tema ou o problema"),
            Pergunta("Prazo que a empresa tem"),
            Pergunta("Quem decide a contratação"),
            _CNPJ,
        ),
        ("Quer resposta pontual sem contratar um projeto",),
        CONSULTORIA,
    ),
    Servico(
        "Legalização Empresarial", C2,
        "Abrir, alterar ou encerrar empresa, e regularizar cadastros.",
        (Pergunta("Abrir, alterar ou encerrar"), Pergunta("UF e município"), _CNPJ),
        (),
        CONSULTORIA,
        nomes_antigos=("Legalização",),
    ),
    Servico(
        "Auditoria", C2,
        "Auditoria das demonstrações, obrigatória ou voluntária.",
        (
            Pergunta("Obrigatória ou voluntária"),
            Pergunta("Exercício a auditar"),
            Pergunta("Prazo de entrega"),
            _CNPJ,
        ),
        (),
        CONSULTORIA,
    ),
    Servico(
        "FSCP", C2,
        "Fechamento das demonstrações financeiras com procedimento definido.",
        (Pergunta("Data de fechamento"), Pergunta("Sistema contábil usado"), _LANC, _CNPJ),
        (),
        CONSULTORIA,
        nome_por_extenso="Finance Statement Closing Procedure",
    ),
)


def _chave(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


_POR_NOME: dict[str, Servico] = {}
for _servico in CATALOGO:
    for _nome in (_servico.nome, *_servico.nomes_antigos):
        _POR_NOME[_chave(_nome)] = _servico


def servico_do_catalogo(nome: str | None) -> Servico | None:
    """O serviço do catálogo com esse nome, atual ou antigo. Sem acento e sem
    caixa: "endereço fiscal" e "Endereço Fiscal" são o mesmo."""
    return _POR_NOME.get(_chave(nome))


def linha_do_servico(nome: str | None) -> LinhaServico | None:
    """C1 ou C2 pelo serviço. `None` quando o serviço não está no catálogo:
    quem chama decide o que fazer (a carga mantém a coluna da planilha)."""
    servico = servico_do_catalogo(nome)
    return servico.linha if servico else None


def problema_na_descricao(servico: str | None, descricao: str | None) -> str | None:
    """"Outro" exige a descrição; os serviços do catálogo não levam descrição."""
    texto = (descricao or "").strip()
    if (servico or "").strip() == OUTRO:
        if len(texto) < DESCRICAO_MINIMA:
            return f'para "Outro", descreva o serviço que o lead pediu (ao menos {DESCRICAO_MINIMA} caracteres)'
        return None
    if texto:
        return 'a descrição do serviço só vale para "Outro"'
    return None

