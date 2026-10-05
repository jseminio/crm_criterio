"""Tarefas de manutenção de dados, aplicadas pelo Redeploy e **uma vez só** (#93, 05/10/2026).

Regra do dono: nenhuma mudança estrutural exige comando manual no servidor. Esquema muda por migração
Alembic; **dado** muda por uma tarefa daqui, que o `atualizador.sh` roda sozinho no próximo Redeploy
(`scripts/manutencao.py`) e registra em `manutencao_aplicada`.

Contrato de cada tarefa (`Tarefa`):

- `id` estável no formato `AAAA_MM_DD_assunto` (data em que foi escrita). **Nunca renomeie** um id
  já publicado: o banco o conhece por esse nome, e um id novo rodaria a tarefa de novo.
- `executar(sessao)` recebe uma sessão já dentro da transação da tarefa e **não faz commit**: quem
  confirma é o executor, junto com a linha em `manutencao_aplicada`. Se a tarefa levantar exceção,
  nada fica (nem o efeito, nem o registro) e ela roda de novo no próximo Redeploy.
- Devolve uma linha de resultado (contagens, nunca dado de cliente) ou `None`.
- Mesmo rodando uma vez, escreva-a de modo que rodar de novo não estrague nada (ex.: `UPDATE … WHERE`
  o valor ainda é o antigo): é a defesa contra um banco restaurado de um backup anterior a ela.

A lista fica em `crm.manutencao.registro.TAREFAS`, em ordem de aplicação.
"""

from crm.manutencao.executor import (
    TABELA,
    FalhaNaTarefa,
    Tarefa,
    aplicar_pendentes,
    estado,
    problemas_do_registro,
)

__all__ = ["TABELA", "FalhaNaTarefa", "Tarefa", "aplicar_pendentes", "estado", "problemas_do_registro"]
