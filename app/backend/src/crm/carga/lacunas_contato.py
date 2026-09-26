"""Lê a planilha de lacunas de contato preenchida à mão e a devolve ao CRM.

Regras (decisão de Eduardo, 25/09/2026): **o mesmo cliente pode ter várias
empresas, em linhas separadas** com o mesmo ID_GRUPO. Cada linha vira:

- uma **Empresa**, quando traz razão social, CNPJ ou endereço;
- uma **PessoaContato**, quando traz nome, e-mail ou telefone — ligada à empresa
  da linha, ou ao grupo se a linha não tem empresa.

Nada é sobrescrito em silêncio: campo já preenchido no CRM com valor diferente
vira **conflito** no relatório e só muda com `sobrescrever=True`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import sqlalchemy as sa
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from crm.db.modelos import Empresa, GrupoEconomico, PessoaContato

__all__ = ["Relatorio", "ler", "aplicar", "cnpj_valido"]

UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NUMERO = re.compile(r"^\s*(\d+[A-Za-z]?|S/?N)\b[\s,.\-–]*(.*)$", re.IGNORECASE)

# cabeçalho da planilha -> campo interno
COLUNAS = {
    "ID_GRUPO": "id_grupo",
    "Razão social": "razao_social",
    "CNPJ (só números)": "cnpj",
    "Contato — nome": "contato_nome",
    "Contato — cargo": "contato_cargo",
    "E-mail": "email",
    "Telefone": "telefone",
    "Logradouro": "logradouro",
    "Número / compl.": "numero_compl",
    "Bairro": "bairro",
    "Município": "municipio",
    "UF": "uf",
    "CEP": "cep",
    "Observação": "observacao",
}
CAMPOS_EMPRESA = ("razao_social", "cnpj", "logradouro", "numero", "complemento", "bairro", "municipio", "uf", "cep")
CAMPOS_CONTATO = ("contato_nome", "contato_cargo", "email", "telefone")


@dataclass
class Linha:
    n: str
    """Rótulo de onde a linha está ("Linha 5", "Prospects, linha 12"), para os avisos."""
    id_grupo: int
    dados: dict[str, str]
    id_empresa: int | None = None
    """Presente nas linhas por empresa (aba Clientes da planilha nova): aponta a empresa certa."""
    avisos: list[str] = field(default_factory=list)


@dataclass
class Relatorio:
    linhas_lidas: int = 0
    linhas_vazias: int = 0
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    conflitos: list[str] = field(default_factory=list)
    empresas_criadas: int = 0
    empresas_atualizadas: int = 0
    contatos_criados: int = 0
    contatos_atualizados: int = 0

    @property
    def pode_aplicar(self) -> bool:
        return not self.erros


def cnpj_valido(cnpj: str) -> bool:
    if len(cnpj) != 14 or not cnpj.isdigit() or len(set(cnpj)) == 1:
        return False

    def dv(base: str) -> int:
        soma, peso = 0, 2
        for d in reversed(base):
            soma += int(d) * peso
            peso = 2 if peso == 9 else peso + 1
        r = soma % 11
        return 0 if r < 2 else 11 - r

    d1 = dv(cnpj[:12])
    return d1 == int(cnpj[12]) and dv(cnpj[:12] + str(d1)) == int(cnpj[13])


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())


def _so_digitos(v: str) -> str:
    return re.sub(r"\D", "", v)


ABAS = ("Clientes", "Prospects")


def ler(caminho: Path, rel: Relatorio) -> list[Linha]:
    """Lê e valida as abas Clientes e Prospects. Só considera as colunas a preencher."""
    wb = load_workbook(caminho, data_only=True)
    abas = [a for a in ABAS if a in wb.sheetnames]
    if not abas:
        rel.erros.append("A planilha não tem a aba Clientes nem a Prospects. Use o modelo gerado pelo CRM.")
        return []
    linhas: list[Linha] = []
    for aba in abas:
        linhas.extend(_ler_aba(wb[aba], aba, rel))
    return linhas


def _ler_aba(ws, aba: str, rel: Relatorio) -> list[Linha]:
    prefixo = "Linha" if aba == "Clientes" else f"{aba}, linha"
    cab = {_texto(c.value): i for i, c in enumerate(ws[1])}
    faltam = [t for t in COLUNAS if t not in cab]
    if faltam:
        rel.erros.append(f"Aba {aba} sem as colunas: {', '.join(faltam)}. Use o modelo gerado pelo CRM.")
        return []
    linhas: list[Linha] = []
    for numero, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        n = f"{prefixo} {numero}"
        bruto = {campo: _texto(row[cab[t]]) for t, campo in COLUNAS.items()}
        if not bruto["id_grupo"] or not bruto["id_grupo"].isdigit():
            continue  # rodapé de totais e linhas em branco
        rel.linhas_lidas += 1
        preench = {k: v for k, v in bruto.items() if k != "id_grupo" and v}
        if not preench:
            rel.linhas_vazias += 1
            continue
        id_emp = _texto(row[cab["ID_EMPRESA"]]) if "ID_EMPRESA" in cab else ""
        lin = Linha(n, int(bruto["id_grupo"]), preench, int(id_emp) if id_emp.isdigit() else None)
        d = lin.dados

        if "cnpj" in d:
            d["cnpj"] = _so_digitos(d["cnpj"])
            if not cnpj_valido(d["cnpj"]):
                rel.erros.append(f"{n}: CNPJ inválido ({d['cnpj']!r}).")
        if "cep" in d:
            d["cep"] = _so_digitos(d["cep"])
            if len(d["cep"]) != 8:
                rel.erros.append(f"{n}: CEP deve ter 8 dígitos ({d['cep']!r}).")
        if "uf" in d:
            d["uf"] = d["uf"].upper()
            if d["uf"] not in UFS:
                rel.erros.append(f"{n}: UF inválida ({d['uf']!r}).")
        if "email" in d:
            d["email"] = d["email"].lower()
            if not _EMAIL.match(d["email"]):
                rel.erros.append(f"{n}: e-mail inválido ({d['email']!r}).")
        if "numero_compl" in d:
            m = _NUMERO.match(d.pop("numero_compl"))
            if m:
                d["numero"] = m.group(1)
                if m.group(2).strip():
                    d["complemento"] = m.group(2).strip()
            else:
                d["complemento"] = _texto(row[cab["Número / compl."]])
                lin.avisos.append(f"{n}: número não reconhecido; texto inteiro foi para o complemento.")
        for campo, limite in (("numero", 20), ("complemento", 100), ("logradouro", 200), ("bairro", 100),
                              ("municipio", 100), ("razao_social", 200), ("contato_nome", 200), ("email", 200)):
            if len(d.get(campo, "")) > limite:
                rel.erros.append(f"{n}: {campo} passa de {limite} caracteres.")
        tem_empresa = any(k in d for k in CAMPOS_EMPRESA)
        if tem_empresa and "razao_social" not in d and "cnpj" not in d:
            lin.avisos.append(f"{n}: sem razão social; usei o nome do grupo.")
        rel.avisos.extend(lin.avisos)
        linhas.append(lin)

    vistos: dict[str, int] = {}
    for lin in linhas:
        c = lin.dados.get("cnpj")
        if c:
            if c in vistos and vistos[c] != lin.id_grupo:
                rel.erros.append(f"{lin.n}: o CNPJ {c} já aparece em outro cliente (ID {vistos[c]}).")
            vistos.setdefault(c, lin.id_grupo)
    return linhas


def _preencher(obj, valores: dict, rotulo: str, rel: Relatorio, sobrescrever: bool) -> bool:
    mudou = False
    for campo, valor in valores.items():
        atual = getattr(obj, campo)
        if atual in (None, ""):
            setattr(obj, campo, valor)
            mudou = True
        elif atual != valor:
            if sobrescrever:
                setattr(obj, campo, valor)
                mudou = True
            else:
                rel.conflitos.append(f"{rotulo}: {campo} já é {atual!r}; planilha traz {valor!r} (não alterado).")
    return mudou


def aplicar(sessao: Session, linhas: list[Linha], rel: Relatorio, *, sobrescrever: bool = False) -> None:
    """Grava as linhas. Chamar dentro de uma transação que o chamador confirma ou desfaz."""
    for lin in linhas:
        grupo = sessao.get(GrupoEconomico, lin.id_grupo)
        if grupo is None:
            rel.erros.append(f"{lin.n}: não existe grupo com ID {lin.id_grupo}.")
            continue
        d = lin.dados
        vals_e = {k: d[k] for k in CAMPOS_EMPRESA if k in d}
        empresa: Empresa | None = None
        if lin.id_empresa is not None:
            # Linha por empresa: vale o ID, não o nome nem o CNPJ digitado.
            empresa = sessao.get(Empresa, lin.id_empresa)
            if empresa is None or empresa.grupo_id != grupo.id:
                rel.erros.append(f"{lin.n}: a empresa {lin.id_empresa} não existe ou não é do grupo {grupo.id}.")
                continue
            if _preencher(empresa, {k: v for k, v in vals_e.items()}, f"{lin.n} (empresa)", rel, sobrescrever):
                rel.empresas_atualizadas += 1
            sessao.flush()
        elif vals_e:
            if "cnpj" in d:
                empresa = sessao.scalars(sa.select(Empresa).where(Empresa.cnpj == d["cnpj"])).first()
                if empresa and empresa.grupo_id != grupo.id:
                    rel.erros.append(f"{lin.n}: o CNPJ {d['cnpj']} já pertence a outro cliente no CRM.")
                    continue
            if empresa is None:
                razao = d.get("razao_social") or grupo.nome
                empresa = sessao.scalars(
                    sa.select(Empresa).where(Empresa.grupo_id == grupo.id, sa.func.lower(Empresa.razao_social) == razao.lower())
                ).first()
            if empresa is None:
                empresa = Empresa(grupo_id=grupo.id, razao_social=d.get("razao_social") or grupo.nome)
                sessao.add(empresa)
                _preencher(empresa, {k: v for k, v in vals_e.items() if k != "razao_social"}, f"{lin.n}", rel, sobrescrever)
                rel.empresas_criadas += 1
            elif _preencher(empresa, vals_e, f"{lin.n} (empresa)", rel, sobrescrever):
                rel.empresas_atualizadas += 1
            sessao.flush()

        nome = d.get("contato_nome")
        vals_c = {"cargo": d.get("contato_cargo"), "email": d.get("email"), "telefone": d.get("telefone")}
        vals_c = {k: v for k, v in vals_c.items() if v}
        if nome or vals_c:
            dono = {"empresa_id": empresa.id} if empresa else {"grupo_id": grupo.id}
            base = sa.select(PessoaContato).where(PessoaContato.grupo_id == grupo.id) if not empresa else \
                sa.select(PessoaContato).where(PessoaContato.empresa_id == empresa.id)
            achado = None
            if d.get("email"):
                achado = sessao.scalars(base.where(PessoaContato.email == d["email"])).first()
            if achado is None and nome:
                achado = sessao.scalars(base.where(sa.func.lower(PessoaContato.nome) == nome.lower())).first()
            if achado is None:
                sessao.add(PessoaContato(nome=nome or d.get("email") or grupo.nome, **dono, **vals_c))
                rel.contatos_criados += 1
            elif _preencher(achado, vals_c, f"{lin.n} (contato)", rel, sobrescrever):
                rel.contatos_atualizados += 1
            sessao.flush()
