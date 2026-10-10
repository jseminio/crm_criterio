"""O registro das tarefas de manutenção de dados, em ordem de aplicação (#93).

Para acrescentar uma tarefa:

1. Crie `crm/manutencao/tarefas/<assunto>.py` (crie a pasta `tarefas/` com um `__init__.py` vazio na
   primeira vez) com uma função `executar(sessao) -> str | None`, que **não faz commit** (ver o
   contrato em `crm/manutencao/__init__.py`).
2. Acrescente **no fim** da lista abaixo, com o id `AAAA_MM_DD_<assunto>` (a data de hoje):

       from crm.manutencao.tarefas import preencher_origem
       ...
       Tarefa("2026_10_06_preencher_origem", "Preenche a origem vazia das oportunidades antigas",
              preencher_origem.executar),

3. Escreva o teste da tarefa (roda contra o banco de teste, como os outros) e rode a suíte:
   `tests/test_manutencao.py` já garante id único, formato e ordem.

No próximo Redeploy, o `atualizador.sh` aplica a tarefa uma vez e a registra em `manutencao_aplicada`;
os Redeploys seguintes dizem "nada a fazer". Nunca apague uma tarefa já publicada da lista: ela fica
como registro (o `--listar` de `scripts/manutencao.py` mostra o que já rodou).
"""

from __future__ import annotations

from crm.manutencao.executor import Tarefa
from crm.manutencao.tarefas import (
    configuracao_para_a_tela, meta_de_mrr_em_13_parcelas, premissas_em_13_parcelas, saida_dos_encerramentos_antigos,
)

TAREFAS: list[Tarefa] = [
    Tarefa("2026_10_07_configuracao_para_a_tela",
           "Copia para a tela de Integrações as chaves e configurações das variáveis de ambiente",
           configuracao_para_a_tela.executar),
    Tarefa("2026_10_09_premissas_em_13_parcelas",
           "Converte as premissas em reais do plano de MRR para a base de 13 parcelas (× 13 ÷ 12)",
           premissas_em_13_parcelas.executar),
    Tarefa("2026_10_10_meta_de_mrr_em_13_parcelas",
           "Converte a meta e o alerta do MRR para a base de 13 parcelas (R$ 433.333,33 e R$ 216.666,67)",
           meta_de_mrr_em_13_parcelas.executar),
    Tarefa("2026_10_10_saida_dos_encerramentos_antigos",
           "Preenche a saída efetiva dos encerramentos antigos com a data do evento (nada muda no MRR)",
           saida_dos_encerramentos_antigos.executar),
    # Acrescente no fim. Ex.: Tarefa("2026_10_06_assunto", "o que faz", modulo.executar),
]
