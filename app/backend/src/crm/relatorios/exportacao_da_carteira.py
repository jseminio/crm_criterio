"""Exporta o histórico completo da classificação da carteira para Excel, para conferência
(pedido de Eduardo, 28/09/2026): "planilha em excel com fórmulas auditáveis", no modelo de
`Classificacao_Grupo_COMPLETO.xlsx` — visão **Grupo → Empresa**, com Score, Classe, Classe
Efetiva, Alerta de churn, `$$$` de inadimplência e Eixo de Ação todos em **fórmula viva**,
referenciando a aba Parâmetros (mais auditável que o modelo original, que grava os pesos direto
na fórmula — aqui, mudar um peso na aba Parâmetros recalcula a planilha inteira). A coluna
Rentabilidade (a margem, não a nota 1-5) fica logo ao lado do Score, por pedido de Eduardo.

**Diferença honesta do modelo**: o modelo tem margem e horas por CNPJ, porque a planilha de
rentabilidade os calcula por empresa. O CRM não guarda esse insumo por empresa (mesma lacuna já
documentada em `crm.domain.rentabilidade` e na tela) — por isso a linha de cada empresa aqui traz
nome, CNPJ e mensalidade, e o resto fica em branco, em vez de inventar número.

**Todo o histórico, não só o snapshot atual**: cada linha de `ClassificacaoDoGrupo` que já existiu
vira uma linha "▸ Grupo" (o banco é imutável — comparar mês a mês é o que isso permite). As
empresas do grupo aparecem **uma vez**, depois da leitura mais recente, porque `Empresa`/`Contrato`
não têm histórico versionado como a classificação.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

__all__ = ["LinhaDeHistorico", "EmpresaDaExportacao", "ParametrosDaPlanilha", "gerar_planilha"]

_AZUL_NOTURNO = "0B0E17"
_BRANCO = "FFFFFF"
_CINZA_CLARO = "F2F2F2"


@dataclass(frozen=True)
class LinhaDeHistorico:
    """Uma leitura de `ClassificacaoDoGrupo`, com o nome do grupo já resolvido."""

    grupo_id: int
    grupo_nome: str
    referencia: date
    revisao: int
    registrado_em: datetime
    fonte: str
    atribuido_por: str | None
    motivo: str | None
    receita_mensal: Decimal
    margem: Decimal | None
    horas_por_mes: Decimal | None
    nota_receita: Decimal
    nota_rentabilidade: Decimal
    complexidade: Decimal
    disciplina: Decimal
    risco_tecnico: Decimal
    cross_sell: Decimal
    adimplencia: Decimal
    semaforo: int
    churn: int | None
    score: Decimal
    classe: str
    classe_efetiva: str
    alerta_de_churn: str | None
    em_cobranca: bool
    eixo_de_acao: str


@dataclass(frozen=True)
class EmpresaDaExportacao:
    """Uma empresa do grupo — sem histórico próprio, aparece uma vez por grupo."""

    razao_social: str
    cnpj: str | None
    mensalidade: Decimal | None


@dataclass(frozen=True)
class ParametrosDaPlanilha:
    """Os campos de `VersaoDeParametros` que a aba "Parâmetros" mostra e as fórmulas usam."""

    corte_a: Decimal
    corte_b: Decimal
    trava_de_adimplencia: int
    churn_alto: int
    peso_receita: Decimal
    peso_rentabilidade: Decimal
    peso_adimplencia: Decimal
    peso_complexidade: Decimal
    peso_cross_sell: Decimal
    peso_disciplina: Decimal
    peso_risco: Decimal


# Layout de colunas — A a AA. Rentabilidade (a margem) fica logo depois do Score (pedido de
# Eduardo, 28/09/2026): dá pra ver de relance o que sustenta o Score daquele grupo.
_NOMES_DAS_COLUNAS = (
    "grupo", "tipo", "cnpj", "receita", "horas", "nota_receita", "nota_rentabilidade",
    "complexidade", "disciplina", "risco", "cross_sell", "adimplencia", "churn", "semaforo",
    "score", "margem", "classe", "classe_efetiva", "alerta", "cifrao", "eixo",
    "referencia", "revisao", "registrado_em", "fonte", "atribuido_por", "motivo",
)
_ROTULOS = {
    "grupo": "Grupo / Empresa", "tipo": "Tipo", "cnpj": "Nº CNPJs / CNPJ", "receita": "Receita (R$/mês)",
    "horas": "Horas/mês", "nota_receita": "Nota Receita", "nota_rentabilidade": "Nota Rentabilidade",
    "complexidade": "Complexidade", "disciplina": "Disciplina", "risco": "Risco técnico",
    "cross_sell": "Cross-sell", "adimplencia": "Adimplência", "churn": "Churn", "semaforo": "Semáforo",
    "score": "Score", "margem": "Rentabilidade (Margem %)", "classe": "Classe",
    "classe_efetiva": "Classe Efetiva", "alerta": "Alerta", "cifrao": "$$$", "eixo": "Eixo de Ação",
    "referencia": "Referência", "revisao": "Revisão", "registrado_em": "Registrado em", "fonte": "Fonte",
    "atribuido_por": "Atribuído por", "motivo": "Motivo",
}
_COLUNAS = tuple(_ROTULOS[n] for n in _NOMES_DAS_COLUNAS)
_COL = {nome: i + 1 for i, nome in enumerate(_NOMES_DAS_COLUNAS)}
_LINHA_DO_CABECALHO = 4
_PRIMEIRA_LINHA_DE_DADOS = 5


def _aba_de_parametros(wb: Workbook, p: ParametrosDaPlanilha) -> None:
    ws = wb.create_sheet("Parâmetros")
    ws["A1"] = "PARÂMETROS DE CLASSIFICAÇÃO"
    ws["A1"].font = Font(bold=True, size=13)
    linhas = (
        (2, "Corte A — Score mínimo", float(p.corte_a)),
        (3, "Corte B — Score mínimo", float(p.corte_b)),
        (4, "Trava inadimplência ≤", p.trava_de_adimplencia),
        (5, "Churn alto ≥", p.churn_alto),
    )
    for linha, rotulo, valor in linhas:
        ws.cell(row=linha, column=1, value=rotulo)
        ws.cell(row=linha, column=2, value=valor)
    ws["A7"] = "Pesos do Score"
    ws["A7"].font = Font(bold=True)
    pesos = (
        (8, "Receita", p.peso_receita), (9, "Rentabilidade", p.peso_rentabilidade),
        (10, "Adimplência", p.peso_adimplencia), (11, "Complexidade (invertido)", p.peso_complexidade),
        (12, "Cross-sell", p.peso_cross_sell), (13, "Disciplina", p.peso_disciplina),
        (14, "Risco técnico (invertido)", p.peso_risco),
    )
    for linha, rotulo, valor in pesos:
        ws.cell(row=linha, column=1, value=f"  {rotulo}")
        celula = ws.cell(row=linha, column=2, value=float(valor))
        celula.number_format = "0%"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 14


def _aba_de_criterios(wb: Workbook) -> None:
    ws = wb.create_sheet("Critérios e Fórmulas")
    ws["B1"] = "CRITÉRIOS E FÓRMULAS — AUDITORIA DO HISTÓRICO DA CARTEIRA"
    ws["B1"].font = Font(bold=True, size=12)
    linhas = (
        ("Score", "FÓRMULA VIVA: soma ponderada das sete notas (Complexidade e Risco técnico entram invertidos, "
                   "6 − nota). Pesos e cortes na aba Parâmetros — mude lá e o Score recalcula sozinho."),
        ("Rentabilidade", "A margem (%), ao lado do Score para leitura rápida — não é a Nota Rentabilidade "
                           "(1-5, mais à esquerda, é essa que entra na fórmula do Score)."),
        ("Classe", "FÓRMULA VIVA: A se Score ≥ Corte A | B se Score ≥ Corte B | senão C."),
        ("Classe Efetiva", "FÓRMULA VIVA: Classe + Semáforo (ex. \"B3\"); some \" (TRAVADO)\" se Adimplência ≤ trava."),
        ("Alerta", "FÓRMULA VIVA: \"⚠\" se churn alto em Classe A/B (há o que salvar), \"⚑\" se em Classe C, vazio se não."),
        ("$$$", "FÓRMULA VIVA: \"$$$\" se Adimplência ≤ trava (mesma trava que sinaliza a cobrança na tela)."),
        ("Eixo de Ação", "FÓRMULA VIVA: $$$ > Alerta \"⚠\" (Reter já se Classe A, Reter/vigiar se B) > Alerta \"⚑\" "
                          "(Saída organizada) > Sem urgência de churn, nessa ordem de precedência."),
        ("Margem e Horas por empresa", "EM BRANCO nas linhas de empresa: o CRM não guarda o insumo de porte/horas "
                                        "por CNPJ para refazer a margem (mesma lacuna já registrada na tela de "
                                        "avaliação) — não inventamos o número."),
        ("Histórico", "Uma linha \"▸ Grupo\" por leitura de `ClassificacaoDoGrupo` — o banco é imutável, uma edição "
                       "de nota grava linha nova e a anterior fica. As linhas \"• Empresa\" aparecem uma vez, depois "
                       "da leitura mais recente do grupo, porque `Empresa`/`Contrato` não têm histórico versionado."),
    )
    for i, (rotulo, texto) in enumerate(linhas):
        linha = 3 + i
        ws.cell(row=linha, column=2, value=rotulo).font = Font(bold=True)
        ws.cell(row=linha, column=3, value=texto).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 90


def _cabecalho(ws: Worksheet) -> None:
    ws["A1"] = "HISTÓRICO DA CLASSIFICAÇÃO DA CARTEIRA — visão Grupo → Empresa, todas as leituras"
    ws["A1"].font = Font(bold=True, size=13, color=_BRANCO)
    ws["A2"] = ("Score, Classe, Classe Efetiva, Alerta, $$$ e Eixo de Ação têm fórmula viva "
                "(referencia a aba Parâmetros); o resto é o valor já calculado no CRM.")
    ws["A2"].font = Font(italic=True, color=_BRANCO)
    for linha in (1, 2):
        for col in range(1, len(_COLUNAS) + 1):
            ws.cell(row=linha, column=col).fill = PatternFill("solid", fgColor=_AZUL_NOTURNO)
    for col, titulo in enumerate(_COLUNAS, start=1):
        c = ws.cell(row=_LINHA_DO_CABECALHO, column=col, value=titulo)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=_CINZA_CLARO)


def _escrever_grupo(ws: Worksheet, linha_n: int, l: LinhaDeHistorico, n_empresas: int) -> None:
    ws.cell(row=linha_n, column=_COL["grupo"], value=f"▸ {l.grupo_nome}")
    ws.cell(row=linha_n, column=_COL["tipo"], value="Grupo")
    ws.cell(row=linha_n, column=_COL["cnpj"], value=n_empresas)
    ws.cell(row=linha_n, column=_COL["receita"], value=float(l.receita_mensal)).number_format = "R$ #,##0.00"
    if l.horas_por_mes is not None:
        ws.cell(row=linha_n, column=_COL["horas"], value=float(l.horas_por_mes)).number_format = "0.0"
    for campo, valor in (
        ("nota_receita", l.nota_receita), ("nota_rentabilidade", l.nota_rentabilidade),
        ("complexidade", l.complexidade), ("disciplina", l.disciplina), ("risco", l.risco_tecnico),
        ("cross_sell", l.cross_sell), ("adimplencia", l.adimplencia),
    ):
        ws.cell(row=linha_n, column=_COL[campo], value=float(valor)).number_format = "0.00"
    if l.churn is not None:
        ws.cell(row=linha_n, column=_COL["churn"], value=l.churn)
    ws.cell(row=linha_n, column=_COL["semaforo"], value=l.semaforo)
    if l.margem is not None:
        ws.cell(row=linha_n, column=_COL["margem"], value=float(l.margem)).number_format = "0.00%"

    receita_col, rentab_col = get_column_letter(_COL["nota_receita"]), get_column_letter(_COL["nota_rentabilidade"])
    adimp_col = get_column_letter(_COL["adimplencia"])
    compl_col, disc_col, risco_col = get_column_letter(_COL["complexidade"]), get_column_letter(_COL["disciplina"]), get_column_letter(_COL["risco"])
    cross_col, churn_col, sem_col = get_column_letter(_COL["cross_sell"]), get_column_letter(_COL["churn"]), get_column_letter(_COL["semaforo"])
    score_col, classe_col = get_column_letter(_COL["score"]), get_column_letter(_COL["classe"])
    alerta_col, cifrao_col = get_column_letter(_COL["alerta"]), get_column_letter(_COL["cifrao"])

    # Score: soma ponderada, referenciando os pesos da aba Parâmetros — mesma fórmula de
    # `crm.domain.classificacao.score`. Complexidade e Risco técnico entram invertidos (6 − nota).
    formula_do_score = (
        f"={receita_col}{linha_n}*Parâmetros!$B$8 + {rentab_col}{linha_n}*Parâmetros!$B$9"
        f" + {adimp_col}{linha_n}*Parâmetros!$B$10 + (6-{compl_col}{linha_n})*Parâmetros!$B$11"
        f" + {cross_col}{linha_n}*Parâmetros!$B$12 + {disc_col}{linha_n}*Parâmetros!$B$13"
        f" + (6-{risco_col}{linha_n})*Parâmetros!$B$14"
    )
    ws.cell(row=linha_n, column=_COL["score"], value=formula_do_score).number_format = "0.0000"
    # Classe: os dois cortes fixos da aba Parâmetros — mesma fórmula de `classificacao.classe`.
    ws.cell(row=linha_n, column=_COL["classe"],
            value=f'=IF({score_col}{linha_n}>=Parâmetros!$B$2,"A",IF({score_col}{linha_n}>=Parâmetros!$B$3,"B","C"))')
    # Classe Efetiva: letra + semáforo, com "(TRAVADO)" se adimplência ≤ trava — `classificacao.classe_efetiva`.
    ws.cell(row=linha_n, column=_COL["classe_efetiva"], value=(
        f'={classe_col}{linha_n}&{sem_col}{linha_n}&IF({adimp_col}{linha_n}<=Parâmetros!$B$4," (TRAVADO)","")'
    ))
    # Alerta de churn: "⚠" em A/B, "⚑" em C, só se churn ≥ churn_alto — `classificacao.alerta_de_churn`.
    ws.cell(row=linha_n, column=_COL["alerta"], value=(
        f'=IF(OR({churn_col}{linha_n}="",{churn_col}{linha_n}<Parâmetros!$B$5),"",'
        f'IF({classe_col}{linha_n}="C","⚑","⚠"))'
    ))
    # $$$: adimplência ≤ trava — `classificacao.cobranca`.
    ws.cell(row=linha_n, column=_COL["cifrao"], value=f'=IF({adimp_col}{linha_n}<=Parâmetros!$B$4,"$$$","")')
    # Eixo de ação: $$$ > alerta "⚠" (A ou B) > alerta "⚑" > sem urgência — `classificacao.eixo_de_acao`.
    ws.cell(row=linha_n, column=_COL["eixo"], value=(
        f'=IF({cifrao_col}{linha_n}="$$$","Cobrança — sem tratamento preferencial",'
        f'IF(AND({alerta_col}{linha_n}="⚠",{classe_col}{linha_n}="A"),"Reter já (crítico)",'
        f'IF(AND({alerta_col}{linha_n}="⚠",{classe_col}{linha_n}="B"),"Reter / vigiar",'
        f'IF({alerta_col}{linha_n}="⚑","Saída organizada","Sem urgência de churn"))))'
    ))

    # O código de formato gravado no arquivo é sempre o inglês (YYYY); o Excel em português o
    # mostra traduzido. "AAAA" aqui não é ano para o Excel.
    ws.cell(row=linha_n, column=_COL["referencia"], value=l.referencia).number_format = "DD/MM/YYYY"
    ws.cell(row=linha_n, column=_COL["revisao"], value=l.revisao)
    c = ws.cell(row=linha_n, column=_COL["registrado_em"], value=l.registrado_em.replace(tzinfo=None))
    c.number_format = "DD/MM/YYYY HH:MM"
    ws.cell(row=linha_n, column=_COL["fonte"], value=l.fonte)
    ws.cell(row=linha_n, column=_COL["atribuido_por"], value=l.atribuido_por or "")
    ws.cell(row=linha_n, column=_COL["motivo"], value=l.motivo or "")


def _escrever_empresa(ws: Worksheet, linha_n: int, e: EmpresaDaExportacao) -> None:
    ws.cell(row=linha_n, column=_COL["grupo"], value=f"    • {e.razao_social}")
    ws.cell(row=linha_n, column=_COL["tipo"], value="Empresa")
    ws.cell(row=linha_n, column=_COL["cnpj"], value=e.cnpj or "")
    if e.mensalidade is not None:
        ws.cell(row=linha_n, column=_COL["receita"], value=float(e.mensalidade)).number_format = "R$ #,##0.00"


def gerar_planilha(
    linhas: list[LinhaDeHistorico], parametros: ParametrosDaPlanilha,
    empresas_por_grupo: dict[int, list[EmpresaDaExportacao]] | None = None,
) -> bytes:
    """Devolve os bytes do `.xlsx` — três abas, prontas para `Content-Disposition: attachment`.

    `linhas` já deve vir ordenada por grupo (depois referência, depois revisão) — quem chama
    (a rota) faz essa consulta; esta função só desenha. `empresas_por_grupo` é por `grupo_id`:
    o nome do grupo não é único no banco."""
    empresas_por_grupo = empresas_por_grupo or {}
    wb = Workbook()
    ws = wb.active
    ws.title = "Histórico da Carteira"
    _cabecalho(ws)

    linha_n = _PRIMEIRA_LINHA_DE_DADOS
    for i, l in enumerate(linhas):
        proximo_e_outro_grupo = i + 1 >= len(linhas) or linhas[i + 1].grupo_id != l.grupo_id
        empresas = empresas_por_grupo.get(l.grupo_id, [])
        _escrever_grupo(ws, linha_n, l, len(empresas))
        linha_n += 1
        if proximo_e_outro_grupo:
            for e in empresas:
                _escrever_empresa(ws, linha_n, e)
                linha_n += 1

    larguras = (34, 8, 15, 15, 9, 11, 12, 11, 9, 11, 10, 10, 7, 9, 9, 12, 8, 12, 7, 6, 30, 11, 8, 16, 30, 16, 30)
    for col, largura in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(col)].width = largura
    ws.freeze_panes = f"A{_PRIMEIRA_LINHA_DE_DADOS}"

    _aba_de_parametros(wb, parametros)
    _aba_de_criterios(wb)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
