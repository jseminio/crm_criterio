# SDR de IA — Inventário das fontes da base de conhecimento

> ⚠️ **PROPOSTA PARA VALIDAÇÃO. HIPÓTESE, NÃO DECISÃO.**
> Escrita em 04/10/2026 a pedido de Eduardo. É o **passo 2** da base de
> conhecimento do SDR de IA. O passo 1 está em `sdr-ia-limites-de-atuacao.md`.
> Os donos sugeridos abaixo são **proposta**: ninguém foi consultado ainda.
>
> **Atualizado em 04/10/2026** com as decisões de Eduardo e as fichas aprovadas
> na tela (seção "Decidido em 04/10/2026", no fim).

**Como ler.** Cada fonte traz uma marca de status:

- **[decisão]**: decisão tomada, registrada em outro documento do projeto.
- **[proposta]**: o que este inventário sugere, à espera de aprovação.
- **[pendência]**: falta informação para fechar.

---

## 1. A conclusão

**A base cresce mais rápido pelas entrevistas do Granola do que pela Matriz
de Objeções.** **[proposta]**

A Matriz tem 17 objeções, mas os tipos são cláusula contratual, LGPD,
escopo, preço e multa. São objeções de **fim de negociação**, com posição
jurídica e alçada (`ESCALAR`, `ACEITAR COM AJUSTE`). O SDR conversa no
**topo do funil**: ali aparecem "quanto custa", "já tenho contador", "agora
não é o momento". Dessas, a Matriz cobre bem só a de preço.

Por isso, a proposta é:

- Da Matriz, a IA usa **só as objeções de topo de funil**. As contratuais e de
  LGPD continuam exclusivas da equipe e viram gatilho de transbordo.
- As **objeções de topo** e as **perguntas frequentes** saem das entrevistas
  do Granola (template "[Potencial Cliente]", que já tem a seção de objeções)
  e dos motivos de descarte e recusa que o CRM já registra.

## 2. O inventário

Uma linha por fonte. A coluna "Na IA?" diz se o conteúdo pode virar ficha
que a IA usa. Nenhuma fonte entra copiada: cada ficha é escrita por uma
pessoa, na versão para a IA, e aprovada na tela.

| # | Fonte | Onde está | Alimenta o bloco | Status da fonte | Dono sugerido | Na IA? |
|---|---|---|---|---|---|---|
| F1 | Limites de atuação (passo 1) | `sdr-ia-limites-de-atuacao.md` e fichas P1–P12, T1–T11, V1–V3 | Regras, Transbordo, Tom de voz | Proposta em validação **[pendência]** | Eduardo, com aprovação do Bruno | Sim, depois de aprovadas |
| F2 | Catálogo de serviços | CRM (`crm/domain/servicos.py`) e fichas S01–S12 | Serviços, Qualificação | Lista aprovada em 27/09/2026 **[decisão]**; textos "para quem é" e "fora do perfil" em rascunho | Eduardo | Sim |
| F3 | Matriz de Objeções | SharePoint, site Comercial, `09_Governança comercial - IA/03_Matriz de objeções/matriz-objecoes.csv` | Objeções (só as de topo) | Entra no CRM como base viva **[decisão, 19/09]**; lida de novo em 04/10/2026 (seção 8) | Bruno (posições); Comercial (versão para a IA) | **Parcial**: 4 das 17 (seção 8) |
| F4 | Entrevistas no Granola, template "[Potencial Cliente]" | Granola | Perguntas frequentes, Objeções de topo, "como o lead pergunta" | Em uso **[decisão]**; só o resumo entra no CRM | Comercial | Sim, **anonimizado**: sem nome de cliente, número ou caso identificável |
| F5 | Motivos de descarte e de recusa | CRM (lead e oportunidade) | Objeções (qual priorizar), Transbordo | Listas controladas no CRM **[decisão]** | Eduardo | **Não como texto**: orienta quais fichas escrever primeiro |
| F6 | Questionário de volumetria | SharePoint, `Questionario_BPO_Full_2026_v2.docx` | Qualificação (só as perguntas que o SDR faz) | Oficial **[decisão]**; seção 9 proposta, arquivo não alterado **[pendência]** | Eduardo | Só as perguntas de qualificação |
| F7 | Régua de porte | `regua-de-porte-e-plano-de-teste.md` | Qualificação | Hipótese, não decisão **[decisão de 19/09]** | Eduardo | Só as perguntas; a régua em si, não (P6) |
| F8 | Modelos de proposta: BPO Full, BPO Financeiro e carta de consultoria | SharePoint, site Comercial | Serviços (o que o escopo cobre) | Oficiais **[decisão]** | Eduardo | Só a descrição de escopo, sem preço nem prazo |
| F9 | Apresentação Institucional Critério 02.2026 (17 páginas) | OneDrive Frame Capital, `…/CRITERIO CONTAB/Comercial/PPT/` | Quem é a Critério, Perguntas frequentes | Material oficial de fev/2026, lido em 04/10/2026 | Eduardo | **Parcial**: ver seção 6 |
| F10 | Base legal do lead frio | Em preparação **[pendência]** | Transbordo (T10) | — | A definir | Sim, quando aprovada |
| F11 | Conversas do SDR: transbordos, falhas e notas baixas | CRM, quando o canal existir | Lacunas que viram ficha nova | Integração não existe ainda | Quem fizer a revisão semanal | Indireto: gera fichas novas |
| F12 | Referências externas | Fichas R1–R6 | Referências | Consultadas em 03/10/2026 | Eduardo | **Nunca** (só consulta da equipe) |
| F13 | Pasta `09_Governança comercial - IA` (bases vivas, modelos, playbook e base de contratos) | SharePoint, site Comercial, `01. Ponto de Partida/` | Nenhum bloco da IA | Material da equipe, de ago/2026 | Bruno | **Não**: contratos e posições jurídicas |

## 3. O que nunca entra na base

Nem em versão resumida. **[proposta]**

| Fonte | Por quê |
|---|---|
| `Planilha de Precificação.xlsx` e a tabela de consultoria e auditoria | A IA não informa preço (P1) |
| Modelos de contrato | Posição jurídica: é da equipe |
| Objeções contratuais, de LGPD e de multa da Matriz | Posição jurídica e alçada: viram transbordo |
| Planilhas de classificação, rentabilidade e faturamento da carteira | Dado de cliente e de margem |
| `KPI de Head de Novos Negócios.xlsx` | Gestão interna, não conversa com o lead |
| Roteiro da Descoberta do Cliente | Fica fora do CRM **[decisão]** |
| Da apresentação institucional: logos de clientes, Código de Cultura, telefone e e-mail dos sócios | Nome de cliente (P9); cultura é material interno; o contato com a equipe é pelo transbordo |
| Transcrição ou nota de entrevista com dado identificável | Dado de cliente não entra no repositório nem na base |

## 4. Onde a base está fraca hoje

Situação depois da carga de 04/10/2026: 46 fichas, nenhuma aprovada.

| Bloco | Hoje | Fonte que fecha a lacuna | Ação |
|---|---|---|---|
| Regras, Transbordo, Tom de voz | 26 fichas em revisão | F1 | Eduardo e Bruno aprovam ou ajustam |
| Serviços | 12 rascunhos | F2, F8 | Revisar "para quem é" e "fora do perfil"; escrever o Representante Legal; fechar a versão do FSCP |
| Objeções | **0** | F3 (preço), F4, F5 | Escrever as objeções de topo, uma ficha cada |
| Perguntas frequentes | **0** | F4 | Levantar as perguntas que mais aparecem nas entrevistas |
| Quem é a Critério | 1 rascunho | F9 | Trocar o texto da C1 pelo da seção 6 e criar a C2 e a C3 |
| Qualificação | 1 rascunho | F6, F7 | Decidir como perguntar o faturamento (passo 1, seção 6) |

**As primeiras objeções de topo a escrever**, revistas depois da leitura do
Granola (seção 7). **[proposta]**

| # | Objeção | Evidência | Status |
|---|---|---|---|
| O1 | Preço e orçamento: "quanto custa?", "quero preço fechado já" | Matriz (OBJ-011, posição consolidada) e 1 entrevista | Confirmada. Texto na seção 8 |
| O2 | "Estou trocando de sistema; agora não é o momento" | 2 de 2 entrevistas com potencial cliente | **Confirmada**: é a forma concreta do "agora não é o momento" |
| O3 | "Quem vai fazer o dia a dia? Não quero sócio na venda e equipe júnior na execução" | 1 entrevista e 1 Descoberta do Cliente | **Confirmada**: objeção nova, não estava na lista |
| O4 | "Quanto tempo vocês levam para arrumar?" | 1 Descoberta do Cliente | Confirmada. Resposta já existe (P4) |
| O5 | "Já tenho contador e não quero trocar agora" | Motivo de descarte no CRM; **não apareceu** nas entrevistas | Hipótese |
| O6 | "Só preciso de um serviço pontual" | Motivo de descarte no CRM | Hipótese |
| O7 | "Vocês garantem o resultado ou a economia?" | Matriz (OBJ-012, inegociável) | Confirmada. Texto na seção 8 |
| O8 | "Vocês usam inteligência artificial? Não aceitamos" | Matriz (OBJ-008, sempre escalar) | Confirmada. **Transbordo** |
| O9 | "Vocês resolvem qualquer demanda do tema?" | Matriz (OBJ-010, posição consolidada) | Confirmada. Texto na seção 8 |

A hipótese "trocar de contador dá muito trabalho" **não apareceu** nas entrevistas
e sai da lista. Aparece outra, parecida, que é a O2: a troca de sistema.

## 5. Ordem de trabalho

| Ordem | O quê | Quem (sugerido) | Depende de |
|---|---|---|---|
| 1 | Aprovar ou ajustar as regras e os gatilhos (F1) | Eduardo e Bruno | — |
| 2 | Revisar as 12 fichas de serviço (F2, F8) | Eduardo | — |
| 3 | Escrever as objeções de topo (F3, F4, F5) | Comercial; Bruno valida as que tocam precedente | Ordem 1 |
| 4 | Levantar as perguntas frequentes nas entrevistas (F4) | Comercial | — |
| 5 | Reescrever a C1 e criar a C2 e a C3 a partir da apresentação (F9, seção 6) | Eduardo | — |
| 6 | Passo 3: fechar o modelo de ficha com o que as ordens 1 a 5 ensinarem | Eduardo, com apoio do Claude | Ordens 1 a 4 |

As ordens 2, 4 e 5 andam em paralelo com a 1.

## 6. "Quem é a Critério", a partir da apresentação institucional

Fonte: `Apresentação Institucional Critério 02.2026.pdfv2.pdf`, lida em
04/10/2026. Os textos abaixo são **proposta** para colar nas fichas pela tela.
Todos passam pela trava de preço.

**C1 · Quem é a Critério** (substitui o rascunho da carga)

- **O que a IA pode dizer:** "A Critério está há 30 anos no Rio de Janeiro,
  atuando como parte do negócio dos seus clientes. Cuidamos da contabilidade,
  do fiscal, do departamento pessoal e do financeiro das empresas, e apoiamos
  as decisões com consultoria tributária e de finanças corporativas: avaliação
  de empresas, captação de recursos e compra e venda de empresas. A equipe é
  formada por sócios com longa experiência de mercado, vários com passagem por
  grandes firmas de auditoria."
- **O que a IA nunca diz:** os números de resultado da apresentação; nomes de
  clientes; telefone ou e-mail de sócios.
- **Como o lead pergunta:** "Quem são vocês?" · "Há quanto tempo existem?" ·
  "O que vocês fazem?"

**C2 · Onde fica a Critério** (bloco Perguntas frequentes)

- **O que a IA pode dizer:** "Nosso escritório fica na Rua do Rosário, 103,
  12º andar, no Centro do Rio de Janeiro."
- **O que a IA nunca diz:** se atende fora do Rio ou se atende só a distância.
  A apresentação não diz **[pendência]**.
- **[decisão, 04/10/2026]** A Critério atende fora do Rio. Esta ficha virou
  duas, pelo modelo de ficha (um assunto por ficha): **F1 · Onde fica a
  Critério** e **F2 · Atendem fora do Rio?**, ambas aprovadas. Como é o
  atendimento fora do Rio (a distância ou presencial) continua sem definição.
- **Como o lead pergunta:** "Onde vocês ficam?" · "Vocês têm escritório?"

**C3 · Como a Critério trabalha** (bloco Quem é a Critério)

- **O que a IA pode dizer:** "Usamos o Acessórias para controlar prazos e
  falar com os clientes, e o Master Tax para auditoria fiscal e prevenção de
  riscos. A equipe se organiza pelo MOSAIC, uma metodologia ágil inspirada no
  Scrum e feita para prestadores de serviço."
- **O que a IA nunca diz:** que esses sistemas são vendidos ou entregues ao
  cliente, ou prazo de implantação.
- **Como o lead pergunta:** "Que sistema vocês usam?" · "Como eu acompanho o
  trabalho de vocês?"

**Três pontos para decidir antes de aprovar:**

1. **Os números de resultado ficam fora da IA.** **[proposta]** A apresentação
   traz mais de 300 milhões captados, mais de 60% de redução de custos, mais de
   200 milhões de dívidas tributárias renegociadas e mais de 40 milhões em
   descontos em transações tributárias. Ditos pela IA a um lead, soam como
   promessa de resultado (P4). A frase dos 40 milhões ainda seria barrada pela
   trava, porque contém "descontos". Recomendação: os números ficam para a
   equipe, na reunião.
2. **A apresentação diz "terceirizamos".** O tom de voz da base (V2) vende tempo
   e capacidade de decisão, e proíbe "terceirização de tarefas". As fichas
   acima evitam a palavra; a apresentação continua com ela. Vale alinhar a
   próxima versão da apresentação com o posicionamento? **[pendência]**
3. **A apresentação está no OneDrive da Frame Capital.** Para a fonte ter dono
   na Critério, vale guardar a versão oficial no SharePoint Comercial da
   Critério e apontar a ficha para lá. **[proposta]**

A apresentação **não menciona** BPO Financeiro como produto separado, BPO Plus
nem CFO as a Service. Isso é coerente com essas fronteiras ainda serem
hipótese (P6): a IA continua sem anunciá-las.

## 7. O que as entrevistas do Granola mostram

Lidas em 04/10/2026, na conta de Eduardo: duas entrevistas com potenciais
clientes (template "[Potencial Cliente]", mais a primeira conversa com um
deles), uma Descoberta do Cliente e uma conversa de escopo com cliente novo.
Nada foi copiado: abaixo só o que se repete, sem nome, número ou frase que
identifique alguém.

**Limites da amostra.** **[pendência]**

- São **quatro conversas**, e só **duas** com potencial cliente. Serve para
  confirmar ou descartar hipótese, não para medir frequência.
- As duas empresas estão **acima do ICP em teste** (R$ 300 mil a R$ 2 milhões
  por mês), e as conversas foram com sócios, não com um SDR. O lead que chega
  pelo tráfego pago tende a ser menor e a perguntar coisas mais simples.
- O plano atual do Granola só mostra reuniões a partir de 04/09/2026, e só as
  de Eduardo. As notas da Karine e as conversas mais antigas ficaram de fora.

**1. O motivo de mudar é a contabilidade passiva, não o preço.** Nas duas
entrevistas, o lead já tem contador, e a queixa é a mesma: a contabilidade
entrega o que o fisco pede, não ajuda na gestão, não conversa com o
financeiro, e o próprio gestor acaba "pensando pelo contador" e controlando
tudo em planilha. **Para a base:** é a dor que a IA deve reconhecer e
devolver na qualificação, e reforça o posicionamento (Empresário Operador →
Empresário Gestor). Vira ficha de Qualificação e de Perguntas frequentes.

**2. A barreira é o momento, não a confiança.** Nas duas entrevistas, a troca
ou a implantação de sistema de gestão aparece como motivo para esperar (O2).
Nenhuma levantou dúvida sobre a Critério.

**3. Quem executa pesa mais do que quem vende.** Um potencial cliente disse
que não quer o sócio na venda e uma equipe fraca na execução; a Descoberta do
Cliente contou de um fornecedor descartado por falta de vivência operacional
(O3). **Para a base:** a resposta da O3 precisa de uma promessa que a Critério
consiga cumprir (por exemplo, apresentar na reunião quem vai atender). **O
texto depende de decisão sua** **[pendência]**; até lá, a O3 vira transbordo
para os sócios. **[decisão, 04/10/2026]** Eduardo escreveu o texto: a execução
é organizada em duas frentes (BPO Financeiro, com Head e analistas;
contabilidade, fiscal e folha, com Head, supervisores por frente e
analistas). A ficha O3 está aprovada.

**4. Saving e funding vendem mais do que organização.** A Descoberta do
Cliente disse que organização financeira é vista como "bom ter", e redução de
custo e captação de recursos como "preciso ter"; e que o cliente não aceita
uma jornada em etapas. **Para a base:** confirma que a IA não deve anunciar a
escada BPO Financeiro → BPO Plus → CFO as a Service (P6). É hipótese da
Descoberta do Cliente em curso, não decisão.

**5. O que a equipe disse ao lead, e a IA não pode repetir.** Na primeira
conversa com um potencial cliente, a Critério apresentou a escada do BPO
Financeiro em três etapas e citou casos com nome de clientes e valores. Na
reunião, com sócios, faz sentido; dito pela IA, cairia em P6 (fronteiras em
validação) e P9 (nome de cliente). Nenhuma ficha deve levar esse conteúdo.

**Fichas propostas a partir das entrevistas** (texto para colar na tela):

- **O2 · "Estou trocando de sistema"** (Objeções). O que a IA pode dizer:
  "A troca de sistema muda o que a contabilidade precisa receber, então vale
  conversar antes, para nada ser feito duas vezes. Posso marcar uma conversa
  com a equipe para entender o seu calendário?"
- **O3 · "Quem vai fazer o dia a dia?"** (Objeções). Texto de Eduardo
  (04/10/2026), condensado no padrão do modelo de ficha e aprovado.
- **O4 · "Quanto tempo leva?"** (Objeções). Usa a frase da P4: "Isso entra na
  proposta, depois do levantamento."
- **Q2 · A dor que a IA reconhece** (Qualificação). O que a IA pode dizer:
  "Muitas vezes a contabilidade cuida só das obrigações com o fisco e não
  ajuda na gestão. É isso que acontece com vocês?" Como o lead fala: "minha
  contabilidade não me ajuda na gestão", "faço tudo em planilha", "o
  financeiro e a contabilidade não conversam".

## 8. A Matriz de Objeções, lida em 04/10/2026

Lida do SharePoint, só leitura: 17 objeções. Nenhuma resposta, análise ou
texto acordado foi copiado para cá; abaixo só o tema, o tipo, o status de
precedente e o destino na base.

**Só a objeção com precedente "sim" (posição estável da casa) pode virar
ficha para a IA.** "A validar", "não", "depende" e qualquer item na faixa
ESCALAR ficam com a equipe. **[proposta]**

| ID | Tema | Tipo | Precedente | Destino na base |
|---|---|---|---|---|
| OBJ-011 | Preço fechado antes da volumetria | Preço | sim | **Ficha O1** |
| OBJ-012 | Garantia de resultado ou economia | Escopo | sim (inegociável) | **Ficha O7** |
| OBJ-010 | Escopo aberto, "qualquer demanda" | Escopo | sim | **Ficha O9** |
| OBJ-008 | Proibição de terceiros, nuvem ou IA | Cláusula | não (escalar) | **Ficha O8, só transbordo** |
| OBJ-013 | Suporte até a implantação completa | Escopo | sim | Equipe: é conversa de proposta de consultoria |
| OBJ-014 | Fatos novos sem mudar preço e prazo | Escopo | sim | Equipe: acontece com o projeto em curso |
| OBJ-009 | Prazo de comunicação de incidente | LGPD | sim | Equipe: negociação de contrato |
| OBJ-016 | Uso irrestrito do relatório | Cláusula | sim (escalar) | Equipe |
| OBJ-017 | Encarregado de dados formal | LGPD | sim | Equipe |
| OBJ-001 | Suspensão por inadimplência | Cláusula | a validar | Equipe |
| OBJ-002 | Exclusão de fiscalizações do escopo | Cláusula | a validar | Equipe |
| OBJ-004 | Limitação de responsabilidade | Cláusula | a validar | Equipe |
| OBJ-005 | Responsabilidade em incidente de dados | LGPD | a validar | Equipe |
| OBJ-003 | Controle de prazos e domicílio eletrônico | Cláusula | não (ponto em aberto) | Equipe; sempre escalar |
| OBJ-007 | Cláusula de dados só declaratória | LGPD | não | Equipe |
| OBJ-006 | Teto de responsabilidade para cliente grande | Cláusula | depende | Equipe |
| OBJ-015 | Multa em acordo de confidencialidade | Multa | depende | Equipe |

**Novo gatilho de transbordo proposto: T12 · Objeção de contrato, dados ou
multa.** Se o lead levanta cláusula contratual, LGPD, multa, responsabilidade
ou uso de tecnologia, a IA não discute: "Esse ponto é tratado pela nossa
equipe na proposta. Vou passar para eles." Destino: Sócios · conta grande.
**[proposta]**

**Textos propostos** (para colar na tela; todos passam pela trava de preço):

- **O1 · Preço antes do levantamento** (OBJ-011). O que a IA pode dizer: "O
  valor depende do volume da sua operação. Por isso a nossa equipe começa
  entendendo a sua rotina, e a proposta vem depois. Posso passar o seu
  contato?" Nunca diz: faixa, valor de diagnóstico ou qualquer número.
- **O7 · Garantia de resultado** (OBJ-012). O que a IA pode dizer: "Cuidamos
  da análise, da estruturação e do acompanhamento com rigor técnico, mas o
  resultado também depende de decisões de órgãos e autoridades. Por isso não
  prometemos o desfecho." Se o lead insiste: transbordo (T4).
- **O8 · Uso de inteligência artificial** (OBJ-008). A IA confirma o que já
  disse na apresentação, que é uma assistente virtual, e passa a conversa
  para a equipe (T12). **Atenção:** esta é a objeção mais provável de
  aparecer, porque quem conversa com o lead é uma IA.
- **O9 · Escopo aberto** (OBJ-010). O que a IA pode dizer: "Cada contratação
  tem um escopo definido, para garantir qualidade e prazo. O que ficar fora
  dele vira uma proposta complementar." Se o lead quer detalhar: transbordo.

**O que a Matriz não cobre.** As objeções do começo da conversa que as
entrevistas mostraram (O2 troca de sistema, O3 quem executa) **não estão na
Matriz**. Vale acrescentá-las a ela, para a Matriz continuar sendo a base
viva das objeções da casa. **[proposta]**

---

## Decisões, pendências e próximos passos

**Para aprovar (Eduardo e Bruno):**

- [ ] A conclusão da seção 1: da Matriz, só objeções de topo na IA.
- [ ] Os donos sugeridos na seção 2.
- [ ] A lista do que nunca entra (seção 3).
- [ ] As cinco primeiras objeções de topo (seção 4).
- [ ] Os textos de C1, C2 e C3 e os três pontos da seção 6.
- [ ] As objeções revistas (seção 4) e as fichas O2, O4 e Q2 (seção 7).
- [x] O que a Critério pode prometer sobre quem executa o dia a dia (O3).
  Decidido em 04/10/2026.
- [ ] A regra da seção 8 (só precedente "sim" vira ficha), os textos O1, O7,
  O8 e O9 e o gatilho T12.
- [ ] Acrescentar O2 e O3 à Matriz de Objeções.

**Pendências:**

- Como é o atendimento fora do Rio: a distância, presencial ou os dois? (F2)
- Ampliar a amostra do Granola: compartilhar as notas da Karine com a conta
  de Eduardo, ou avaliar o plano pago para ler as conversas anteriores a
  04/09/2026.
- Quem recebe as permissões `sdr.base` e `sdr.base_aprovar` na tela.
- O texto da base legal do lead frio (F10).

**Próximos passos:** aprovar este inventário; executar as ordens 1 a 5; depois,
o passo 3 (modelo de ficha) e o passo 5 (conjunto de perguntas-teste).

**Decidido em 04/10/2026** (Eduardo, no chat e na tela):

- A Critério atende fora do Rio: fichas F1 e F2.
- O texto da O3 (quem executa o dia a dia).
- A P1 oferece o questionário e mantém a palavra "volumetria": "…depois de
  entender a sua volumetria pelo nosso questionário. Posso te enviar o
  questionário?"
- Fichas aprovadas na tela, entre as propostas deste inventário: C1, C3, F1,
  F2, O1 a O7, O9, O10 e Q2, além dos 12 serviços (S01 a S12).
- Ficam abertos: os números de resultado e o "terceirizamos" da apresentação
  (seção 6); a regra do precedente "sim" e o gatilho T12 como regra escrita
  (seção 8); acrescentar O2 e O3 à Matriz de Objeções.

**Decidido em 04/10/2026, à tarde** (respostas de Eduardo às decisões abertas):

| Decisão | Resposta | Onde ficou |
|---|---|---|
| Números de resultado da apresentação | **A IA não cita** | Ficha C1 ("nunca diz") |
| Gatilho T12 (contrato, dados, multa, tecnologia) | **Oficial** | Ficha T12, nova |
| Origem do contato (T10) | Sempre a origem real e registrada, nunca resposta genérica, sempre com a opção de sair; texto de Eduardo para indicação e para tráfego pago | Ficha T10 |
| Atendimento fora do Rio | **Sempre por videoconferência** | Ficha F2 |
| Duração e formato da conversa com a equipe | **30 a 40 minutos, por videoconferência** | Ficha Q6 (convite) |
| Permissões da base para a Karine | Ela já é Administradora: edita e aprova | Nada a mudar |
| Acrescentar O2 e O3 à Matriz de Objeções | **Sim** | Matriz no SharePoint **[pendência: quem edita]** |
| "Terceirizamos" e local da apresentação | Eduardo ajusta a apresentação | Fora do CRM |

**Decidido em seguida, no mesmo dia:**

| Decisão | Resposta | Onde ficou |
|---|---|---|
| Regra do precedente "sim" | **Oficial**: a IA só responde sozinha às objeções da Matriz com posição "sim"; as demais passam para a equipe | Seção 8; fichas O1, O7 e O9 |
| S06 (Representante Legal) | **A pergunta passa para os sócios** | Ficha S06 |
| Origem do lead (T10), inclusive prospecção ativa | **A origem tem de ser registrada na entrada do lead no funil**; a IA informa a origem registrada | Ficha T10 (caso da prospecção ativa acrescentado); mudança no CRM **[pendência: amostra]** |

**Seguem abertos:** tornar a origem obrigatória na entrada do lead (mudança
no CRM, com amostra antes); quem acrescenta O2 e O3 à Matriz de Objeções; e a
aprovação formal dos documentos dos passos 1, 2, 3 e 5 e do roteiro SPIN.

**A revalidar:** se os motivos de descarte do CRM continuam sendo a melhor
amostra das objeções de topo depois dos primeiros 60 dias ou 300 leads, na
mesma revisão das metas do SDR.
