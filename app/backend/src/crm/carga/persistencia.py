"""Grava as propostas de 2026 no CRM, e sabe rodar de novo.

Eduardo decidiu em 20/09/2026 **rodar o CRM em paralelo com a planilha**. Isso
muda a natureza da carga: ela não é um evento único, é uma operação repetida.
Cada rodada traz o que mudou na planilha desde a anterior, e não pode duplicar
nada nem apagar o que já existe.

Três princípios governam este módulo:

1. **Identidade pelo conteúdo.** A proposta é reconhecida pela chave de
   `crm.carga.identidade`, nunca pelo número da linha.
2. **Nada muda em silêncio.** Toda alteração de valor entra no relatório, campo
   a campo, com o antes e o depois. Quem confere precisa ver.
3. **Nada é apagado.** Registro que sumiu da planilha permanece no CRM. Sumir
   de uma planilha não é decisão de negócio — pode ser filtro, recorte ou
   engano.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.carga.identidade import chave_de_origem, detectar_duplicatas
from crm.carga.planilha_2026 import Proposta, Relatorio
from crm.db.base import agora
from crm.db.modelos import (
    ExecucaoDeCarga,
    GrupoEconomico,
    OcorrenciaDeCarga,
    Oportunidade,
)
from crm.domain.listas import Origem, SituacaoGrupo, TipoDeOcorrencia

__all__ = [
    "importar",
    "registrar_execucao",
    "ResultadoImportacao",
    "Mudanca",
    "Ocorrencia",
    "CENTAVO",
]

CENTAVO = Decimal("0.01")

#: Campo da oportunidade → como lê-lo da proposta da planilha.
#:
#: `nome` é o único que muda de nome no caminho: na planilha a coluna se chama
#: "Nome da oportunidade" e, enquanto a coluna "Empresa" não for preenchida, é
#: ela que identifica o cliente.
CAMPOS = {
    "nome": "nome_oportunidade",
    "servico": "servico",
    "tipo_servico": "tipo_servico",
    "linha_servico": "linha_servico",
    "tipo_canal": "tipo_canal",
    "canal": "canal",
    "captador": "captador",
    "situacao": "situacao",
    "temperatura": "temperatura",
    "data_colocacao": "data_colocacao",
    "data_aceite": "data_aceite",
    "motivo_recusa": "motivo_recusa",
    "motivo_recusa_original": "motivo_recusa_original",
    "preco_mensal": "preco_mensal",
    "preco_anual": "preco_anual",
    "valor_mensalizado": "valor_mensalizado",
}

CAMPOS_DE_DINHEIRO = {"preco_mensal", "preco_anual", "valor_mensalizado"}


def _legivel(valor: object) -> str:
    """Como um valor aparece para quem confere: 'Aceita', não '<Situacao.ACEITA>'."""
    if valor is None:
        return "vazio"
    return str(getattr(valor, "value", valor))


@dataclass(frozen=True)
class Ocorrencia:
    """Uma linha do relatório, já classificada pelo que pede de quem lê."""

    tipo: TipoDeOcorrencia
    linha: int | None
    campo: str | None
    texto: str


@dataclass(frozen=True)
class Mudanca:
    """Um valor que a recarga alterou."""

    linha: int
    nome: str
    campo: str
    de: object
    para: object

    @property
    def texto(self) -> str:
        return (
            f"linha {self.linha} · {self.nome} · {self.campo}: "
            f"{_legivel(self.de)} → {_legivel(self.para)}"
        )


@dataclass
class ResultadoImportacao:
    """O que a carga fez, para uma pessoa conferir antes de confiar."""

    criadas: int = 0
    atualizadas: int = 0
    inalteradas: int = 0
    ignoradas_incompletas: int = 0
    ignoradas_duplicatas: int = 0
    grupos_criados: int = 0
    grupos_reaproveitados: int = 0
    mudancas: list[Mudanca] = field(default_factory=list)
    ocorrencias: list[Ocorrencia] = field(default_factory=list)

    @property
    def avisos(self) -> list[str]:
        """Os textos das ocorrências, para quem só quer ler a lista."""
        return [o.texto for o in self.ocorrencias]

    @property
    def total_gravado(self) -> int:
        return self.criadas + self.atualizadas + self.inalteradas

    def resumo(self) -> str:
        linhas = [
            f"Oportunidades criadas:      {self.criadas}",
            f"Atualizadas:                {self.atualizadas}",
            f"Sem mudança:                {self.inalteradas}",
            f"Ignoradas, incompletas:     {self.ignoradas_incompletas}",
            f"Ignoradas, duplicatas:      {self.ignoradas_duplicatas}",
            f"Grupos econômicos criados:  {self.grupos_criados}",
            f"Grupos reaproveitados:      {self.grupos_reaproveitados}",
        ]
        if self.mudancas:
            linhas += ["", f"Mudanças ({len(self.mudancas)}):"]
            linhas += [f"  {m.texto}" for m in self.mudancas]
        if self.avisos:
            linhas += ["", f"Avisos ({len(self.avisos)}):"]
            linhas += [f"  {a}" for a in self.avisos]
        return "\n".join(linhas)


def _em_centavos(valor: Decimal | None) -> Decimal | None:
    """Arredonda para centavos, que é a precisão de dinheiro.

    A planilha traz valores com até dez casas — resíduo de fórmula, não preço.
    Quem chama avisa quando o arredondamento muda o número.
    """
    if valor is None:
        return None
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _valor_da_proposta(proposta: Proposta, campo: str):
    bruto = getattr(proposta, CAMPOS[campo])
    return _em_centavos(bruto) if campo in CAMPOS_DE_DINHEIRO else bruto


def _grupo_para(
    sessao: Session, nome: str, cache: dict[str, GrupoEconomico], resultado: ResultadoImportacao
) -> GrupoEconomico:
    """Acha ou cria o grupo econômico desta proposta.

    **Propostas com o mesmo nome de cliente compartilham o grupo.** Não é o
    de-para completo que Eduardo ainda vai fazer à mão — é o agrupamento que o
    próprio dado sustenta sem ninguém decidir nada: se duas linhas dizem o mesmo
    nome, são o mesmo cliente. Nas 157 propostas isso reduz de 157 para 141
    grupos, e as fusões restantes ficam para `crm.db.grupos.fundir_grupos`.
    """
    chave = " ".join(nome.casefold().split())
    if chave in cache:
        resultado.grupos_reaproveitados += 1
        return cache[chave]

    existente = sessao.scalar(
        sa.select(GrupoEconomico).where(
            sa.func.lower(GrupoEconomico.nome) == nome.casefold(),
            GrupoEconomico.fundido_em_id.is_(None),
        )
    )
    if existente is not None:
        cache[chave] = existente
        resultado.grupos_reaproveitados += 1
        return existente

    grupo = GrupoEconomico(
        nome=nome, situacao=SituacaoGrupo.PROSPECT, origem=Origem.CARGA_2026
    )
    sessao.add(grupo)
    sessao.flush()
    cache[chave] = grupo
    resultado.grupos_criados += 1
    return grupo


def importar(sessao: Session, propostas: Iterable[Proposta]) -> ResultadoImportacao:
    """Grava as propostas, criando o que falta e atualizando o que mudou.

    Pode ser chamada quantas vezes for preciso sobre a mesma planilha: a
    segunda chamada não cria nada e não altera nada.
    """
    propostas = list(propostas)
    resultado = ResultadoImportacao()

    # Duplicatas: a primeira linha entra, as seguintes ficam de fora com aviso.
    # Importar as duas inflaria contagem e valor do funil — e escolher qual vale
    # não é decisão de código.
    linhas_duplicadas: set[int] = set()
    for duplicata in detectar_duplicatas(propostas):
        linhas_duplicadas.update(duplicata.linhas[1:])
        resultado.ocorrencias.append(
            Ocorrencia(
                TipoDeOcorrencia.PENDENCIA,
                duplicata.linhas[0],
                "linha duplicada",
                duplicata.texto,
            )
        )

    cache_de_grupos: dict[str, GrupoEconomico] = {}

    for proposta in propostas:
        if not proposta.completa:
            resultado.ignoradas_incompletas += 1
            resultado.ocorrencias.append(
                Ocorrencia(
                    TipoDeOcorrencia.PENDENCIA,
                    proposta.linha,
                    "linha incompleta",
                    "sem nome ou sem situação — não vira oportunidade",
                )
            )
            continue

        if proposta.linha in linhas_duplicadas:
            resultado.ignoradas_duplicatas += 1
            continue

        for campo in CAMPOS_DE_DINHEIRO:
            bruto = getattr(proposta, campo)
            if bruto is not None and _em_centavos(bruto) != bruto:
                resultado.ocorrencias.append(
                    Ocorrencia(
                        TipoDeOcorrencia.AJUSTE,
                        proposta.linha,
                        campo,
                        f"{bruto} arredondado para {_em_centavos(bruto)} — "
                        f"planilha traz resíduo de fórmula",
                    )
                )

        chave = chave_de_origem(proposta)
        existente = sessao.scalar(
            sa.select(Oportunidade).where(Oportunidade.chave_origem == chave)
        )

        if existente is None:
            grupo = _grupo_para(sessao, proposta.nome_oportunidade, cache_de_grupos, resultado)
            sessao.add(
                Oportunidade(
                    grupo_id=grupo.id,
                    origem=Origem.CARGA_2026,
                    chave_origem=chave,
                    linha_planilha=proposta.linha,
                    **{campo: _valor_da_proposta(proposta, campo) for campo in CAMPOS},
                )
            )
            resultado.criadas += 1
            continue

        # A posição na aba é ponteiro, não dado de negócio: acompanha a planilha
        # sempre, sem contar como mudança. Se ficasse parada, o relatório de
        # conferência mandaria quem confere para a linha errada.
        existente.linha_planilha = proposta.linha

        editados_no_crm = set(existente.campos_do_crm or [])
        mudancas = []
        for campo in CAMPOS:
            novo = _valor_da_proposta(proposta, campo)
            atual = getattr(existente, campo)
            if novo == atual:
                continue
            if campo in editados_no_crm:
                # Uma pessoa mudou este campo aqui. A planilha discorda, e a
                # decisão de qual vale é dela — não da carga. Mantém o do CRM e
                # deixa a divergência à vista, em vez de sobrescrever calada.
                resultado.ocorrencias.append(
                    Ocorrencia(
                        TipoDeOcorrencia.PENDENCIA,
                        proposta.linha,
                        campo,
                        f"{proposta.nome_oportunidade}: a planilha diz "
                        f"{_legivel(novo)}, mas o CRM tem {_legivel(atual)} "
                        f"(editado aqui) — mantido o do CRM",
                    )
                )
                continue
            mudancas.append(
                Mudanca(
                    linha=proposta.linha,
                    nome=proposta.nome_oportunidade,
                    campo=campo,
                    de=atual,
                    para=novo,
                )
            )

        if not mudancas:
            resultado.inalteradas += 1
            continue

        for mudanca in mudancas:
            setattr(existente, mudanca.campo, mudanca.para)
        resultado.mudancas.extend(mudancas)
        resultado.atualizadas += 1

    sessao.flush()
    return resultado


def registrar_execucao(
    sessao: Session,
    arquivo: str,
    leitura: Relatorio,
    resultado: ResultadoImportacao,
) -> ExecucaoDeCarga:
    """Guarda a rodada como o relatório de conferência que a tela mostra.

    Junta duas fontes com olhares diferentes sobre a mesma planilha: a **leitura**
    (o que havia nas células e como foi normalizado) e a **gravação** (o que
    entrou no CRM e o que mudou). Cada linha vira uma ocorrência classificada
    pelo que pede de quem lê — pendência, ajuste ou mudança.
    """
    ocorrencias: list[Ocorrencia] = []

    for aviso in leitura.avisos:
        # Pede uma pessoa quando não converteu (bloqueia) ou quando entrou
        # incompleto e só alguém completa (acao_humana). O resto foi ajustado
        # sozinho — e é justamente o que a pessoa quer poder conferir.
        tipo = (
            TipoDeOcorrencia.PENDENCIA
            if aviso.bloqueia or aviso.acao_humana
            else TipoDeOcorrencia.AJUSTE
        )
        ocorrencias.append(Ocorrencia(tipo, aviso.linha, aviso.campo, aviso.texto))

    # A leitura já diz por que uma linha ficou de fora. Repetir a consequência
    # ("não vira oportunidade") contaria a mesma linha duas vezes.
    ja_pendentes = {
        o.linha for o in ocorrencias if o.tipo is TipoDeOcorrencia.PENDENCIA
    }
    for ocorrencia in resultado.ocorrencias:
        if ocorrencia.campo == "linha incompleta" and ocorrencia.linha in ja_pendentes:
            continue
        ocorrencias.append(ocorrencia)

    for mudanca in resultado.mudancas:
        ocorrencias.append(
            Ocorrencia(
                TipoDeOcorrencia.MUDANCA,
                mudanca.linha,
                mudanca.campo,
                f"{mudanca.nome}: {_legivel(mudanca.de)} → {_legivel(mudanca.para)}",
            )
        )

    execucao = ExecucaoDeCarga(
        executada_em=agora(),
        arquivo=arquivo.replace("\\", "/").rsplit("/", 1)[-1],
        lidas=leitura.total_lidas,
        de_outro_ano=leitura.descartadas_outro_ano,
        residuais=leitura.descartadas_residuais,
        importadas=leitura.importadas,
        criadas=resultado.criadas,
        atualizadas=resultado.atualizadas,
        inalteradas=resultado.inalteradas,
        ignoradas_incompletas=resultado.ignoradas_incompletas,
        ignoradas_duplicatas=resultado.ignoradas_duplicatas,
        grupos_criados=resultado.grupos_criados,
        grupos_reaproveitados=resultado.grupos_reaproveitados,
        ocorrencias=[
            OcorrenciaDeCarga(tipo=o.tipo, linha=o.linha, campo=o.campo, texto=o.texto)
            for o in ocorrencias
        ],
    )
    sessao.add(execucao)
    sessao.flush()
    return execucao
