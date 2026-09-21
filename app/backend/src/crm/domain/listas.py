"""Listas controladas do funil comercial e a normalização da planilha de 2026.

A planilha registra estes campos em texto livre, e o mesmo conceito aparece
escrito de várias formas: "Socio" e "Sócios", "Enviar proposta" e
"Enviar Proposta". Aqui cada conceito tem um valor só, e o de-para converte o
que veio da planilha.

⚠️ As listas são **proposta**, autorizada por Eduardo em 19/09/2026 ("pode
propor"), e ainda não aprovadas. Mudar um valor é mudar este módulo e a carga.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Situacao",
    "SituacaoLead",
    "SituacaoGrupo",
    "SituacaoEmpresa",
    "PapelContato",
    "Origem",
    "TipoDeOcorrencia",
    "TipoCanal",
    "Temperatura",
    "LinhaServico",
    "MotivoRecusa",
    "Normalizacao",
    "normalizar_situacao",
    "normalizar_tipo_canal",
    "normalizar_temperatura",
    "normalizar_linha_servico",
    "normalizar_motivo_recusa",
    "normalizar_captador",
]


def _chave(texto: str | None) -> str:
    """Reduz o texto à sua forma comparável: sem acento, sem caixa, sem sobra."""
    if texto is None:
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


class Situacao(Enum):
    """Onde a oportunidade está no funil."""

    ENVIAR_PROPOSTA = "Enviar proposta"
    EM_AVALIACAO = "Em avaliação pela empresa"
    ON_HOLD = "On hold"
    ACEITA = "Aceita"
    RECUSADA = "Recusada"
    PERDIDO = "Perdido"

    @property
    def decidida(self) -> bool:
        """Situação terminal — entra no denominador da taxa de conversão.

        ⚠️ Qual denominador usar é **decisão pendente** de Eduardo: só as
        decididas (38% em 2026) ou todas as trabalhadas (26%). Esta propriedade
        marca o conceito; o indicador não é calculado aqui.
        """
        return self in {Situacao.ACEITA, Situacao.RECUSADA, Situacao.PERDIDO}

    @property
    def ganha(self) -> bool:
        return self is Situacao.ACEITA


class SituacaoLead(Enum):
    """Onde o lead está antes de virar oportunidade.

    ⚠️ **Proposta.** O funil de lead não existe na planilha de 2026 — ela começa
    na proposta já enviada. Estes cinco estados saem do desenho aprovado em
    19/09/2026 e ainda não foram usados por ninguém.
    """

    NOVO = "Novo"
    EM_CONTATO = "Em contato"
    QUALIFICADO = "Qualificado"
    CONVERTIDO = "Convertido"
    DESCARTADO = "Descartado"

    @property
    def aberto(self) -> bool:
        return self in {SituacaoLead.NOVO, SituacaoLead.EM_CONTATO, SituacaoLead.QUALIFICADO}


class SituacaoGrupo(Enum):
    """O que o grupo econômico é para a Critério hoje.

    ``FUNDIDO`` é o estado de um grupo que se revelou parte de outro. Ele não é
    apagado: a arquitetura proíbe exclusão física. Fica apontando para quem o
    absorveu, e o histórico continua legível.
    """

    PROSPECT = "Prospect"
    CLIENTE = "Cliente"
    ENCERRADO = "Encerrado"
    FUNDIDO = "Fundido"

    @property
    def ativo(self) -> bool:
        return self in {SituacaoGrupo.PROSPECT, SituacaoGrupo.CLIENTE}


class SituacaoEmpresa(Enum):
    ATIVA = "Ativa"
    INATIVA = "Inativa"
    BAIXADA = "Baixada"


class PapelContato(Enum):
    """Para que serve falar com esta pessoa."""

    DECISOR = "Decisor"
    INFLUENCIADOR = "Influenciador"
    USUARIO = "Usuário"
    PONTO_FOCAL = "Ponto focal"


class Origem(Enum):
    """De onde o registro veio.

    Distingue o que a carga trouxe do que nasceu no CRM. Enquanto a planilha e o
    CRM rodarem em paralelo — decisão de Eduardo em 20/09/2026 — essa diferença
    é o que permite recarregar sem atropelar o que foi digitado aqui.
    """

    CARGA_2026 = "Carga 2026"
    CRM = "CRM"


class TipoDeOcorrencia(Enum):
    """O que uma linha do relatório de conferência pede de quem lê.

    Três tipos, pensados para a pergunta de quem confere a carga: *o que ficou
    pendente, o que foi corrigido, o que mudou?* Mais categorias que isso
    obrigariam a pessoa a decorar a taxonomia antes de conseguir conferir.
    """

    PENDENCIA = "Precisa de você"
    AJUSTE = "Ajustado sozinho"
    MUDANCA = "Mudou na recarga"


class TipoCanal(Enum):
    """Primeira camada da origem: a categoria de quem trouxe o lead."""

    SOCIOS = "Sócios"
    PARCEIROS = "Parceiros"
    ADVOGADOS = "Advogados"
    CARTEIRA = "Carteira"
    INTERNO = "Interno"
    COLABORADORES = "Colaboradores"
    TRAFEGO_PAGO = "Tráfego pago"
    AFILIADOS = "Afiliados"

    @property
    def em_operacao(self) -> bool:
        """Tráfego pago e afiliados são desejo, ainda sem operação.

        Existem na lista desde já para que o indicador de origem possa medir a
        redução da dependência de sócios a partir do primeiro lead.
        """
        return self not in {TipoCanal.TRAFEGO_PAGO, TipoCanal.AFILIADOS}


class Temperatura(Enum):
    FRIO = "Frio"
    MORNO = "Morno"
    QUENTE = "Quente"


class LinhaServico(Enum):
    """C1 e C2, como a planilha registra."""

    C1 = "C1"
    C2 = "C2"

    @property
    def descricao(self) -> str:
        return {
            LinhaServico.C1: "BPO contábil, fiscal e departamento pessoal",
            LinhaServico.C2: "Consultorias em geral",
        }[self]


class MotivoRecusa(Enum):
    """Por que a oportunidade não avançou.

    A planilha mistura motivo com situação — "Em formalização" e "Em avaliação
    pela empresa" não são motivos de recusa, são estados. O de-para separa os
    dois e devolve um aviso.
    """

    PRECO = "Preço"
    SEM_RETORNO = "Sem retorno"
    DESISTENCIA = "Desistência"
    CLIENTE_INTERNALIZOU = "Cliente internalizou"
    CONCORRENCIA = "Concorrência"
    MOMENTO = "Momento"
    ESCOPO = "Escopo"
    PRO_BONO = "Pro bono"
    OUTRO = "Outro"


@dataclass(frozen=True)
class Normalizacao[T]:
    """O resultado de converter um valor da planilha.

    `valor` é ``None`` quando o texto não corresponde a nenhum item da lista.
    `aviso` explica o que aconteceu e alimenta o relatório de conferência da
    carga — nada é descartado em silêncio.
    """

    valor: T | None
    original: str | None
    aviso: str | None = None

    @property
    def ok(self) -> bool:
        return self.valor is not None

    @property
    def ajustado(self) -> bool:
        """Converteu, mas o texto de origem não era o valor canônico."""
        return self.ok and self.aviso is not None


_SITUACAO: dict[str, Situacao] = {
    "enviar proposta": Situacao.ENVIAR_PROPOSTA,
    "em avaliacao pela empresa": Situacao.EM_AVALIACAO,
    "em avaliacao": Situacao.EM_AVALIACAO,
    "on hold": Situacao.ON_HOLD,
    "aceita": Situacao.ACEITA,
    "aceito": Situacao.ACEITA,
    "recusada": Situacao.RECUSADA,
    "recusado": Situacao.RECUSADA,
    "perdido": Situacao.PERDIDO,
    "perdida": Situacao.PERDIDO,
}

_TIPO_CANAL: dict[str, TipoCanal] = {
    "socio": TipoCanal.SOCIOS,
    "socios": TipoCanal.SOCIOS,
    "parceiro": TipoCanal.PARCEIROS,
    "parceiros": TipoCanal.PARCEIROS,
    "advogado": TipoCanal.ADVOGADOS,
    "advogados": TipoCanal.ADVOGADOS,
    "carteira": TipoCanal.CARTEIRA,
    "interno": TipoCanal.INTERNO,
    "colaborador": TipoCanal.COLABORADORES,
    "colaboradores": TipoCanal.COLABORADORES,
    "trafego pago": TipoCanal.TRAFEGO_PAGO,
    "afiliado": TipoCanal.AFILIADOS,
    "afiliados": TipoCanal.AFILIADOS,
}

_TEMPERATURA: dict[str, Temperatura] = {
    "frio": Temperatura.FRIO,
    "morno": Temperatura.MORNO,
    "quente": Temperatura.QUENTE,
}

_LINHA: dict[str, LinhaServico] = {"c1": LinhaServico.C1, "c2": LinhaServico.C2}

_MOTIVO: dict[str, MotivoRecusa] = {
    "preco": MotivoRecusa.PRECO,
    "sem retorno": MotivoRecusa.SEM_RETORNO,
    "nao nos retornou": MotivoRecusa.SEM_RETORNO,
    "desistencia": MotivoRecusa.DESISTENCIA,
    "possivel desistencia": MotivoRecusa.DESISTENCIA,
    "cliente internalizou": MotivoRecusa.CLIENTE_INTERNALIZOU,
    "concorrencia": MotivoRecusa.CONCORRENCIA,
    "momento": MotivoRecusa.MOMENTO,
    "escopo": MotivoRecusa.ESCOPO,
    "pro-bono": MotivoRecusa.PRO_BONO,
    "pro bono": MotivoRecusa.PRO_BONO,
}

# Textos que a planilha registra como motivo de recusa, mas que descrevem a
# situação da oportunidade. Não viram motivo: viram aviso.
_MOTIVO_E_SITUACAO: dict[str, Situacao] = {
    "em formalizacao": Situacao.ACEITA,
    "em avaliacao pela empresa": Situacao.EM_AVALIACAO,
    "proposta reajustada": Situacao.ENVIAR_PROPOSTA,
}

# Captadores. "AN" aparece no histórico anterior a 2026 e ninguém soube dizer
# quem é; Eduardo determinou em 19/09/2026 que seja convertido para "BO".
_CAPTADOR_DEPARA: dict[str, str] = {"an": "BO"}
_CAPTADORES = {"BO", "EL", "TC", "FS", "JC", "MO", "JS"}


def _converter[T](
    bruto: str | None, tabela: dict[str, T], nome_do_campo: str
) -> Normalizacao[T]:
    chave = _chave(bruto)
    if not chave:
        return Normalizacao(None, bruto, f"{nome_do_campo} vazio")
    valor = tabela.get(chave)
    if valor is None:
        return Normalizacao(None, bruto, f"{nome_do_campo} fora da lista: {bruto!r}")
    canonico = getattr(valor, "value", valor)
    if str(bruto) != str(canonico):
        return Normalizacao(valor, bruto, f"{bruto!r} convertido para {canonico!r}")
    return Normalizacao(valor, bruto)


def normalizar_situacao(bruto: str | None) -> Normalizacao[Situacao]:
    return _converter(bruto, _SITUACAO, "situação")


def normalizar_tipo_canal(bruto: str | None) -> Normalizacao[TipoCanal]:
    return _converter(bruto, _TIPO_CANAL, "tipo de canal")


def normalizar_temperatura(bruto: str | None) -> Normalizacao[Temperatura]:
    return _converter(bruto, _TEMPERATURA, "temperatura")


def normalizar_linha_servico(bruto: str | None) -> Normalizacao[LinhaServico]:
    return _converter(bruto, _LINHA, "linha de serviço")


def normalizar_motivo_recusa(bruto: str | None) -> Normalizacao[MotivoRecusa]:
    """Converte o motivo, separando o que na verdade é situação."""
    chave = _chave(bruto)
    if not chave:
        return Normalizacao(None, bruto, "motivo de recusa vazio")
    situacao = _MOTIVO_E_SITUACAO.get(chave)
    if situacao is not None:
        return Normalizacao(
            None,
            bruto,
            f"{bruto!r} descreve situação, não motivo — "
            f"conferir se a situação é {situacao.value!r}",
        )
    return _converter(bruto, _MOTIVO, "motivo de recusa")


def normalizar_captador(bruto: str | None) -> Normalizacao[str]:
    """Converte as iniciais do responsável pela captação."""
    chave = _chave(bruto)
    if not chave:
        return Normalizacao(None, bruto, "captador vazio")
    destino = _CAPTADOR_DEPARA.get(chave)
    if destino is not None:
        return Normalizacao(
            destino, bruto, f"{bruto!r} convertido para {destino!r} por decisão de Eduardo"
        )
    sigla = chave.upper()
    if sigla not in _CAPTADORES:
        return Normalizacao(None, bruto, f"captador desconhecido: {bruto!r}")
    if str(bruto) != sigla:
        return Normalizacao(sigla, bruto, f"{bruto!r} convertido para {sigla!r}")
    return Normalizacao(sigla, bruto)
