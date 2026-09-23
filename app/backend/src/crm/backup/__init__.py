"""Backup lógico: exporta e importa **os dados**, não o banco.

O arquivo é um `.zip` com:

- `manifesto.json` — versão do formato, revisão do esquema, contagem e
  impressão digital (SHA-256) de cada tabela;
- `dados/<tabela>.jsonl` — uma linha JSON por registro, colunas pelo nome.

Não depende de PostgreSQL: o mesmo arquivo importa em outro PostgreSQL ou num
SQLite. Vale para levar o CRM a outra máquina e para guardar cópia.

⚠️ O arquivo contém **todos os dados de cliente**, sem criptografia. Guarde fora
do repositório e fora de pastas compartilhadas.
"""

from crm.backup.formato import (
    VERSAO_DO_FORMATO,
    ErroDeBackup,
    ResumoDeBackup,
    exportar,
    importar,
    verificar,
)

__all__ = [
    "VERSAO_DO_FORMATO",
    "ErroDeBackup",
    "ResumoDeBackup",
    "exportar",
    "importar",
    "verificar",
]
