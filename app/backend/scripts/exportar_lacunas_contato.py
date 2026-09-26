"""Gera a planilha de lacunas de contato: uma aba para CLIENTES (por empresa) e outra para PROSPECTS.

    exportar_lacunas_contato.py [arquivo.xlsx]

Clientes e prospects ficam **separados**. A aba Clientes tem uma linha por empresa (CNPJ), com razão
social, CNPJ, escopo e mensalidade já vindos do CRM; a aba Prospects, uma linha por grupo. Em ambas,
as colunas douradas são as a preencher (contato, e-mail, telefone, endereço). As colunas ID_GRUPO e
ID_EMPRESA são a chave para devolver os dados ao CRM (`importar_lacunas_contato.py`): não altere.

⚠️ Contém nome de cliente e valores. Fica fora do repositório (padrão ~/Dados-CRM).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sqlalchemy as sa  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from crm.db.sessao import criar_engine  # noqa: E402

PASTA = Path.home() / "Dados-CRM"
UFS = "AC,AL,AP,AM,BA,CE,DF,ES,GO,MA,MT,MS,MG,PA,PB,PR,PE,PI,RJ,RN,RS,RO,RR,SC,SP,SE,TO"
MARINHO = "1F2A44"
CINZA = PatternFill("solid", fgColor="EEF0F4")
AMARELO = PatternFill("solid", fgColor="FFF8DC")
FINA = Side(style="thin", color="C8CDD6")
BORDA = Border(left=FINA, right=FINA, top=FINA, bottom=FINA)

# As colunas a preencher são as mesmas nas duas abas: o importador as lê pelo título.
A_PREENCHER = [
    ("Contato — nome", 28), ("Contato — cargo", 20), ("E-mail", 32), ("Telefone", 18),
    ("Logradouro", 32), ("Número / compl.", 16), ("Bairro", 20), ("Município", 20), ("UF", 6),
    ("CEP", 12), ("Observação", 34),
]
ESSENCIAIS = ["Contato — nome", "E-mail", "Telefone", "Logradouro", "Município", "UF", "CEP"]

# (título, largura, preenchimento manual?)
CLIENTES = [
    ("ID_GRUPO", 10, False), ("ID_EMPRESA", 11, False), ("Cliente (grupo)", 30, False),
    ("Razão social", 34, False), ("CNPJ (só números)", 18, False), ("Escopo", 28, False),
    ("Mensalidade (R$)", 14, False),
] + [(t, w, True) for t, w in A_PREENCHER]

PROSPECTS = [
    ("ID_GRUPO", 10, False), ("Prospect (grupo)", 34, False), ("Relação", 22, False),
    ("Propostas", 10, False), ("Serviços propostos", 34, False), ("Última proposta", 14, False),
    ("Captador", 10, False), ("Razão social", 34, True), ("CNPJ (só números)", 18, True),
] + [(t, w, True) for t, w in A_PREENCHER]

LEADS = [("ID_LEAD", 9, False), ("Nome", 28, False), ("Empresa (texto)", 28, False), ("Situação", 14, False),
         ("E-mail", 32, True), ("Telefone", 18, True), ("Observação", 34, True)]

SQL_CLIENTES = sa.text("""
    SELECT g.id AS id_grupo, e.id AS id_empresa, g.nome AS grupo, e.razao_social, e.cnpj,
           e.logradouro, e.numero, e.complemento, e.bairro, e.municipio, e.uf, e.cep,
           c.escopo, c.preco_mensal
    FROM empresa e
    JOIN grupo_economico g ON g.id = e.grupo_id
    LEFT JOIN contrato c ON c.empresa_id = e.id AND c.situacao IN ('Ativo', 'Suspenso')
    WHERE g.situacao = 'Cliente' AND g.fundido_em_id IS NULL
    ORDER BY COALESCE(c.preco_mensal, 0) DESC, g.nome, e.razao_social
""")

SQL_PROSPECTS = sa.text("""
    SELECT g.id, g.nome,
           COUNT(o.id) AS propostas,
           COUNT(*) FILTER (WHERE o.situacao NOT IN ('Aceita', 'Recusada', 'Perdido')) AS em_aberto,
           STRING_AGG(DISTINCT o.servico, ' · ') AS servicos,
           MAX(o.data_colocacao) AS ultima,
           STRING_AGG(DISTINCT o.captador, ', ') AS captador
    FROM grupo_economico g
    LEFT JOIN oportunidade o ON o.grupo_id = g.id
    WHERE g.situacao = 'Prospect' AND g.fundido_em_id IS NULL
    GROUP BY g.id, g.nome
    ORDER BY (COUNT(*) FILTER (WHERE o.situacao NOT IN ('Aceita', 'Recusada', 'Perdido')) > 0) DESC, g.nome
""")


def _cabecalho(ws, colunas):
    for i, (titulo, largura, manual) in enumerate(colunas, 1):
        c = ws.cell(1, i, titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="8A6D1D" if manual else MARINHO)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BORDA
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(colunas) + 1)}1"


def _lacunas_e_validacoes(ws, colunas, ultima):
    titulos = [t for t, _, _ in colunas]
    col = {t: get_column_letter(i) for i, t in enumerate(titulos, 1)}
    n_col = len(colunas) + 1
    c = ws.cell(1, n_col, "Lacunas")
    c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=MARINHO); c.border = BORDA
    ws.column_dimensions[get_column_letter(n_col)].width = 9
    for n in range(2, ultima + 1):
        f = ws.cell(n, n_col, "=" + "+".join(f"COUNTBLANK({col[t]}{n})" for t in ESSENCIAIS))
        f.border = BORDA; f.alignment = Alignment(horizontal="center")
    if ultima >= 2:
        dv = DataValidation(type="list", formula1=f'"{UFS}"', allow_blank=True)
        dv.add(f"{col['UF']}2:{col['UF']}{ultima}")
        cn = col["CNPJ (só números)"]
        dv2 = DataValidation(type="custom", allow_blank=True, showErrorMessage=True, errorTitle="CNPJ",
                             error="Informe os 14 dígitos, sem pontos, barra ou traço.",
                             formula1=f'=OR({cn}2="",AND(LEN({cn}2)=14,ISNUMBER(VALUE({cn}2))))')
        dv2.add(f"{cn}2:{cn}{ultima}")
        ws.add_data_validation(dv); ws.add_data_validation(dv2)
    ws.cell(ultima + 2, 3, "Lacunas restantes").font = Font(bold=True)
    ws.cell(ultima + 2, n_col, f"=SUM({get_column_letter(n_col)}2:{get_column_letter(n_col)}{ultima})").font = Font(bold=True)


def _linha(ws, n, valores, colunas):
    for i, ((titulo, _, manual), v) in enumerate(zip(colunas, valores), 1):
        cel = ws.cell(n, i, v)
        cel.border = BORDA
        cel.fill = AMARELO if manual else CINZA
        cel.alignment = Alignment(vertical="top")
        if titulo in ("CNPJ (só números)", "Telefone", "CEP"):
            cel.number_format = "@"
        if titulo == "Mensalidade (R$)":
            cel.number_format = '#,##0.00'
        if titulo == "Última proposta" and v:
            cel.number_format = "DD/MM/YYYY"


def gerar(destino: Path) -> dict:
    engine = criar_engine()
    with engine.connect() as c:
        clientes = c.execute(SQL_CLIENTES).all()
        prospects = c.execute(SQL_PROSPECTS).all()
        leads = c.execute(sa.text("SELECT id, nome, empresa_texto, situacao, email, telefone, observacao FROM lead ORDER BY nome")).all()
        contatos = c.execute(sa.text("SELECT count(*) FROM pessoa_contato")).scalar()

    wb = Workbook()
    ws = wb.active
    ws.title = "Instruções"
    ws.column_dimensions["A"].width = 112
    linhas = [
        ("Lacunas de contato — Critério CRM", True),
        (f"Gerada em {datetime.now():%d/%m/%Y %H:%M}. Contém dados de cliente: não envie nem compartilhe sem necessidade.", False),
        ("", False),
        ("Como usar", True),
        (f"• Aba Clientes: {len(clientes)} empresas dos clientes (uma linha por CNPJ). Razão social, CNPJ, escopo e mensalidade já vêm do CRM.", False),
        (f"• Aba Prospects: {len(prospects)} grupos que ainda não são cliente (uma linha por grupo). Razão social e CNPJ são opcionais.", False),
        ("• Preencha as colunas de cabeçalho dourado: contato, e-mail, telefone e endereço. As azuis vêm do CRM: só as altere se estiverem erradas.", False),
        ("• ID_GRUPO e ID_EMPRESA são a chave para devolver os dados ao CRM. Não altere.", False),
        ("• CNPJ: só os 14 números. UF: escolha na lista. A coluna “Lacunas” conta o que ainda falta (contato, e-mail, telefone, logradouro, município, UF, CEP).", False),
        ("• Para dois contatos na mesma empresa, duplique a linha mantendo os IDs.", False),
        ("", False),
        ("O que esta planilha revela", True),
        (f"• O CRM tem hoje {contatos} contatos cadastrados: nenhum contato de pessoa existe ainda.", False),
        ("• Clientes vieram da planilha de saúde da carteira; prospects, das propostas de 2026 (o nome do grupo às vezes é o nome da proposta).", False),
    ]
    for r, (t, negrito) in enumerate(linhas, 1):
        cel = ws.cell(r, 1, t)
        cel.font = Font(bold=negrito, size=14 if r == 1 else 11)
        cel.alignment = Alignment(wrap_text=True, vertical="top")

    wc = wb.create_sheet("Clientes")
    _cabecalho(wc, CLIENTES)
    for n, r in enumerate(clientes, 2):
        _linha(wc, n, [r.id_grupo, r.id_empresa, r.grupo, r.razao_social, r.cnpj, r.escopo, r.preco_mensal,
                       None, None, None, None, r.logradouro,
                       " ".join(x for x in (r.numero, r.complemento) if x) or None,
                       r.bairro, r.municipio, r.uf, r.cep, None], CLIENTES)
    _lacunas_e_validacoes(wc, CLIENTES, len(clientes) + 1)

    wp = wb.create_sheet("Prospects")
    _cabecalho(wp, PROSPECTS)
    for n, r in enumerate(prospects, 2):
        relacao = "Em negociação" if r.em_aberto else ("Proposta recusada" if r.propostas else "Sem proposta")
        _linha(wp, n, [r.id, r.nome, relacao, r.propostas, r.servicos, r.ultima, r.captador] + [None] * (2 + len(A_PREENCHER)), PROSPECTS)
    _lacunas_e_validacoes(wp, PROSPECTS, len(prospects) + 1)

    wl = wb.create_sheet("Leads")
    _cabecalho(wl, LEADS)
    for n, l in enumerate(leads, 2):
        for i, v in enumerate(list(l), 1):
            cel = wl.cell(n, i, v)
            cel.border = BORDA
            cel.fill = AMARELO if LEADS[i - 1][2] else CINZA
    wl.freeze_panes = "C2"

    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    os.chmod(destino, 0o600)
    return {"clientes": len(clientes), "prospects": len(prospects), "leads": len(leads)}


if __name__ == "__main__":
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else PASTA / f"lacunas-contato-{datetime.now():%Y%m%d-%H%M}.xlsx"
    r = gerar(saida)
    if not sys.argv[1:]:
        os.chmod(PASTA, 0o700)
    print(f"✓ {saida}\n  {r['clientes']} empresas de clientes, {r['prospects']} prospects, {r['leads']} lead(s)")
