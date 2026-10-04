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
**Etapa 2** (*fechar o ciclo*): a oportunidade aceita vira contrato. Desde
26/09/2026, o **agente SDR** do go-to-market: pesquisa a conta, monta a ficha
e o rascunho da abordagem — e nada sai sem a aprovação de Eduardo. Desde
27/09/2026, o **SDR de IA** que qualifica leads de tráfego pago e leads frios:
a etapa de lead voltou, as conversas são registradas e o painel mede o
resultado (ver "SDR de IA", abaixo).

## Funil comercial › Inteligência de Conversão: o plano de MRR (03/10/2026)

Aprovado por Eduardo em 03/10/2026, Entrega 1. Terceira aba do Funil comercial ("Inteligência de
Conversão", permissão "Funil comercial: ver"). Regras em `crm.domain.plano_de_mrr`; a tela lê
`GET /api/inteligencia/plano` (`crm.api.inteligencia`).

- **A meta é acréscimo líquido sobre a receita atual** (R$ 250 mil até 30/06/2027): venda nova e
  escada menos churn e contração. A barra mostra o realizado contra o previsto até hoje; a situação
  vem com palavra e seta (no ritmo ≥ 100% do previsto, atenção de 90% a 99%, abaixo < 90%).
- **Três motores**: BPO Financeiro (clientes por mês no ticket, até o teto da célula), Contábil
  (limitado pelas vagas de onboarding; o atípico ocupa duas; os contratos previstos do pipeline
  entram no mês deles) e a **escada** (Plus e depois CFO as a Service, após o prazo). Churn mensal de
  `churn_anual_pct ÷ 12` sobre a carteira do começo do mês.
- **Três cenários** com as mesmas regras: alerta, previsto (o compromisso) e otimista. O gráfico
  compara o acumulado realizado com os três; "Ver o gráfico em tabela" mostra os mesmos números.
- **Realizado** = movimento do MRR dos contratos do CRM, em bruto, separado por motor pelo serviço.
  Reajuste e expansão de contrato contábil entram em "outros movimentos", sem previsto.
- **Premissas**: só quem tem "Configurações: metas" muda (`PUT /api/inteligencia/plano`), e a mudança
  vai para o histórico de alterações. Sem nada gravado, valem as de `PADRAO`.
- **Cenários de ticket** saíram da aba Oportunidades e passaram a ser por serviço, nesta aba
  (`GET /api/inteligencia/cenarios-de-ticket`).
- Migração `a7c3e9f1b5d2`: só acrescenta as tabelas `plano_de_mrr` (vazia) e
  `contrato_previsto_do_plano`, com os três contratos previstos de 03/10/2026, sem nome de cliente.

## Funil do Sucesso do Cliente por classe, com vendas na ata (03/10/2026)

Aprovado por Eduardo em 03/10/2026, a partir das amostras. **Substitui a cadência e as colunas** das
duas seções do Funil do Sucesso do Cliente de 02/10/2026, mais abaixo (a implantação e a ata seguem
como lá).

- **Uma reunião por classe:** **A mensal, B trimestral, C semestral** (6 meses, nova). A **anual
  saiu** ("com a semestral não há necessidade da anual") e a **bimestral virou interna**, da carteira.
  As pautas começam pelo dashboard (análise vertical e horizontal e indicadores de performance
  financeira; o dashboard em si é outro projeto) e todas terminam em **lacunas técnicas do cliente e
  os serviços da Critério que as cobrem**. A semestral começa por "entender a estratégia e os desafios
  da empresa". Reuniões bimestrais e anuais já registradas ficam no histórico, sem cobrança.
- **Visões:** Consolidado · Classe A · Classe B · Classe C · Sem classe (lembrada no navegador), em
  **Kanban** ou **Grade**, como o Funil comercial: **as mesmas colunas e os mesmos cartões** (pedido
  de Eduardo em 03/10/2026). Embaixo do nome da coluna, a fase e o MRR somado; no cartão, o MRR bruto
  do cliente por mês, a classe e a reunião. O que se faz em cada etapa, e quem participa, só aparece
  no **ⓘ** do cabeçalho (mouse, foco ou clique). A Grade tem uma linha por cliente, as mais
  atrasadas primeiro, e ordena por qualquer coluna.
- **Consolidado:** um quadro compara as classes (clientes, **MRR bruto** dos contratos ativos, % de
  reuniões em dia, vencidas, ajustes pendentes e **vendas abertas**, com o valor por mês e o de projeto
  **separados**, nunca somados). Ao lado, a **bimestral da carteira**.
- **Cada classe** mostra no topo a **intenção** dela e os números só dela. A intenção e a reunião de
  cada classe mudam em **Configurações › Metas**; a intenção apagada volta ao texto padrão.
- **Bimestral da carteira:** interna, entre o Head do BPO e o CEO da Critério, para um overview da
  carteira e correção de rotas de análise. Vence 2 meses depois da última (sem nenhuma, conta de
  02/10/2026). Registra data, participantes, overview e correções de rota.
- **A ata lê o responsável:** a IA devolve o nome de quem ficou com cada ajuste e o prazo combinado; o
  CRM acha a pessoa entre quem recebe ajustes (sem acento e sem caixa; só o primeiro nome basta se for
  único). Citado e não cadastrado, ou dois possíveis, fica em branco com ⚠ para escolher. A frase de
  onde saiu aparece embaixo.
- **Oportunidades de novos negócios na ata:** a IA também anota a **estratégia e os desafios** do
  cliente e uma oportunidade por lacuna (serviço do catálogo, tema da Consultoria, valor só se foi
  dito). O **"+"** abre outra, para quantas forem. O serviço vem em dois grupos: **recorrente** (valor
  por mês) e **projeto** (valor total). Uma oportunidade sem serviço trava o registro. Cada uma
  marcada em **"Abrir no Funil comercial"** vira, ao registrar, uma oportunidade em **Enviar proposta**,
  no grupo do cliente, canal **Carteira**, com o captador pelas iniciais de quem registrou (se for uma
  das siglas; senão em branco) e a lacuna na observação; recorrente leva o valor no preço mensal,
  projeto no preço anual (o total). A não marcada fica só anotada na ata. O painel do cliente mostra as
  **vendas abertas nas reuniões**, com a situação de cada uma no Funil comercial.
- Rotas novas: `GET /api/sucesso/carteira` e `POST /api/sucesso/carteira/reunioes`. `PUT
  /api/sucesso/cadencia` aceita `intencao`. **Migração `d1e5b8c3f7a2`:** a intenção por classe, a
  estratégia e os desafios na reunião, as tabelas `oportunidade_da_reuniao` e `reuniao_da_carteira`, e
  **apaga a cadência gravada em Configurações** para valer a nova (autorizado por Eduardo em
  03/10/2026). **Rode `alembic upgrade head`**, com o backup antes.

## Comparar um backup de outro CRM (03/10/2026)

Para quando alguém trabalhou num **outro** CRM (outro computador, outra cópia do banco) e mandou o
backup. `scripts/comparar_backup.py <arquivo>` **só lê**: mostra, tabela por tabela, o que está
só no arquivo (incluído lá), o que tem diferença entre as duas cópias (e quais campos), e quantos
registros estão só no banco daqui. Reconhece o mesmo registro nas duas cópias pelo que o identifica de verdade, e não pela hora em que nasceu (revisto em 03/10/2026): empresa
pelo CNPJ, contato pelo e-mail ou nome, oportunidade pela chave da planilha ou grupo e nome, contrato
pela oportunidade ou grupo, empresa e escopo. Cada diferença diz se é para **preencher** (vazio aqui),
um **conflito** (preenchido nos dois) ou **vazio lá**, e qual cópia mexeu por último. A saída tem nomes
de clientes: fica na tela.

```
cd app/backend && ~/.venvs/criterio-crm/bin/python scripts/comparar_backup.py ~/Downloads/<arquivo>.zip
```

**Não importe o backup de outra cópia pela tela:** a importação substitui o banco inteiro.

**Trazer o que foi feito no outro CRM** (03/10/2026, regras aprovadas por Eduardo):
`scripts/importar_do_backup.py <arquivo>` mostra o que faria; com `--gravar`, grava numa transação
só. **Acrescenta** empresas (no grupo de mesmo nome daqui), contatos e vínculos que só existem lá,
sem duplicar contato sem e-mail cujo nome está contido no de outro da mesma empresa. **Preenche**
o que está vazio aqui (CNPJ, telefone, cargo, data de aceite, data de colocação…). **Troca** só
quando lá mexeu por último: nos contatos, nome, cargo, papel, telefone e observação (que junta as
duas); nas oportunidades, temperatura e nome. Os outros conflitos (preço, parcelas, situação) ficam
como estão e aparecem na lista. Não apaga nada; não mexe em contrato, proposta nem Score. A
comparação agora também reconhece a empresa com CNPJ de um lado e sem do outro, e o contrato sem a
empresa preenchida.

**Apagar um grupo de teste** (03/10/2026, para o "Karine ON"): `scripts/apagar_grupo.py --cnpj <CNPJ>`
(ou `--grupo <nome>`) mostra tudo o que sairia: grupo, empresas, oportunidades com proposta e
questionário, vínculos, os contatos que só existem nele, leitura do Score, jornada e reuniões. Com
`--apagar`, apaga numa transação só, sem backup antes (para guardar, rode `backup.py exportar` antes).
Recusa grupo com contrato ou em fusão. O histórico de alterações fica.

## Busca automática dos questionários (02/10/2026)

Aprovado por Eduardo em 02/10/2026, depois de o questionário da Smarthis ficar esperando no site até
alguém apertar o botão. **Enquanto o CRM estiver ligado, ele busca sozinho**: logo ao iniciar e
depois a cada **10 minutos**. O questionário novo vira oportunidade em "Enviar proposta" (ou fica
"Precisa de você"), exatamente como no botão.

- **Painel Questionários** (Funil comercial › Questionários): no topo, a linha da busca diz a última
  (automática ou na hora), o que trouxe, a próxima e, se falhou, **⚠ o motivo** (chave errada,
  Supabase fora do ar, `.env` sem configuração). **"Buscar agora"** faz a mesma busca na hora. A linha
  se atualiza a cada minuto e o painel recarrega sozinho quando chega questionário.
- **"Precisa de você"** se resolve no próprio painel ("Anexar à existente" ou "Criar nova") e
  aparece também na **Agenda**, até alguém resolver.
- O botão "Buscar questionários" da aba Oportunidades continua; botão e busca automática nunca
  importam o mesmo questionário juntos.
- **Com o CRM desligado, ninguém busca:** o questionário espera no site e entra assim que o CRM volta.
  Resolver isso de vez é o CRM na nuvem (E1).
- Rota nova `GET /api/questionarios/busca`. Sem migração.

## Contrato bruto ou líquido, e o MRR em bruto (02/10/2026)

Aprovado por Eduardo em 02/10/2026, no lugar de uma "data do valor líquido": cada contrato diz se o
preço mensal é **Líquido (sem o imposto)** ou **Bruto (com o imposto)**, na tela do contrato (Gestão
de contratos › Abrir). Vale até para contrato assinado ou encerrado: é como o valor se lê, não uma
mudança de preço. A lista mostra "líquido", "bruto" ou "⚠ bruto ou líquido?" embaixo do preço.

- **O MRR soma tudo em bruto.** O contrato líquido entra com o imposto dos Parâmetros de cálculo:
  `bruto = líquido ÷ (1 − imposto)`, ao centavo (ex.: 8.000 líquido com 11% = 8.988,76). O preço e
  os eventos (reajuste, expansão, contração, encerramento) são convertidos do mesmo jeito, para o
  NRR e o GRR não misturarem bases. Aqui não se arredonda a R$ 50 como na proposta.
- O contrato sem bruto/líquido informado entra **como está**, e o painel avisa quantos são. O painel
  também diz quantos líquidos entraram com o imposto, e recalcula assim que um contrato é salvo.
- Contrato que nasce de uma oportunidade com **proposta gerada no CRM** já entra como líquido (a
  proposta grava o líquido no preço). A migração `c9f2a7d4e1b8` faz o mesmo com os que já existem;
  os outros ficam em branco para a pessoa marcar. **Rode `alembic upgrade head`**, com o backup antes.
- A receita em contrato da Saúde da carteira continua somando o preço como está (não mudou aqui).

## Funil do Sucesso do Cliente no formato do fluxograma (02/10/2026)

Aprovado por Eduardo em 02/10/2026. O funil passou a ter **uma coluna por etapa do fluxograma**:
Contrato → Handover → Kickoff (implantação) e Mensal → Bimestral → Trimestral → Anual (em curso).
O cabeçalho de cada coluna é a seta do fluxograma, com quem participa e o que se faz ali (o botão
"Recolher o que se faz em cada etapa" esconde os itens, e o navegador lembra a escolha).

- **Implantação:** igual a antes; o grupo fica numa etapa só e anda pelo checklist.
- **Em curso:** o grupo aparece em **cada reunião que a classe dele pede** (A nas quatro, B na
  Trimestral e na Anual, C só na Anual). Em cada coluna, as vencidas vêm no topo, com ⚠ e há quantos
  dias; depois, pela data. O cabeçalho conta os grupos e as vencidas. Clicar no cartão abre o painel
  já naquela reunião.
- **Sem classe:** não entra em coluna de reunião; aparece num aviso acima das colunas, clicável.
- **Cliente anterior ao CRM (opção A):** as reuniões contam do início do funil, **02/10/2026**:
  primeira Mensal em 02/11, Bimestral em 02/12, Trimestral em 02/01/2027, Anual em 02/10/2027. Antes,
  toda a carteira antiga aparecia vencida só por não ter reunião registrada. Cada reunião registrada
  recalcula a próxima a partir dela. Sem migração.

## Ata da reunião e ajustes da área técnica (02/10/2026)

Aprovado por Eduardo em 02/10/2026. A ata existe para a **área técnica** fazer os ajustes que a reunião
de resultado identificou.

- **Montar a ata:** no painel do cliente em curso (Funil do Sucesso do Cliente), cole a transcrição ou
  as notas do **Granola** e clique "Montar a ata com a IA". O CRM manda a transcrição à API da
  Anthropic (Claude Opus 5.5, saída em JSON garantido, fallback automático se recusar) e devolve um
  **rascunho**: resumo, decisões do cliente, **ajustes para a área técnica**, pendências do cliente e
  pontos sensíveis. Nada é gravado: o gestor revisa, escolhe o **responsável** (obrigatório) e o
  prazo de cada ajuste, inclui ou tira ajustes, e só então clica "Registrar reunião". Custa centavos
  de dólar por ata (a tela mostra a estimativa). Sem `ANTHROPIC_API_KEY` no `.env`, avisa e não monta
  nada; a reunião pode ser registrada à mão.
- **Transcrição:** fica guardada no banco com a reunião (dado de cliente: só no banco, nunca no
  repositório nem no histórico de alterações). O histórico mostra só que ela existe.
- **Ajustes na Agenda:** cada ajuste aparece na **Agenda** do responsável, com prazo e ⚠ quando
  vence. Ele marca **Feito** (com observação, se quiser) e pode reabrir. O cartão do cliente no funil
  e o painel mostram "N ajustes pendentes · ⚠ atrasados".
- **Copiar a ata:** cada reunião do histórico tem o botão, que põe o texto pronto para colar no Teams
  ou num e-mail.
- **Perfil novo Área técnica** (criado pela migração): só vê os próprios ajustes na Agenda e marca
  feito. Para o Bruno, o Jefferson e os outros técnicos entrarem: Configurações › Perfis e acesso,
  incluir a conta Microsoft de cada um com o perfil Área técnica. Só quem tem esse perfil (ou o
  Administrador) aparece na lista de responsáveis. Funcionalidades novas: "Ajustes da área técnica:
  ver os de todos" e "ver os seus e marcar feito"; quem vê o Funil do Sucesso também vê todos.
- Rotas: `POST /api/sucesso/grupos/{id}/ata` (rascunho), `GET /api/ajustes`,
  `GET /api/ajustes/responsaveis`, `POST /api/ajustes/{id}/feito` e `/reabrir`. Migração
  `b8e4f1a6d3c7`, só aditiva (colunas novas na reunião, tabela `ajuste_tecnico`, perfil Área técnica).
  **Rode `alembic upgrade head`**, com o backup antes.

## Funil do Sucesso do Cliente (02/10/2026)

Aprovado por Eduardo em 02/10/2026, a partir do fluxograma "Macroprocesso — Comercial & Sucesso do
Cliente". Terceira aba de **Sucesso do Cliente**. Entra todo grupo (não fundido) com contrato ativo,
suspenso ou aguardando assinatura, numa destas colunas:

- **Implantação:** **Contrato** (Comercial & Cliente) → **Handover** (Comercial) → **Kickoff** (Gestor &
  Cliente). Cada etapa tem o checklist do fluxograma; "Concluir etapa" só libera com todos os itens
  marcados. O fluxograma junta Handover e Kickoff numa caixa só: o que o comercial passa adiante
  (os pontos sensíveis da abordagem) ficou no Handover; o que se faz com o cliente (apresentação da
  Critério, carta de rescisão e termo de transferência, lista de documentos, fluxo financeiro, KYC),
  no Kickoff. Contrato novo começa em Contrato; contrato anterior ao CRM já entra em curso.
- **Em curso:** pelas reuniões de resultado que a classe do Score pede (a da leitura mais recente);
  desde 02/10/2026, uma coluna por reunião (ver "Funil do Sucesso do Cliente no formato do
  fluxograma", acima). Cadência aceita por Eduardo: **A** mensal, bimestral, trimestral e
  anual; **B** trimestral e anual; **C** anual. Cada reunião vence 1, 2, 3 ou 12 meses depois da
  última daquele tipo; sem nenhuma, conta da entrada em curso (o fim do kickoff). O cliente anterior
  ao CRM conta do início do funil, 02/10/2026 (opção A, ver acima). Grupo sem classe fica num aviso,
  "Sem classe: avalie o Score na Saúde da carteira".
  Atraso sempre com ⚠ e texto.

O objetivo das reuniões (Eduardo, 02/10/2026) é apresentar um dashboard com os principais números do
cliente para ele tomar decisões mais arrojadas. Por isso "Registrar reunião" guarda tipo, data,
participantes, pauta (já preenchida com os itens do fluxograma; a da **Anual** — resultados do ano,
renovação e reajuste, NPS — é sugestão, a confirmar), **decisões do cliente** e **próximos passos**.
O dashboard é um link opcional: ainda não existe. A data não pode ser futura.

A cadência muda em **Configurações › Metas** ("Reuniões de resultado por classe"), com histórico.
Funcionalidades novas: "Funil do Sucesso do Cliente: ver" e "marcar etapas e registrar reuniões",
só do Administrador até alguém liberar em Perfis e acesso. Rotas em `/api/sucesso/…`. Migração
`a7d3e5f9c2b4`, só aditiva (tabelas `jornada_do_cliente`, `reuniao_de_resultado` e
`cadencia_de_reuniao`, já com a cadência aceita). **Rode `alembic upgrade head`**, com o backup antes.

## Menu reorganizado e Configurações em abas (02/10/2026)

Aprovado por Eduardo em 02/10/2026. O menu ficou: **Agenda · Contatos · Funil comercial · Sucesso do Cliente ·
SDR - Abordagens e conhecimento · Configurações**.

- **Funil comercial** (era "Funil") em abas: **Oportunidades** (o funil de sempre) · **Questionários**.
- **Sucesso do Cliente** (era "Saúde da Carteira", antes "Carteira") em abas: **Saúde da carteira** ·
  **Gestão de contratos** (era o menu Contratos) · **Funil do Sucesso do Cliente** (entrou na
  entrega seguinte, ver acima). O atalho da Agenda para contratos abre direto em Gestão de contratos.
- As permissões não mudaram: cada aba segue a sua (`funil.ver`, `questionarios.ver`, `carteira.ver`,
  `contratos.ver`). O perfil Comercial vê Sucesso do Cliente só com Gestão de contratos.

- **Configurações** em abas, nesta ordem: **Perfis e acesso · Metas · Propostas · Grupos ·
  Conferência · Histórico · Backup · Serviços pedidos**. **Grupos** e **Conferência** saíram do menu
  e viraram abas, sem mudar nada dentro delas. Cada aba só aparece para quem tem a funcionalidade
  dela (Grupos: "Grupos: ver"; Conferência: "Conferência: ver"; "Serviços pedidos", só leitura, para
  quem vê Configurações). Por isso o perfil Comercial passa a ver o menu Configurações, só com
  Grupos, Conferência e Serviços pedidos. A fileira de abas usa a largura toda; os formulários,
  até 960px; Grupos e Conferência, a largura toda.
- **SDR - Abordagens e conhecimento** junta, em abas, **Abordagens** (o agente SDR de prospecção) e
  **SDR da IA** (a qualificação de leads). A base de conhecimento da SDR de IA vai ganhar uma aba
  aqui quando for construída.
- Os dois lugares abrem na primeira aba visível, e o navegador lembra a última escolhida.

No mesmo dia, a pedido de Eduardo, o menu **Carteira** passou a se chamar **Saúde da Carteira** (também na
tabela de Perfis e acesso). A permissão continua `carteira.*`: nenhum perfil precisa ser refeito.

## Metas dos indicadores editáveis (02/10/2026)

Aprovado por Eduardo em 02/10/2026: a meta e o alerta deixaram de ser fixos no código.
**Configurações › Metas** (funcionalidade "Configurações: metas", só do Administrador; outro perfil
recebe pela tela) altera:
- **MRR da carteira**: meta e alerta em R$/mês (KPI oficial de hoje: R$ 400 mil e R$ 200 mil);
- **Taxa de conversão**: meta e alerta em % (KPI oficial de hoje: 50% e 30%).

O alerta precisa ficar abaixo da meta, e a meta da conversão vai até 100% (o servidor recusa com o
motivo). Muda na hora o painel de MRR em Contratos e a etiqueta da conversão no Funil. Cada mudança
vai para o histórico de alterações, com quem mudou e o antes e depois. Rotas `GET`/`PUT /api/metas`.
Migração `f6c2d8a4b1e9`, só aditiva (tabela `meta_de_indicador`, já com os valores oficiais de hoje).
**Rode `alembic upgrade head`**, com o backup antes.

## Menu Questionários e alçada nos eventos de contrato (02/10/2026)

Amostra e decisões aprovadas por Eduardo em 02/10/2026.

**Questionários** (menu novo, depois do Funil; funcionalidade "Questionários: ver", que o perfil
Comercial ganhou na migração): tudo o que chegou pelo questionário do site num lugar só.
- Cinco números no topo, que seguem os filtros de período, serviço e porte: recebidos (com o mesmo
  número de dias logo antes), aguardando proposta (destacando os que esperam há mais de 5 dias
  úteis), quantos viraram proposta enviada, a média de dias do questionário à primeira proposta
  enviada e os que precisam de você. O filtro de situação muda só a tabela.
- A **situação vem da oportunidade**, nunca digitada de novo: precisa de você, aguardando proposta,
  proposta enviada (com o número), em espera, aceita, perdida (com o motivo). Ícone e texto, nunca só cor.
- Clicar na linha abre **as respostas do cliente por seção** (`GET /api/questionarios/{id}/respostas`),
  só o que foi respondido e só as seções do escopo pedido. É a resposta original; as correções da
  entrevista ficam na ficha da oportunidade.
- Rota: `GET /api/questionarios/painel?dias=30` (`dias=0` = desde o primeiro).

**Alçada nos eventos de contrato** (`crm/domain/alcada.py`). Para quem não tem a funcionalidade nova
**"Contratos: aprovar eventos acima da alçada"** (só o Administrador tem; outro perfil recebe pela tela):
- **Contração** e **reajuste para baixo** que reduzam o preço mensal ou anual em **mais de 10%**, e
  **aditivo que mude o escopo** (ou reduza o preço em mais de 10%), viram **pedido de aprovação**
  (`202`): o contrato não muda e não recebe outro evento até a decisão.
- Expansão, reajuste para cima, renovação, correção e **encerramento** entram direto, como antes.
- Quem aprova vê os pedidos no topo da **Agenda** (`GET /api/aprovacoes`). **Aprovar** aplica o evento
  com a data pedida, revalidando contra o contrato de agora; **recusar** exige o porquê e o contrato
  fica como estava. Pedido, decisão e evento vão para o histórico de alterações.
- Sem login não há alçada: tudo entra direto, como antes do E1.
- A absorção de horas fora da política fica para a Etapa 2, com o saldo de horas de conforto.
- Migração `e3a9c6b4d2f1`, só aditiva (tabela `pedido_de_aprovacao` e "Questionários: ver" no
  Comercial). **Rode `alembic upgrade head`**, com o backup antes.

## Entrada pela conta Microsoft, perfis e histórico de alterações (E1, 02/10/2026)

Amostra aprovada por Eduardo em 02/10/2026.

- **Entrada:** cada pessoa entra com a conta Microsoft da Critério (Microsoft Entra). O CRM
  não guarda senha: a Microsoft confere quem é; o CRM decide o que a pessoa pode. Cada pedido à
  API leva o token, que a API confere (assinatura, emissor, público e validade) antes de tudo.
- **Sem a configuração, nada muda:** sem `CRM_ENTRA_TENANT_ID` e `CRM_ENTRA_CLIENT_ID` no
  `backend/.env`, o CRM segue sem login, só na máquina, como antes. O rodapé do menu avisa.
- **Perfis por funcionalidade dentro de cada menu**, com a opção de liberar o menu inteiro
  (pedido de Eduardo). Menu sem nenhuma funcionalidade liberada não aparece. Os perfis
  iniciais: **Administrador** (tudo, inclusive o que for criado depois; não se muda) e
  **Comercial** (o comercial inteiro, sem converter em contrato, sem Carteira e sem
  Configurações; contratos e grupos só para ver). Os outros se criam na tela, em
  **Configurações › Perfis e acesso**, onde também se libera cada conta e se tira o acesso.
  Precisa sobrar pelo menos um Administrador ativo.
- **A API confere tudo, a tela só ajuda:** toda rota está num mapa de permissões
  (`crm/acesso/catalogo.py`); rota fora do mapa é **recusada** (um teste garante que nenhuma
  fica de fora). A tela esconde ou trava o que o perfil não libera e diz o porquê; se algo
  escapar, a API responde "O seu perfil não libera esta ação."
- **Histórico de alterações por usuário:** toda gravação feita por quem entrou vira linha no
  histórico: quem, quando, o quê, o campo, o antes e o depois (criou, alterou, excluiu). Não se
  edita nem se apaga. Começa quando o login entra no ar: o que veio antes não tem autor (decisão
  de Eduardo). Aparece em **Configurações › Histórico de alterações** (filtro por pessoa, tela e
  período, no dia de Brasília) e no painel da oportunidade (aba **Histórico**), do contato, da
  empresa e do contrato (**Histórico de alterações**, recolhido no fim). Arquivos (matriz,
  PDF) e respostas de questionário não entram campo a campo, só o registro.
- **"Quem preenche" sai de cena:** com login, a ficha, a lista do que falta e a matriz de
  proposta gravam o nome de quem entrou; os seletores de nome somem.
- **Downloads** (backup, Excel, PowerPoint, PDF) passam a levar o token.
- Migração `d8b2f5a1c3e7`, só aditiva (tabelas `perfil`, `usuario` e `registro_de_alteracao`,
  com os dois perfis iniciais). Dependência nova no backend: `pyjwt[crypto]`; na tela,
  `@azure/msal-browser`.

### Ligar a entrada pela conta Microsoft (passo a passo, uma vez)

Feito por quem administra o Microsoft 365 da Critério, no portal do Azure
(`portal.azure.com`). Nada aqui é pago, nem pede segredo: o CRM usa o fluxo de aplicativo de
página única (com PKCE), sem senha de aplicativo.

1. **Microsoft Entra ID › Registros de aplicativo › Novo registro.** Nome: `Critério CRM`.
   Tipos de conta: **somente contas deste diretório organizacional**. URI de redirecionamento:
   plataforma **Aplicativo de página única (SPA)**, endereço `http://localhost:5173/`.
2. Na **Visão geral**, anote o **ID do aplicativo (cliente)** e o **ID do diretório
   (locatário)**.
3. **Expor uma API › Adicionar** o URI de ID do aplicativo (aceite o sugerido,
   `api://<ID do aplicativo>`) e **Adicionar um escopo**: nome `acesso`, quem pode consentir
   **Administradores e usuários**, nome de exibição "Acessar o Critério CRM".
4. **Permissões de API › Adicionar uma permissão › Minhas APIs › Critério CRM › `acesso`**, e
   depois **Conceder consentimento do administrador**.
5. **Manifesto:** ponha `"requestedAccessTokenVersion": 2` (no editor antigo,
   `"accessTokenAcceptedVersion": 2`) e salve. Sem isso a Microsoft emite o token no formato
   antigo e a API recusa ("A entrada expirou ou não vale").
6. No `backend/.env` (nunca no código):

   ```
   CRM_ENTRA_TENANT_ID=<ID do diretório>
   CRM_ENTRA_CLIENT_ID=<ID do aplicativo>
   CRM_ADMINISTRADORES=eduardo@grupocriterio.com.br
   ```

7. Pare e suba o CRM de novo (`./iniciar.sh`). Entre com a conta de Eduardo: ela nasce
   Administrador. Em **Configurações › Perfis e acesso**, libere a Karine no perfil Comercial.

Para usar pelo túnel (ngrok), acrescente o endereço do túnel, com `/` no fim, como mais um URI
de redirecionamento SPA no passo 1.

## Ficha e "o que falta para a proposta" (E4, 02/10/2026)

Amostra aprovada por Eduardo em 02/10/2026. Fecha os dois itens do E4 que faltavam no
`planejamento.md`: a ficha com as nove seções do questionário, cada campo sabendo de onde veio,
e a lista do que falta para a proposta, com responsável e prazo.

- **Aba Ficha** (entre "Volumetria e porte" e "Proposta"): as nove seções do questionário do site
  (`crm.proposta.ficha`, espelho do `SECOES` de `app/site/questionario/index.html`). Cada seção diz
  "✓ 14 de 14", "◐ 3 de 5", "✗ 0 de 7", "fora do escopo" (Folha sem DP, Financeiro sem
  Financeiro) ou "para a implantação" (seção 9). Cada resposta mostra a origem: **Questionário** e a
  data do envio, ou **Entrevista**, quem e quando. Corrigir na Ficha grava como Entrevista em
  `oportunidade.ficha`; a resposta do cliente continua em `questionario_recebido.respostas`. Só
  conta a pergunta visível para as respostas atuais, como no formulário.
- **O que falta para a proposta**, no alto da aba Proposta, com a contagem no rótulo da aba
  ("Proposta · 3 pendentes"). Itens **automáticos** (`crm.proposta.pendencias`) que fecham
  sozinhos: volumes sem resposta, seção do escopo inteira sem resposta, porte não confirmado,
  matriz não subida ou com marcador faltando, nenhum contato com e-mail nas empresas do grupo,
  proposta ainda não gerada. Itens **manuais**, que se marcam como feitos. Todos podem ter
  responsável (quem revisa as propostas) e prazo.
- **Decisões de Eduardo (02/10/2026):** a lista **não bloqueia** o "Gerar PowerPoint"; pendência
  aberta **com prazo entra na Agenda**, no balde do prazo, com o responsável; a **seção 9** aparece na
  ficha mas **não conta** como pendência (é levantada no kick-off).
- **Quem preenche:** sem login, a pessoa escolhe o nome uma vez (o navegador lembra). Com o login
  do E1, vale o nome de quem entrou e o seletor some.
- Migração `c4e1a7d2f9b3`, só aditiva (coluna `oportunidade.ficha` e tabela
  `pendencia_da_proposta`): **rode `alembic upgrade head`**, com o backup antes.

## Menu e título sempre à vista (02/10/2026)

O menu lateral e a faixa do título da tela ficam parados; só o conteúdo rola. Antes a página
inteira rolava e levava o menu junto. Em janela baixa, o próprio menu ganha rolagem.

## Ordenação nas tabelas (27/09/2026)

Todo título de coluna clicável ordena a lista: primeiro clique crescente, segundo decrescente, terceiro
volta à ordem original (a que a API mandou). `componentes/Ordenacao.tsx` reúne o hook (`usarOrdenacao`),
a função pura (`ordenar`, testada) e o cabeçalho clicável (`ThOrdenavel`, com seta e `aria-sort`). Valor
sem informação (`null`) fica sempre por último, nas duas direções — nunca parece "o menor" nem "o maior".
Aplicado em: Funil (Grade e, por valor, dentro de cada coluna do Kanban), Contatos (empresas e pessoas),
Grupos, Contratos, Carteira, Abordagens, histórico de revisões, propostas de um grupo (DetalheDoGrupo),
Conferência e Configurações (resumo do backup). Fora do escopo, de propósito: Receita (o movimento do
MRR é uma sequência contábil, não uma lista), Cenários de ticket (três cenários fixos), o histórico de
preço de uma oportunidade (é uma linha do tempo) e a tela Leads (fora do menu desde 27/09/2026).

## Estado

Atualizado em 02/10/2026.

| | |
|---|---|
| O que roda | Banco PostgreSQL, carga de 2026 repetível, funil, contratos e eventos de contrato, carteira classificada, questionário do site, proposta em PowerPoint com ficha e "o que falta", agente SDR, SDR de IA, backup lógico (manual e diário) e dez telas |
| Testes | **1.185** no backend e **504** nas telas, todos passando. Backend com pytest; telas com Vitest e Testing Library. `npm run build` compila sem erro |
| Banco | PostgreSQL 18 local, 42 tabelas, migrações até `d1e5b8c3f7a2` (funil do sucesso por classe, 03/10/2026). Antes de cada `alembic upgrade head`, rode `scripts/backup.py exportar` |
| API | 136 rotas, em `127.0.0.1:8000`. **Com a conta Microsoft configurada, toda rota exige entrada e permissão do perfil**; sem a configuração, segue sem login, só na máquina |
| Telas | Agenda, Contatos, Funil comercial (Oportunidades e Questionários), Sucesso do Cliente (Saúde da carteira, Gestão de contratos e Funil do Sucesso do Cliente), SDR - Abordagens e conhecimento (Abordagens e SDR da IA) e Configurações (com Grupos e Conferência em abas). React com TypeScript, em `../frontend` |
| Incrementos | E2, E3, E4 e E5 prontos (o MRR da carteira inteira se compara com a meta oficial desde 02/10/2026). E1: login, perfis e histórico prontos; faltam a nuvem e o backup fora da máquina |
| Fora do ar | **E1:** nuvem em região brasileira (custo a estimar antes de contratar) e backup fora da máquina com restauração testada. Login, perfis e histórico já estão no código, à espera do registro no Microsoft Entra. **Etapa 2:** Clicksign, renovação, saldo de horas de conforto. O dashboard do cliente para as reuniões de resultado (fonte dos números e ferramenta a decidir). Buscar a transcrição direto no Granola, sem colar (depende de o plano do Granola ter API) |

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

## Proposta em PowerPoint (01/10/2026)

Na oportunidade, a aba **Proposta** monta a proposta a partir de uma **matriz em PowerPoint** e baixa
o .pptx. Eduardo ou Karine revisam, ajustam à mão se preciso, salvam como PDF no PowerPoint e
enviam. A proposta fica em PowerPoint justamente para isso: dá para mudar um detalhe e reenviar.

- **Matriz pelo questionário:** pediu só Financeiro → matriz **Financeiro** (três planos de preço de
  tabela); qualquer outra combinação → matriz **Contábil** (Contábil/Fiscal + DP). Dá para trocar na aba.
- **Preço sugerido** (matriz Contábil): a mesma conta do honorário calculado da Carteira, aberta na
  tela. Horas do porte × (1 + atrito) × custo/hora ÷ (1 − imposto − margem alvo) dá o **bruto**;
  × (1 − imposto) dá o **líquido sugerido**. Disciplina entra 3 (cliente novo não tem nota);
  complexidade ou risco sem nota também entram 3, e a tela diz isso. Sem porte, não há sugestão.
- **Honorários e horas de consulta** (03/10/2026, Eduardo): **Contábil/Fiscal** vem do valor
  apurado pelo questionário (o preço sugerido, ao múltiplo de R$ 50), mesmo quando há DP; **DP** vem
  de **R$ 50 por colaborador** (CLT da volumetria + PJs/estagiários e jovens aprendizes do
  questionário; o item "Jovens aprendizes" entrou no questionário em 03/10/2026, e o que chegou antes
  conta zero). Os dois se editam, com "voltar ao apurado" e
  "voltar ao calculado". As **horas de consulta por ano** não se digitam: 50% do 13º honorário
  (Contábil + DP, líquidos) ÷ **R$ 350/h**, ao inteiro mais próximo; Contábil fica com 70% e DP com
  o resto (sem DP, todas são de Contábil). O servidor refaz a conta ao gerar (`crm.proposta.conta`).
- **Líquido e bruto:** a proposta mostra o líquido (o que vai no contrato) e o bruto com a alíquota
  estimada, prática da Critério para a Reforma Tributária. Bruto = líquido ÷ (1 − alíquota),
  **arredondado ao múltiplo de R$ 50 mais próximo** (NRH: 6.900 → 7.750). A alíquota é o imposto de
  Carteira › Parâmetros de cálculo (11%): uma fonte só.
- **Numeração PROP CCE RJ:** sequência única para as duas matrizes, começando em **154** (a última
  da planilha foi a 153.2026); o ano vem da data. Gerar de novo **antes de enviar** regrava a mesma
  proposta, com o mesmo número; depois de enviada, gerar abre número novo. Número usado nunca volta.
- **Marcar como enviada:** pede quem enviou (Eduardo ou Karine) e a data. A oportunidade em
  "Enviar proposta" passa a "Em avaliação pela empresa"; na matriz Contábil, o total líquido vira o
  preço mensal e o anual o acompanha (× 13 ou × 12, pelo serviço), com linha no Histórico de preço.
- **Preço anual pelo serviço** (03/10/2026, Eduardo): nos serviços de contábil e DP (BPO Contábil,
  Fiscal e Dep. Pessoal · BPO Contábil e Fiscal · Dep. Pessoal) o anual é **mensal × 13**; no BPO
  Financeiro, **mensal × 12**. Na Nova oportunidade e no detalhe o campo fica travado e as parcelas
  não se pedem; os outros serviços C1 seguem mensal × parcelas. O anual só se recalcula quando o
  mensal ou o serviço muda. Os anuais gravados antes da regra foram recalculados em 03/10/2026
  (autorizado por Eduardo) com `scripts/recalcular_anual_por_servico.py` (ensaio por padrão;
  `--aplicar` grava com backup antes e deixa linha no Histórico de preço). Contratos não mudam.
- **Baixar de novo** sai igual, com a matriz e os valores da época, mesmo depois de trocar a matriz.
- **Valores no padrão brasileiro** (02/10/2026): os honorários e os planos aceitam `3.287,38`,
  `3287,38` ou `3287`; valor que não dá para ler avisa no campo e fica em branco, em vez de valer o
  número anterior escondido. O resultado de **Gerar PowerPoint** aparece logo abaixo do botão, com
  o nome do arquivo e a pasta Downloads; a recusa da validação diz o campo e o motivo.

**Configurações › Propostas:** subir e trocar as matrizes, próximo número, quem revisa e envia, e
o preço de tabela dos planos financeiros. Matriz com marcador obrigatório faltando, ou com
marcador desconhecido (erro de digitação), fica gravada mas **não é usada** até subir a corrigida.
A lista completa de marcadores está na própria tela ("Lista de marcadores"). A matriz aceita até
**200 MB** (era 40 MB até 01/10/2026; a Contábil oficial, cheia de imagens, não cabia).

### Pôr os marcadores nas matrizes oficiais

As matrizes oficiais estão no SharePoint Comercial (Kit Contábil: *01_Proposta BPO Full_Mar.26 -
Template*; Kit Financeiro: *Proposta_BPO_Financeiro_slide13_corrigido*). Numa **cópia** de cada uma,
troque no PowerPoint o texto da esquerda pelo marcador da direita e suba em Configurações › Propostas.

| Onde (matriz Contábil) | Hoje | Marcador |
|---|---|---|
| Capa | `[Nome do Cliente]` | `{{cliente}}` |
| Capa | `PROP CCE RJ [00X].2026` | `PROP CCE RJ {{numero}}` |
| Carta | `Prezado Sr. [NOME]` | `{{tratamento}}` |
| Contextualização | o parágrafo inteiro | `{{contextualizacao}}`, sozinho no parágrafo |
| Perfil | `[QUANTIDADE]` transações / `R$ [VALOR]/ano` / `[QUANTIDADE]` bancos | `{{movimentacao}}` / `{{faturamento}}/ano` / `{{instituicoes}}` |
| Perfil | `[MEIOS]` CLT + PJs / `[REGIME]` / `[00.000.000/0000-00]` / `[ERP / SISTEMA]` | `{{funcionarios}}` / `{{regime}}` / `{{cnpj}}` / `{{sistema}}` |
| Perfil | `[SEGMENTO]` / `[X] empresa(s) \| [CIDADE/UF]` | `{{segmento}}` / `{{empresas}} \| {{localidade}}` |
| Honorários | `[V1]` / `[V2]` | `{{valor_contabil}}` / `{{valor_dp}}` |
| Honorários | `até XX horas` (Contábil) / `até XX horas` (DP) / `até 20 horas` (total) | `{{horas_contabil}}` / `{{horas_dp}}` / `{{horas_total}}` |
| Honorários | `Valor Líquido: [V3]` / `Valor Bruto: [V3]` | `Valor Líquido: {{valor_liquido}}` / `Valor Bruto: {{valor_bruto}}` |

| Onde (matriz Financeiro) | Hoje | Marcador |
|---|---|---|
| Capa e carta | `[Nome do Cliente]` / `[00X]` / `Prezado(a) Sr(a). [NOME]` | `{{cliente}}` / `{{numero}}` / `{{tratamento}}` |
| Contextualização | o texto inteiro | `{{contextualizacao}}`, sozinho no parágrafo |
| Perfil | `[NOME DO CLIENTE]` / `[Segmento de atuação do cliente]` / `[Sistema financeiro utilizado]` | `{{cliente}}` / `{{segmento}}` / `{{sistema}}` |
| Perfil | os "A validar" de documentos, faturamento, bancos, meios de pagamento, regime e CNPJ | `{{volume_documentos}}`, `{{faturamento}}`, `{{instituicoes}}`, `{{meios_de_pagamento}}`, `{{regime}}`, `{{cnpj}}` |
| Honorários | `R$ 5.000` / `R$ 7.000` / `R$ 9.000` | `{{plano_bpo}}` / `{{plano_plus}}` / `{{plano_cfo}}` |

Aproveite a cópia para corrigir o que já saiu errado em propostas enviadas: na Contábil,
"assessorial"; na Financeiro, "2 hora por mês", "até 1 usuários", "To dos", "Este proposta" e o
Perfil numerado 5 antes de Honorários 4. Texto escrito para cada cliente que não tem marcador (o
"[XX] anos" de mercado, o resumo do negócio) continua sendo ajustado no PowerPoint.

**Para usar nesta máquina:** `git pull`, depois
`cd backend && ~/.venvs/criterio-crm/bin/pip install -e ".[dev]"` (instala o `python-pptx`) e
`~/.venvs/criterio-crm/bin/alembic upgrade head` (cria as três tabelas novas, sem tocar no que existe).

## Questionário do site vira oportunidade (01/10/2026)

O cliente preenche o questionário para proposta no site (Lovable), que grava na tabela
`questionarios_proposta` do Supabase. No Funil, **"Buscar questionários"** traz para o CRM o que
ainda não entrou e marca `importado_crm_em` lá. O CRM **busca**; o Supabase nunca chama o CRM, que
continua só em `127.0.0.1`.

- **Configuração:** `CRM_QUESTIONARIO_URL` e `CRM_QUESTIONARIO_CHAVE` no `backend/.env` (ver
  `.env.example`). O banco do site é administrado pelo Lovable e a chave secreta do Supabase não
  fica à vista, então o caminho é a **função do site** `questionarios-crm`: a URL termina em
  `/functions/v1/questionarios-crm` e a "chave" é uma senha nossa (`openssl rand -hex 32`), a mesma
  guardada no Lovable como segredo `CRM_QUESTIONARIO_SENHA`. A função só entrega os pendentes e marca
  os importados; sem a senha, recusa. Com a chave secreta de um Supabase próprio, a URL do projeto
  também funciona (o CRM escolhe pelo endereço). O código da função está em `site/questionarios-crm/index.ts`.
- **Fora do Lovable (01/10/2026):** a página do questionário está em `site/questionario/` (HTML
  único, sem build) com o `banco.sql` do projeto Supabase da própria Critério. Com ela publicada,
  a busca usa a URL do projeto e a chave secreta, sem função nem créditos. Passo a passo em
  `site/questionario/LEIAME.md`.
- **O CNPJ é a identidade.** Empresa nova cria grupo (Prospect, origem "Questionário do cliente"),
  empresa, contato e a oportunidade em "Enviar proposta". Empresa já cadastrada leva a oportunidade
  ao grupo dela (ao que ficou, se foi fundido). Grupo homônimo sem o CNPJ é só avisado: juntar é
  com Fundir grupos.
- **Não duplica:** com oportunidade em aberto no grupo, o questionário fica **"Precisa de você"**.
  "Anexar à existente" só preenche o que está vazio (nada digitado some); "Criar nova" abre outra.
- **A oportunidade nasce preenchida:** os nove direcionadores com origem "Questionário" (campo em
  branco fica fora da média), serviços além do primeiro, consolidação, auditoria e as notas de
  complexidade e risco. O **porte não é confirmado**: a régua do CRM sugere, e o cálculo que o
  formulário faz em JavaScript fica só para comparação.
- As regras de **leitura** das respostas (qual resposta acende qual fator) estão em
  `crm.questionario.leitura`, copiadas do formulário "BPO Full 2026 v6": mudou o formulário, muda
  o módulo. As de porte e nota são as do CRM.
- O questionário inteiro fica em `questionario_recebido`, com o PDF (base64, para o backup levar
  junto). A aba "Volumetria e porte" da oportunidade mostra de onde veio, o PDF, as notas com o
  motivo e os pontos de atenção.
- Cada questionário é gravado aqui **antes** de ser marcado lá: se a marca falhar, ele volta na
  próxima busca e o CRM só refaz a marca. Linha sem razão social, CNPJ ou contato fica no site, com aviso.
- Migração `3b26e19f7eeb` (só cria a tabela). **Rode `alembic upgrade head`.**

## Detalhe da oportunidade: abas no topo (27/09/2026)

O painel de uma oportunidade tinha "Volumetria e porte" e "Histórico de preço" empilhados abaixo do
cadastro, tomando a primeira visão. Agora o topo do painel tem três abas — **Cadastro**, **Volumetria e
porte** e **Histórico de preço** (com a contagem de mudanças de preço) — e o **Salvar alterações** fica
fixo no rodapé, fora das abas: salva o que estiver no rascunho, qualquer que seja a aba aberta. "Vem da
planilha" (captador, origem, linha da planilha) ficou dentro da aba Cadastro, por ser parte do cadastro
da oportunidade.

## Carteira: retrato com semáforo clicável (27/09/2026)

Os chips de "% travado" e "grupos travados" viraram um só (o número grande é a contagem; o percentual da
receita fica na legenda de baixo), sem perder o clique que filtra a tabela pelo eixo Cobrança. Um quarto
elemento na faixa mostra os **três semáforos (1, 2, 3)** com a contagem de grupos em cada um; clicar
filtra a tabela por aquele semáforo (clicar de novo desliga). As duas coisas se combinam com o filtro de
eixo já existente.

## Catálogo de serviços e C1/C2 pelo serviço (27/09/2026)

Amostra do pop-up aprovada por Eduardo, com os textos em rascunho. Lista de serviços
e linhas confirmadas por ele no mesmo dia. **Regra nova: C1 é recorrente, C2 não é
recorrente**, e a linha sai do serviço, no passado e daqui para frente.

| Serviço | Linha |
|---|---|
| BPO Contábil, Fiscal e Dep. Pessoal · BPO Contábil e Fiscal · Dep. Pessoal · BPO Financeiro · Endereço Fiscal · Representante Legal | C1 (recorrente) |
| Consultoria · Legalização Empresarial · Auditoria · FSCP (Finance Statement Closing Procedure) | C2 (não recorrente) |

- **Fonte única:** `crm/domain/servicos.py`. `GET /api/servicos` entrega o catálogo à tela e,
  quando existir a integração, ao SDR de IA. **Sem preço**, de propósito.
- **O pop-up** (`CatalogoDeServicos.tsx`) substitui o campo de texto "Serviço" na Nova
  oportunidade, no detalhe da oportunidade, na conversão do lead e no "Serviço de interesse"
  da qualificação. Mostra o roteiro: o que perguntar (as perguntas da régua de porte vêm
  marcadas), quando fica fora do perfil e para quem a IA passa a conversa.
- **Textos em rascunho:** "para quem é", "fora do perfil" e "passa para" foram escritos por
  mim e aprovados para construir; faltam revisar com Eduardo. Representante Legal está quase
  vazio porque ninguém descreveu o serviço ainda.
- **A linha acompanha o serviço:** criar, editar e converter gravam a linha do catálogo.
  Editar o serviço protege a linha da recarga (`campos_do_crm`). Serviço fora do catálogo
  não mexe na linha que já estava.
- **Carga:** vale o serviço, não a coluna "Responsável". Quando discordam, vira aviso
  ("vale o serviço") no relatório de conferência, sem bloquear. Serviço fora do catálogo
  mantém a coluna.
- **Nomes antigos da planilha** também são reconhecidos: "BPO Contábil" (C1, sem dizer se
  tinha folha), "Legalização" (agora C2), "Representação".
- **"Outro serviço"** (aprovado no mesmo dia): fica no fim do pop-up, em "Fora do catálogo", e
  abre uma caixa para descrever o serviço como o lead falou (ao menos 10 caracteres). Grava
  `servico = "Outro"` e a descrição em `servico_descricao` (no lead, `interesse_descricao`).
  **A linha fica "ainda não sei"** (vazia) até Eduardo decidir se o serviço entra no catálogo.
  Serviço do catálogo não leva descrição, e trocar de "Outro" para um do catálogo apaga a antiga.
  Todo "Outro" aparece em **Configurações → Pedidos de serviço novo**
  (`GET /api/servicos/pedidos`). Sem roteiro: o SDR de IA passa a conversa para a equipe.
  Migração `bf638b8cce5f`, só aditiva, **ainda não aplicada**: rode `alembic upgrade head`.
- **Duas pontas de migração (27/09/2026, corrigido).** A `bf638b8cce5f` e a junção da
  volumetria da carteira com o SDR (`5935b1a6769e`) saíram do mesmo ponto; na `main`,
  `alembic upgrade head` recusou rodar ("Multiple head revisions"). A junção `a96818a796a7`,
  que veio com a ordenação nas tabelas, liga as duas sem mudar nenhuma tabela.
  `tests/test_migracoes.py` falha se voltar a haver mais de uma ponta.
- **DIRPF e Perícia** (27/09/2026) entram como C2. **Consultoria pede o tema**, obrigatório:
  Tributária e fiscal · Valuation, PPA e laudos · M&A, due diligence e captação · Contábil e
  financeira · Societária e reestruturação · Trabalhista. Cada tema tem as suas perguntas para o
  SDR de IA. O tema fica em `servico_tema` (no lead, `interesse_tema`), **não** em
  `tipo_servico`: esse vem da planilha e faz parte da identidade da proposta na carga. Proposta
  antiga que já era Consultoria sem tema continua editável; o tema só é exigido de quem escolhe
  Consultoria agora. Migração `a3727af424db`, só aditiva.
- **Reclassificação pelo tipo:** `scripts/reclassificar_servico_pelo_tipo.py` (ensaio por padrão,
  `--aplicar` com backup) lê a coluna "Tipo serviço" das propostas marcadas "Consultoria": as que
  são de outro serviço do catálogo (Legalização Empresarial, Auditoria, FSCP, Perícia, DIRPF)
  passam a ele, com a troca protegida da recarga em `campos_do_crm`; as demais ganham o tema.
  Tema escolhido por uma pessoa nunca é sobrescrito. O de-para está em
  `crm.domain.servicos.reclassificar_pelo_tipo`, aprovado por Eduardo em 27/09/2026. Rodar de
  novo depois de uma recarga pega as propostas novas.
- **O passado:** `scripts/reclassificar_linha_por_servico.py` mostra, sem gravar, quantas
  oportunidades mudam de linha e de quê para quê; `--aplicar` grava com backup antes, na
  pasta `~/Backups-CRM`. **Ainda não rodado na máquina de Eduardo.**

## SDR de IA: qualificação de leads (27/09/2026)

Decisão de Eduardo: a IA de atendimento é o **SDR que qualifica os leads de
tráfego pago e os leads frios**. Amostra do painel aprovada em chat no mesmo
dia, com as metas. Construído em três partes, nesta ordem.

**1. A etapa de lead voltou, dentro da tela "SDR da IA".** A tela tem três abas:
Painel, Leads e Custos e mídia. A aba Leads é a antiga tela de leads, com o
que a qualificação pede:

- **Só lead qualificado vira oportunidade** (422 nos outros). O funil e a
  conversão continuam medindo proposta; o trabalho de antes fica no painel do
  SDR. "Nova oportunidade" no Funil não muda: continua para quem chega pelos
  sócios.
- **Qualificar exige o porte estimado** (régua de porte, com o que o lead
  informou). É sugestão: o porte da oportunidade continua confirmado por uma
  pessoa, com autor e data.
- **Descartar exige o motivo**, de uma lista controlada
  (`MotivoDeDescarte`). "Pediu para não ser contatado" marca o lead como
  **não contatar**.
- Voltar para Novo ou Em contato apaga a qualificação e o descarte de antes.
  O "não contatar" não se desfaz sozinho.
- Origem nova **"Prospecção ativa"** para o lead frio (`TipoCanal`). O lead de
  tráfego pago usa "Tráfego pago" com o canal escrito ("Meta Ads").
- Campos novos do lead: CNPJ, porte estimado, motivo de descarte, reunião
  marcada, não contatar, e as datas de qualificação e descarte, carimbadas
  pelo servidor.

**2. O registro das conversas** (`crm/api/sdr.py`). Quem chama é a integração
do canal, a cada mensagem. **Decisão de Eduardo: o SDR de IA envia sozinho**,
sem aprovação por mensagem. As travas ficam no servidor:

- nada sai da IA ou da equipe para lead "não contatar" (409); o lead ainda
  pode escrever;
- **mensagem da IA não fala de preço** (422; a mesma regra da abordagem,
  `fala_de_preco`). Depois do transbordo, a equipe pode;
- a IA não fala em conversa encerrada (409); uma conversa aberta por lead;
- o horário de cada mensagem é o do servidor.

Encerrar a conversa exige o desfecho: **Qualificado** (com porte),
**Fora do perfil** (com motivo), **Passou para a equipe** (com motivo e
destino) ou **Parou no meio**. Os dois primeiros mudam a situação do lead.
A primeira mensagem da equipe depois do transbordo marca o fim da espera.
A nota (CSAT, 1 a 5) vem depois de encerrar, uma vez só.

⚠️ **A integração que conversa com o lead ainda não existe.** O WhatsApp está
em preparação (modelo aprovado pela Meta, base legal para lead frio). Estas
rotas são a porta por onde ela vai gravar; até lá o painel mostra só os leads
cadastrados. As abordagens de contas âncora (tela Abordagens) **continuam**
exigindo a aprovação de Eduardo: a decisão de 27/09 vale para o SDR de IA.

As rotas do SDR confirmam a transação **antes** de responder. O `commit` de
`obter_sessao` roda depois que a resposta sai; com chamadas em sequência
(encerrar e logo dar nota), a segunda chegava antes da primeira estar gravada.
O resto da API tem o mesmo comportamento e fica para outra demanda.

**3. O painel** (`GET /api/sdr/painel?mes=AAAA-MM&origem=`), calculado em
`crm/domain/sdr.py`, sem banco:

- **Coorte do mês**: os leads que *chegaram* no mês (horário de Brasília) e
  tudo o que aconteceu com eles. Por isso o funil fecha: cada lead está em uma
  etapa, e o que sai de uma etapa é a soma dos motivos listados.
- O desfecho do lead é o da conversa mais recente.
- **Nada vira zero por falta de dado**: taxa sem denominador, CSAT sem nota e
  custo sem parâmetro saem nulos, e a tela diz o que falta.
- Falhas de compreensão por conversa contam só as conversas em que o lead
  respondeu.
- Filtros: mês e origem (tráfego pago ou leads frios). Os filtros de canal e
  de serviço da amostra **não foram feitos**.

**Metas aprovadas** (ponto de partida, rever depois de 60 dias ou 300 leads),
em `crm.domain.sdr.METAS`:

| Indicador | Meta | Alerta |
|---|---|---|
| 1ª resposta ao lead pago (mediana) | até 60 s | acima de 5 min |
| Qualificação concluída pela IA | 70% ou mais | abaixo de 55% |
| Transbordo | até 20% | acima de 30% |
| Taxa de resposta | pago 60% · frio 8% | pago abaixo de 40% · frio abaixo de 3% |
| Qualificados sobre leads | pago 20% · frio 3% | pago abaixo de 10% · frio abaixo de 1% |
| Reunião marcada sobre qualificados | 60% ou mais | abaixo de 40% |
| CSAT | 4,0 ou mais | abaixo de 3,5 |
| Falhas de compreensão (conversas) | até 10% | acima de 15% |
| Espera no transbordo | até 15 min | acima de 60 min |
| Custo de mídia por qualificado | até R$ 300 | acima de R$ 450 |

O tempo de qualificação não tem meta. O NPS ficou de fora: o lead ainda não é
cliente.

**Custos e mídia.** O custo poupado precisa de três valores, lançados na aba
Custos e mídia (`/api/sdr/parametros`): custo da hora de SDR, minutos que um
SDR levaria por conversa e cotação do dólar (o custo da IA é gravado em dólar
por mensagem). O investimento em mídia é lançado à mão, por mês e canal
(`/api/sdr/midia`), até existir integração com Meta Ads e Google Ads. O canal
precisa ser escrito igual ao do lead.

**Banco.** Migração `562856af0eb8`, só aditiva: colunas novas em `lead` e as
tabelas `conversa_do_sdr`, `mensagem_do_sdr`, `parametros_do_sdr` e
`investimento_em_midia`. Testada ida e volta num PostgreSQL 16 de rascunho;
**ainda não aplicada nesta máquina**: rode `alembic upgrade head`.

## Carteira: revisão mensal do ISC e evolução (27/09/2026)

Uma barra de uma linha só, acima do painel do ISC: "Registrar revisão do mês" (exige nome de quem
revisa) congela o ISC, os três componentes e o retrato de hoje como o placar do mês civil corrente —
`RevisaoDaCarteira`, imutável nos números. **Uma por mês**: uma segunda tentativa no mesmo mês é
recusada (409), apontando quem já registrou. "Ver histórico de revisões" abre um painel com o
**gráfico de evolução do ISC** (as três zonas de fundo, como no medidor) e uma tabela; cada linha tem
"Editar mês", que só corrige o **rótulo** (nunca os números congelados) — é assim que se corrige uma
revisão feita no dia errado, ou se rotula uma revisão antiga (ex.: a leitura de 31/07/2026 foi
registrada depois e rotulada para julho). Rotas: `GET/POST /api/carteira/revisoes`,
`PATCH /api/carteira/revisoes/{id}/mes`.

## Carteira: retrato geral e análise escrita pela IA (27/09/2026)

Acima do painel do ISC, uma faixa com o "retrato da carteira": unidades, receita mensal recorrente e
quanto está travado por inadimplência (percentual e contagem de grupos). Os dois chips de travados são
clicáveis e filtram a tabela pelo eixo "Cobrança — sem tratamento preferencial" — o mesmo conjunto,
sem filtro novo. Números vem de `crm.domain.classificacao.retrato()` (puro, testado), expostos em
`GET /api/carteira/classificacao` no campo `retrato`.

Abaixo da faixa, uma caixa **"Análise da IA"**: um parágrafo curto (Sonnet, sem busca na web) que só
descreve os números já calculados — zona do ISC, componente que mais pesa, inadimplência, distribuição
por classe — e nunca decide nem sugere ação. Não gera sozinha a cada visita: o botão "Gerar análise"
(exige nome de quem gera, sem login ainda) chama `POST /api/carteira/analise`; o resultado fica gravado
(`AnaliseDaCarteira`, imutável) e é o que `GET /api/carteira/analise` devolve até a próxima geração.
Custo estimado por geração: uma fração de centavo (poucos tokens, sem ferramenta). `crm.agente.erros`
reúne a mensagem de falha da Anthropic, usada também pelo agente SDR.

## Carteira: distribuição por classe contra a meta (27/09/2026)

Dentro do card escuro do ISC, uma faixa na base (abaixo do medidor, mesma largura): para A, B e C,
quantas unidades, que percentual da carteira e se está **dentro ou fora da meta declarada**
(A 15–20% · B 35–40% · C 40–50%) — texto, não só cor, marca a diferença. Meta parametrizada e
versionada como pesos e cortes do Score (`Parametros.meta_distribuicao_de_classe`), calculada por
`crm.domain.classificacao.distribuicao_por_classe()` (pura, testada) e exposta em
`GET /api/carteira/classificacao` no campo `distribuicao_por_classe`.

## Carteira: período de avaliação, rascunho e cálculo da carteira (29/09/2026)

Pedido de Eduardo: as informações da avaliação vêm de vários setores, então gravar tem que ser
possível aos poucos, e a carteira só muda quando todos os grupos estiverem avaliados.

- **Período de avaliação** (`periodo_de_avaliacao`): aberto na Carteira ("Abrir período", mês +
  quem abre). Um aberto por vez. Cada período tem a sua **janela de rentabilidade** (margem mínima
  e alvo); o primeiro começa em 60% e 70%, os seguintes repetem a do anterior. Editável em
  **Parâmetros de cálculo → Janela de rentabilidade desejada** enquanto o período está aberto.
- **Rascunho por grupo** (`avaliacao_em_andamento`): no painel Avaliar, **"Salvar rascunho"** grava
  só as abas revistas (a que se abriu, se mexeu ou está na tela ao salvar — "nada se aplica" também
  conta) e **não mexe no Score**. O painel reabre com o rascunho; sem rascunho, com a última
  avaliação gravada, para só revisar. Cada aba mostra "✓ preenchida", "✎ não salva" ou "· pendente".
- **Botão Avaliar com status** quando há período aberto: verde "✓ completo" (6 abas), amarelo
  "n de 6", vermelho "vazio" — sempre com o texto, não só a cor (PAD-002).
- **"Calcular este cliente"**: salva o que está na tela e mostra o resultado só daquele grupo
  (Score e classe antes → depois, horas, margem, honorário calculado, defasagem, revisão de
  honorários). Aba pendente usa a nota atual. **A carteira não muda.**
- **"Calcular carteira"**: só libera com **todos** os grupos completos; antes disso a faixa diz
  quantos faltam e quais. Pede confirmação, grava uma leitura nova por grupo (fonte "Cálculo da
  carteira, período MM/AAAA", com as respostas), aplica o porte do rascunho no grupo e fecha o
  período. O "Registrar revisão" continua sendo a foto do mês.
- **Porte com justificativa**: a sugestão vem do questionário de porte (os nove direcionadores).
  Porte confirmado diferente da sugestão só grava com justificativa (`GrupoEconomico.porte_justificativa`).
- **Receita praticada × calculada** (colunas novas): honorário calculado = custo ÷ (1 − imposto −
  alvo), com custo = horas-base do porte do grupo × (1 + atrito das notas de complexidade,
  disciplina invertida e risco) × custo/hora do porte (`crm.domain.avaliacao`). **Nível do grupo**,
  por decisão de Eduardo: difere da planilha de rentabilidade, que soma horas empresa por empresa.
  Defasagem = (praticada − calculada) ÷ calculada; acima está tudo bem. Sem porte confirmado, "sem porte".
- **Filtro "Revisão de honorários"** no campo Eixo de ação: grupos com margem, pelo honorário
  praticado, abaixo da mínima da janela. É filtro a mais; o grupo continua no seu eixo.
- A aba "Inadimplência" passou a se chamar **"Adimplência"** (nota alta = paga em dia).
- **Risco técnico corrigido (29/09/2026, autorizado por Eduardo):** a nota das respostas saía
  invertida (0 fatores = 5) e o Score invertia de novo, tratando cliente sem risco como risco
  máximo. Agora 0 fatores = 1 e 4 ou mais = 5, como na Complexidade (`escala-das-notas-humanas.md`,
  seção 3). Leituras gravadas antes disso ficam como estão (snapshot imutável); o próximo
  "Calcular carteira" recalcula a nota a partir das respostas.
- As regras de nota das respostas agora existem também no backend (`crm.domain.avaliacao`), iguais
  às da tela: a tela mostra ao vivo, o backend é quem vale no cálculo. Mudou uma, muda a outra.
- Migração `8f8c7f3862e8` (só acrescenta duas tabelas e uma coluna). **Rode `alembic upgrade head`.**

**Rentabilidade do Score pela margem do CRM (decisão de Eduardo, 29/09/2026):** a partir do
"Calcular carteira", a nota de Rentabilidade (25% do Score) sai da margem calculada no CRM, no
nível do grupo, pela régua de margem dos Parâmetros (30% → 2, 45% → 3, 60% → 4, 70% → 5), e a
leitura grava a margem e as horas usadas. As leituras anteriores continuam com a nota da planilha,
e a coluna "Rentabilidade" da Carteira mostra a da planilha até o primeiro cálculo e a do CRM
depois dele. "Calcular este cliente" já mostra a nota nova (antes → depois). Sem honorário
praticado não há margem, e o grupo mantém a nota anterior.

**Valor em contrato e cliente novo na Carteira (pedido de Eduardo, 30/09/2026):**
- **Receita praticada = valor em contrato:** a soma das mensalidades (`preco_mensal` > 0) dos
  contratos **ativos e suspensos** do grupo, o mesmo critério do MRR. A coluna mostra quantos
  contratos entraram na soma. Grupo sem contrato com mensalidade no CRM continua com a receita da
  leitura (da planilha), e a célula diz "sem contrato no CRM: valor da planilha". É esse valor que
  entra na margem, no honorário calculado, na defasagem e no filtro "Revisão de honorários".
- O **"Calcular carteira"** grava na leitura nova a receita em contrato (quando há). A nota de
  Receita dos grupos que já estavam na Carteira não muda.
- **Cliente novo:** grupo não fundido, com contrato ativo ou suspenso com mensalidade, e **sem
  nenhuma leitura** de classificação. Aparece no topo da tabela com a etiqueta "novo" e o início do
  contrato mais antigo; Score e Classe ficam em branco até o cálculo, e ele fica fora do ISC, do
  retrato e da distribuição por classe. No período, entra com **7 abas**: as 6 de sempre mais a aba
  **Saúde** (semáforo 1–3 e churn 1–5), que só existe para ele (a API recusa `saude` para quem já
  tem leitura). Só visitar a aba Saúde não a marca como preenchida: é preciso escolher os dois.
- A **primeira leitura** do cliente novo nasce no "Calcular carteira" (fonte "Cálculo da carteira,
  período MM/AAAA"): Receita pelo porte (Micro 1 … Extra Grande 5), Rentabilidade pela margem do CRM
  com o valor em contrato, semáforo e churn da aba Saúde. "Calcular este cliente" mostra o Score só
  com as 7 abas; antes disso, mostra as notas que já dá para saber.
- Sem migração: tudo sai das tabelas que já existem.

## Carteira: avaliação dos sete componentes do Score, em abas (27/09/2026, ampliado 28/09/2026)

Régua em `escala-das-notas-humanas.md`, agora com tela. Cada grupo ganha o botão **"Avaliar"**, que
abre um painel com uma aba por componente do Score, mais Porte — oito no total, em duas fileiras
(`.abas-avaliacao` em `app.css`, para caber na largura do painel sem transbordar):

- **Receita** (20%) e **Rentabilidade** (25%): abas **somente leitura** — mostram a nota já
  registrada (`notas.receita`/`notas.rentabilidade`, campo que já vinha do backend mas faltava no
  tipo TS `ItemDaCarteira`, corrigido nesta rodada). **Decisão de 28/09/2026:** Receita passa a vir
  direto do Porte (Micro=1, Pequeno=2, Médio=3, Grande=4, Extra Grande=5), substituindo o corte por
  percentil sobre o honorário praticado (`modelo-classificacao-carteira.md`, seção 4, que fica como
  registro histórico da régua anterior); Rentabilidade continua pela margem sobre o honorário
  praticado, sem mudança. **Pendência:** o recálculo automático de Receita a partir do Porte ainda
  não está implementado no backend — hoje o valor mostrado é o que já está gravado.
- **Complexidade** (12%, invertida), **Risco técnico** (7%, invertida), **Disciplina** (9%,
  interina: 3 perguntas trimestrais, até existir o registro de prazo × entrega), **Cross-sell**
  (12%, proposta de 27/09/2026 aprovada por Eduardo: 5 fatores estruturais sim/não, revisita só
  quando algo muda) e **Inadimplência** (15%, trava a classe e marca "$$$" se a nota ficar ≤2;
  interina, mesma lógica de 3 perguntas da Disciplina, até existir o registro automático de atraso
  de pagamento) — todas calculando a nota 1–5 sozinhas a partir do que foi marcado ou respondido,
  **em tempo real, sem clique extra** (conferido ao vivo: marcar um fator ou trocar uma resposta já
  atualiza "Nota calculada" na hora). O motivo enviado ao servidor é montado a partir do que foi
  marcado (ex.: "Complexidade 3 (2/6: holding; auditoria externa). Cross-sell 2 (1/5: porte comporta
  upsell)"), sem exigir texto livre de quem avalia. Salva as cinco notas de uma vez, reaproveitando
  `POST /api/carteira/grupos/{id}/notas` (que já aceitava `cross_sell`/`adimplencia`, sem tela até
  agora).
  **Correção de 29/09/2026 (grupo INMD):** o painel reabria em branco depois de gravar. As notas
  ficavam salvas, mas as respostas que as geraram só existiam como texto no motivo, e gravar de
  novo trocava as notas boas pelas do painel vazio. Agora as respostas vão junto
  (`respostas_da_avaliacao`, coluna JSON em `classificacao_do_grupo`, migração `e270619bf426`,
  que só acrescenta) e o painel reabre com as da última avaliação que as gravou, dizendo quando
  e por quem. Grupo sem respostas gravadas (avaliado antes desta data, ou só da planilha) abre
  com o aviso para marcar todas as abas antes de salvar. **Rode `alembic upgrade head`.**
- **Porte**: os nove direcionadores da régua de volume (`crm.domain.porte`, a mesma que já roda
  na Oportunidade — rótulos compartilhados em `componentes/direcionadoresDePorte.ts`), um botão
  "Ver sugestão" que calcula sem gravar (`POST /api/carteira/porte/sugestao`) e um "Porte
  confirmado" que a pessoa aceita ou sobrepõe. Diferente das outras notas, o porte **não entra no
  Score** — por isso grava direto no grupo (`GrupoEconomico.porte`/`porte_definido_por`/
  `porte_definido_em`, `POST /api/carteira/grupos/{id}/porte`), não numa nova revisão da
  classificação. Exigiu migração (`GrupoEconomico` ganha os campos de volumetria e porte).

`componentes/AvaliacaoDeNotas.tsx`.

## Carteira: parâmetros de cálculo e exportar o histórico para Excel (28/09/2026)

Dois controles **globais** (valem para toda a carteira, não para um grupo), lado a lado, acima da
tabela de grupos — deliberadamente **fora** do painel "Avaliar" de cada grupo, de onde saíram
depois de nascer lá por engano: pesos e cortes afetam o Índice de Saúde da carteira inteira, não é
avaliação de um grupo (decisão de Eduardo, 28/09/2026).

**Parâmetros de cálculo** — recolhível, ao lado do botão de exportar. Pesos do Score, cortes de
classe, trava, churn alto, imposto, atrito e cortes de margem, e a matriz de horas/mix de
equipe/taxa por Porte — tudo editável e gravado no banco (decisão de Eduardo: "existe a
possibilidade deles variarem"). Salvar grava uma **versão nova** (`VersaoDeParametros` +
`MixDeEquipe`, snapshot imutável, mesmo princípio de `ClassificacaoDoGrupo`), nunca sobrescreve —
as classificações já feitas continuam apontando pra versão que as produziu, e **quem mudou o quê
fica registrado**: autor e motivo são obrigatórios em cada edição, e "Vigente desde/por" no topo do
painel sempre mostra o responsável pela versão atual — é o log que a mudança pediu. O custo/hora
ponderado por Porte é **calculado** (taxa × mix, somado), nunca digitado solto — bate célula a
célula com `Classificacao_Grupo_COMPLETO.xlsx` (aba Parâmetros) e
`Rentabilidade_Grupo_COMPLETO.xlsx` (abas "2. Matriz Horas", "3. Fator de Atrito" e "6. Régua
Rentab."), conferido a ponto de reproduzir os mesmos R$ 41,69/R$ 39,88/R$ 40,19/R$ 45,06 que já
estavam fixos no código. A validação (pesos somando 100%, mix de cada Porte somando 100%) roda no
cliente e no servidor, com o mesmo motivo recusado nos dois lados
(`crm.domain.parametros.erros_de_pesos`/`erros_de_mix`). `GET`/`POST /api/carteira/parametros`; sem
nenhuma versão gravada, o motor cai nas constantes do código (mesma semente que a migração grava —
nunca fica sem parâmetro). Migração `5dc8a026d67a`, com a versão inicial semeada a partir das
constantes já vigentes. `componentes/AbaDeParametros.tsx`, montado em `telas/Carteira.tsx` dentro
de `componentes/Recolhivel.tsx`.

**Exportar para conferência** — baixa `carteira-historico-AAAAMMDD.xlsx` com **todas** as leituras
de `ClassificacaoDoGrupo` de todos os grupos — não só o snapshot atual — porque o banco já é
imutável (uma edição de nota grava linha nova, a anterior fica). Segue o modelo de
`Faturamento_Grupo_COMPLETO.xlsx`, três abas:

- **Histórico da Carteira**: uma linha por leitura, com **Score e Classe em fórmula viva** —
  `=I5*Parâmetros!$B$8 + J5*Parâmetros!$B$9 + ...` para o Score (a mesma soma ponderada de
  `crm.domain.classificacao.score`, com Complexidade e Risco técnico invertidos) e
  `=IF(R5>=Parâmetros!$B$2,"A",IF(R5>=Parâmetros!$B$3,"B","C"))` para a Classe — reabrindo no Excel
  e mudando um peso na aba Parâmetros, a planilha inteira recalcula sozinha. Classe efetiva, alerta
  de churn e eixo de ação ficam como **valor**, não fórmula: misturam texto e precedência (trava >
  churn > o resto), não conta — o mesmo critério que o próprio modelo de faturamento já usava (só a
  nota de receita, ali, virava fórmula).
- **Parâmetros**: os pesos e cortes vigentes no banco no momento da exportação, no mesmo layout de
  linhas da aba "Parâmetros" de `Classificacao_Grupo_COMPLETO.xlsx` — é nela que as fórmulas da
  primeira aba se apoiam.
- **Critérios e Fórmulas**: documenta em prosa o que não virou fórmula, e por quê.

`crm/relatorios/exportacao_da_carteira.py` (função pura, testada sem banco) +
`GET /api/carteira/exportar` (monta as linhas e os parâmetros vigentes, devolve o `.xlsx` como
anexo).

## Funil: indicadores compactos (26/09/2026)

Os sete indicadores do topo do Funil passaram a **cartões compactos e coloridos**, numa só linha, para o kanban aparecer já na primeira visão. Cada cartão mostra rótulo, número e uma linha de apoio; a **explicação** (definição e ressalvas, como "não é o MRR da carteira") abre numa **janela ao redor do indicador** ao passar o mouse ou ao focar com Tab. As cores vêm do design base "Critério CRM" (chart-1/4/5/6 e status ganho, atenção e perdido, com fundo suave); a taxa de conversão muda de tom conforme o estado e traz a etiqueta escrita, e o indicador não calculável mostra "Não calculável", nunca zero. **Recortes do funil** e **Cenários de ticket** ficam recolhidos por padrão e só buscam os dados quando abertos.

## Cliente não recorrente (26/09/2026)

Decisão de Eduardo: **quem fechou uma proposta é cliente**, com contrato recorrente ou sem (consultoria
pontual). Antes, só a carteira recorrente era "Cliente". Agora:

- **Proposta aceita torna o grupo Cliente**, sozinho, ao aceitar na tela e na recarga da planilha.
  `scripts/promover_clientes_por_aceite.py` corrigiu o que já existia: **32 grupos** passaram de Prospect a
  Cliente (backup antes). Hoje: 63 clientes (57 recorrentes + 32 não recorrentes, mais o Tabor, baixado) e 99 prospects.
- **Recorrente** = tem contrato Ativo com preço mensal. Sem ele, é **não recorrente**: aparece em
  Contatos → Clientes com o rótulo "Não recorrente" e as propostas no lugar da mensalidade. **Não entra no
  MRR nem no ticket** (esses vêm dos contratos).
- Os não recorrentes não têm empresa cadastrada (só a carteira tem), então aparecem pelo **grupo**.
- A sugestão "prospect que já é cliente" passou a comparar os grupos **sem empresa** (prospects e clientes
  não recorrentes) com os clientes da carteira, para não perder as duplicatas depois da promoção.

## Questionário preenche pessoa, empresa e oportunidade (01/10/2026)

Pedido de Karine: continua pelo botão **"Buscar questionários"** no Funil, e cada questionário novo já
preenche tudo sozinho.

- **Oportunidade** nasce ligada à **empresa** do CNPJ (`oportunidade.empresa_id`), também em "criar
  nova"; "anexar" só preenche a empresa se a oportunidade ainda não tiver.
- **Pessoa:** se o e-mail do contato já está na base (em qualquer empresa), a pessoa é reaproveitada —
  ganha o vínculo com esta empresa e só os campos vazios (cargo, telefone) são preenchidos. Sem isso,
  nasce a pessoa nova, como antes.
- **Endereço:** o questionário não pergunta o endereço; ele vem do **cadastro público do CNPJ**
  (BrasilAPI, `crm/questionario/endereco.py`), só nos campos vazios. Sai do CRM apenas o CNPJ. Falha de
  rede ou CNPJ não achado não impede a importação: o "o que fez" avisa "Endereço não encontrado pelo
  CNPJ". A BrasilAPI recusa o agente padrão do Python (403); o CRM se identifica como `CRM-Criterio/1.0`.
- Nos testes não há rede: `criar_app(fabrica=...)` não busca endereço, a menos que o teste passe
  `busca_de_endereco`.

## Oportunidade ligada a uma empresa da base (01/10/2026)

Pedido de Karine, amostra aprovada. Em **Funil > Nova oportunidade** a empresa é escolhida na base
de empresas — ao clicar no campo a lista aparece, e a busca acha por **nome fantasia, razão social ou
CNPJ** (com ou sem pontuação). O **grupo vem da empresa**; o campo "Grupo (cliente)" saiu. O Funil
**não cadastra empresa**: quem não está na base aparece como "Empresa não encontrada — cadastre em
Contatos > Nova empresa", e o botão "Criar oportunidade" só libera com empresa escolhida. Ao escolher,
o nome da oportunidade é preenchido com a razão social e continua editável.

- **Editar depois:** no detalhe da oportunidade, **nome** e **empresa** são editáveis (busca e
  "Trocar"); trocar a empresa leva o grupo junto. A oportunidade que **já virou contrato não troca de
  empresa** (409). O contrato passa a nascer com a empresa da oportunidade.
- **Banco:** `oportunidade.empresa_id` (migração `b7d2e9f4a1c8`). As oportunidades antigas cujo grupo
  tem **uma única empresa** receberam essa empresa (decisão de Karine); as demais ficam em branco
  para escolher no detalhe. Excluir uma empresa deixa as oportunidades dela sem empresa (o grupo fica).
- **API:** `GET /api/empresas/busca`; `POST /api/oportunidades` aceita `empresa_id` (quando vem, o
  grupo é o da empresa e `grupo_id`/`nome_do_grupo` são ignorados — o caminho antigo continua para
  integrações); `PATCH /api/oportunidades/{id}` aceita `nome` e `empresa_id`.

## Datas no padrão brasileiro (01/10/2026)

Pedido de Karine: os campos de data apareciam como mm/dd/aaaa. Motivo: o `<input type="date">` do
navegador segue o idioma do sistema (aqui, en-US), não o `lang="pt-BR"` da página. Os 14 campos de data
(filtro De/Até, Nova oportunidade, detalhe da oportunidade, Agenda, Contratos, eventos de contrato,
Leads e Abordagens) passaram a usar `CampoDeData`: sempre **dd/mm/aaaa**, as barras entram sozinhas ao
digitar, o 📅 abre um calendário em português, e data que não existe (31/02) avisa "Data inválida" e não
é repassada. Por dentro o valor continua ISO (aaaa-mm-dd), o mesmo da API — conversões em `src/dataBr.ts`.

## Contatos: clientes e prospects segregados (26/09/2026)

**Nova pessoa (26/09/2026).** O botão "Nova pessoa", no topo do menu Contatos, abre um painel para cadastrar uma pessoa sem precisar abrir antes uma empresa: busca a empresa, o CNPJ ou o grupo (entre clientes e prospects), escolhe se a pessoa fica ligada só à empresa ou ao grupo todo (prospect sem empresa liga ao grupo) e preenche nome, cargo, e-mail, telefone, papel, observação e "não contatar". Usa a mesma rota `POST /api/contatos/pessoas`. Desde 30/09/2026 a empresa é opcional (ver "Base única de contatos", abaixo).

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

**Ainda fora:** importação de contatos em lote pela tela (segue pela planilha), e as listas de
campanha que **respeitam** o *não contatar* (o campo já é gravado).

### Base única de contatos: pessoa antes da empresa (30/09/2026)

Pedido de Karine, amostra e proposta aprovadas em chat. O objetivo é não recadastrar a mesma pessoa a
cada empresa nova. Fluxo: **Nova pessoa → salva na base → Nova empresa → busca o contato → vincula →
salva a empresa**.

- **Nova pessoa sem empresa.** A empresa passou a ser opcional. A pessoa sem empresa nem grupo aparece
  em **Prospects > Pessoa** como "Sem empresa". Clicar no nome abre o painel da pessoa, com os dados e
  **todas as empresas** em que ela está (★ onde é principal).
- **Nova empresa** (botão ao lado de "Nova pessoa"): razão social, CNPJ, endereço e **Contato(s)
  vinculado(s)**. A busca cobre a base inteira (clientes e prospects) por **nome, e-mail ou telefone**.
  O grupo (o cliente) é reaproveitado pelo nome ou nasce um prospect novo, como na Nova oportunidade.
  CNPJ, UF e CEP são validados como na edição.
- **Muitos para muitos.** Uma pessoa pode estar em **várias empresas**; uma empresa tem **vários
  contatos** e pode ter **vários principais**. "Principal" é do vínculo: Maria pode ser principal na
  Delta e não na Alfa. Cargo, e-mail e telefone são da pessoa, iguais em todas as empresas.
- No painel da empresa: marcar/desmarcar principal, **Desvincular** (a pessoa continua na base e nas
  outras empresas) e **Vincular contato já cadastrado**.
- **Banco:** tabela nova `vinculo_de_contato` (pessoa, empresa, principal, único por par); saiu
  `pessoa_contato.empresa_id` e a regra "todo contato pertence a alguém". A migração `5e8b3f1a2c47`
  transforma cada ligação antiga em um vínculo. Ensaio numa cópia do banco (pg_dump) em 30/09/2026:
  226 pessoas antes e depois, 175 ligações → 175 vínculos idênticos, e o downgrade devolveu as mesmas
  ligações. O downgrade guarda só o vínculo mais antigo de cada pessoa e perde a marca de principal.
- Rotas novas: `GET /api/contatos/pessoas/busca`, `POST /api/empresas`,
  `POST /api/empresas/{id}/contatos`, `PATCH` e `DELETE /api/empresas/{id}/contatos/{pessoa_id}`.
  `GET /api/contatos/pessoas` passou a trazer `empresas` (todas as da pessoa).
- Abordagens (ficha do SDR) e a planilha de lacunas de contato passaram a ler os vínculos.

**Excluir contato e empresa (30/09/2026).** Pedido de Karine, proposta aprovada. Os botões ficam **no
fim do painel** da pessoa e da empresa, longe dos botões do dia a dia, e pedem **confirmação em dois
passos**, dizendo o que vai sumir ("Não dá para desfazer").

- **Excluir contato** apaga a pessoa da base e de todas as empresas em que está
  (`DELETE /api/contatos/pessoas/{id}`). Para tirar de uma empresa só, use **Desvincular**.
- **Excluir empresa** apaga a empresa; os contatos **continuam na base** (só o vínculo some) e o grupo
  fica (`DELETE /api/empresas/{id}`).
- **Empresa com contrato não pode ser excluída**, em qualquer situação do contrato: apagar quebraria o
  histórico, o MRR e a carteira. A API responde 409 e o painel mostra o motivo no lugar do botão
  (`tem_contrato` em `GET /api/contatos/empresas`).

**Excluir oportunidade (04/10/2026).** Amostra aprovada por Eduardo. O botão "Excluir oportunidade…"
fica no rodapé do detalhe, à esquerda e longe do "Salvar"; não fica no cartão. Exige a permissão
**Funil comercial: excluir** (`funil.excluir`), que começa só no Administrador; o perfil Comercial não
a recebe. Regra em `crm.db.excluir_oportunidade`.

- Ao clicar, `GET /api/oportunidades/{id}/exclusao` diz o que **sai junto** (propostas, pendências da
  proposta, histórico de preço) e o que **fica sem apontar para ela** (lead de origem, questionário do
  site, venda anotada em reunião). Grupo, empresas, contatos e reuniões ficam. Se ela está como
  Perdido, a tela avisa que sai da taxa de conversão.
- O **motivo é obrigatório**. `POST /api/oportunidades/{id}/excluir` grava no Histórico de alterações
  uma linha "excluiu" com o motivo, **mesmo sem login** (quem fica "sem login"): a exclusão não se
  desfaz pela tela, e o porquê é o que sobra dela. O Histórico mostra "registro excluído · motivo: …".
- **Recusa** (409, com o motivo no lugar do botão): oportunidade **Aceita** ou **Recusada** (conta na
  taxa de conversão; se a venda não aconteceu, mude para Perdido) e a que **virou contrato**.
- Apagar um grupo inteiro continua só por script (`scripts/apagar_grupo.py`).

**Contato só por empresa; o grupo mora na empresa (01/10/2026).** Pedido de Karine, aprovado: as
empresas de uma pessoa nem sempre são do mesmo grupo, então o contato deixou de ser ligado ao grupo.

- Saiu a opção "Ao grupo todo" da Nova pessoa e a coluna `pessoa_contato.grupo_id`. Escolher um
  prospect ainda sem empresa (na Nova pessoa ou no painel) cria a empresa com o nome do grupo e vincula
  a pessoa a ela.
- O **Grupo** é informado na empresa: campo em "Nova empresa" e no painel da empresa, com os grupos
  existentes como sugestão; nome novo vira prospect novo. **Empresa com contrato não troca de grupo**
  (409; use a fusão de grupos).
- Migração `9a1c7e4b2d63`: cada contato ligado a grupo virou vínculo — grupo com uma empresa: com ela;
  sem empresa: nasce a empresa com o nome do grupo; com duas ou mais: se a pessoa já está numa empresa
  do grupo, fica só nela, senão vai para todas.
- Fusão de grupos: o contato vai junto com a empresa a que está vinculado; `movidos["pessoa_contato"]`
  passou a ser só registro de quem foi junto (desfazer não o usa). Questionário do site, planilha de
  lacunas e ficha das Abordagens leem só os vínculos.

**Pendente, por decisão:** a base tem **33 e-mails repetidos**, provavelmente a mesma pessoa cadastrada
em mais de uma empresa. Juntar cada caso numa pessoa só fica para depois, caso a caso, com aprovação.

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

**Parcial ou da carteira inteira, e a tela diz qual.** O KPI oficial de MRR é a receita da
**carteira inteira** (R$ 226.341 em 19/09/2026). Sem a carteira anterior ao CRM carregada
(`importar_carteira.py`, ver acima), só entram os contratos registrados no CRM: o painel diz
"MRR parcial" e **não compara com a meta** (seria um "atingimento" enganoso). Com ela
carregada (`cobertura_completa: true`), o painel vira **"MRR da carteira"** e compara com o KPI
oficial (aprovado por Eduardo em 02/10/2026): **meta e alerta de Configurações › Metas** (hoje R$ 400 mil e R$ 200 mil),
com etiqueta de ícone e texto (⚠ abaixo do alerta · entre o alerta e a meta · ✓ na meta) e
quanto falta para a meta. A API devolve `meta`, `alerta`, `contra_a_meta` e `falta_para_a_meta`.

- **MRR atual** = preço mensal dos contratos **Ativos**. **Suspenso** aparece à parte. Contrato sem
  preço mensal (só anual) **fica de fora** e é contado: não se inventa "anual ÷ 12".
- **Movimento do período:** novos (pelo preço da assinatura) · expansão · reajuste · contração
  (qualquer queda de preço) · **churn separado por quem decidiu**: cliente (churn de fato) e
  Critério (saída organizada). A conta fecha: início + novos + expansão + reajuste − contração −
  churn = fim.
- **NRR** e **GRR** contam só contratos que já existiam no início do período. Sem MRR no início,
  **não são calculáveis** (nunca 0%).
- MRR em qualquer data = MRR atual − o movimento líquido desde então.

**Fora:** a inadimplência (o KPI oficial
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
- **Situação pelo `PATCH`** (regra aprovada por Eduardo em 01/10/2026): **Encerrado não se mexe
  mais**, nem a situação nem campo nenhum (422); **assinado só alterna entre Ativo e Suspenso**,
  sem voltar para "Aguardando assinatura" — essa volta destravava o preço, e a volta para Ativo o
  deixava trocado sem evento. A tela só oferece as situações permitidas e trava tudo no encerrado.

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
- Até o E1 não registrava **quem** mudou. Com a entrada pela conta Microsoft ligada, o histórico de alterações registra (ver "Entrada pela conta Microsoft").

**Origem da volumetria.** Cada um dos nove direcionadores da régua de porte pode dizer se
veio da **entrevista** ou do **questionário** (`origem_da_volumetria`, um mapa por
oportunidade). Só vale para campo preenchido: a origem de um campo que voltou a ficar vazio é
descartada pelo servidor, e a API recusa origem de campo que não seja direcionador (422).

**Ainda fora:** a *lista do que falta para a proposta, com responsável e prazo* e a *geração do
documento* — a primeira depende de definir os itens, a segunda do modelo oficial e do formato.

## Grade do funil em Excel (28/09/2026)

Na visão **Grade** do funil, o botão **Exportar para Excel** (ao lado da troca Kanban/Grade) baixa
`funil-AAAA-MM-DD.xlsx` com as mesmas oito colunas da tabela — Cliente, Oportunidade, Situação,
Temperatura, Captador, Originação, Mensal e Anual — e as mesmas oportunidades que os filtros da tela
selecionam, inclusive Situação. Sem limite de página. Valor sai como número (R$) e Originação como
data; cabeçalho congelado e filtro do Excel ligado.

- Rota: `GET /api/oportunidades/exportar`, com os mesmos parâmetros de `GET /api/oportunidades`.
- A ordem é a padrão da lista (originação mais recente primeiro). A ordenação clicada nas colunas da
  tela não vai para a planilha: ordene lá, pelo filtro do Excel.
- Só lê. Leva dado de cliente: guarde fora do repositório.

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
- **Backup antes de migrar (02/10/2026):** o `exportar` lê as tabelas e colunas que estão no
  banco, não as do código. Pode e deve rodar depois do `git pull` e antes do
  `alembic upgrade head` — antes quebrava com `UndefinedColumn` e, no caso inverso, sairia sem a
  coluna que a migração ia transformar. Para restaurar um backup de esquema anterior, volte o
  código para a mesma versão: a importação recusa coluna que o código não conhece, em vez de
  descartá-la calada.
- **Só na máquina do CRM:** as rotas `/api/backup/*` recusam pedido que chegue por
  túnel (ngrok) ou host que não seja `localhost`, porque o arquivo tem todos os dados
  de cliente e a API não tem login.
- **Sem criptografia.** Guarde fora do repositório e de pastas compartilhadas.
- **Grupos juntados (29/09/2026):** a importação quebrava com "Erro 500" quando um grupo
  fundido tinha número menor que o principal (o caso comum depois de "Juntar grupos"). Agora
  o apontamento da fusão é gravado depois que todos os grupos existem, com a data de
  atualização original preservada.
- **Erro com explicação:** se algum registro do arquivo não puder ser gravado (por exemplo,
  um valor que esta versão do CRM não conhece), a tela diz qual tabela e por quê, em vez de
  "Erro 500". Nada fica gravado pela metade.
- **Banco recém-criado não é vazio:** as migrações gravam os parâmetros iniciais
  (`versao_de_parametros`, `mix_de_equipe`), então importar num banco novo também pede
  `--substituir` (na tela, a confirmação de substituir).
- **Conferido no PostgreSQL** (29/09/2026), em bancos descartáveis: ida e volta com grupo
  fundido, dados idênticos e a sequência de ids continuando certa depois da importação.

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

A API escuta **só em `127.0.0.1`**, de propósito. Sem a entrada pela conta Microsoft
configurada, ela não tem login: não a exponha na rede assim.

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

**Cada linha do relatório diz de quem é (pedido de Eduardo, 30/09/2026).** A tela de Conferência
mostra a oportunidade e o grupo de cada linha, achados pela `linha_planilha` que a carga grava na
oportunidade. O nome abre a oportunidade para completar, por exemplo, a data de aceite. A coluna
"Situação hoje" olha o CRM agora: "✓ preenchida: DD/MM/AAAA" ou "· falta preencher", e o topo conta
quantas faltam. Só na **rodada mais recente**: a `linha_planilha` guarda a posição da última carga,
e numa rodada antiga a linha pode ter mudado de lugar. Linha com mais de uma oportunidade também
fica sem nome, porque nome errado é pior que nome nenhum.

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

**Desfazer a fusão (26/09/2026, precaução pedida por Eduardo).** Toda fusão agora grava um registro
(`fusao_de_grupos`) com os **ids** do que ela moveu (empresas, propostas, contatos e **contratos**) e o
estado anterior do principal. Na tela **Grupos**, o painel "Fusões feitas" lista as fusões com o botão
**Desfazer**, em dois passos. Desfazer devolve ao absorvido **exatamente** esses itens e o reabre, com a
situação que ele tinha; o que foi criado no principal depois **fica onde está**; e situação/data de
entrada do principal só voltam se ninguém as tiver mudado depois. Uma fusão não se desfaz duas vezes.
`POST /api/grupos/fusoes/{id}/desfazer`, `GET /api/grupos/fusoes`.

- **Antes a fusão não movia os contratos** (só empresas, propostas e contatos). Era um risco latente:
  agora move e devolve. Ficha de conta e abordagem do agente SDR **ainda não** são movidas.
- **As 38 fusões já feitas** em 26/09/2026 tiveram o registro **reconstruído do backup** de antes do lote
  (`scripts/reconstruir_fusoes.py`, marcado "registro refeito do backup"). Prova: desfazer as 38 numa
  transação devolveu **0** itens e **0** grupos diferentes do backup, e a transação foi descartada.
  As 3 fusões anteriores ao lote não têm registro: só o backup as desfaz.

**Prospect que já é cliente (26/09/2026).** Depois da carga da carteira, `sugerir_clientes` cruza cada
prospect com os clientes pelo **nome das empresas** de cada grupo (a carteira usa o grupo econômico e a
razão social; as propostas usam o nome que o comercial digitou, como "ASM retomada… - 3AW" para o "Grupo
3AW"). A **palavra em comum** (3+ letras, fora de uma lista de genéricas) precisa apontar para **um único
cliente**; cada sugestão é um **par** (cliente, prospect) com o cliente como principal, nunca uma
corrente. O motivo diz **onde** a palavra apareceu (no nome do grupo, evidência mais forte, ou numa
empresa). Prospects que apontam para dois clientes ficam de fora. Só sugere: quem funde é uma pessoa.
Os candidatos são os grupos **sem empresa cadastrada**, sejam prospects ou clientes não recorrentes, e os
alvos são os clientes da carteira. Em 26/09/2026: 28 pares, 14 com a palavra no nome do grupo e 14 só na
razão social de uma empresa.
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

### Parcelas no serviço recorrente (30/09/2026)

Pedido de Karine: em "Nova oportunidade", quando o serviço escolhido é
**recorrente (C1)**, aparece o campo **Quantidade de parcelas** (1 a 120) e o
**Preço anual** deixa de ser digitado — vira `preço mensal × parcelas`, travado
(somente leitura). Exemplo: R$ 5.000,00 × 12 = R$ 60.000,00.

- A quantidade fica guardada em `oportunidade.quantidade_parcelas` (migração
  `3b1d5c0a9e27`) e volta no detalhe da oportunidade.
- O servidor refaz a conta em `POST /api/oportunidades`: com serviço C1 e
  parcelas, qualquer `preco_anual` enviado é ignorado; parcelas sem preço
  mensal dão 422. Em serviço não recorrente (C2) ou fora do catálogo, as
  parcelas são descartadas e o preço anual segue livre, como antes.
- A conta na tela é feita em centavos inteiros (`src/parcelas.ts`), para o
  valor mostrado bater com o gravado.
- Vale só para a criação. A edição de preço no detalhe não mudou.

### Reajuste na nova oportunidade (30/09/2026)

Pedido de Karine: "Nova oportunidade" ganhou o seletor **Reajuste**, para
qualquer serviço, com as opções **IPCA (IBGE)**, **IGP-M (FGV)** e **Sem
reajuste**. Em branco fica "Não informado".

- Só registra o índice escolhido; o CRM não calcula reajuste.
- A lista vive em `IndiceDeReajuste` (`crm/domain/listas.py`) e chega à tela
  por `GET /api/listas` (`indices_de_reajuste`). Incluir um índice novo é
  acrescentar um item ali, sem migração, porque a coluna guarda texto.
- Fica em `oportunidade.reajuste` (migração `7c4e2a91d6b0`); valor fora da
  lista dá 422.

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

## O agente SDR (26/09/2026)

Decisão de Eduardo no go-to-market de R$ 250 mil de MRR até jun/27: o SDR é um
agente de IA. Fase 1 aprovada: **pesquisa, ficha e rascunho**; canais e-mail
(Microsoft 365) e WhatsApp; **toda mensagem aprovada por Eduardo**. Amostra da
tela aprovada em chat antes da construção.

### O que ele faz

1. A conta entra na fila de um mês (`POST /api/abordagens` ou o script
   `backend/scripts/importar_abordagens.py`, a partir de um CSV **fora do
   repositório**). Sem "quem apresenta", a conta aparece **Bloqueada** — a
   abordagem de uma conta âncora sempre tem um padrinho.
2. "Preparar a ficha" chama o Claude (`crm/agente/sdr.py`) em segundo plano. Ele
   lê o histórico da conta no CRM, busca na web (até 8 buscas) e registra, pela
   ferramenta `registrar_preparo`: o que a Critério já fez com a conta, fatos
   públicos **cada um com a fonte**, quem decide, assunto e mensagem.
3. O rascunho fica **Aguardando aprovação**. Eduardo edita à vontade, pede outra
   versão com uma instrução, ou descarta.
4. **Aprovar** só passa se as conferências passarem (`crm/domain/abordagem.py`):
   sem preço, sem destino marcado "não contatar", fato só com fonte,
   destinatário válido, nenhum `[campo]` por preencher, quem apresenta definido.
   E-mail sai na hora pelo Microsoft Graph; WhatsApp vira um link `wa.me` com o
   texto pronto — a pessoa envia e marca como enviada.

### Por que o agente não envia

O agente **não tem ferramenta de envio**. O único caminho até o cliente é a
rota de aprovação, que confere tudo de novo no servidor, com a linha travada
(`with_for_update`). Se o envio falha, a abordagem continua como estava (502) e
nada é marcado como enviado.

### Situações

`A preparar` → `Pesquisando` → `Aguardando aprovação` → (`Aprovada`, só
WhatsApp) → `Enviada`. Laterais: `Erro` (volta a preparar), `Descartada`.
`Bloqueada` não é gravada: é `A preparar` sem quem apresenta, calculada na hora.
A mesma conta não entra duas vezes na fila do mesmo mês, salvo se a anterior foi
descartada.

### Rotas

`GET /api/abordagens` (filtros `mes`, `situacao`), `GET /api/abordagens/resumo`,
`POST /api/abordagens`, `GET` e `PATCH /api/abordagens/{id}`, e as ações
`preparar`, `nova-versao`, `aprovar`, `marcar-enviada` e `descartar`, todas
`POST /api/abordagens/{id}/<ação>`.

### Configuração

No `backend/.env` (modelo em `.env.example`, sem valores):

| Variável | Para quê |
|---|---|
| `ANTHROPIC_API_KEY` | Obrigatória para preparar. Sem ela, a abordagem vai para `Erro` explicando |
| `CRM_AGENTE_MODELO` | Opcional; padrão `claude-opus-5` |
| `CRM_M365_TENANT_ID`, `CRM_M365_CLIENT_ID`, `CRM_M365_CLIENT_SECRET` | Aplicativo no Entra ID com a permissão de aplicativo `Mail.Send` e consentimento de administrador |
| `CRM_M365_REMETENTE` | A caixa que envia (ex.: a de Eduardo) |

Sem as variáveis do M365, aprovar por e-mail recusa (409) e diz o que falta; o
WhatsApp funciona sem nada disso. O `.env` é relido a cada uso: não precisa
reiniciar a API depois de preencher.

### Custo

Cada preparo grava uma linha em `execucao_do_agente` (tokens, buscas, custo
estimado em US$). O resumo do mês soma e avisa quando parte do custo não pôde
ser estimada. É **estimativa**: a fatura da Anthropic é a fonte da verdade.

### O que sai da máquina (LGPD)

Para a API da Anthropic vão: o nome da conta, o histórico de propostas no CRM
(serviço, situação, mês, preço mensal e motivo de recusa), o contexto digitado,
e **nome e cargo** dos contatos. **E-mail e telefone não vão**: o destinatário
fica só no CRM. Isso precisa de uma decisão formal de Eduardo sobre base legal
(legítimo interesse, B2B) antes do uso com contas reais.

### Uma lição do PostgreSQL

A tarefa em segundo plano do FastAPI roda **antes** da sessão da requisição
fechar. No SQLite dos testes (uma conexão só) ela via a mudança; no PostgreSQL,
não — a conta ficava presa em "Pesquisando". `preparar` e `nova-versao`
confirmam a transação (`_confirmar_antes_de_agendar`) antes de agendar o
preparo. Achado só porque o fluxo inteiro rodou num PostgreSQL de verdade.

## Classificação da carteira (Etapa 3, 26/09/2026)

Tela **Carteira** (somente leitura): ISC, componentes, distribuição por classe e, por grupo, classe efetiva, Score, alerta de churn e eixo de ação.

- **Regra** em `backend/src/crm/domain/classificacao.py`, parâmetros versionados (`2026-07-planilha-v1`). Score = 0,20 receita + 0,25 rentabilidade + 0,12 cross-sell + 0,12×(6−complexidade) + 0,09 disciplina + 0,07×(6−risco) + 0,15 adimplência. Classe por corte fixo (A ≥ 3,95; B ≥ 3,35; senão C) mais o sufixo do semáforo. Adimplência ≤ 2 marca "(TRAVADO)" e `$$$` sem rebaixar. O churn é campo próprio (na planilha estava escondido na fórmula).
- **Carga**: `backend/scripts/importar_classificacao.py <classificacao.xlsx> <rentabilidade.xlsx>` roda em ensaio por padrão. Liga cada unidade ao grupo do CRM pelo CNPJ (seguindo as fusões), recalcula tudo e compara com a planilha; qualquer divergência bloqueia a gravação. `--aplicar` faz backup antes e grava um snapshot por (grupo, referência), idempotente.
- **Conferência de 31/07/2026**: 31 unidades, ISC 53,65 (zona de atenção), igual ao da planilha; receita R$ 226.341,20.
- **Notas de grupo são decimais** (média das empresas), por isso as colunas são `Numeric(4,2)`.
- **Rentabilidade recalculada (defeito 7.2, decisão de 26/09/2026)**: a fórmula viva da planilha indexa o atrito de indisciplina com a disciplina direta, contra a própria documentação (`6 − disciplina`) e o Score (5 = cliente ótimo). `crm/domain/rentabilidade.py` calcula margem e nota com a disciplina invertida; `importar_classificacao.py --recalcular-rentabilidade` grava a **revisão 2** da mesma referência (a revisão 1, com a nota da planilha, fica; a tela e a API mostram a maior). Antes de gravar, confere que a fórmula viva reproduz a nota da planilha. Onde os honorários por empresa não fecham com a receita oficial: empresa única usa a oficial (aviso); grupo com várias empresas não rateia e mantém a nota da planilha (aviso). Resultado em 31/07/2026: ISC 53,65 → 50,40; 7 notas de rentabilidade e 2 classes mudam. `horas_por_mes` guarda as horas-base, como a planilha.
- **Pendente**: notas humanas (complexidade, disciplina, risco, cross-sell, adimplência), churn e semáforo: quem atribui e a régua de cada uma. Grupo sem contrato ativo hoje (ex.: Tabor) continua no snapshot da referência e é marcado.
- Rota: `GET /api/carteira/classificacao`.
- **Empresas do grupo (opcional)**: cada grupo tem um botão "+" que abre as empresas dele (razão social, CNPJ e mensalidade dos contratos ativos e suspensos); "−" fecha. Vêm no mesmo `GET /api/carteira/classificacao`, no campo `empresas`, e seguem as fusões (as empresas ficam no grupo que ficou).
- **Observações** (rentabilidade recalculada, grupos que mantiveram a nota da planilha, grupo sem contrato ativo) ficam no rodapé da tela, em texto pequeno, e não no topo.
- **Legenda do eixo de ação**: no rodapé, compacta, em texto pequeno (recolhível), com os cinco eixos, a condição de cada um e o que significa, na ordem de precedência (Cobrança > Reter já > Reter / vigiar > Saída organizada > Sem urgência).
- **Design da tela (26/09/2026)**: segue a família dos decks de Classificação da Carteira (`Classificacao_Carteira_Grupo_v9`, `Slide_ISC`, `Tabelas_Score`): painel escuro do ISC com medidor em arco (zonas escritas, não só cor), três cartões de componentes, tabela com grupos em negrito e "▸", legenda dos símbolos e "Como é calculado" recolhido. **Tipografia Cambria (títulos) e Calibri (corpo) só nesta tela**, com fallback para Source Serif 4 e Segoe UI/Poppins onde não estiverem instaladas; o resto do CRM segue o PAD-002. As cores do painel (marino, dourado, vermelho, âmbar, verde) ficam como variáveis `--isc-*` dentro de `.carteira`.

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

## Movimento reduzido (26/09/2026)

Quem liga "reduzir movimento" no sistema operacional deixa de ver transição e
animação na tela. Antes só o esqueleto de carregamento respeitava a preferência;
o destaque da coluna do kanban ao arrastar esmaecia mesmo assim. Agora uma
regra só, no **fim** de `frontend/src/app.css`, vale para todo elemento: a
duração cai para quase zero (não `none`), então o estado final continua
aparecendo — a coluna-alvo ainda fica destacada, só que sem esmaecer.

A regra ser global e a última do arquivo é o que cobre a transição que alguém
criar depois. `movimento.test.ts` confere as duas coisas; verificado quebrando a
regra de propósito (o teste falha) e no Chromium, com e sem a preferência
ligada: sem ela, 0,1 s na coluna e 1,4 s em loop no esqueleto; com ela, ~0 nos
dois. O jsdom não avalia `@media`, por isso a checagem no navegador.

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

215 testes com **Vitest** e **Testing Library**, em `frontend/src/**/*.test.{ts,tsx}`:

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

## Menu: Funil e Oportunidades viraram uma tela só (27/09/2026)

Fusão pedida por Eduardo: as duas telas mostravam a mesma base (a oportunidade), só em formatos
diferentes — Kanban (colunas por situação, sempre todas visíveis, com arrasto) e Grade (tabela plana,
filtrável por uma situação de cada vez). Agora é **uma tela só ("Funil"), com um botão Kanban/Grade**
na barra de filtros. O filtro "Situação" só aparece na Grade — no Kanban ele não faz sentido, porque
todas as situações já ficam visíveis lado a lado. As duas visões usam a mesma busca (texto, captador,
canal, serviço, temperatura, período) e o mesmo painel de detalhe; cada uma chama sua própria rota
(`GET /api/funil` para o Kanban, `GET /api/oportunidades` para a Grade) só enquanto está em tela — a
outra não busca nada. `Lista.tsx` foi removido (a lógica virou parte de `Funil.tsx`); o atalho da
Agenda que abria a lista agora abre o Funil.

## Menu: Leads saiu do menu (27/09/2026)

> **Atualização do mesmo dia:** a fila de leads voltou como aba da tela "SDR da
> IA", onde o lead é qualificado antes de virar oportunidade. Ver "SDR de IA".

Decisão de Eduardo: "Nova oportunidade" (dentro de Oportunidades/Funil) já captura o mesmo que a tela
Leads — nome, canal, captador, temperatura — e nasce direto como proposta, sem passar por um estágio
de lead. O item **saiu do menu lateral**; `Leads.tsx`, o modelo `Lead` e as rotas `/api/leads` continuam
no código (o único lead existente já está "Convertido", sem pendência). Na Agenda, o atalho que antes
abria "Leads" agora abre **Oportunidades**.

## Ressalva de processo — resolvida

Este código começou em 20/09/2026, depois de Eduardo dizer "pode codar agora",
**antes da proposta do PF-09.5 existir**. O gate foi atravessado por instrução
direta, e por isso o código se limitou ao que não dependia das decisões abertas.

**No mesmo dia a situação foi regularizada:** as seis decisões fecharam, a
proposta foi escrita (`../proposta.md`) e **Eduardo a aprovou**, inclusive a
inversão E1 ↔ E2/E3. A construção do E2 e do E3 está liberada com gate cumprido.

Fica o registro porque a ordem importou: o código veio antes da proposta, e isso
só não custou nada porque o escopo foi contido de propósito.
