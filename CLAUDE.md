# CLAUDE.md — Critério CRM

Projeto independente desde 23/09/2026, por decisão de Eduardo. **Não é governado
pelo vortexOS**: não carregue `contexto.py`, não aplique pipeline PF/PA, gates
ou agentes de lá. O contexto da Critério e o estilo de comunicação do
`~/.claude/CLAUDE.md` global continuam valendo.

## Como rodar e testar

```bash
cd app && ./iniciar.sh                      # API em 127.0.0.1:8000, tela em localhost:5173
cd app/backend && PYTHONDONTWRITEBYTECODE=1 ~/.venvs/criterio-crm/bin/python -m pytest
cd app/frontend && npx vitest run
```

Banco: PostgreSQL 18 local. Credenciais só em `app/backend/.env`, a partir do
`.env.example`.

## Regras de trabalho

1. **Uma branch por demanda.** Antes de editar, confira `git branch --show-current`.
2. **A `main` só muda com autorização explícita de Eduardo**, seja commit, merge
   ou push. Nenhum push para o GitHub sem pedido.
3. **Nenhuma branch é apagada sem autorização**, nem local nem remota.
4. **Evidência ou não aconteceu.** Antes de propor um merge, rode os testes do
   backend e das telas e mostre o resultado. Se algo não rodou, diga que não rodou.
5. **Tela nova ou mudança visível:** mostre a amostra antes de construir e só
   construa depois do aprovado.
6. **Irreversível pede confirmação:** apagar, publicar, migração que descarta dado,
   carga que sobrescreve.

## Segurança e dados

- Segredo só em `.env` ou cofre — nunca em código, JSON, nota ou log.
- **Dado de cliente não entra no repositório:** nem planilha, nem nota de
  entrevista, nem saída de script de conferência.
- **A API não tem login** até o E1. Ela escuta só em `127.0.0.1`. O acesso
  remoto (ngrok, com `allowedHosts: true` no Vite) só se liga quando for usado
  e se desliga logo depois.
- Nota de entrevista e contrato assinado exigem controle de acesso quando
  houver login.

## Design

PAD-002, aprovado por Eduardo em 19/09/2026. A fonte da verdade é
`app/frontend/src/tokens.css`. As regras que aparecem no código: estado nunca
só por cor, uma ação primária por tela ou painel, os quatro estados de toda
lista, e a logomarca da Critério sempre sozinha.

## Documentos históricos

Os `.md` da raiz anteriores a 23/09/2026 usam o vocabulário do vortexOS (PF-xx,
gates, RN-xx). Eles registram as decisões tomadas e **não se reescrevem**.
Mudança de comportamento atualiza o `app/README.md` no mesmo incremento.
