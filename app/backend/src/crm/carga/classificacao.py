"""Carrega a classificação da carteira das planilhas de saúde da carteira e a **confere**.

Fontes (dado de cliente; **ficam fora do repositório**):

- `Classificacao_Grupo_COMPLETO.xlsx`: uma linha por unidade (grupo ou cliente individual) com as
  notas, o Score, a classe e o eixo de ação; e a aba do ISC, onde vive o **churn** de cada unidade
  (na aba principal ele só existe escondido dentro de uma fórmula, defeito 7.1).
- `Rentabilidade_Grupo_COMPLETO.xlsx`, aba "4. Clientes": liga cada unidade aos seus **CNPJs**, e é
  pelo CNPJ que a unidade encontra o grupo do CRM (o nome do grupo mudou com as fusões; o CNPJ não).

O CRM **recalcula** Score, classe, trava, alerta, eixo e ISC com `crm.domain.classificacao` e compara
com o que a planilha diz. Divergência é erro e bloqueia a gravação: ou a planilha ou o código está errado,
e isso precisa ser visto antes de virar dado. **A nota de rentabilidade é a da planilha**, sem recálculo
(defeito 7.2 pendente).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from crm.db.modelos import ClassificacaoDoGrupo, Empresa, GrupoEconomico
from crm.domain import classificacao as regra

__all__ = ["Linha", "Relatorio", "ler", "aplicar"]

ABA_CLASSIFICACAO = "Classificação Grupo"
ABA_ISC = "ISC - Índice de Saúde"
ABA_CLIENTES = "4. Clientes"

# Onde o eixo de ação da planilha começa, para comparar com o do CRM sem depender do sufixo ("… OK").
_EIXO_DA_PLANILHA = (
    ("cobrança", "Cobrança — sem tratamento preferencial"),
    ("reter já", "Reter já (crítico)"),
    ("reter /", "Reter / vigiar"),
    ("saída organizada", "Saída organizada"),
    ("sem urgência", "Sem urgência de churn"),
)


def _norm(texto) -> str:
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    s = s.replace("▸", " ")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def _dec(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


@dataclass
class Linha:
    unidade: str
    grupo_id: int
    receita: Decimal
    margem: Decimal | None
    horas: Decimal | None
    notas: regra.Notas


@dataclass
class Relatorio:
    unidades: int = 0
    criadas: int = 0
    ja_existiam: int = 0
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    isc_da_planilha: Decimal | None = None
    isc_do_crm: regra.Isc | None = None
    por_classe: dict[str, int] = field(default_factory=dict)

    @property
    def pode_aplicar(self) -> bool:
        return not self.erros


def _cnpjs_por_unidade(caminho: Path, rel: Relatorio) -> dict[str, list[str]]:
    ws = load_workbook(caminho, data_only=True)[ABA_CLIENTES]
    cab = {}
    for r in range(1, 12):
        nomes = {str(c.value).replace("\n", " ").strip(): i for i, c in enumerate(ws[r]) if c.value is not None}
        if "Razão Social" in nomes and "CNPJ" in nomes and "Grupo Econômico" in nomes:
            cab, primeira = nomes, r + 1
            break
    if not cab:
        rel.erros.append(f"Não achei o cabeçalho da aba “{ABA_CLIENTES}” na planilha de rentabilidade.")
        return {}
    unidades: dict[str, list[str]] = {}
    for row in ws.iter_rows(min_row=primeira, values_only=True):
        razao = row[cab["Razão Social"]]
        if not razao:
            continue
        grupo = str(row[cab["Grupo Econômico"]] or "").strip()
        chave = _norm(razao) if not grupo or _norm(grupo) == "sem grupo" else _norm(grupo)
        unidades.setdefault(chave, []).append(re.sub(r"\D", "", str(row[cab["CNPJ"]] or "")))
    return unidades


def _destino(sessao: Session, grupo_id: int) -> int:
    """Segue as fusões até o grupo que ficou."""
    for _ in range(50):
        g = sessao.get(GrupoEconomico, grupo_id)
        if g is None or g.fundido_em_id is None:
            return grupo_id
        grupo_id = g.fundido_em_id
    raise RuntimeError("cadeia de fusões longa demais")


def ler(classificacao: Path, rentabilidade: Path, sessao: Session, rel: Relatorio) -> list[Linha]:
    wb = load_workbook(classificacao, data_only=True)
    for aba in (ABA_CLASSIFICACAO, ABA_ISC):
        if aba not in wb.sheetnames:
            rel.erros.append(f"A planilha de classificação não tem a aba “{aba}”.")
    if rel.erros:
        return []
    cnpjs = _cnpjs_por_unidade(rentabilidade, rel)
    if not cnpjs:
        return []

    # churn e semáforo numéricos, da aba do ISC
    churn: dict[str, int | None] = {}
    semaforo_isc: dict[str, int] = {}
    isc_planilha: Decimal | None = None
    for row in wb[ABA_ISC].iter_rows(min_row=1, values_only=True):
        if row[0] and _num(row[7]) is not None and row[3] in ("A", "B", "C"):
            churn[_norm(row[0])] = int(row[7])
            semaforo_isc[_norm(row[0])] = int(row[5])
        if row[0] and str(row[0]).startswith("ISC") and _num(row[4]) is not None:
            isc_planilha = Decimal(str(row[4]))
    rel.isc_da_planilha = isc_planilha

    ws = wb[ABA_CLASSIFICACAO]
    linhas: list[Linha] = []
    for numero, row in enumerate(ws.iter_rows(min_row=5, values_only=True), 5):
        if not row[0] or row[1] not in ("Grupo", "Individual"):
            continue  # linhas-filhas (empresas de um grupo) e rodapé
        rel.unidades += 1
        nome = _norm(row[0])
        rotulo = f"Linha {numero}"
        ciqs = cnpjs.get(nome)
        if not ciqs:
            rel.erros.append(f"{rotulo}: não achei os CNPJs da unidade na aba “{ABA_CLIENTES}”.")
            continue
        destinos = set()
        for cnpj in ciqs:
            e = sessao.scalars(sa.select(Empresa).where(Empresa.cnpj == cnpj)).first()
            if e is None:
                rel.erros.append(f"{rotulo}: o CNPJ {cnpj} não está no CRM.")
                continue
            destinos.add(_destino(sessao, e.grupo_id))
        if len(destinos) != 1:
            rel.erros.append(f"{rotulo}: os CNPJs da unidade caem em {len(destinos)} grupos do CRM (esperava 1).")
            continue
        try:
            sem = int(re.match(r"\s*0*(\d)", str(row[13])).group(1))
        except (AttributeError, TypeError):
            rel.erros.append(f"{rotulo}: semáforo ilegível ({row[13]!r}).")
            continue
        if nome in semaforo_isc and semaforo_isc[nome] != sem:
            rel.erros.append(f"{rotulo}: o semáforo difere entre a aba principal ({sem}) e a do ISC ({semaforo_isc[nome]}).")
        if nome not in churn:
            rel.avisos.append(f"{rotulo}: a unidade não tem nota de churn na aba do ISC; ficou sem churn e fora do ISC.")
        try:
            notas = regra.Notas(
                receita=_dec(row[6]), rentabilidade=_dec(row[7]), complexidade=_dec(row[8]), disciplina=_dec(row[9]),
                risco=_dec(row[10]), cross_sell=_dec(row[11]), adimplencia=_dec(row[12]), semaforo=sem, churn=churn.get(nome),
            )
            pontos = regra.score(notas)
        except (ValueError, TypeError) as erro:
            rel.erros.append(f"{rotulo}: {erro}")
            continue

        # Conferência: o CRM recalcula e compara com a planilha.
        letra = regra.classe(pontos)
        efetiva = regra.classe_efetiva(letra, notas)
        eixo = regra.eixo_de_acao(letra, notas)
        if abs(float(pontos) - (_num(row[14]) or -1)) > 0.006:
            rel.erros.append(f"{rotulo}: Score do CRM {float(pontos):.3f} ≠ planilha {_num(row[14])}.")
        if str(row[16]).split()[0][0] != letra or str(row[16]).split()[0] != (efetiva.split()[0]):
            rel.erros.append(f"{rotulo}: classe do CRM {efetiva.split()[0]} ≠ planilha {str(row[16]).split()[0]}.")
        if ("TRAVADO" in str(row[16])) != ("TRAVADO" in efetiva):
            rel.erros.append(f"{rotulo}: a trava de inadimplência diverge da planilha.")
        planilha_alerta = row[17] if row[17] in ("⚠", "⚑") else None
        if notas.churn is not None and planilha_alerta != regra.alerta_de_churn(letra, notas):
            rel.erros.append(f"{rotulo}: alerta de churn do CRM ≠ planilha ({planilha_alerta!r}).")
        eixo_planilha = next((v for k, v in _EIXO_DA_PLANILHA if _norm(row[19]).startswith(_norm(k))), None)
        if eixo_planilha != eixo:
            rel.erros.append(f"{rotulo}: eixo de ação do CRM ({eixo}) ≠ planilha ({row[19]}).")

        linhas.append(Linha(
            unidade=str(row[0]).replace("▸", "").strip(), grupo_id=destinos.pop(),
            receita=Decimal(str(row[3])).quantize(Decimal("0.01")),
            margem=Decimal(str(row[4])).quantize(Decimal("0.0001")) if _num(row[4]) is not None else None,
            horas=Decimal(str(row[5])).quantize(Decimal("0.01")) if _num(row[5]) is not None else None,
            notas=notas,
        ))
        rel.por_classe[letra] = rel.por_classe.get(letra, 0) + 1

    # Conferência do ISC
    calculado = regra.isc(
        regra.Unidade(l.receita, regra.classe(regra.score(l.notas)), l.notas.semaforo, l.notas.churn) for l in linhas
    )
    rel.isc_do_crm = calculado
    if calculado and rel.isc_da_planilha is not None and abs(float(calculado.valor) - float(rel.isc_da_planilha)) > 0.01:
        rel.erros.append(f"ISC do CRM {float(calculado.valor):.2f} ≠ planilha {float(rel.isc_da_planilha):.2f}.")
    grupos_repetidos = {l.grupo_id for l in linhas if sum(1 for x in linhas if x.grupo_id == l.grupo_id) > 1}
    if grupos_repetidos:
        rel.erros.append("Duas unidades da planilha caem no mesmo grupo do CRM (fusão entre unidades diferentes?).")
    return linhas


def aplicar(sessao: Session, linhas: list[Linha], rel: Relatorio, referencia: date, fonte: str) -> None:
    """Grava um snapshot por grupo. Idempotente por (grupo, data de referência)."""
    for l in linhas:
        if sessao.scalars(sa.select(ClassificacaoDoGrupo).where(
            ClassificacaoDoGrupo.grupo_id == l.grupo_id, ClassificacaoDoGrupo.referencia == referencia
        )).first():
            rel.ja_existiam += 1
            continue
        n = l.notas
        pontos = regra.score(n)
        letra = regra.classe(pontos)
        sessao.add(ClassificacaoDoGrupo(
            grupo_id=l.grupo_id, referencia=referencia, fonte=fonte, versao_dos_parametros=regra.PARAMETROS.versao,
            receita_mensal=l.receita, margem=l.margem, horas_por_mes=l.horas, rentabilidade_da_planilha=True,
            nota_receita=n.receita, nota_rentabilidade=n.rentabilidade, complexidade=n.complexidade,
            disciplina=n.disciplina, risco_tecnico=n.risco, cross_sell=n.cross_sell, adimplencia=n.adimplencia,
            semaforo=n.semaforo, churn=n.churn, score=pontos.quantize(Decimal("0.0001")), classe=letra,
            classe_efetiva=regra.classe_efetiva(letra, n), alerta_de_churn=regra.alerta_de_churn(letra, n),
            em_cobranca=regra.cobranca(n), eixo_de_acao=regra.eixo_de_acao(letra, n),
        ))
        rel.criadas += 1
    sessao.flush()
