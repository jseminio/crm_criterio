# Critério CRM — aplicação

Código da **Etapa 1** do Critério CRM: o banco, a carga das propostas de 2026,
a API do funil e as telas. Cobre os incrementos E2 (*a carteira existe*) e E3
(*o funil funciona*), na ordem invertida que a proposta aprovada em 20/09/2026
autorizou por causa do prazo.

## Estado

| | |
|---|---|
| O que roda | Banco PostgreSQL, carga de 2026 repetível, API do funil e quatro telas |
| Testes | **247** no backend, **72** nas telas, todos passando. Backend com pytest; telas com Vitest e Testing Library |
| Banco | PostgreSQL 18.6 local, cinco tabelas, migração aplicada. Dados de 2026 carregados: 153 oportunidades, 138 grupos |
| API | 15 rotas, em `127.0.0.1:8000`, **sem autenticação** — o E1 foi adiado |
| Telas | Funil em kanban (com arrasto entre colunas), oportunidades em lista, leads, grupos econômicos (com detalhe) e conferência da carga. React com TypeScript, em `../frontend` |
| Fora do ar | Nuvem, login, backup automático (E1); proposta e preço (E4); demais KPIs (E5) |

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

Subir tudo com um comando (a API e a tela, cada uma no seu processo; Ctrl+C
derruba as duas):

```bash
./iniciar.sh        # abre em http://localhost:5173
```

Ele **falha antes de subir qualquer coisa**, dizendo o que fazer: ambiente Python
ausente, dependências da tela por instalar, PostgreSQL fora do ar, `.env`
ausente ou porta em uso. Os servidores caem quando a sessão que os iniciou
fecha — por isso o comando existe.

Ou à mão, cada um no seu terminal:

```bash
cd backend && ~/.venvs/criterio-crm/bin/python scripts/servir.py
cd frontend && npm install && npm run dev
```

A API escuta **só em `127.0.0.1`**, de propósito: não tem login. Não a exponha na
rede antes do E1.

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

Nada disso está no `alembic.ini`, que é versionado. O código lê o `.env`
sozinho — nenhum comando precisa exportar variável, e a senha não passa por
linha de comando nem fica no histórico do shell.

**Em desenvolvimento, use as partes separadas.** A senha vai **crua**, e quem
codifica é `crm.db.sessao`:

```
CRM_DB_USER=criterio_crm
CRM_DB_PASSWORD=a senha como ela é, com # @ / % ou espaço
```

**Na nuvem, use o endereço inteiro** — é como o provedor entrega — e ele tem
precedência sobre as partes:

```
CRM_DATABASE_URL=postgresql+psycopg://usuario:senha@servidor:5432/banco
```

> **Por que existem os dois.** Senha dentro de uma URL precisa de escape, e
> errar isso falha de um jeito cruel: o `#` inicia a âncora, **tudo depois dele
> é descartado em silêncio**, a senha chega truncada e o servidor responde
> apenas *password authentication failed*. Aconteceu aqui em 20/09/2026. As
> partes separadas eliminam a classe inteira de problema.

Sem nenhum dos dois, o código **para com mensagem clara** em vez de gravar dado
de cliente num SQLite improvisado.

```bash
cp backend/.env.example backend/.env   # e preencha CRM_DB_PASSWORD
cd backend && ~/.venvs/criterio-crm/bin/alembic upgrade head
```

Dois scripts ajudam quem prefere não abrir o arquivo. `scripts/definir_senha.py`
troca só a linha da senha e testa a conexão; `scripts/configurar_env.py` monta o
`.env` inteiro. Os dois pedem a senha sem mostrá-la e **exigem um terminal de
verdade** — por botão ou por pipe param com aviso em vez de morrer com erro de
leitura, que foi exatamente o que aconteceu na primeira vez.

### O servidor desta máquina

**PostgreSQL 18.6**, instalador EnterpriseDB, em `/Library/PostgreSQL/18`,
escutando em `localhost:5432`. Instalado por Eduardo em 20/09/2026 e
confirmado respondendo. **O pgAdmin que vem no instalador é compilado só para
Apple Silicon e não abre neste Mac Intel** (erro `-10661`); para uma interface
gráfica será preciso outra ferramenta. Os binários não estão no `PATH` por
padrão:

```bash
sudo mkdir -p /etc/paths.d && echo /Library/PostgreSQL/18/bin | sudo tee /etc/paths.d/postgresql
```

**A migração está aplicada neste servidor desde 20/09/2026.** Sobe, desce e
sobe de novo, e `alembic check` não acusa deriva entre modelos e esquema.

| Tabela | Colunas | Índices |
|---|---|---|
| `grupo_economico` | 10 | 2 |
| `empresa` | 13 | 2 |
| `pessoa_contato` | 14 | 3 |
| `lead` | 19 | 3 |
| `oportunidade` | 26 | 6 |

### Duas lições do primeiro contato com o PostgreSQL

Gerar migração contra SQLite e aplicar no PostgreSQL **não funciona**, mesmo com
tipos genéricos. A primeira tentativa morreu em:

```
column "nao_contatar" is of type boolean but default expression is of type integer
```

SQLite escreve `false` como `0`; o PostgreSQL exige `false`. A migração foi
regerada contra o PostgreSQL e passou. **Regra:** migração se gera contra o
banco de destino, sempre. SQLite serve para o teste rodar rápido, não para
decidir DDL.

O `alembic.ini` **não recebe a URL nem em memória**. O `configparser` trata `%`
como interpolação, e a senha chega codificada para endereço, cheia de `%23` e
`%40`. Passá-la por ali derrubava a migração com `invalid interpolation syntax`
— erro que não menciona senha nem URL, e custa caro para diagnosticar.

## A carga de 2026

`crm/carga/persistencia.py` grava as propostas e **sabe rodar de novo** — que é o
que a decisão de rodar em paralelo com a planilha exige. Resultado contra a
planilha real, no PostgreSQL, em 20/09/2026:

```
1ª carga: criadas 153 · grupos criados 138 · reaproveitados 15
2ª carga: criadas   0 · atualizadas 0 · sem mudança 153
```

**153 + 3 incompletas + 1 duplicata = as 157 propostas de 2026.**

Três princípios. **Identidade pelo conteúdo** — nome, data de colocação, serviço
e tipo de serviço; a posição na aba não é identidade, então inserir uma linha
acima não cria registro novo. **Nada muda em silêncio** — toda alteração entra no
relatório campo a campo, com antes e depois. **Nada é apagado** — registro que
sumiu da planilha permanece, porque sumir de uma planilha não é decisão de
negócio.

Dinheiro é arredondado para centavos **com aviso**: a planilha traz até dez casas
decimais, resíduo de fórmula. O arredondamento acontece antes da comparação, para
a recarga não acusar mudança de preço que não houve.

```bash
~/.venvs/criterio-crm/bin/python scripts/importar_2026.py <planilha>            # simula e desfaz
~/.venvs/criterio-crm/bin/python scripts/importar_2026.py <planilha> --gravar   # grava
```

**Sem `--gravar` nada é mantido**: faz tudo e desfaz no fim, mostrando o que
aconteceria. É o padrão de propósito.

### Quando o CRM e a planilha discordam

Com os dois rodando em paralelo, situação, temperatura, motivo de recusa e data
do aceite são editáveis **nos dois lados**. A regra: **quem editou no CRM tem a
última palavra sobre aquele campo.** Cada oportunidade lembra quais campos foram
mudados na tela (`campos_do_crm`), e a recarga não os sobrescreve. Se a planilha
discordar, a divergência vira uma pendência em **Conferência**, com os dois
valores lado a lado, para uma pessoa decidir.

A trava é **por campo, não por oportunidade**: editar a data do aceite não
congela a linha inteira, e o resto continua seguindo a planilha. Só conta o que
de fato mudou de valor — abrir o painel e salvar sem alterar nada não trava
nada.

> **Isto foi um defeito real, provado antes da correção.** A planilha não tem
> nenhuma data de aceite; preencher a data na tela e rodar a carga de novo a
> apagava (`2026-04-15 → vazio`). O relatório registrava a mudança, mas o dado já
> estava perdido. Teria acontecido na primeira vez que alguém preenchesse as 40
> datas.

### O grupo econômico que a carga não enxerga

A carga agrupa pelo **nome exato** do cliente, e a coluna de origem mistura
cliente com serviço (*"Sete Brasil (Leo Fraga) - Regularização do Bacen"* é uma
coisa só). Por isso o mesmo cliente aparece repartido: um deles em **nove** grupos.
Os 138 grupos são portanto um teto, não a carteira real. O reagrupamento é feito
por Eduardo na tela de grupos, um par por vez, com o histórico intacto — e
`scripts/conferir_grupos.py` lista os candidatos. Sua saída contém nome de cliente
e valor: **não a grave dentro do repositório**.

## Conferência da carga

O relatório de conferência **é gravado no banco**, não só impresso: `ExecucaoDeCarga`
guarda a rodada e `OcorrenciaDeCarga` cada linha dela. Sem isso ele aparecia no
terminal e sumia — e confiar na base, condição para largar a planilha, dependia
de alguém ter guardado a saída. A rodada é **imutável** de propósito: um
relatório que muda depois de escrito deixa de ser evidência.

Cada ocorrência pede algo diferente de quem lê, e são só três tipos:

| Tipo | O que é |
|---|---|
| **Precisa de você** | O que só uma pessoa resolve: linha que ficou de fora, duplicata, proposta aceita **sem data do aceite** — que entra no CRM e mesmo assim exige alguém |
| **Ajustado sozinho** | O que a carga corrigiu ou anotou sem perguntar: grafias unificadas, valores arredondados, campos vazios de propósito |
| **Mudou na recarga** | O que a planilha alterou desde a rodada anterior, com antes e depois |

A tela **Conferência** mostra, para a rodada escolhida: lidas → de 2026 → gravadas →
de fora, e **verifica que a conta fecha** (gravadas + de fora = de 2026). Se não
fechar, avisa em vermelho: há linha sumindo. Na carga real de 20/09/2026 fechou:
153 + 4 = 157.

Só grava rodada quem grava: a simulação (`importar_2026.py` sem `--gravar`) não
deixa rastro, porque um histórico cheio de ensaios deixaria de provar o que está
de fato no CRM. Guarda **só o nome do arquivo**, não o caminho.

## Indicadores do funil

`crm/domain/indicadores.py` calcula **pouco, de propósito**. Só entra o que os
dados de 2026 sustentam sem que alguém tenha de escolher uma definição. O que
não dá para calcular volta com o **motivo** e **o que falta** — nunca zero, nunca
traço: zero pareceria medição, traço esconderia que há trabalho a fazer.

| Indicador | Situação | Motivo |
|---|---|---|
| Propostas em aberto | Calculado | Inverso de `Situacao.decidida`: se as situações mudarem, a conta muda junto |
| Aceitas em 2026 | Calculado | Com quantas têm preço mensal — 20 das 40 são de valor único |
| Taxa de conversão | **Pendente** | Denominador: 38% ou 26%. O anexo técnico diz "não implementar sem a definição" |
| Ticket médio | **Pendente** | Venda nova ou receita média por grupo? |
| Ciclo médio | **Pendente** | 0 de 40 datas de aceite; a base do cálculo não está registrada |
| MRR | **Fora** | O oficial é da carteira inteira; aqui só há o preço mensal das propostas |

`GET /api/indicadores` aceita os mesmos filtros do funil.

## Lacunas da verificação automática da plataforma

A varredura de vazamento lê **o disco, não o índice do git**, e só abre arquivos
de uma lista fechada de extensões. Consequências concretas para este workspace:

| Arquivo | Efeito |
|---|---|
| `__pycache__/*.pyc` | Ignorado pelo git, mas varrido. Contornado com `PYTHONDONTWRITEBYTECODE=1` |
| `.env.example`, modelo de migração `.mako` | Extensão fora da lista: ficam em amarelo, **sem verificação** |
| `node_modules/` | Ignorado pelo git, mas varrido: cerca de 130 pendências falsas |
| `.tsx` | **Fora da lista: o código das telas inteiro não tem cobertura de segurança** |

O último não é ruído — é uma parte do sistema que ninguém verifica. **A varredura
é Zona Núcleo e não foi alterada.** Duas emendas resolveriam, ambas decisão de
Eduardo: respeitar o `.gitignore`, e aceitar `.tsx` como texto.

## Lições de teste

O banco de teste é SQLite em memória, com uma conexão compartilhada entre threads
— sem isso o `TestClient` roda a API noutra thread e ela lê um banco vazio,
diferente do que o teste gravou. Toda a suíte roda com o ambiente isolado: nenhum
teste enxerga o `.env` nem as variáveis de quem roda. Três testes de configuração
passavam só enquanto não existia `.env` e quebraram no instante em que ele foi
criado.

## Arrastar cartões no kanban

Cada cartão do `Funil` é `draggable`; soltar numa coluna diferente muda a
situação. Três regras, nenhuma delas óbvia de fora:

- **Soltar em "Aceita" não grava direto.** O cartão do kanban (`OportunidadeResumo`)
  não carrega `data_aceite` — só o detalhe traz. Adivinhar do lado do cliente
  arriscaria um PATCH que a API recusa (a mesma trava de 21/09/2026: aceita sem
  data). Em vez disso, o drop **abre o painel de detalhe com "Aceita" já
  selecionada** (`situacaoInicial` em `DetalheDaOportunidade`), e a validação
  que já existe — salvar desabilitado sem a data — cuida do resto sem duplicar
  a regra.
- **Soltar na própria coluna não faz nada.** Comparado antes de qualquer
  chamada à API.
- **Uma falha ao gravar mostra um aviso dispensável** (`.aviso-de-movimento`) e
  **não recarrega** — o cartão continua onde a última leitura confirmada o
  colocou, em vez de a tela mentir que a mudança aconteceu.

Verificado no navegador contra a API e o PostgreSQL reais (21/09/2026): mover
grava e recarrega; soltar em "Aceita" abre o painel sem PATCH; soltar na mesma
coluna não dispara nada; uma falha simulada de rede mostra o aviso, é
dispensável, e o cartão não se move.

> ⚠️ **O arrasto com mouse simulado pela ferramenta de automação não iniciou o
> gesto nativo do Chromium** — nenhuma chamada disparou, o cartão não se moveu.
> Testado via `DragEvent` despachado diretamente (que exercita exatamente o
> mesmo código que o navegador chama para um arrasto de verdade) e confirmado
> correto nos três casos acima. É a mesma API (`draggable`, `dragstart`,
> `dragover`, `drop`) que Trello e board de kanban qualquer usam com mouse
> real — mas **não pude confirmar com um mouse de verdade** nesta máquina.
> **Peço para Eduardo confirmar amanhã** arrastando um cartão de verdade.

## Testes das telas

76 testes com **Vitest** e **Testing Library**, em `frontend/src/**/*.test.{ts,tsx}`:

```bash
cd frontend && npx vitest run
```

Cobrem o que já quebrou de verdade ou pode quebrar em silêncio: formatação em
pt-BR (`formato.ts`, com o espaço fino sem quebra que o `Intl.NumberFormat`
insere — visualmente idêntico a um espaço comum, byte diferente), a regra 4 do
PAD-002 ("estado nunca só por cor") em `Etiqueta`, os quatro estados obrigatórios
de toda lista, o tratamento de erro da API (`ErroDaApi`, "fora do ar" vs.
"recusou"), e as travas com defeito real por trás: **aceita sem data de
aceite** trava o botão de salvar (o mesmo defeito corrigido no backend em
21/09/2026), **"Convertido" nunca é uma opção do seletor** de situação do
lead — só a conversão leva lá —, e as três regras do arrasto no kanban acima.

Cada teste crítico foi verificado quebrando a regra de propósito e confirmando
que o teste pega — não basta o teste passar, ele precisa falhar quando o
comportamento muda.

**Numa máquina sob carga, `vitest run` pode não subir.** Aconteceu aqui: dois
núcleos, vários aplicativos abertos, `load average` acima de 300. Um worker por
arquivo de teste estoura o tempo de inicialização e o Vitest falha antes de
rodar um teste sequer — não é defeito do teste. `vitest.config.ts` já roda com
um processo só (`maxWorkers: 1`) e sem isolar entre arquivos (`isolate: false`),
o que também deixou a suíte inteira em 5–6 segundos em vez de mais de um minuto.

## Ressalva de processo — resolvida

Este código começou em 20/09/2026, depois de Eduardo dizer "pode codar agora",
**antes da proposta do PF-09.5 existir**. O gate foi atravessado por instrução
direta, e por isso o código se limitou ao que não dependia das decisões abertas.

**No mesmo dia a situação foi regularizada:** as seis decisões fecharam, a
proposta foi escrita (`../proposta.md`) e **Eduardo a aprovou**, inclusive a
inversão E1 ↔ E2/E3. A construção do E2 e do E3 está liberada com gate cumprido.

Fica o registro porque a ordem importou: o código veio antes da proposta, e isso
só não custou nada porque o escopo foi contido de propósito.
