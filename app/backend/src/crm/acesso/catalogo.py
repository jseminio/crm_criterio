"""Menus, funcionalidades e o que cada rota da API exige (E1, 02/10/2026).

Pedido de Eduardo: perfis que liberam **funcionalidades dentro de cada menu**, com a opção de
liberar o menu inteiro. A permissão é `"menu.funcionalidade"` (ex. `"funil.converter"`); o perfil
Administrador tem tudo, inclusive o que for criado depois.

Toda rota da API está no mapa `ROTAS`. Rota fora do mapa é **recusada** (teste garante que nenhuma
fica de fora): esquecer uma rota nunca a deixa aberta.
"""

from __future__ import annotations

import re

__all__ = ["MENUS", "PERMISSOES", "PUBLICAS", "ROTAS", "permissoes_da_rota", "permissoes_do_comercial"]

MENUS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    ("agenda", "Agenda", (("ver", "ver"),)),
    ("contatos", "Contatos", (("ver", "ver"), ("editar", "criar e editar"), ("excluir", "excluir"))),
    ("funil", "Funil comercial", (
        ("ver", "ver"),
        ("editar", "criar e editar oportunidade e lead"),
        ("proposta", "montar e gerar proposta"),
        ("enviar_proposta", "marcar proposta enviada"),
        ("converter", "converter em contrato"),
        ("exportar", "exportar para Excel"),
        ("questionarios", "buscar e resolver questionários do site"),
    )),
    ("questionarios", "Questionários", (("ver", "ver"),)),
    ("grupos", "Grupos", (("ver", "ver"), ("editar", "editar"), ("fundir", "fundir e desfazer fusão"))),
    ("contratos", "Gestão de contratos", (
        ("ver", "ver"), ("editar", "editar"), ("eventos", "registrar evento"),
        ("aprovar", "aprovar eventos acima da alçada"),
    )),
    ("carteira", "Saúde da carteira", (
        ("ver", "ver"), ("avaliar", "avaliar e calcular"), ("parametros", "parâmetros"), ("exportar", "exportar"),
    )),
    ("sucesso", "Funil do Sucesso do Cliente", (("ver", "ver"), ("editar", "marcar etapas e registrar reuniões"))),
    ("abordagens", "Abordagens", (("ver", "ver"), ("editar", "preparar, editar e descartar"), ("aprovar", "aprovar e marcar enviada"))),
    ("sdr", "SDR da IA", (("ver", "ver"), ("editar", "registrar conversas"), ("parametros", "parâmetros e custos"))),
    ("conferencia", "Conferência", (("ver", "ver"),)),
    ("configuracoes", "Configurações", (
        ("propostas", "matrizes e numeração das propostas"), ("backup", "backup"),
        ("perfis", "perfis e acesso"), ("historico", "histórico de alterações"), ("metas", "metas dos indicadores"),
    )),
)
PERMISSOES: frozenset[str] = frozenset(f"{m}.{f}" for m, _, fs in MENUS for f, _ in fs)


def permissoes_do_comercial() -> list[str]:
    """O perfil inicial da Karine (decisão de Eduardo, 02/10/2026): o comercial inteiro, sem converter
    em contrato, sem Carteira e sem Configurações; contratos e grupos só para ver. O menu Questionários
    entrou em 02/10/2026, também para ver."""
    return sorted(
        {"agenda.ver", "questionarios.ver", "contatos.ver", "contatos.editar", "contatos.excluir", "grupos.ver", "contratos.ver",
         "abordagens.ver", "abordagens.editar", "sdr.ver", "sdr.editar", "conferencia.ver"}
        | {f"funil.{f}" for m, _, fs in MENUS if m == "funil" for f, _ in fs if f != "converter"}
    )


PUBLICAS: tuple[str, ...] = ("/api/acesso/entrada",)
"""Sem entrada nenhuma: a tela precisa saber como entrar antes de ter entrado."""

_TODOS = ()  # qualquer pessoa que entrou

# (métodos, padrão do caminho, permissões — basta ter uma). Ordem importa: a primeira que casa vale.
ROTAS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # comuns a quem entrou
    ("GET", r"/api/eu", _TODOS),
    ("GET", r"/api/listas", _TODOS),
    ("GET", r"/api/servicos(/pedidos)?", _TODOS),
    # acesso e histórico
    ("GET", r"/api/acesso/catalogo", ("configuracoes.perfis",)),
    ("GET|POST|PATCH", r"/api/acesso/(perfis|usuarios)(/\d+)?", ("configuracoes.perfis",)),
    ("GET", r"/api/historico", _TODOS),  # a rota confere: geral pede configuracoes.historico
    # agenda
    ("GET", r"/api/agenda", ("agenda.ver",)),
    # contatos e empresas
    ("GET", r"/api/contatos/pessoas/busca", ("contatos.ver", "funil.ver")),
    ("GET", r"/api/contatos/(pessoas|empresas)", ("contatos.ver",)),
    ("POST", r"/api/contatos/pessoas", ("contatos.editar",)),
    ("PATCH", r"/api/contatos/pessoas/\d+", ("contatos.editar",)),
    ("DELETE", r"/api/contatos/pessoas/\d+", ("contatos.excluir",)),
    ("GET", r"/api/empresas/busca", ("contatos.ver", "funil.ver", "grupos.ver")),
    ("POST", r"/api/empresas", ("contatos.editar",)),
    ("PATCH", r"/api/empresas/\d+", ("contatos.editar",)),
    ("DELETE", r"/api/empresas/\d+", ("contatos.excluir",)),
    ("POST|PATCH|DELETE", r"/api/empresas/\d+/contatos(/\d+)?", ("contatos.editar",)),
    # funil: oportunidades, leads, propostas, questionários, números
    ("GET", r"/api/oportunidades/exportar", ("funil.exportar",)),
    ("GET", r"/api/(oportunidades|funil|indicadores(/recortes|/cenarios-de-ticket)?)", ("funil.ver",)),
    ("GET", r"/api/mrr", ("funil.ver", "contratos.ver", "carteira.ver")),
    ("POST", r"/api/oportunidades", ("funil.editar",)),
    ("GET", r"/api/oportunidades/\d+(/(ficha|pendencias|proposta|questionario))?", ("funil.ver", "agenda.ver")),
    ("PATCH", r"/api/oportunidades/\d+", ("funil.editar",)),
    ("POST", r"/api/oportunidades/\d+/converter-em-contrato", ("funil.converter",)),
    ("PUT", r"/api/oportunidades/\d+/ficha/[^/]+", ("funil.editar", "funil.proposta")),
    ("POST|PATCH", r"/api/oportunidades/\d+/pendencias(/[^/]+)?", ("funil.editar", "funil.proposta")),
    ("POST", r"/api/oportunidades/\d+/proposta", ("funil.proposta",)),
    ("GET", r"/api/propostas/\d+/pptx", ("funil.ver",)),
    ("POST", r"/api/propostas/\d+/enviada", ("funil.enviar_proposta",)),
    ("GET", r"/api/propostas/(matrizes|configuracao)", ("funil.proposta", "configuracoes.propostas")),
    ("GET", r"/api/propostas/matrizes/\d+/pptx", ("funil.proposta", "configuracoes.propostas")),
    ("POST", r"/api/propostas/matrizes/[^/]+", ("configuracoes.propostas",)),
    ("PUT", r"/api/propostas/configuracao", ("configuracoes.propostas",)),
    ("GET", r"/api/leads", ("funil.ver",)),
    ("POST", r"/api/leads(/\d+/converter)?", ("funil.editar",)),
    ("PATCH", r"/api/leads/\d+", ("funil.editar",)),
    ("GET", r"/api/questionarios/painel", ("questionarios.ver",)),
    ("GET", r"/api/questionarios/\d+/respostas", ("questionarios.ver", "funil.ver")),
    ("GET", r"/api/questionarios(/\d+/pdf)?", ("funil.ver", "questionarios.ver")),
    ("POST", r"/api/questionarios/(buscar|\d+/resolver)", ("funil.questionarios",)),
    # grupos
    ("GET", r"/api/grupos(/sugestoes-de-fusao|/fusoes)?", ("grupos.ver", "funil.ver")),
    ("PATCH", r"/api/grupos/\d+", ("grupos.editar",)),
    ("POST", r"/api/grupos/\d+/empresas", ("grupos.editar", "contatos.editar")),
    ("POST", r"/api/grupos/(\d+/fundir|fusoes/\d+/desfazer)", ("grupos.fundir",)),
    # contratos
    ("GET", r"/api/contratos(/\d+)?", ("contratos.ver",)),
    ("PATCH", r"/api/contratos/\d+", ("contratos.editar",)),
    ("POST", r"/api/contratos/\d+/eventos", ("contratos.eventos",)),
    ("GET", r"/api/aprovacoes", ("contratos.aprovar",)),
    ("POST", r"/api/aprovacoes/\d+/(aprovar|recusar)", ("contratos.aprovar",)),
    # carteira
    ("GET", r"/api/carteira/exportar", ("carteira.exportar",)),
    ("GET", r"/api/carteira/.+", ("carteira.ver",)),
    ("POST|PATCH", r"/api/carteira/(parametros|periodo/janela)", ("carteira.parametros",)),
    ("POST|PUT|PATCH", r"/api/carteira/.+", ("carteira.avaliar",)),
    # funil do sucesso do cliente
    ("GET", r"/api/sucesso/cadencia", ("sucesso.ver", "configuracoes.metas")),
    ("PUT", r"/api/sucesso/cadencia", ("configuracoes.metas",)),
    ("GET", r"/api/sucesso/(funil|grupos/\d+/reunioes)", ("sucesso.ver",)),
    ("PATCH|POST", r"/api/sucesso/grupos/\d+/(itens|concluir-etapa|reunioes)", ("sucesso.editar",)),
    # abordagens do agente SDR
    ("GET", r"/api/abordagens(/resumo|/\d+)?", ("abordagens.ver",)),
    ("POST", r"/api/abordagens/\d+/(aprovar|marcar-enviada)", ("abordagens.aprovar",)),
    ("POST|PATCH", r"/api/abordagens(/\d+(/[a-z-]+)?)?", ("abordagens.editar",)),
    # SDR da IA
    ("GET", r"/api/sdr/.+", ("sdr.ver",)),
    ("PUT", r"/api/sdr/(parametros|midia)", ("sdr.parametros",)),
    ("POST", r"/api/sdr/conversas(/\d+/(encerrar|mensagens|nota))?", ("sdr.editar",)),
    # conferência da carga
    ("GET", r"/api/cargas(/\d+(/ocorrencias)?)?", ("conferencia.ver",)),
    # metas dos indicadores
    ("GET|PUT", r"/api/metas", ("configuracoes.metas",)),
    # backup
    ("GET|POST", r"/api/backup/(exportar|importar|verificar)", ("configuracoes.backup",)),
)
_COMPILADAS = [(set(m.split("|")), re.compile(p + r"/?"), ps) for m, p, ps in ROTAS]


def permissoes_da_rota(metodo: str, caminho: str) -> tuple[str, ...] | None:
    """As permissões que a rota aceita (basta uma); `()` = qualquer um que entrou; `None` = rota fora
    do mapa, que deve ser recusada."""
    for metodos, padrao, permissoes in _COMPILADAS:
        if metodo in metodos and padrao.fullmatch(caminho):
            return permissoes
    return None
