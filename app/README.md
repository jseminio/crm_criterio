# Critério CRM — aplicação

Primeiro código da **Etapa 1**, o incremento E2 (*a carteira existe*):
as listas controladas do funil e a carga das propostas de 2026.

## Estado

| | |
|---|---|
| O que roda | Normalização das listas e carga da planilha, com relatório de conferência |
| Testes | 86, todos passando |
| Banco | **ainda não** — o domínio é testável sem ele |
| API e telas | **ainda não** |

## Como rodar

```bash
cd backend
python3 -m venv ~/.venvs/criterio-crm
~/.venvs/criterio-crm/bin/pip install -e ".[dev]" openpyxl
PYTHONDONTWRITEBYTECODE=1 ~/.venvs/criterio-crm/bin/python -m pytest
```

> **Por que o ambiente virtual fica fora do repositório.** A verificação do
> vortexOS varre `workspaces/` inteiro à procura de vazamento da engine, e não
> consegue ler binário. Um `.venv` dentro do workspace gera **1887 pendências
> falsas** e enterra as reais. Pelo mesmo motivo o pytest roda sem cache em
> disco (`-p no:cacheprovider`).

Conferir a carga contra uma planilha real — **lê e mostra, não grava nada**:

```bash
~/.venvs/criterio-crm/bin/python scripts/conferir_carga.py "/caminho/Relatório Performance Comercial 2026.xlsx"
```

## Desenho

```
backend/src/crm/
  domain/listas.py        listas controladas e de-para — lógica pura
  carga/planilha_2026.py  normalização e relatório — lógica pura
  carga/arquivo.py        leitura do .xlsx — a única camada que sabe de arquivo
```

A separação é proposital: a normalização é testada sem abrir arquivo nenhum, e
os testes usam os valores que **existem de verdade** na planilha — as duas
grafias de "Sócio", o "Captação de recursos" no campo de temperatura, o
"#DIV/0!" numa célula de valor.

## Princípios que o código sustenta

**Nada é descartado em silêncio.** Todo valor que não converte vira aviso no
relatório, com o texto original preservado.

**O relatório de conferência é entregável, não log.** Sem ele ninguém confia na
base — e confiar na base é a condição para abandonar a planilha.

**Aviso ≠ bloqueio.** Aceita sem data de aceite avisa e entra; situação
desconhecida bloqueia. A distinção é do negócio, não do código.

## O que este código deliberadamente não faz

- **Não calcula preço nem margem.** As fórmulas seguem travadas pelos dois
  defeitos das planilhas — o churn sem célula e a possível inversão da
  disciplina no atrito. Ver `../modelo-classificacao-carteira.md`.
- **Não agrupa em grupo econômico.** A planilha não traz o grupo. Decisão de
  Eduardo em 20/09/2026: **carregar cada proposta como grupo próprio e reagrupar
  depois**, com função de fundir grupos no CRM. Ver `../planejamento.md`, seção 5.
- **Não calcula a taxa de conversão.** O denominador é decisão pendente — 38%
  ou 26%. `Situacao.decidida` marca o conceito e para por aí.

## A identidade da proposta

Eduardo decidiu **rodar o CRM em paralelo com a planilha**. A carga roda mais de
uma vez, então cada proposta precisa de identidade estável: reimportar não pode
duplicar.

`linha` não serve — número de linha se desloca quando alguém insere uma linha no
meio. Testei quatro candidatos contra as 157 propostas reais:

| Chave | Chaves distintas | Colisões |
|---|---|---|
| nome | 141 | 16 |
| nome + data de colocação | 146 | 11 |
| nome + data + serviço | 151 | 6 |
| **nome + data + serviço + tipo de serviço** | **156** | **1** |

**Adotada a última**, em `crm/carga/identidade.py`. Cinco das seis colisões
anteriores eram propostas legítimas e distintas — mesmo cliente, mesma data,
mesmo serviço, **valores diferentes**: são cenários alternativos oferecidos ao
cliente. Preservá-los é correto; fundi-los apagaria a negociação.

`linha` continua no modelo para apontar a origem no relatório de conferência.
Deixou de ser identidade.

> **Defeito confirmado na planilha.** Sobra **uma colisão real**: as linhas
> **317 e 318** são idênticas nos dezessete campos comparados. É linha repetida,
> não cenário alternativo, e infla a contagem e o valor do funil em uma proposta
> de consultoria. `detectar_duplicatas` separa os dois casos e **não decide
> nada** — descreve, para que uma pessoa confirme. **Confirme com a Karine.**

## O banco

Modelos em `crm/db/modelos.py`, migrações em `migrations/`. Cinco tabelas, que
são o que o E2 e o E3 pedem: `grupo_economico`, `empresa`, `pessoa_contato`,
`lead`, `oportunidade`.

**Contrato, implantação e carteira classificada não estão aqui.** Estão na
arquitetura, e cada uma depende de decisão humana ainda pendente.

### Três decisões que valem para todas as tabelas

**Listas controladas viram texto legível, não tipo nativo do banco.** Um `ENUM`
do PostgreSQL exige `ALTER TYPE` para ganhar um valor novo, e as listas são
proposta ainda não aprovada: vão mudar. Guardamos `"Enviar proposta"`, não
`"ENVIAR_PROPOSTA"`, para que uma consulta direta ao banco seja legível.

**Sem restrição de verificação duplicando a lista.** A validação já vive em
`normalizar_*`. Repeti-la no banco criaria a segunda cópia da mesma regra —
o oposto da diretriz da casa: *modelo único = manutenção única*.

**Exclusão nunca é física.** Grupo fundido não some: muda de situação e aponta
para quem o absorveu. É o que preserva o histórico quando uma empresa muda de
mão — e o que torna o caminho 2 reversível.

### Fundir grupos

A contrapartida do caminho 2. `crm/db/grupos.py` move empresas, oportunidades e
contatos, e cuida de duas coisas que passariam batidas:

- **um prospect que absorve um cliente vira cliente** — sem isso, reagrupar
  rebaixaria a carteira sem ninguém ter decidido;
- **a data de entrada do conjunto é a mais antiga** — é quando a Critério
  começou a atender, não quando descobriu o vínculo.

Recusa três fusões: um grupo nele mesmo, um grupo já fundido antes, e a que
fecharia um ciclo deixando os dois sem raiz.

### Credenciais

`CRM_DATABASE_URL`, lida do ambiente. **Não está no `alembic.ini`**, que é
versionado. Ver `.env.example`. Sem a variável, o código **para com mensagem
clara** em vez de gravar dado de cliente num SQLite improvisado.

```bash
cp backend/.env.example backend/.env   # e preencha
createdb criterio_crm
cd backend && ~/.venvs/criterio-crm/bin/alembic upgrade head
```

> ⚠️ **A migração ainda não subiu num PostgreSQL de verdade.** Não há Postgres
> nesta máquina — é a pendência de segunda-feira. Ela foi gerada e verificada
> contra SQLite: sobe, desce e sobe de novo, e `alembic check` não acusa deriva
> entre modelos e esquema.
>
> Os modelos usam só tipos genéricos — sem `JSONB`, sem array, sem `ENUM` nativo
> — exatamente para que o comportamento seja o mesmo nos dois bancos. Mas isso é
> argumento, não evidência. **O esquema precisa subir uma vez no Postgres real
> antes de qualquer dado entrar.**

## Ressalva de processo — resolvida

Este código começou em 20/09/2026, depois de Eduardo dizer "pode codar agora",
**antes da proposta do PF-09.5 existir**. O gate foi atravessado por instrução
direta, e por isso o código se limitou ao que não dependia das decisões abertas.

**No mesmo dia a situação foi regularizada:** as seis decisões fecharam, a
proposta foi escrita (`../proposta.md`) e **Eduardo a aprovou**, inclusive a
inversão E1 ↔ E2/E3. A construção do E2 e do E3 está liberada com gate cumprido.

Fica o registro porque a ordem importou: o código veio antes da proposta, e isso
só não custou nada porque o escopo foi contido de propósito.
