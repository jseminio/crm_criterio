"""A matriz do contrato recorrente: um Word (.docx) com marcadores `{{campo}}` (aprovado por Eduardo em 14/10/2026).

O mesmo jeito da proposta (`crm.proposta.marcadores`), agora em Word: o CRM troca cada marcador pelo valor, no corpo,
nas tabelas, no cabeçalho e no rodapé, mesmo quando o Word quebrou o marcador em pedaços de formatação. Marcador sem
valor fica à vista, para a revisão pegar. As marcas INCLUÍDO / N/A dos anexos continuam sendo ajustadas no Word
(primeira versão).

Sem dependência nova: o .docx é um zip de XML, lido com `zipfile` e `lxml` (que já vem com o python-pptx).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

from lxml import etree

__all__ = ["MARCADORES", "OBRIGATORIOS", "Exame", "MatrizIlegivel", "examinar", "preencher"]

PADRAO = re.compile(r"\{\{\s*([A-Za-z_]+)\s*\}\}")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_PARTES = re.compile(r"^word/(document|header\d*|footer\d*)\.xml$")

#: Todos os marcadores que o CRM sabe preencher no contrato recorrente, com o que entra no lugar.
MARCADORES: dict[str, str] = {
    "numero": 'número do contrato com o ano: "102.2026" (a matriz traz "CONTRATO CCE_RJ1 {{numero}}")',
    "razao_social": "razão social do cliente",
    "cnpj": "CNPJ do cliente, formatado",
    "endereco": "endereço completo do cliente, com CEP",
    "competencia_inicial": 'primeira competência faturada: "novembro de 2026"',
    "atividade": "atividade econômica principal",
    "cnae": 'CNAE principal: "62.03-1-00"',
    "regime": "regime tributário",
    "faturamento": 'faturamento anual: "até R$ 18.000.000,00"',
    "filiais": '"Sem filiais" ou a quantidade',
    "lancamentos": 'limite de lançamentos: "300"',
    "funcionarios": 'quadro do DP: "64 CLT, 5 estagiários e 1 PJ"',
    "valor_contabil": 'honorário mensal líquido de Contábil e Fiscal: "R$ 7.200,00"',
    "bruto_contabil": "honorário mensal bruto estimado de Contábil e Fiscal",
    "valor_dp": 'honorário mensal líquido de Departamento Pessoal: "R$ 2.800,00"',
    "bruto_dp": "honorário mensal bruto estimado de Departamento Pessoal",
    "horas_contabil": "horas de consulta por ano, Contábil e Fiscal",
    "horas_dp": "horas de consulta por ano, Departamento Pessoal",
    "vencimento": 'dia do vencimento: "25"',
    "excedente_dp": 'valor por funcionário além do quadro: "R$ 50,00"',
    "data_extenso": 'data da emissão por extenso: "14 de outubro de 2026"',
    "signatario": "quem assina pela Critério",
    "cargo_signatario": "cargo de quem assina pela Critério",
    "cpf_signatario": "CPF de quem assina pela Critério",
}

#: Sem estes o contrato sai com dado de outro cliente ou sem número: a matriz não é usada.
OBRIGATORIOS: tuple[str, ...] = ("numero", "razao_social", "cnpj", "endereco", "data_extenso", "signatario")


class MatrizIlegivel(ValueError):
    """O arquivo não é um Word .docx que dê para abrir."""


@dataclass(frozen=True)
class Exame:
    encontrados: list[str]
    faltando: list[str]
    desconhecidos: list[str]


def _q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _abrir(conteudo: bytes) -> zipfile.ZipFile:
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(conteudo))
        arquivo.getinfo("word/document.xml")
        return arquivo
    except (zipfile.BadZipFile, KeyError) as erro:
        raise MatrizIlegivel("o arquivo não é um Word .docx") from erro


def _paragrafos(raiz) -> list:
    return list(raiz.iter(_q("p")))


def _textos(paragrafo) -> list:
    """Os `w:t` do parágrafo, na ordem, só dos runs diretos ou dentro de hiperlink/inserção (não os de caixas de texto
    aninhadas, que têm parágrafo próprio)."""
    return [t for t in paragrafo.iter(_q("t")) if _paragrafo_de(t) is paragrafo]


def _paragrafo_de(elemento):
    pai = elemento.getparent()
    while pai is not None and pai.tag != _q("p"):
        pai = pai.getparent()
    return pai


def _texto(paragrafo) -> str:
    return "".join(t.text or "" for t in _textos(paragrafo))


def examinar(conteudo: bytes) -> Exame:
    nomes: list[str] = []
    with _abrir(conteudo) as arquivo:
        for nome in arquivo.namelist():
            if _PARTES.match(nome):
                raiz = etree.fromstring(arquivo.read(nome))
                for p in _paragrafos(raiz):
                    for m in PADRAO.finditer(_texto(p)):
                        if m.group(1) not in nomes:
                            nomes.append(m.group(1))
    return Exame(
        encontrados=nomes,
        faltando=[n for n in OBRIGATORIOS if n not in nomes],
        desconhecidos=[n for n in nomes if n not in MARCADORES],
    )


def _trocar_no_paragrafo(paragrafo, valores: dict[str, str]) -> None:
    textos = _textos(paragrafo)
    desde = 0  # depois do último valor posto: um valor com "{{...}}" dentro não é trocado de novo
    while True:
        partes = [t.text or "" for t in textos]
        inteiro = "".join(partes)
        m = next((m for m in PADRAO.finditer(inteiro, desde) if m.group(1) in valores), None)
        if m is None:
            return
        inicio, fim = m.span()
        valor = valores[m.group(1)].replace("\n", " ")
        desde = inicio + len(valor)
        pos = 0
        primeiro = ultimo = None
        for i, t in enumerate(partes):
            if primeiro is None and inicio < pos + len(t):
                primeiro, ini_primeiro = i, pos
            if fim <= pos + len(t):
                ultimo, ini_ultimo = i, pos
                break
            pos += len(t)
        resto = partes[ultimo][fim - ini_ultimo:]
        textos[primeiro].text = partes[primeiro][: inicio - ini_primeiro] + valor + resto
        textos[primeiro].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        for i in range(primeiro + 1, ultimo + 1):
            textos[i].text = ""


def preencher(conteudo: bytes, valores: dict[str, str]) -> bytes:
    """Troca cada marcador conhecido pelo valor e devolve o .docx novo; o resto do arquivo sai byte a byte igual."""
    saida = io.BytesIO()
    with _abrir(conteudo) as entrada, zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as novo:
        for item in entrada.infolist():
            dados = entrada.read(item.filename)
            if _PARTES.match(item.filename):
                raiz = etree.fromstring(dados)
                for p in _paragrafos(raiz):
                    if "{{" in _texto(p):
                        _trocar_no_paragrafo(p, valores)
                dados = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
            novo.writestr(item, dados)
    return saida.getvalue()
