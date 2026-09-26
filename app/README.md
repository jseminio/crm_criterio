# Critério CRM — aplicação

Código da **Etapa 1** do Critério CRM: o banco, a carga das propostas de 2026,
a API do funil e as telas. Cobre os incrementos E2 (*a carteira existe*) e E3
(*o funil funciona*), na ordem invertida que a proposta aprovada em 20/09/2026
autorizou por causa do prazo — e, desde 22/09/2026, o começo do E4 (*a
proposta nasce no CRM*): preço, serviço e criação de oportunidade direto na
tela, sem depender da planilha ou de um lead; desde 23/09/2026, a régua de
porte por volume (sugestão, nunca decisão), a captura de complexidade e
risco técnico, o começo do E5 (*os números aparecem*): ciclo médio de
vendas, cobertura do processo e dependência de canal — e o começo da
**Etapa 2** (*fechar o ciclo*): a oportunidade aceita vira contrato.

## Estado

| | |
|---|---|
| O que roda | Banco PostgreSQL, carga de 2026 repetível, API do funil e seis telas |
| Testes | **296** no backend, **113** nas telas, todos passando. Backend com pytest; telas com Vitest e Testing Library |
| Banco | PostgreSQL 18.6 local, seis tabelas (`contrato` desde 23/09/2026), migração aplicada. Dados de 2026 carregados: 155 oportunidades (153 da planilha + 2 do kit do Bruno), 138+ grupos |
| API | 20 rotas, em `127.0.0.1:8000`, **sem autenticação** — o E1 foi adiado |
| Telas | Funil em kanban (com arrasto entre colunas), oportunidades em lista, leads, grupos econômicos (com detalhe), contratos (novo, 23/09/2026) e conferência da carga. React com TypeScript, em `../frontend` |
| Fora do ar | Nuvem, login, backup automático (E1); documento da proposta, ficha de volumetria completa (E4); ticket médio, MRR e os seis indicadores de cobertura que exigem implantação/entrevista/classificação (E5); Clicksign, evento de contrato, renovação, saldo de horas de conforto, Implantação (Etapa 2) |

## Como rodar

```bash
cd backend
python3 -m venv ~/.venvs/criterio-crm
~/.venvs/criterio-crm/bin/pip install -e ".[dev]" openpyxl
PYTHONDONTWRITEBYTECODE=1 ~/.venvs/criterio-crm/bin/python -m pytest
```

> **Por que o ambiente virtual fica fora do repositório.** Mantém o
> repositório só com código e documentos: nada de binário, cache ou artefato de
> build versionado por engano. Pelo mesmo motivo o pytest roda sem cache em
> disco (`-p no:cacheprovider`).

## Contatos: clientes e prospects segregados (26/09/2026)

Menu **Contatos** (`crm/api/contatos.py`, `crm/domain/contatos.py`). Duas abas, **Clientes** e
**Prospects**, e dois modos de busca:

- **Empresa:** razão social, CNPJ (com ou sem pontuação) ou nome do grupo. Cliente = uma linha por
  empresa (CNPJ), com a mensalidade; prospect = o grupo (ou a empresa, quando já existe), com as propostas.
- **Pessoa:** nome, cargo, e-mail ou telefone.
- A busca **não depende de acento nem de caixa** ("acao" acha "Ação"), feita em Python porque o
  PostgreSQL não faz isso sem extensão e a base é pequena.
- **Lacunas** = o que falta dos sete itens da planilha de lacunas (contato, e-mail, telefone,
  logradouro, município, UF, CEP). Vários contatos se completam: sem lacuna de e-mail se *algum* tem.
  Filtro "só com lacunas".
- O painel da empresa cadastra e edita **contatos** (e-mail validado, papel, *não contatar* com a data)
  e o **endereço** (UF e CEP validados; CNPJ com dígito verificador e sem repetir). Contato pode ser da
  empresa ou **só do grupo** (aparece em todas as empresas dele, marcado "do grupo"). Prospect sem empresa
  ganha uma com "Cadastrar empresa", porque é nela que o endereço mora.
- `GET /api/contatos/empresas`, `GET /api/contatos/pessoas`, `POST/PATCH /api/contatos/pessoas`,
  `PATCH /api/empresas/{id}`, `POST /api/grupos/{id}/empresas`.

**Ainda fora:** duplicar contato entre empresas, importação de contatos em lote pela tela (segue pela
planilha), e as listas de campanha que **respeitam** o *não contatar* (o campo já é gravado).

## Carga da carteira anterior ao CRM (26/09/2026)

A carteira que já existia antes do CRM vem da planilha de saúde da carteira
(`Rentabilidade_Grupo_COMPLETO.xlsx`, aba **"4. Clientes"**: razão social, CNPJ, grupo econômico,
escopo e honorário mensal, uma linha por empresa). **O arquivo fica fora do repositório** (dado de
cliente). Ensaio, sem gravar:

```bash
cd backend
~/.venvs/criterio-crm/bin/python scripts/importar_carteira.py ~/Downloads/Rentabilidade_Grupo_COMPLETO.xlsx
~/.venvs/criterio-crm/bin/python scripts/importar_carteira.py <planilha> --aplicar   # grava, com backup antes
```

- Cada linha vira uma **Empresa** (por CNPJ) e um **Contrato Ativo** dela, com o honorário como preço
  mensal. `Contrato` ganhou `empresa_id` e `anterior_ao_crm`.
- **Não se inventa data de assinatura.** A planilha não a traz, então o contrato fica marcado
  `anterior_ao_crm`: pode ser Ativo sem `data_inicio`, conta no MRR **desde sempre** e **nunca aparece
  como "novo"** de um período. Se a data aparecer, basta preenchê-la depois.
- "Sem grupo" = cliente individual, com grupo de uma empresa só e o nome da razão social. Grupo que
  **já existe** no CRM é reaproveitado pela *chave do nome* (o de mais propostas, com aviso, se houver
  vários); Prospect que recebe cliente vira **Cliente**. Nomes diferentes viram grupo novo — a fusão
  continua sendo um clique humano.
- **Idempotente** (empresa por CNPJ, contrato por empresa) e **nada é sobrescrito**: preço diferente
  vira conflito no relatório. Tudo ou nada, com backup antes.
- Ensaio de 26/09/2026: 58 empresas, 58 contratos, 31 grupos (7 reaproveitados, 24 novos), R$ 227.462,65
  por mês, nenhum erro (58 CNPJs válidos). 14 escopos "verificar contrato" ficam em branco.

**Reconciliação dos totais (26/09/2026) — resolvida.** O R$ 226.341 oficial é a linha TOTAL da aba de
Faturamento e bate com a soma das 31 unidades da aba "Margem por Grupo". O CRM (aba "4. Clientes", por
empresa) difere em **+R$ 1.121,45**, e toda a diferença vem de **4 unidades** (duas a mais, duas a
menos), cuja decisão de qual valor vale é de Eduardo. O ticket médio de 23/09 (R$ 229.641,20) é o oficial
mais R$ 3.300 de uma delas. Nada foi alterado no banco por causa disso.

**Três totais que não são o mesmo número:** R$ 227.462,65 (soma das empresas na aba "4. Clientes"),
R$ 229.641,20 (31 unidades, ticket médio de 23/09, com o grupo Blac pela aba "Margem por Grupo") e
R$ 226.341 (MRR oficial de 19/09/2026). Conferir antes de tratar o MRR do CRM como o oficial.

## MRR dos contratos registrados (26/09/2026)

`GET /api/mrr` e o painel no topo de **Contratos** (`crm/domain/mrr.py`). Sem parâmetros, vale o
mês corrente até hoje; `de`/`ate` mudam o período (não passa de hoje).

**⚠️ É parcial, e a tela e a API dizem isso sempre** (`cobertura_completa: false`). O KPI oficial
de MRR é a receita da **carteira inteira** (R$ 226.341 em 19/09/2026, em planilha fora do CRM);
aqui só entram os contratos registrados no CRM, e a carteira anterior ainda não foi carregada
(Etapa 3). Por isso o número **não é comparado com a meta de R$ 400 mil** nem com o alerta de
R$ 200 mil: seria um "atingimento" enganoso. Hoje há **0 contratos**, então o MRR é R$ 0,00.

- **MRR atual** = preço mensal dos contratos **Ativos**. **Suspenso** aparece à parte. Contrato sem
  preço mensal (só anual) **fica de fora** e é contado: não se inventa "anual ÷ 12".
- **Movimento do período:** novos (pelo preço da assinatura) · expansão · reajuste · contração
  (qualquer queda de preço) · **churn separado por quem decidiu**: cliente (churn de fato) e
  Critério (saída organizada). A conta fecha: início + novos + expansão + reajuste − contração −
  churn = fim.
- **NRR** e **GRR** contam só contratos que já existiam no início do período. Sem MRR no início,
  **não são calculáveis** (nunca 0%).
- MRR em qualquer data = MRR atual − o movimento líquido desde então.

**Fora:** comparação com a meta, MRR da carteira anterior (Etapa 3), e a inadimplência (o KPI oficial
conta receita contratada, e 41% dela estava travada por inadimplência em 19/09/2026: o MRR pode estar
saudável enquanto o caixa não entra).

## Etapa 2 — eventos de contrato (26/09/2026)

**Decisão de Eduardo: a vigência do contrato começa na assinatura.** Por isso:

- `data_inicio` do contrato é a **data da assinatura**, e o contrato nasce **sem ela** (antes
  partia da data do aceite — decisão de 23/09/2026 **revista**). Sem a data, **não vira Ativo**.
- Só contrato **Ativo ou Suspenso** recebe evento; antes da assinatura (409) ou depois de
  encerrado (409), não. Evento não pode ser anterior à assinatura.
- **Depois de assinado, preço e data de fim só mudam por evento** (o `PATCH` recusa com 422); e
  **encerrar só por evento com motivo**. O rascunho inteiro com os mesmos valores não conta como mudança.

`POST /api/contratos/{id}/eventos` valida, grava o evento **com o antes e o depois** e aplica o
efeito no contrato, tudo na mesma transação (`crm/domain/eventos_de_contrato.py`):

| Tipo | Exige | Efeito |
|---|---|---|
| Aditivo | descrição | opcionalmente novo escopo e/ou preço |
| Reajuste | novo preço | novo preço, para cima ou para baixo |
| Expansão | novo preço, não menor | novo preço |
| Contração | novo preço, não maior | novo preço |
| Renovação | nova data de fim, depois da atual | nova data de fim |
| Encerramento | **motivo** | situação Encerrado; fim = data do evento |

Cada evento é **imutável**: não há rota para editar nem apagar; errou, registra outro. Ainda não
registra **quem** (sem login, E1). A tela de Contratos mostra os eventos e registra em dois passos.

**Renovação na agenda:** contrato Ativo com data de fim entra na fila como "Vencimento do
contrato" (a data usada é a do fim, **sem prazo de aviso inventado**).

**Quem decidiu encerrar (26/09/2026, pedido de Eduardo).** O encerramento também exige a
**iniciativa**: `Cliente` ou `Critério`. É o que separa *churn* (o cliente saiu) de *saída
organizada* (a Critério saiu). Fica **separada** da categoria do motivo (que diz *por que*), e as
duas se combinam livremente: "Preço" pode ser o cliente que achou caro ou a Critério que reajustou
para sair. O sistema **não amarra** as duas (por exemplo, não obriga "Saída organizada" a ser
Critério): quem registra decide.

**Correção (26/09/2026).** Sétimo tipo de evento, para corrigir um valor **lançado errado** (por
exemplo, na carga inicial): exige novo preço **e o motivo**, guarda o antes e o depois, mas **não é
movimento comercial**: não conta como expansão, contração nem reajuste no MRR, e o MRR do início do
período já é o valor corrigido. Foi usado para levar 7 contratos ao valor oficial de 19/09/2026 (R$ 226.341,20):
sem esse tipo, corrigir apareceria como R$ 5.300 de contração e R$ 1.578,54 de expansão que nunca
aconteceram no negócio. Com o grupo de três empresas (R$ 27.930,00 no oficial, dividido igualmente, R$ 9.310,00 cada, porque a
planilha não traz a divisão), **o MRR do CRM fechou em R$ 226.341,20, igual ao oficial de 19/09/2026**, com
movimento zero no mês (7 eventos de correção, 4 unidades).

**Motivo de encerramento (26/09/2026).** O encerramento exige a **categoria do motivo**, de uma
lista de nove itens (`MotivoDeEncerramento`): Preço · Insatisfação com o serviço · Migrou para
concorrente · Internalizou a operação · Empresa encerrada, vendida ou reestruturada ·
Inadimplência · Saída organizada pela Critério · Não precisa mais do serviço · Outro. "Outro"
exige texto; nas demais o texto é opcional. A categoria só vale no Encerramento (422 nos outros
tipos). **Lista aprovada por Eduardo em 26/09/2026.** Nenhum documento trazia uma lista de motivos de saída;
ela partiu da lista de motivos de recusa e do conceito de "saída organizada" (classe C). Fica como
texto no banco, para mudar com um `UPDATE`. Responde *por que saiu*; *quem decidiu* é o campo `iniciativa`.

**Fora, por decisão pendente:** alçadas de aditivo (presumidas no `anexo-tecnico.md`), NRR,
Clicksign e implantação.

## Etapa 2 — agenda de follow-up (25/09/2026)

`GET /api/agenda` e a tela **Agenda** montam a fila do que pede uma próxima ação, por urgência
(`crm/domain/agenda.py`). Baldes: **atrasadas**, **hoje**, **próximos 7 dias**, **depois**,
**sem data** e **sem próxima ação**. Entra só o que está em aberto: oportunidade não decidida e
lead ainda no funil.

**O achado que desenhou a tela:** das 50 propostas em aberto, **nenhuma tinha próxima ação**
(cobertura do processo em 0%). Uma agenda só de datas ficaria vazia; por isso o balde
"sem próxima ação" existe, vem ordenado por temperatura e valor anual, e a linha permite
**escrever a próxima ação e a data ali mesmo**, sem abrir o painel. É por esse balde que a
cobertura do processo sobe.

- **Lembrete é tela, não notificação.** A API do WhatsApp continua pendente.
- Lead aparece na fila mas se edita na tela **Leads**.
- Contrato ainda não tem próxima ação; entra junto dos eventos de contrato.

## Histórico de preço e origem da volumetria (E4, 25/09/2026)

**Histórico de preço.** Cada mudança de `preco_mensal` ou `preco_anual` grava uma linha em
`historico_de_preco`: valor **antes** e **depois**, quando (relógio do servidor), de onde veio
(`CRM` ou `Recarga da planilha`) e o motivo, se alguém disse ("reajuste anual"). Reajustar
**não apaga** o preço anterior. A tela pede o motivo só quando o preço muda, e o detalhe da
oportunidade mostra o histórico, do mais recente para o mais antigo.

- A linha só nasce quando o valor **muda de fato**; salvar o painel sem mexer no preço não cria nada.
- É **imutável** (não herda o carimbo de alteração) e a API não tem rota para editá-la.
- Ainda não registra **quem** mudou: não há login. Entra com o E1.

**Origem da volumetria.** Cada um dos nove direcionadores da régua de porte pode dizer se
veio da **entrevista** ou do **questionário** (`origem_da_volumetria`, um mapa por
oportunidade). Só vale para campo preenchido: a origem de um campo que voltou a ficar vazio é
descartada pelo servidor, e a API recusa origem de campo que não seja direcionador (422).

**Ainda fora:** a *lista do que falta para a proposta, com responsável e prazo* e a *geração do
documento* — a primeira depende de definir os itens, a segunda do modelo oficial e do formato.

## Endereço da empresa

A tabela `empresa` ganhou, em 25/09/2026, `logradouro`, `numero`, `complemento`,
`bairro` e `cep` (só os 8 dígitos), somando-se a `municipio` e `uf`, que já
existiam. Todos opcionais. Nenhuma tela edita esses campos ainda: eles existem
para receber os dados preenchidos na planilha de lacunas de contato.

### Planilha de lacunas por empresa (26/09/2026)

`exportar_lacunas_contato.py` agora gera **duas abas separadas**: **Clientes** (uma linha por
empresa/CNPJ, com razão social, CNPJ, escopo e mensalidade já vindos do CRM) e **Prospects** (uma
linha por grupo que ainda não é cliente). `ID_GRUPO` e `ID_EMPRESA` são a chave; a linha por empresa
atualiza **aquela** empresa pelo ID, não pelo nome nem pelo CNPJ digitado. A importação lê as duas abas
e os avisos dizem de qual veio ("Prospects, linha 12"). Planilha intacta = zero mudança.

### Devolver a planilha de lacunas de contato

```bash
cd backend
~/.venvs/criterio-crm/bin/python scripts/importar_lacunas_contato.py <planilha.xlsx>            # ensaio: não grava
~/.venvs/criterio-crm/bin/python scripts/importar_lacunas_contato.py <planilha.xlsx> --aplicar  # grava, com backup antes
```

Decisão de 25/09/2026: **o mesmo cliente pode ter várias empresas, em linhas separadas**
com o mesmo `ID_GRUPO`. Cada linha vira uma **empresa** (razão social, CNPJ, endereço) e
um **contato** (nome, cargo, e-mail, telefone) ligado a ela. Rodar duas vezes não
duplica. Valor já preenchido no CRM e diferente do da planilha vira **conflito** no
relatório e não é alterado, a menos que se use `--sobrescrever`. Erro (CNPJ inválido,
UF ou CEP fora do padrão, CNPJ repetido em dois clientes) bloqueia a gravação inteira.
Sem razão social na linha, a empresa usa o nome do grupo (aparece como aviso).

## Backup lógico (exportar e importar os dados)

Leva **os dados**, não o banco: um `.zip` com um arquivo `.jsonl` por tabela e um
manifesto com a contagem e a impressão digital (SHA-256) de cada uma. O mesmo
arquivo importa em outro PostgreSQL ou em SQLite, sem depender de versão de banco.

```bash
cd backend
~/.venvs/criterio-crm/bin/python scripts/backup.py exportar            # ~/Backups-CRM/crm-AAAAMMDD-HHMMSS.zip
~/.venvs/criterio-crm/bin/python scripts/backup.py verificar <arquivo> # confere sem tocar no banco
~/.venvs/criterio-crm/bin/python scripts/backup.py importar <arquivo>  # só em banco vazio
~/.venvs/criterio-crm/bin/python scripts/backup.py importar <arquivo> --substituir  # apaga o atual
```

Na tela, **Configurações** faz o mesmo: baixar o backup, conferir o arquivo e importar.

- **Tudo ou nada:** a importação roda numa transação; qualquer erro desfaz por inteiro.
- **Recusa destino com dados** e esquema de outra revisão (rode `alembic upgrade head` antes).
- **Só na máquina do CRM:** as rotas `/api/backup/*` recusam pedido que chegue por
  túnel (ngrok) ou host que não seja `localhost`, porque o arquivo tem todos os dados
  de cliente e a API não tem login.
- **Sem criptografia.** Guarde fora do repositório e de pastas compartilhadas.
- **Limite de conferência:** a importação em PostgreSQL (acerto das sequências) não foi
  testada num banco descartável — a máquina não permitiu criar um. Teste num destino
  vazio antes de depender dela.

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


### Backup automático diário

```bash
cd backend/scripts/agendamento
./instalar.sh            # agenda para todo dia às 12:00 (launchd, no macOS)
./instalar.sh remover    # desliga; os arquivos são mantidos
launchctl kickstart gui/$(id -u)/com.criterio.crm.backup    # roda agora
```

Grava `~/Backups-CRM/crm-auto-AAAAMMDD-HHMMSS.zip`, **confere o arquivo** e mantém os
últimos 14 automáticos. A retenção só apaga `crm-auto-*.zip` — nunca um backup manual nem
o `antes-de-importar-*` — e só depois de um backup novo e conferido. Se o Mac estiver
dormindo às 12:00, roda ao acordar. Falha (banco fora do ar, arquivo que não confere)
sai no `backup.log` e numa notificação do macOS; o log não guarda dado de cliente.

**O que este backup não é:** não sai da máquina. Se o disco falhar, ele vai junto. Copiar
`~/Backups-CRM` para fora (nuvem cifrada, disco externo) continua pendente e faz parte do E1.

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

#### Sugestões de fusão (25/09/2026)

`GET /api/grupos/sugestoes-de-fusao` e o painel no topo de **Grupos** apontam grupos que
parecem ser o mesmo cliente. **Só sugere; nunca funde.** A fusão é um clique de uma pessoa,
em dois passos, pelo `POST /api/grupos/{id}/fundir` de sempre. Regras em
`crm/domain/sugestoes_de_fusao.py`:

- **alta:** a *chave* do nome é a mesma (sem acento, sem caixa, sem o que está entre
  parênteses e sem o que vem depois de " - ");
- **média:** um nome contém o outro e o menor tem duas palavras ou mais. Cada sugestão
  média é **um par** de nomes, nunca uma corrente: "João Silva" e "Silva Santos" estão
  ambos dentro de "João Silva Santos" e viram dois pares, não um bloco de três (corrigido
  em 26/09/2026 — antes as ligações se encadeavam e um clique fundia clientes diferentes);
- **fora de propósito:** nome de uma palavra só dentro de outro ("Aeskins" e "Horas
  adicionais Aeskins") e nomes só parecidos na escrita ("BRA" e "BRAP") — falso positivo demais.

Com os dados de 25/09/2026: 19 sugestões entre os 138 grupos (contagem anterior à
correção dos pares; pode mudar). "Não é o mesmo cliente" some com a sugestão **só neste
navegador** (não grava no banco); se o navegador bloquear o armazenamento, ela some só até
recarregar a página. Quando uma junção falha em parte, o aviso fica no topo do painel.

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

**Prospect que já é cliente (26/09/2026).** Depois da carga da carteira, `sugerir_clientes` cruza cada
prospect com os clientes pelo **nome das empresas** de cada grupo (a carteira usa o grupo econômico e a
razão social; as propostas usam o nome que o comercial digitou, como "ASM retomada… - 3AW" para o "Grupo
3AW"). A **palavra em comum** (3+ letras, fora de uma lista de genéricas) precisa apontar para **um único
cliente**; cada sugestão é um **par** (cliente, prospect) com o cliente como principal, nunca uma
corrente. O motivo diz **onde** a palavra apareceu (no nome do grupo, evidência mais forte, ou numa
empresa). Prospects que apontam para dois clientes ficam de fora. Só sugere: quem funde é uma pessoa.
Em 26/09/2026: 28 pares, 14 com a palavra no nome do grupo e 14 só na razão social de uma empresa.
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

## A conciliação com o kit do Bruno (22/09/2026)

O Bruno passou um kit de 100 arquivos reconstruindo, a partir do próprio
e-mail e WhatsApp, um CRM paralelo (Twenty, numa VPS) enquanto foi o
comercial exclusivo da Critério. Eduardo pediu para complementar **só os
dados de 2026** com o que ele já conciliou — não para adotar o CRM dele.
O kit em si **não entrou no repositório** (dado de cliente, LGPD amarelo);
fica fora, no Downloads de quem processa.

`scripts/conciliar_kit_bruno.py` casa as 124 propostas de 2026 do kit contra
a carteira pela mesma chave da carga (nome + data + serviço + tipo). Resultado
real, contra o banco, em 22/09/2026:

```
Batem pela chave completa: 105
Reclassificação (servico/tipo_servico corrigido, chave_origem preservada): 9
Novas, aprovadas por Eduardo, inseridas com Origem.KIT_BRUNO_2026: 2 (CIH, BPO Contábil Andréa Curcio)
Fora do escopo, aguardando confirmação: 8
```

Duas lições que custaram uma rodada de correção cada:

- **Reclassificação não é dado novo.** Nome+data+serviço+tipo de 9 propostas
  batem por nome+data mas não pela chave inteira — o kit corrige o
  `tipo_servico` (às vezes o `servico`) que a planilha tinha errado. A chave
  de origem **não muda** — ela precisa continuar batendo com a recarga
  semanal da planilha — só o campo corrigido entra em `campos_do_crm`, pela
  mesma trava que protege edição manual na tela.
- **Nome parecido não é casamento automático.** Da primeira comparação por
  nome aproximado sobraram 19 "sem match"; pela chave real sobraram 10, das
  quais 6 acabaram sendo as mesmas propostas de novo, só com o nome escrito
  diferente entre kit e CRM (ex.: kit "Proposta Tupi" = CRM "Rádio Tupi",
  mesma data e serviço). O script **não** casa por nome aproximado — quando
  há mais de uma oportunidade candidata na mesma data (caso "Thiago Becker",
  duas propostas no mesmo dia), ele desiste e deixa para conferência manual,
  em vez de arriscar corrigir o campo errado.

Duas propostas do kit ficaram de fora por decisão de Eduardo: "Empresa XPTO"
(sem CNPJ, suspeita de nome-placeholder) e "CFO AaS - Restaurante Igor Dutra"
(o próprio arquivo do Bruno marca `tipo: pesquisar` — nem ele tinha fechado).

```bash
~/.venvs/criterio-crm/bin/python scripts/conciliar_kit_bruno.py <kit.csv>            # simula e desfaz
~/.venvs/criterio-crm/bin/python scripts/conciliar_kit_bruno.py <kit.csv> --gravar   # grava
```

## O começo do E4 — a proposta nasce no CRM (22/09/2026)

Eduardo aprovou o escopo (gate PF-07, amostra aprovada em chat) para dois
pedaços do E4, deixando de fora a geração do documento da proposta:

1. **Preço, serviço e data de originação viram editáveis** no painel de
   detalhe (`OportunidadeEdicao`, em `crm/api/esquemas.py`). Não foi preciso
   inventar mecanismo novo: os três campos já estavam em `CAMPOS` (a lista que
   `crm/carga/persistencia.py` usa para decidir o que a recarga da planilha
   pode sobrescrever) — só abrir o campo na tela já ativa a mesma trava que
   protege situação e temperatura desde 21/09/2026.
2. **`POST /api/oportunidades` cria a proposta do zero**, sem passar por lead
   nem por planilha. Mesmo padrão de `POST /api/leads/{id}/converter`: o
   grupo existente é reaproveitado pelo nome, ou nasce um novo. Nasce com
   `Situacao.ENVIAR_PROPOSTA` e `Origem.CRM`; `data_colocacao` sem valor vira
   a data de hoje no servidor, não na tela — dois clientes abrindo o
   formulário no mesmo minuto não podem divergir por relógio local.

Na tela, o botão "Nova oportunidade" mora no filtro (`Filtros`/`acao`), igual
ao seletor de Situação da tela Lista — mesmo lugar, mesmo padrão, em vez de
inventar uma barra de ações nova.

**Fora desta rodada, por decisão explícita:** gerar o documento da proposta
(PDF/Word) para enviar ao cliente. Precisaria de modelo aprovado e
provavelmente envolve o Bruno na definição do template — escopo maior,
adiado para quando entrar em pauta.

## A régua de porte — sugestão, nunca decisão (23/09/2026)

Especificada em `../regua-de-porte-e-plano-de-teste.md`. O próprio documento
avisa: aferida contra **um caso só**, "confirma que a escala não está
grosseiramente errada, não que está calibrada". Por isso o código nunca
decide — só sugere, sempre (`crm/domain/porte.py`).

```
base    = média dos direcionadores aplicáveis          (0 a 4, os que faltam ficam fora — nunca viram zero)
escopo  = +0,25 por serviço contratado além do primeiro (máx. +0,75)
grupo   = +0,50 se houver consolidação de grupo
audit   = +0,25 se a empresa for auditada
pontuação = base + escopo + grupo + audit → corte em Micro / Pequeno / Médio / Grande / Extra Grande
```

Os nove direcionadores (documentos fiscais, lançamentos contábeis, pagamentos,
contas bancárias, conciliações de cartão, empregados CLT, admissões e
desligamentos, CNPJs no escopo, tomadores de serviço) e complexidade/risco
técnico (nota 1 a 5, mesma escala do `modelo-classificacao-carteira.md`)
entram **na oportunidade, antes da proposta** — decisão da seção 7 do
documento: "nada no cálculo [automático] — mas complexidade e risco técnico
passam a ser preenchidos aqui, senão não há histórico para calibrar nada
quando a precificação automática entrar".

`GET /api/oportunidades/{id}` devolve `sugestao_de_porte` calculada na hora
(nunca gravada — muda se a régua mudar). O campo `porte` só grava quando uma
pessoa confirma ou sobrepõe, via `PATCH` — com `porte_definido_por` e
`porte_definido_em`, este último carimbado pelo **servidor**, não pelo
navegador. É esse par que vira material para recalibrar a régua depois.

> **Defeito real, corrigido antes de ir ao ar:** a tela manda o rascunho
> inteiro a cada "Salvar alterações", `porte` incluso mesmo quando ninguém
> mexeu nele. A primeira versão carimbava `porte_definido_em` só por `"porte"`
> estar presente no corpo do PATCH — não por ter mudado de valor —, então
> **qualquer** salvamento (editar preço, mudar temperatura) registrava uma
> "confirmação" fantasma. Corrigido comparando o valor novo contra o atual
> antes de carimbar; `tests/test_api.py::test_salvar_outro_campo_com_porte_null_no_corpo_nao_carimba_data`
> é a regressão.

### Decisões da seção 6 — registradas em 23/09/2026

O documento listava cinco pontos em aberto antes de ir além do código. Eduardo
decidiu:

| Ponto | Decisão | Status |
|---|---|---|
| Régua sugere ou decide | **Só sugere** — confirma o que já estava construído | ✅ Decisão tomada |
| Quem atribui complexidade/risco na fase comercial | **Em aberto** — qualquer pessoa preenche, sem regra formal, por enquanto | ⏳ Pendência, decisão adiada por escolha |
| Validação do Bruno no texto da seção 9 do questionário | **Fica para depois** — não bloqueia o CRM (campos já funcionam, independente do questionário formal existir) | ⏳ Pendência, decisão adiada por escolha |
| Teste da seção 4 (calibrar contra amostra real) | **Começou** — amostra fechada e ferramenta de comparação entregue | 🟡 Parcial, ver abaixo |
| Rodar o teste completo | Falta o levantamento dos 9 direcionadores reais | ⛔ Sem responsável definido |

**O teste da seção 4, até onde deu para ir sem sair do código:**

- **Fonte da amostra**: `Categorizado de clientes Curva ABC.xlsx` (não a
  planilha simples de rentabilidade — Eduardo pediu para trocar, por ser o
  modelo mais completo e mais atual).
- **Amostra**: 7 grupos de pior classificação + 3 de melhor — **Cargo,
  Aeskins, INBEL, Ritz, 3AW, Ihus, MR** (piores) e **Blac, JGAA, Queimado**
  (melhores). Excluídos da lista de piores: três holdings pessoais da equipe
  (não são clientes) e um grupo sem porte atribuído na planilha de origem.
- **"Porte hoje"** reduzido a um valor por grupo pela empresa de maior
  honorário dentro dele — regra necessária porque a planilha atribui porte
  por CNPJ, e um grupo pode ter CNPJs de portes diferentes.
- **Ferramenta entregue**: `Teste_Regua_Porte_Amostra.xlsx`, em
  `~/Downloads` — **fora do repositório**, dado de cliente (LGPD amarelo).
  Fórmulas conferidas contra `crm/domain/porte.py` (mesmo cálculo, mesmo
  resultado num caso de teste). Só falta preencher os nove direcionadores de
  cada grupo — os números reais viriam dos sistemas de cada cliente (Omie
  etc.), e **quem faz esse levantamento continua sem definição**.

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
| Taxa de conversão | **Calculado** desde 22/09/2026 | Denominador = decididas (Aceita+Recusada+Perdido), decisão de Eduardo. 38,1% sobre os dados reais, contra 26,1% se todas as trabalhadas contassem |
| Ciclo médio de vendas | **Calculado** desde 23/09/2026 | Originação → aceite, decisão de Eduardo. Só entra aceita com as duas datas — hoje 1 de 40 |
| Cobertura do processo | **Calculado** desde 23/09/2026 | % com próxima ação definida (em aberto) e % com ficha de volumetria completa — os dois únicos, dos oito do documento de negócio, que não exigem entidade fora da Etapa 1 |
| Dependência de canal | **Calculado** desde 23/09/2026 | % das propostas vindas da rede dos sócios — insight já identificado em `documento-de-negocio.md` |
| Ticket médio | **Fora do CRM** | R$ 7.407,78 — receita média por grupo/empresa na carteira inteira, decisão de Eduardo em 23/09/2026. Dado não está aqui (só as 2026). Cálculo pontual fora do CRM, ver abaixo |
| MRR | **Fora** | O oficial é da carteira inteira; aqui só há o preço mensal das propostas |

### A taxa de conversão

`TaxaDeConversao` (`crm/domain/indicadores.py`) divide aceitas por decididas —
em aberto não entra em nenhum dos dois lados, porque ainda pode fechar. Contra
os limiares oficiais da planilha de KPIs (meta 50%, alerta abaixo de 30%), o
resultado carrega `abaixo_do_alerta` e `atingiu_a_meta`, os dois `None` só
quando não há nenhuma decidida ainda — divisão por zero não pode virar 0%,
que pareceria "nada fechou" quando na verdade é "não dá para medir".

Na tela, o cartão mostra a etiqueta em palavra (**Abaixo do alerta** /
**Entre o alerta e a meta** / **Na meta**), nunca só a cor — regra 4 do
PAD-002.

### O ciclo médio, a cobertura e a dependência de canal (23/09/2026)

Três indicadores do E5, com as mesmas duas regras que já valiam para a
conversão: **nunca zero quando é "não calculável"**, e **sempre a palavra
junto do número**, nunca só o valor pelado.

- **`CicloMedioDeVendas`** — dias entre `data_colocacao` e `data_aceite`, só
  para aceitas com as duas datas. Decisão de Eduardo sobre a base (era a
  pendência registrada desde 21/09/2026). Aceita sem as duas datas fica de
  fora da média — não vira zero dias, que pareceria "fechou na hora".
- **`Cobertura`** — dos oito indicadores de cobertura do processo listados em
  `documento-de-negocio.md` (seção 12.5), só dois não exigem entidade que a
  Etapa 1 não modela (reunião, classe da carteira, entrevista, implantação,
  contrato): % de oportunidades em aberto com próxima ação definida, e % com
  ficha de volumetria completa (os nove direcionadores de `crm.domain.porte`,
  todos preenchidos).
- **`DependenciaDeCanal`** — % das propostas que nasceram da rede dos sócios
  (`TipoCanal.SOCIOS`). Insight que o documento de negócio já tinha calculado
  à mão (56% em 19/09/2026); agora atualiza sozinho a cada filtro.

### Ticket médio da carteira (26/09/2026, recalculado)

Definição de Eduardo (23/09/2026): **receita mensal média por grupo, na carteira inteira**, não venda nova.
Antes ficava de fora da tela porque a carteira não estava no CRM; agora está, e o ticket sai dos
contratos ativos (`ticket_por_grupo` e `mediana_por_grupo` em `GET /api/mrr`, no painel de **Contratos**).
Empresas do mesmo grupo contam como um; cliente individual é um grupo de uma empresa. A mediana vai junto:
poucos grupos grandes puxam a média (os 2 maiores somam 37,7% do total).

| Momento | Grupos | Total mensal | Ticket médio | Mediana |
|---|---|---|---|---|
| 23/09 (divulgado; Tabor a R$ 4.500) | 31 | R$ 229.641,20 | R$ 7.407,78 | — |
| 26/09, valores corrigidos | 31 | R$ 226.341,20 | **R$ 7.301,33** | R$ 3.200,00 |
| 26/09, após a baixa do Tabor (30/06/2026) | **30** | R$ 225.141,20 | **R$ 7.504,71** | R$ 3.481,42 |

O ticket **sobe** com a baixa do Tabor (que estava abaixo da média), e o R$ 7.407,78 de 23/09 usava um
valor errado. Meta oficial: R$ 3.000, e a mediana está perto dela.

### Ticket recorrente aceito (25/09/2026)

Pedido de Eduardo: o ticket das vendas recorrentes de 2026, **com a mediana ao lado**.
Aparece como cartão no funil (`ticket_recorrente` em `GET /api/indicadores`).

- **Recorrente** = proposta aceita com preço mensal **maior que zero**. Consultoria de
  valor único, proposta sem preço mensal e o diagnóstico pro bono ficam de fora.
- **Segue os filtros da tela.** Sem filtro: 20 propostas, R$ 5.362,95 de média. Para
  "contratou em 2026" (data de colocação de 2026): **19 propostas de 17 clientes,
  R$ 105.259,08 por mês, média R$ 5.539,95 e mediana R$ 2.450,00**.
- **Traz o peso do maior contrato** (R$ 40.000 = 38% do total): a média sozinha engana.
- **Não é o ticket médio da carteira** (R$ 7.407,78, decisão de 23/09/2026), que é receita
  média por grupo na carteira inteira. Grandezas diferentes; o cartão diz isso na tela.
- Só uma aceita tem data de aceite; por isso "contratou em 2026" usa a data de colocação.

### Recortes e cenários de ticket (25/09/2026)

Duas tabelas no funil, abaixo dos números, ambas **seguindo os mesmos filtros da tela**:

- **Recortes** (`GET /api/indicadores/recortes?dimensao=servico|tipo_canal|captador`):
  propostas, aceitas, conversão, contratos recorrentes, mensal aceito, ticket e mediana por corte.
  Sem valor no campo, o corte aparece como "(não informado)", nunca some.
- **Cenários de ticket** (`GET /api/indicadores/cenarios-de-ticket`): conservador, base e
  otimista, com o contrato atípico à parte. **Hipóteses de trabalho, não meta.**

Regra dos cenários (`crm/domain/recortes.py`), estatística e não escolha manual:
**atípico** = recorrente acima de 3 × a mediana; **conservador** = mediana sem atípicos;
**base** = média sem atípicos; **otimista** = terceiro quartil sem atípicos; o atípico entra
pelo menor, médio e maior observados. **Trava** (26/09/2026): o conservador nunca passa do base
e o otimista nunca fica abaixo dele — mediana e quartil não têm ordem garantida com a média
(em 100, 1.000, 1.000, 1.000 a mediana é 1.000 e a média, 775). Na tela, "clientes novos" e
"1 atípico a cada … clientes" são editáveis (padrão 20 e 20) e **não gravam nada**. Menos de 4 contratos recorrentes: "não calculável".

Com o período filtrado por **data de colocação de 2026**: 19 contratos, 2 atípicos, comum de
R$ 2.450 / R$ 2.956,42 / R$ 3.500 e atípico de R$ 15.000 / R$ 27.500 / R$ 40.000 — os números
validados em 25/09/2026. **Sem filtro** entra mais um contrato recorrente sem data de colocação
(20 contratos), e a base cai para R$ 2.903,28. Não considera cancelamento nem o tempo até faturar.

### Corte por período (22/09/2026)

Pedido de Eduardo: comparar um recorte de tempo contra o resto da carteira —
ex. o efeito de um teste de prospecção rodado só em julho. `data_de`/`data_ate`
entram em `_consulta_de_oportunidades` (`crm/api/app.py`), a função que as três
rotas de funil compartilham — o corte vale no kanban, na lista e nos
indicadores de uma vez, sem repetir a regra em três lugares.

`data_tipo` escolhe o campo: `colocacao` — rotulado **"Originação"** na tela,
por pedido de Eduardo em 22/09/2026 — (quando a proposta foi enviada, o
padrão, e o que mede o efeito de um teste de prospecção) ou `aceite` (quando
foi decidida). Os dois existem em `Oportunidade`; medem perguntas diferentes.
O nome interno do campo continua `data_colocacao`: só o rótulo visível mudou.

Na tela, `frontend/src/periodo.ts` resolve os atalhos (Este mês, Mês anterior,
Este trimestre, Trimestre anterior, Este ano, Ano anterior) em datas
concretas **no navegador** — a API só recebe `data_de`/`data_ate` prontos,
nunca o nome do atalho. "Personalizado" libera os dois campos de data para
digitar à mão.

## O começo da Etapa 2 — contrato (23/09/2026)

Eduardo pediu para avançar além da Etapa 1 ("Vamos deixar essas pendências
para depois. Avance para implementar a Etapa 2") e confirmou o escopo desta
rodada (gate PF-07, amostra aprovada em chat): **só o registro do contrato**,
sem Clicksign — a assinatura eletrônica fica para depois, por decisão dele.

`Contrato` (`crm/db/modelos.py`) nasce de uma oportunidade aceita, nunca do
zero: `POST /api/oportunidades/{id}/converter-em-contrato` recusa quem não
está em `Situacao.ACEITA` (422) e quem já tem contrato (409 — `oportunidade_id`
é única). Escopo e preço partem da proposta aceita mas podem ser ajustados no
corpo da conversão; `data_inicio` parte de `data_aceite` quando não vier.
Nasce sempre `Aguardando assinatura` — o documento existir não significa que
foi assinado. `GET/PATCH /api/contratos` e a tela "Contratos" (lista +
painel de edição, mesmo padrão de `Leads`) cobrem o resto do ciclo de vida.

**Fora desta rodada, por decisão explícita ou por `anexo-tecnico.md`
marcar "a confirmar":** Clicksign, evento de contrato (aditivo, reajuste,
expansão), renovação automática, saldo de horas de conforto, e Implantação —
esta última porque os documentos recomendam esperar a aprovação de
`MP-SC-01`, uma dependência externa ao projeto.

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

## Checar os tipos de verdade

```bash
cd frontend && npx tsc -b
```

**Não use `tsc --noEmit` sozinho.** `tsconfig.json` na raiz do frontend é só um
arquivo de projeto (`"files": []`, delega tudo via `references` para
`tsconfig.app.json` e `tsconfig.node.json`) — sem `-b`, o `tsc --noEmit`
verifica **nada** e sai limpo mesmo com erro real no código. Descoberto em
22/09/2026: o comando errado tinha sido usado a sessão inteira, e só quando
`tsc -b` rodou de verdade apareceram dois erros que estavam invisíveis —
um deles anterior a essa sessão, sem relação com o trabalho do dia. `npm run
build` já usa `tsc -b` corretamente; o risco era só nas checagens manuais.

## Testes das telas

82 testes com **Vitest** e **Testing Library**, em `frontend/src/**/*.test.{ts,tsx}`:

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
lead — só a conversão leva lá —, as três regras do arrasto no kanban acima, e
os três estados da taxa de conversão contra os limiares oficiais (abaixo do
alerta, entre alerta e meta, na meta), decidida em 22/09/2026.

Cada teste crítico foi verificado quebrando a regra de propósito e confirmando
que o teste pega — não basta o teste passar, ele precisa falhar quando o
comportamento muda.

**Numa máquina sob carga, `vitest run` pode não subir.** Aconteceu aqui: dois
núcleos, vários aplicativos abertos, `load average` acima de 300. Um worker por
arquivo de teste estoura o tempo de inicialização e o Vitest falha antes de
rodar um teste sequer — não é defeito do teste. `vitest.config.ts` roda com um
processo só (`maxWorkers: 1`), que sozinho já resolve isso.

**`isolate: false` foi tentado e revertido.** Parecia seguro em 21/09/2026 —
rodou limpo várias vezes — e virou instabilidade real em 22/09/2026, assim que
um quarto arquivo passou a mockar `../api/cliente` com um formato diferente
dos outros três: `isolate: false` reaproveita o registro de módulos entre
arquivos do mesmo processo, e o `vi.mock` de um arquivo às vezes vazava para
o teste seguinte — falha em cerca de 1 a cada 3 rodadas, sem padrão fixo.
Teste instável é pior que teste lento: ensina a ignorar falha. `maxWorkers: 1`
sozinho é suficiente; isolamento entre arquivos volta a ser o padrão.

## Ressalva de processo — resolvida

Este código começou em 20/09/2026, depois de Eduardo dizer "pode codar agora",
**antes da proposta do PF-09.5 existir**. O gate foi atravessado por instrução
direta, e por isso o código se limitou ao que não dependia das decisões abertas.

**No mesmo dia a situação foi regularizada:** as seis decisões fecharam, a
proposta foi escrita (`../proposta.md`) e **Eduardo a aprovou**, inclusive a
inversão E1 ↔ E2/E3. A construção do E2 e do E3 está liberada com gate cumprido.

Fica o registro porque a ordem importou: o código veio antes da proposta, e isso
só não custou nada porque o escopo foi contido de propósito.
