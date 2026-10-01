"""Das respostas do questionário ao que o CRM usa: volumetria, fatores de complexidade e de risco,
pontos de atenção.

As regras de **porte e de nota** são as do CRM (`crm.domain.porte`, `crm.domain.avaliacao`): o
questionário traz um cálculo próprio em JavaScript, que fica só para comparação. As regras de
**leitura** (qual resposta acende qual fator) são as do formulário publicado, versão "BPO Full 2026
v6", copiadas daqui: mudou o formulário, muda este módulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from crm.domain import avaliacao as regra_de_avaliacao
from crm.domain import porte as regras_de_porte

__all__ = ["Leitura", "ler", "inteiro_ou_nada", "ROTULOS_COMPLEXIDADE", "ROTULOS_RISCO", "SERVICOS"]

SERVICOS = ("Contábil", "Fiscal", "Folha / DP", "Financeiro")

ROTULOS_COMPLEXIDADE = {
    "holding": "holding com consolidação",
    "centros_de_custo": "centros de custo ou rateio entre unidades",
    "plano_de_contas": "plano de contas customizado",
    "auditoria": "auditoria externa",
    "regimes": "mais de um regime tributário",
    "parcelamento_complexidade": "parcelamento tributário ativo",
}
ROTULOS_RISCO = {
    "auto_de_infracao": "auto de infração ou processo fiscal",
    "parcelamento_atraso": "parcelamento em atraso ou já quebrado",
    "obrigacao_atrasada": "obrigação acessória atrasada (3 meses)",
    "certificado_vencendo": "certificado digital vence em até 60 dias",
}
PARCELAMENTO_EM_ATRASO = "Em atraso, ou já quebrado antes"


@dataclass(frozen=True)
class Leitura:
    volumetria: dict[str, int | None]
    """Os nove direcionadores, nos nomes do CRM. `None` = não informado: fica fora da média."""
    servicos: list[str]
    servicos_contratados_alem_do_primeiro: int
    tem_consolidacao_de_grupo: bool
    e_auditada: bool
    porte: str | None
    """Sugestão da régua do CRM; `None` sem nenhum direcionador."""
    pontuacao: str | None
    horas_base: int | None
    fatores_complexidade: list[str]
    nota_complexidade: int
    fatores_risco: list[str]
    nota_risco: int
    pontos_de_atencao: list[tuple[str, str]] = field(default_factory=list)
    """(texto, área), como o formulário mostra no resumo."""
    regimes: list[str] = field(default_factory=list)


def _tem(r: dict[str, Any], campo: str, valor: str) -> bool:
    v = r.get(campo)
    return valor in v if isinstance(v, list) else v == valor


def inteiro_ou_nada(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:  # como o Math.round do formulário: 0,5 sobe (o round do Python arredondaria para o par)
        return max(0, int(Decimal(str(v)).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    except (InvalidOperation, ValueError):
        return None


def _soma(a: int | None, b: int | None) -> int | None:
    return None if a is None and b is None else (a or 0) + (b or 0)


def _volumetria(r: dict[str, Any]) -> dict[str, int | None]:
    vol = r.get("vol") or {}
    n = lambda k: inteiro_ou_nada(vol.get(k))  # noqa: E731
    return {
        "documentos_fiscais_mes": _soma(n("notas_emitidas"), n("notas_recebidas")),
        "lancamentos_contabeis_mes": n("lancamentos"),
        "pagamentos_mes": n("pagamentos"),
        "contas_bancarias": n("contas_bancarias"),
        "conciliacoes_cartao_mes": n("conciliacoes_cartao"),
        "empregados_clt": n("empregados_clt"),
        "admissoes_desligamentos_mes": _soma(n("admissoes"), n("desligamentos")),
        "cnpjs_no_escopo": n("cnpjs"),
        "tomadores_de_servico": n("tomadores"),
    }


def ler(respostas: dict[str, Any], *, recebido_em: date) -> Leitura:
    """`recebido_em` é a data do envio: o "certificado vence em 60 dias" vale para aquele dia."""
    r = respostas or {}
    servicos = [s for s in (r.get("servicos") or []) if isinstance(s, str)]
    consolidacao = _tem(r, "relatorios", "Consolidação")
    auditada = _tem(r, "auditada", "Sim")
    volumetria = _volumetria(r)
    alem = max(0, len(servicos) - 1)
    sugestao = regras_de_porte.sugerir_porte(regras_de_porte.Volumetria(
        **volumetria, servicos_contratados_alem_do_primeiro=alem,
        tem_consolidacao_de_grupo=consolidacao, e_auditada=auditada,
    ))

    regimes = [x for x in (r.get("regime_tributario") or []) if isinstance(x, str) and x != "Outro"]
    passivos = _tem(r, "passivos", "Sim")
    cx = []
    if consolidacao:
        cx.append("holding")
    if _tem(r, "folha_rateio", "Sim") or _tem(r, "relatorios", "DRE por centro/projeto"):
        cx.append("centros_de_custo")
    if _tem(r, "plano_contas", "Sim"):
        cx.append("plano_de_contas")
    if auditada:
        cx.append("auditoria")
    if len(regimes) > 1:
        cx.append("regimes")
    if passivos and (_tem(r, "passivos_tipos", "Parcelamento") or r.get("parcelamento_situacao")):
        cx.append("parcelamento_complexidade")

    rk = []
    if passivos and (_tem(r, "passivos_tipos", "Auto de infração") or _tem(r, "passivos_tipos", "Processo tributário")):
        rk.append("auto_de_infracao")
    if passivos and r.get("parcelamento_situacao") == PARCELAMENTO_EM_ATRASO:
        rk.append("parcelamento_atraso")
    if _tem(r, "obrig_atraso", "Sim"):
        rk.append("obrigacao_atrasada")
    validade = r.get("certificado_validade")
    if r.get("certificado") and r.get("certificado") != "Não possui" and validade:
        try:
            if (date.fromisoformat(str(validade)[:10]) - recebido_em).days <= 60:
                rk.append("certificado_vencendo")
        except ValueError:
            pass

    atencao: list[tuple[str, str]] = []
    if passivos:
        atencao.append(("Parcelamentos, passivos, autos ou processos tributários declarados", "Fiscal"))
    if r.get("parcelamento_situacao") == PARCELAMENTO_EM_ATRASO:
        atencao.append(("Parcelamento em atraso ou já quebrado antes", "Fiscal"))
    if _tem(r, "obrig_atraso", "Sim"):
        atencao.append(("Obrigação acessória entregue com atraso nos últimos 3 meses", "Fiscal"))
    if _tem(r, "folha_rateio", "Sim") and _tem(r, "folha_rateio_formal", "Não"):
        atencao.append(("Rateio da folha sem regra formalizada", "Contábil"))
    if auditada:
        atencao.append(("Empresa auditada: exigências de fechamento", "Contábil"))
    if _tem(r, "exterior", "Sim"):
        atencao.append(("Operações ou pagamentos com o exterior", "Fiscal"))
    if _tem(r, "tomadores_upload", "Sim"):
        atencao.append(("Tomadores exigem upload de folha/encargos", "Folha / DP"))
    if _tem(r, "reestruturacao", "Sim"):
        atencao.append(("Reestruturação societária em curso", "Implantação"))
    if r.get("certificado") == "Não possui":
        atencao.append(("Empresa sem certificado digital", "Implantação"))
    if "certificado_vencendo" in rk:
        atencao.append(("Certificado digital vence em até 60 dias", "Implantação"))
    if r.get("operacao") in ("Terceirizada", "Mista") and r.get("fornecedor_atual"):
        atencao.append((f"Transição de fornecedor atual: {r['fornecedor_atual']}", "Implantação"))

    return Leitura(
        volumetria=volumetria, servicos=servicos, servicos_contratados_alem_do_primeiro=alem,
        tem_consolidacao_de_grupo=consolidacao, e_auditada=auditada,
        porte=sugestao.porte.value if sugestao.porte else None,
        pontuacao=str(sugestao.pontuacao) if sugestao.pontuacao is not None else None,
        horas_base=sugestao.horas_base,
        fatores_complexidade=cx, nota_complexidade=regra_de_avaliacao.nota_de_complexidade(len(cx)),
        fatores_risco=rk, nota_risco=regra_de_avaliacao.nota_de_risco(len(rk)),
        pontos_de_atencao=atencao, regimes=regimes,
    )
