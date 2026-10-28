"""O que a edição de um contrato pode mudar, conforme a situação dele.

Saiu de `PATCH /api/contratos/{id}` em 18/10/2026 para valer igual na conferência do PDF assinado
(`crm.api.documentos`): o documento sugere, mas grava pelas mesmas regras da tela.
"""

from __future__ import annotations

from typing import Any

from crm.db.modelos import Contrato
from crm.domain import parcelas
from crm.domain.listas import SituacaoContrato

__all__ = ["problema_na_edicao"]


def problema_na_edicao(contrato: Contrato, mudancas: dict[str, Any]) -> str | None:
    """A frase de por que a edição não pode ser feita; `None` se pode."""
    # A tela manda o rascunho inteiro: só conta o que difere do valor atual.
    def comparavel(campo: str, valor: Any) -> Any:
        # As parcelas chegam como objetos e moram no banco como texto: compara-se o mesmo JSON (28/10/2026).
        return parcelas.gravar(parcelas.ler(valor)) if campo == "parcelas" else valor

    reais = {campo: valor for campo, valor in mudancas.items()
             if comparavel(campo, valor) != comparavel(campo, getattr(contrato, campo))}

    # Encerrado não se mexe mais — nem por evento, nem por edição. Sem isto, um
    # salvar voltava a situação para Ativo e destravava preço e data de fim.
    # Bruto ou líquido é como o valor se lê, não uma mudança no contrato: vale até no encerrado
    # (o churn dele também entra no MRR em bruto).
    # Parcelas no ano (11/10/2026), como o bruto ou líquido, é como o valor se lê: vale também no encerrado.
    if contrato.situacao is SituacaoContrato.ENCERRADO and set(reais) - {"base_do_valor", "parcelas_no_ano"}:
        return "contrato encerrado não se mexe mais"
    if mudancas.get("situacao") is SituacaoContrato.ENCERRADO and contrato.situacao is not SituacaoContrato.ENCERRADO:
        return "para encerrar, registre um evento de Encerramento com o motivo"

    # Depois de assinado, preço, fim e encerramento só mudam por evento: é o
    # que deixa o antes e o depois registrados.
    assinado = contrato.situacao in (SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO)
    if assinado:
        # Assinado não volta para antes da assinatura: "Aguardando assinatura"
        # destravaria o preço, e a volta para Ativo o mudaria sem evento.
        if "situacao" in reais and reais["situacao"] not in (SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO):
            return "contrato assinado só alterna entre Ativo e Suspenso; para encerrar, registre um Encerramento"
        for campo, evento in (("preco_mensal", "Reajuste, Expansão ou Contração"),
                              ("preco_anual", "Reajuste, Expansão ou Contração")):
            if campo in mudancas and mudancas[campo] != getattr(contrato, campo):
                return f"contrato assinado: para mudar o preço, registre um evento ({evento})"
        if "data_fim" in mudancas and contrato.data_fim is not None and mudancas["data_fim"] != contrato.data_fim:
            return "contrato assinado: para mudar a data de fim, registre uma Renovação"
    return None
