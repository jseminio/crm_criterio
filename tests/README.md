# tests/ — criterio-crm

Estrutura criada no nascimento do workspace, como exige a seção 16.1 do
Documento Fundador. **Ainda não há teste aqui**: o projeto está em PF-01
Discovery e nenhuma linha de código foi escrita.

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
