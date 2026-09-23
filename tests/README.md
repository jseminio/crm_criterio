# tests/ — criterio-crm

Estrutura criada no nascimento do projeto. **Os testes de verdade moram em
`app/backend/tests/` (pytest) e em `app/frontend/src/` (Vitest)** — é lá que
rodam hoje. Esta pasta ficou como o plano original de organização.

## O que entra aqui quando a construção começar

- `dados/` — testes da carga de 2026: contagem de 154 registros, normalização
  de situação, tipo de canal e temperatura, e o relatório do que foi corrigido.
- `dominio/` — regras de negócio (por exemplo: proposta aceita exige data de
  aceite).
- `api/` — testes do backend Python.
- `ui/` — testes das telas React.

## Regra

Todo bug corrigido gera teste de regressão. Relatórios arquivados como
`EVID-###`.
