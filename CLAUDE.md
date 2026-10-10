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
2. **A `main` só muda por PR mesclada**, nunca por commit ou push direto. O
   Claude pode mesclar sozinho a PR de uma demanda que Eduardo pediu, sem
   perguntar de novo, quando tudo isto valer (autorizado por Eduardo em 28/09/2026):
   - os testes do backend e das telas rodaram e passaram na branch já
     atualizada com a `main`;
   - a PR não tem nada da regra 6;
   - se a mudança é visível, a amostra já foi aprovada (regra 5).

   Depois de mesclar, avisa com o número da PR e o resultado dos testes. Faltando
   qualquer condição, abre a PR e espera. O push da branch da demanda faz parte do
   pedido; push para qualquer outra coisa, não.
3. **Nenhuma branch é apagada sem autorização**, nem local nem remota. A
   exclusão automática que o GitHub faz ao mesclar uma PR já está autorizada.
4. **Evidência ou não aconteceu.** Antes de propor um merge, rode os testes do
   backend e das telas e mostre o resultado. Se algo não rodou, diga que não rodou.
5. **Tela nova ou mudança visível:** mostre a amostra antes de construir e só
   construa depois do aprovado.
6. **Irreversível pede confirmação:** apagar, publicar, migração que descarta dado,
   carga que sobrescreve.

## Regra de implantação: nada manual no servidor

Decisão do dono em 05/10/2026 (#93). **Nenhuma mudança estrutural — banco, dados, configuração,
variáveis de ambiente — pode exigir comando manual no servidor.** Tudo é aplicado pelo Redeploy da
versão que sobe, via `app/backend/atualizador.sh` (chamado pelo `entrypoint.sh` antes da API):
ambiente → backup (`pg_dump`, só com migração pendente; gravado local no volume `crmcs_backups`,
retido 7 dias por `BACKUP_ANTES_DIAS`, sem nunca apagar o mais recente) → migrações → manutenção →
conferências.
Sem nada pendente, cada etapa diz "nada a fazer".

Checklist de todo PR estrutural:

- [ ] **Esquema:** migração Alembic nova, encadeada no head (`tests/test_migracoes.py`: uma ponta só).
- [ ] **Dado** (corrigir, preencher, mover linhas em banco que já existe): uma `Tarefa` no fim de
      `app/backend/src/crm/manutencao/registro.py`, com id `AAAA_MM_DD_assunto`, sem commit próprio e
      com teste. Roda uma vez no Redeploy e fica registrada em `manutencao_aplicada`.
- [ ] **Configuração de integração nova** (chave, token, endereço, liga/desliga): campo na tela
      Configurações › Integrações (`app/backend/src/crm/configuracao/catalogo.py`), com teste pela tela.
      Eduardo não configura nada à mão no painel do servidor (07/10/2026).
- [ ] **Variável de ambiente nova** (só o que a API precisa para subir): no catálogo `app/backend/src/crm/config.py` com padrão seguro
      (opcional, salvo se a API não tem como subir sem ela), no `app/backend/.env.example` e no
      `docker-compose.coolify.yml` como `${NOME:-padrão}` (ou `${NOME:?…}` se obrigatória).
      `tests/test_ambiente.py` derruba a suíte se faltar algum dos três.
- [ ] Configuração que não é segredo e muda com o negócio vai para o código ou para o banco, não
      para o painel.
- [ ] Nada de "depois do deploy, rode X no terminal": se precisa rodar, é etapa do atualizador.

## Segurança e dados

- Segredo só na tela Configurações › Integrações (cifrado no banco, decisão de Eduardo em 07/10/2026)
  ou no ambiente — nunca em código, JSON, nota ou log. Segredo salvo na tela nunca volta para o navegador.
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

## Apresentações

Decisão de Eduardo em 09/10/2026: **toda apresentação construída usa o template
da Critério**, em PowerPoint ou deck web. O template e o gerador ficam em
`apresentacoes/`; as regras e os layouts estão em `apresentacoes/README.md`.

- Use `apresentacoes/estilo-template.js`: os fundos do template, com rodapé e
  logomarca, a fonte Delight, os títulos à esquerda e o slide "Obrigado!" no fim.
- Gere a imagem de todos os slides e revise três vezes, uma para fórmulas, uma
  para design e uma para incorreções, antes de entregar.
- O gerador de cada apresentação, com nomes e valores de clientes, fica fora do
  repositório. Só o template e o estilo são versionados.

## Documentos históricos

Os `.md` da raiz anteriores a 23/09/2026 usam o vocabulário do vortexOS (PF-xx,
gates, RN-xx). Eles registram as decisões tomadas e **não se reescrevem**.
Mudança de comportamento atualiza o `app/README.md` no mesmo incremento.
