"""Gera a planilha de lacunas de contato: quem são os clientes e o que falta preencher.

    exportar_lacunas_contato.py [arquivo.xlsx]

O CRM ainda não tem empresa, contato nem endereço cadastrados (a planilha de 2026
não trazia). Esta planilha lista cada grupo (cliente) com o que se sabe das
propostas e deixa em branco as colunas a preencher à mão. A coluna ID_GRUPO é a
chave: não altere, ela permite devolver os dados ao CRM depois.

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
CABECA = PatternFill("solid", fgColor=MARINHO)
FINA = Side(style="thin", color="C8CDD6")
BORDA = Border(left=FINA, right=FINA, top=FINA, bottom=FINA)

# (título, largura, preenchimento manual?)
CLIENTES = [
    ("ID_GRUPO", 10, False), ("Cliente (grupo)", 34, False), ("Relação com a Critério", 20, False),
    ("Propostas", 10, False), ("Aceitas", 9, False), ("Serviços propostos", 36, False),
    ("Última proposta", 14, False), ("Captador", 10, False),
    ("Razão social", 34, True), ("CNPJ (só números)", 18, True),
    ("Contato — nome", 28, True), ("Contato — cargo", 20, True),
    ("E-mail", 32, True), ("Telefone", 18, True),
    ("Logradouro", 32, True), ("Número / compl.", 16, True), ("Bairro", 20, True),
    ("Município", 20, True), ("UF", 6, True), ("CEP", 12, True),
    ("Observação", 34, True),
]
PREENCHER = [i for i, c in enumerate(CLIENTES, 1) if c[2]]
# Lacunas contadas: e-mail, telefone, contato, logradouro, município, UF, CEP
ESSENCIAIS = ["Contato — nome", "E-mail", "Telefone", "Logradouro", "Município", "UF", "CEP"]

LEADS = [
    ("ID_LEAD", 9, False), ("Nome", 28, False), ("Empresa (texto)", 28, False), ("Situação", 14, False),
    ("E-mail", 32, True), ("Telefone", 18, True), ("Observação", 34, True),
]

CONSULTA_GRUPOS = sa.text("""
    SELECT g.id, g.nome,
           COUNT(o.id)                                            AS propostas,
           COUNT(*) FILTER (WHERE o.situacao = 'Aceita')          AS aceitas,
           STRING_AGG(DISTINCT o.servico, ' · ')                  AS servicos,
           MAX(o.data_colocacao)                                  AS ultima,
           STRING_AGG(DISTINCT o.captador, ', ')                  AS captador
    FROM grupo_economico g
    LEFT JOIN oportunidade o ON o.grupo_id = g.id
    WHERE g.situacao <> 'Fundido'
    GROUP BY g.id, g.nome
    ORDER BY (COUNT(*) FILTER (WHERE o.situacao = 'Aceita') > 0) DESC, g.nome
""")


def _cabecalho(ws, colunas, linha=1):
    for i, (titulo, largura, manual) in enumerate(colunas, 1):
        c = ws.cell(linha, i, titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="8A6D1D" if manual else MARINHO)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BORDA
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.row_dimensions[linha].height = 32
    ws.freeze_panes = ws.cell(linha + 1, 3)
    ws.auto_filter.ref = f"A{linha}:{get_column_letter(len(colunas))}{linha}"


def gerar(destino: Path) -> dict:
    engine = criar_engine()
    with engine.connect() as c:
        grupos = c.execute(CONSULTA_GRUPOS).all()
        leads = c.execute(sa.text(
            "SELECT id, nome, empresa_texto, situacao, email, telefone, observacao FROM lead ORDER BY nome"
        )).all()
        contatos = c.execute(sa.text("SELECT count(*) FROM pessoa_contato")).scalar()
        empresas = c.execute(sa.text("SELECT count(*) FROM empresa")).scalar()

    wb = Workbook()

    # ---- Instruções
    ws = wb.active
    ws.title = "Instruções"
    ws.column_dimensions["A"].width = 110
    linhas = [
        ("Lacunas de contato — Critério CRM", True),
        (f"Gerada em {datetime.now():%d/%m/%Y %H:%M}. Contém dados de cliente: não envie nem compartilhe sem necessidade.", False),
        ("", False),
        ("Como usar", True),
        ("1. Na aba Clientes, preencha as colunas de cabeçalho dourado (razão social, CNPJ, contato, e-mail, telefone, endereço).", False),
        ("2. As colunas de cabeçalho azul vêm do CRM e não devem ser alteradas. A coluna ID_GRUPO é a chave para devolver os dados ao CRM.", False),
        ("3. CNPJ: só os 14 números. UF: escolha na lista. A coluna “Lacunas” conta o que ainda falta (contato, e-mail, telefone, logradouro, município, UF, CEP).", False),
        ("4. Filtre “Lacunas” para trabalhar o que falta. A ordem parte dos clientes com proposta aceita, depois os demais.", False),
        ("", False),
        ("O que esta planilha revela sobre a base", True),
        (f"• O CRM tem hoje {empresas} empresas e {contatos} contatos cadastrados: nenhum dado de contato existe ainda. A planilha de 2026 não trazia.", False),
        ("• O CRM não tem campo de endereço completo. Só existem município e UF, na empresa. Logradouro, número, bairro e CEP são colunas novas aqui.", False),
        ("  Pendência de decisão: criar esses campos no CRM antes de devolver os dados.", False),
        ("• Cada linha é um grupo (cliente). Um grupo pode ter várias empresas/CNPJs; se for o caso, use a Observação ou duplique a linha mantendo o ID_GRUPO.", False),
        ("• Foram excluídos os grupos já fundidos em outro (situação Fundido).", False),
    ]
    for r, (t, negrito) in enumerate(linhas, 1):
        cel = ws.cell(r, 1, t)
        cel.font = Font(bold=negrito, size=14 if r == 1 else 11)
        cel.alignment = Alignment(wrap_text=True, vertical="top")

    # ---- Clientes
    wc = wb.create_sheet("Clientes")
    colunas = CLIENTES + [("Lacunas", 9, False)]
    _cabecalho(wc, colunas)
    titulos = [t for t, _, _ in CLIENTES]
    col = {t: get_column_letter(i) for i, t in enumerate(titulos, 1)}
    for n, g in enumerate(grupos, 2):
        relacao = "Cliente (proposta aceita)" if g.aceitas else ("Em negociação" if g.propostas else "Sem proposta")
        valores = [g.id, g.nome, relacao, g.propostas, g.aceitas, g.servicos, g.ultima, g.captador]
        for i, v in enumerate(valores, 1):
            cel = wc.cell(n, i, v)
            cel.fill = CINZA
            cel.border = BORDA
            cel.alignment = Alignment(vertical="top", wrap_text=(i == 6))
            if i == 7 and v:
                cel.number_format = "DD/MM/YYYY"
        for i in PREENCHER:
            cel = wc.cell(n, i)
            cel.fill = AMARELO
            cel.border = BORDA
            if titulos[i - 1] in ("CNPJ (só números)", "Telefone", "CEP"):
                cel.number_format = "@"  # texto: não perde zero à esquerda
        refs = ",".join(f"{col[t]}{n}" for t in ESSENCIAIS)
        f = wc.cell(n, len(colunas), f"=COUNTBLANK({col['Contato — nome']}{n})+COUNTBLANK({col['E-mail']}{n})"
                    f"+COUNTBLANK({col['Telefone']}{n})+COUNTBLANK({col['Logradouro']}{n})"
                    f"+COUNTBLANK({col['Município']}{n})+COUNTBLANK({col['UF']}{n})+COUNTBLANK({col['CEP']}{n})")
        f.border = BORDA
        f.alignment = Alignment(horizontal="center", vertical="top")
    ultima = len(grupos) + 1
    dv_uf = DataValidation(type="list", formula1=f'"{UFS}"', allow_blank=True)
    dv_uf.add(f"{col['UF']}2:{col['UF']}{ultima}")
    dv_cnpj = DataValidation(type="custom", formula1=f'=OR({col["CNPJ (só números)"]}2="",AND(LEN({col["CNPJ (só números)"]}2)=14,ISNUMBER(VALUE({col["CNPJ (só números)"]}2))))',
                             allow_blank=True, showErrorMessage=True, errorTitle="CNPJ", error="Informe os 14 dígitos, sem pontos, barra ou traço.")
    dv_cnpj.add(f"{col['CNPJ (só números)']}2:{col['CNPJ (só números)']}{ultima}")
    wc.add_data_validation(dv_uf)
    wc.add_data_validation(dv_cnpj)
    # Total de lacunas, fora do filtro
    wc.cell(ultima + 2, 2, "Lacunas restantes").font = Font(bold=True)
    wc.cell(ultima + 2, len(colunas), f"=SUM({get_column_letter(len(colunas))}2:{get_column_letter(len(colunas))}{ultima})").font = Font(bold=True)

    # ---- Leads
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
    return {"grupos": len(grupos), "aceitos": sum(1 for g in grupos if g.aceitas), "leads": len(leads)}


if __name__ == "__main__":
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else PASTA / f"lacunas-contato-{datetime.now():%Y%m%d-%H%M}.xlsx"
    r = gerar(saida)
    if not sys.argv[1:]:
        os.chmod(PASTA, 0o700)
    print(f"✓ {saida}\n  {r['grupos']} clientes ({r['aceitos']} com proposta aceita), {r['leads']} lead(s)")
