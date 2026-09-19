# Critério CRM — Anexo Técnico de Encaminhamento

> **Este anexo é de uso interno da equipe técnica e não precisa ser lido ou aprovado pelo cliente.**
> Versão 2.5 · 19/09/2026 · espelha o `documento-de-negocio.md` da mesma pasta.
> **Mudou da 2.4:** recebida a **Matriz de Objeções** (17 registros, 18 campos) — seção (b2.6). Entra como base viva, com separação entre catálogo e ocorrência. Tensão identificada entre a matriz e o MP-SC-01 sobre absorção de esforço extra.
> **Mudou da 2.3:** adotados os **12 KPIs oficiais** (`KPI de Head de Novos Negócios`) — seção (b2.5). Decididos: cadência de reunião por classe, quem atribui as notas humanas do Score, e a entrada de KYC, PRA e dashboard contábil. Quatro entidades novas exigidas pelos KPIs.
> **Mudou da 2.2:** recebidos o **Macroprocesso Comercial & Sucesso do Cliente** e o deck **Classificação da Carteira por Grupo Econômico** — seção (b2.4). Duas consequências: a **unidade de cliente vira o grupo econômico** e entra um **terceiro módulo, Carteira e CS**. Perfis de acesso resolvidos pelas três visões do deck.
> **Mudou da 2.1:** confirmado que **BPO Financeiro e consultoria têm processos próprios** — três processos, um desenhado. Lacunas do MP-SC-01 na seção (b2.3); implicação de desenho na (b2.2).
> **Mudou da 2.0:** recebido o fluxo **MP-SC-01 Implantação de Cliente, Rev.02** (rascunho não aprovado) — mapeado na seção (b2.1). Responde "o que é cliente operando" e revela o conceito de **horas de conforto**.
> **Mudou da 1.5 — 34 respostas de Eduardo.** Mudança de escopo: **o CRM acompanha a implantação**, não apenas entrega o pacote. Decidido: Clicksign; login por conta corporativa Microsoft; ambientes separados; backup automático; nuvem já reservada; Granola puxado automaticamente, só resumo, template "[Potencial Cliente]"; Karine administradora; histórico de preços guardado; vigência controlada; Bruno Oliveira assina; implantação por área. Questionário de volumetria lido. Fases a rediscutir. Risco LGPD aceito pelo cliente.
> **Mudou da 1.4:** integração com a planilha de precificação **adiada por decisão de Eduardo**; **porte da empresa vira campo do CRM**; confirmado que **o elo questionário → precificação não existe hoje**. A precificação sai dos bloqueadores de PF-04.
> **Mudou da 1.3:** planilhas de precificação lidas no SharePoint. O modelo de preço está descrito na seção (b1) e os defeitos encontrados na (b2).
> **Mudou da 1.2:** infraestrutura em **nuvem**; **existe planilha de precificação** (cálculo automático adiado para fase seguinte); **Eduardo é o aprovador**; entrou o bloco de lacunas de construção.
> **Mudou da 1.1:** a entrevista passou a alimentar **precificação** e **onboarding técnico**; o uso do Granola deixou de ser suposição (6 notas conferidas); entrou o mapa de campos da seção (c); fases refeitas.
> *Histórico: 1.0 → 1.1 acrescentou contrato, assinatura digital e Granola.*
> Nenhuma decisão de arquitetura, modelo de dados ou backlog foi tomada aqui.

---

## (a) Resumo estruturado

### Necessidade principal

CRM próprio da Critério, substituindo a planilha "Relatório Performance Comercial 2026" e cobrindo o ciclo do cliente da primeira conversa até estar operando: entrevista puxada do Granola → ficha de volumetria (questionário oficial) → porte e precificação registrados → funil → proposta → contrato assinado no Clicksign → **implantação acompanhada por responsável de área** → vigência → follow-up → KPIs → listas para campanha.

**O eixo.** A entrevista é a fonte primária de dados de todo o ciclo. Hoje ela produz texto estruturado que é lido e redigitado em cada etapa. O CRM transforma esse texto em campo, e o campo viaja até a implantação.

### Necessidades secundárias

| Item | Situação |
|---|---|
| Cálculo automático de preço | **Existe planilha de precificação**, oficial identificada. Fase 1 só registra; tradução em regra fica para depois |
| Roteiro "Descoberta do Cliente" no CRM | **FORA** — decidido por Eduardo |
| Acompanhamento da implantação pós-venda | **DENTRO** — decidido por Eduardo em 19/09/2026. Reverte a recomendação anterior. Ver "Impacto da mudança de escopo" |
| Canais novos: tráfego pago e afiliados | Desejo, sem operação hoje. Fase 3 |
| Envio de campanhas pelo CRM | Futuro |
| Contratos de parceria comercial (finder fee) | Natureza distinta. Entrada a confirmar |
| Vigência e renovação de contrato | A confirmar |
| Painéis de performance | Hipótese |
| Comissionamento | Sem regra, fora do escopo |

### Impacto da mudança de escopo (19/09/2026)

O CRM deixa de terminar na assinatura e passa a acompanhar a implantação. Justificativa dada por Eduardo: o chapéu dele é comercial **e** Customer Success.

**O que isso acrescenta ao produto**

| Item | Consequência técnica |
|---|---|
| Entidade nova: **implantação**, ligada ao contrato | Etapas, responsável, prazo, situação, marco de conclusão |
| **Três responsáveis e três processos distintos** — Bruno Soares (contábil/fiscal/DP, MP-SC-01 em rascunho), Jefferson Souza (BPO Financeiro, sem processo), Jefferson Cruz (consultoria, sem processo) | Etapas e critérios **configuráveis por serviço**, nunca fixos no código. Ver (b2.2) |
| **Não existe checklist de implantação** | Pendência do próprio fluxo MP-SC-01, não do CRM. Bloqueia esta parte, não o resto |
| **Vigência e renovação** controladas | Datas derivadas do marco "Operação", não da assinatura |
| Usuários do CRM deixam de ser só comercial | Modelo de permissão precisa separar Comercial, Implantação, Times Operacionais e CS |
| **Saldo de horas de conforto** | Conceito trazido pelo MP-SC-01. Débito por absorção de desvio. Política não formalizada |

**Risco a monitorar:** o limite entre "acompanhar a implantação" e "gerir a operação do cliente" é tênue. O fluxo ajuda: o marco `End_Operacao` diz onde a implantação termina — "cliente estabilizado, sai da implantação e entra na operação recorrente". O CRM para nesse ponto.

**Segundo risco:** o fluxo separa Comercial e CS em raias com RACI distinto (CS conduz e decide a absorção; Comercial é consultado quando há impacto contratual). Hoje Eduardo acumula os dois papéis. O CRM deve registrar **em qual papel** cada decisão foi tomada, para que a segregação sobreviva quando outra pessoa assumir uma das pontas.

### Escopo por fase (**a rediscutir — Eduardo não considerou a lógica clara**)

Reformulada por resultado, e não por dependência técnica — a versão anterior não ficou clara para Eduardo. Detalhe na seção 18 do documento de negócio.

1. **Sair da planilha** — leads, origem, ficha de volumetria, porte, precificação registrada, lista de pendências, propostas, funil, KPIs, carga de 2026.
2. **Fechar o ciclo** — emissão de contrato, Clicksign, vigência, follow-up e lembretes; **implantação acompanhada, condicionada à aprovação do MP-SC-01**.
3. **Tirar trabalho manual** — Granola automático, listas de campanha, canais novos, cálculo de preço.

*Critério da divisão: cada etapa entrega algo usável sozinho. Aguarda decisão de Eduardo.*

> **Dependência externa nova:** a parte de implantação da etapa 2 depende de três coisas que **não estão no controle do projeto**: aprovação do MP-SC-01, criação do checklist e da política de horas de conforto, e o desenho dos processos de BPO Financeiro e consultoria — que ainda não existem. Contrato, assinatura, vigência e follow-up **não** dependem disso e podem seguir.

### Restrições firmes

| Restrição | Detalhe |
|---|---|
| Stack | PostgreSQL, Python, React |
| Infraestrutura | **Nuvem já reservada** para esta aplicação. Provedor e **região do servidor** pendentes — a região define onde ficam dados de clientes |
| Ambientes | **Separados**: teste e produção |
| Backup | **Automático**, nunca dependente de pessoa — exigência explícita de Eduardo |
| Autenticação | **Conta corporativa Microsoft** (`@grupocriterio.com.br`), sem senha própria do CRM |
| Perfis | Karine **administradora**; Eduardo aprovador; demais com **alçada restrita** (regra pendente); responsáveis de implantação como perfil novo |
| Assinatura digital | **Clicksign**. Signatário pela Critério: **Bruno Oliveira** |
| Granola | **Puxar automaticamente**, **só o resumo**, template **"[Potencial Cliente]"** |
| Aprovação | **Eduardo** valida requisitos, telas e entregas. Satisfaz a regra de que quem constrói não aprova |
| Precificação | Etapa 1 registra porte, direcionadores e preço, **guardando os dois valores quando há reajuste** (medir desconto). Cálculo automático na etapa 3. **Planilhas lidas em 19/09/2026** — modelo na (b0), defeitos na (b1.1). Nenhuma fórmula é traduzida antes de decisão humana. **Preço de tabela é o praticado, sujeito a desconto em negociação** |
| Dados de precificação | Tabela de preço/hora, custo por profissional e margem **não são copiados** para este workspace. Fonte é o SharePoint |
| Design das telas | PAD-002 — `vault/06-Padroes/PAD-002 - Design Criterio CRM.md`. **Status `proposto`, aprovação pendente.** Fonte da verdade é o artefato |
| Design de proposta e contrato | Manual da marca. Logomarca sozinha |
| Integrações | E-mail, WhatsApp Business, Granola, assinatura digital. **Sem Omie** |
| Fronteira — implantação | CRM **acompanha** etapas, responsável e prazo **até o cliente operar**. Não gere a rotina recorrente do cliente depois disso |
| Fronteira — precificação | CRM guarda direcionadores e registra preço com justificativa. **IA não define preço** |
| Fora do escopo | Campanhas enviadas pelo CRM; dados 2023–2025; comissionamento; roteiro da Descoberta do Cliente; gestão da operação recorrente do cliente |
| LGPD — **risco aceito pelo cliente** | Eduardo decidiu **não submeter ao jurídico** a base legal para contatar lead perdido nem a guarda das transcrições. Hoje **não se pede autorização de gravação** das entrevistas, e ele reconhece que deveria. O CRM implementa marcador "não contatar" e controle de acesso — medidas técnicas, não parecer jurídico. Registrado em 19/09/2026; não é recomendação da equipe |

### Perfil dos dados de origem (`Propostas`, Ano = 2026)

Levantado em 19/09/2026 sobre `~/Downloads/03.Relatório Performance Comercial 2026 (1).xlsx` (18/09, 14:57; existe outra de 14:39 não usada). 154 linhas.

| Coluna | Achado | Consequência |
|---|---|---|
| Empresa | Vazia em 149 de 154 | **Confirmado: falta preencher.** Campo próprio no CRM, a completar depois da carga |
| Data do aceite | Vazia nas 40 aceitas | **Confirmado: Eduardo preencherá no CRM.** Campo obrigatório para situação "Aceita", mas a carga entra sem ele |
| Preço mensal | Vazio em 92 | **Confirmado: foi intencional, e não se repete no CRM.** Carga preserva o vazio; novo registro exige preço |
| Responsável "AN" | Só no histórico total, não em 2026 | **Confirmado: converter "AN" para "BO" na carga** |
| Status | 6 valores, "Enviar proposta" e "Enviar Proposta" | Normalizar |
| Tipo Canal | "Socio" (77) e "Sócios" (9); 7 valores | Normalizar |
| Temperatura | Frio 93, Quente 52, Morno 8, e um "Captação de recursos" | Valor fora do domínio |
| Motivo da Recusa | Texto livre; mistura motivo e situação. Inclui "Proposta reajustada" | Lista controlada + observação. "Proposta reajustada" indica necessidade de histórico de preço |
| Contrato Assinado | "Sim", "sim", "Nao", "1", texto livre | Embrião do módulo de contrato; mistura situação, canal de aprovação e observação |
| Responsável (C1/C2) | C2 79, C1 75 | Linha de serviço, não pessoa |
| Responsável (iniciais) | BO 57, EL 53, TC 17, FS 11, JC 7, MO 6, JS 3 | Captadores. "AN" só no histórico total |
| Canal | 33 distintos | Virar cadastro |
| Serviço | BPO Contábil 68, Consultoria 60, Legalização 14, BPO Financeiro 7, Auditoria 3, Representação 1, Endereço fiscal 1 | **BPO Plus, CFO as a Service e FSCP não aparecem** |

> A planilha **não tem nenhum direcionador de preço**: só o valor final. É a lacuna que a ficha de volumetria preenche.

### Evidência sobre o Granola (19/09/2026)

Conector do Granola consultado nesta sessão. Janela disponível: 21/08 a 18/09/2026, 39 reuniões. Nenhuma nota foi copiada para o repositório.

- **6 notas** com o roteiro de diagnóstico comercial, todas abertas e conferidas uma a uma.
- **3 notas** com o roteiro da Descoberta do Cliente (estrutura distinta: earlyvangelist, hipóteses validadas e invalidadas, aderência às categorias).
- **1 das 6** teve o template aplicado a uma reunião que não era de diagnóstico; a própria nota registra a divergência. Sinal de que a escolha de template é manual e falha — o CRM deve tolerar isso.
- **Limitações do conector:** o nome do template **não é exposto pela API** (identificação foi por estrutura de seções); pastas exigem plano pago; a janela é de 30 dias.
- **A primeira busca em linguagem natural devolveu lista incorreta** (2 de 6 corretas). A lista final veio de leitura direta das notas.

### Pontos de atenção para a equipe

1. **A nota da entrevista é semiestruturada, não estruturada.** Seções fixas, conteúdo em prosa, com marcadores de autoria ("CLIENTE DISSE", "CRITÉRIO DISSE", "INTERPRETAÇÃO") e o literal "Não identificado na reunião". A extração precisa preservar essa distinção: o que é fala do cliente vira dado candidato; o que é interpretação vira sugestão. **Nunca colapsar os dois.**
2. **Volumetria vem de duas fontes** — a entrevista (parcial) e o questionário enviado depois (completo). O CRM precisa saber de onde cada número veio e quando.
3. **Catálogo de produtos ≠ dados históricos.** BPO Plus, CFO as a Service e FSCP não aparecem na planilha. As fronteiras entre BPO Financeiro, BPO Plus e CFO as a Service são **hipótese em validação** na Critério; não congelar em regra de sistema.
4. **Três tipos de documento:** apresentação (BPO, FSCP), carta de consultoria, contrato. Mais os contratos de parceria, de outra natureza.
5. **Assinatura digital** é integração com custo e efeito jurídico. Levantar antes: valor jurídico, trilha, ICP-Brasil, custo por envelope, webhook de retorno.
6. **Granola** — na Fase 1, resumo colado à mão. A integração automática da Fase 3 depende de acesso programático, retenção e propriedade do dado.
7. **WhatsApp Business** exige provedor oficial e modelos aprovados.
8. **PAD-002 sem aprovação.** Tela antes do aceite é retrabalho provável.
9. **Guarda de documento assinado e de nota de entrevista** exige controle de acesso e trilha. Fica neste workspace, **nunca** em `vault/09-Conhecimento/`.
10. **Segredos** (banco, e-mail, WhatsApp, assinatura, Granola) só em `.env` ou cofre.

### Pontos a confirmar

Estão na seção 19 do documento, em dois grupos.

**Travam o código (bloco A, novos):** quem constrói e mantém · forma de autenticação · separação de ambientes · responsabilidade de backup · estratégia de virada da planilha · provedor, custo e região da nuvem · prazo e orçamento.

**Atualizado em 19/09/2026 — a maioria foi respondida.** O que resta:

- **Regra de alçada** dos usuários que não são Eduardo nem Karine, e se os responsáveis de implantação veem o comercial.
- **Checklist de implantação** — conteúdo inexistente; um por serviço ou um só.
- **Marco de "cliente operando"** — o que precisa estar pronto para fechar a implantação.
- **Ordem das etapas** — Eduardo não considerou a lógica das fases clara; reexplicada na seção 18 do documento, aguarda decisão.
- **KPIs e critérios de sucesso** — propostos na seção 12; aguardam validação.
- **Região do servidor e provedor** da nuvem já reservada.
- **Estratégia de virada** — a resposta "sim" ficou ambígua entre paralelo e corte seco.
- **Prazo e orçamento.**
- **Modelos de contrato** — link fornecido é do Outlook e não abre pelo conector; pedir caminho no SharePoint.

**Adiado por decisão:** integração com a planilha de precificação e tudo que depende dela.

### Nível de confiança

**Médio.** A base factual melhorou de novo: a planilha de precificação existe, a infraestrutura está definida e o aprovador está nomeado. Mas duas lacunas seguem estruturais: **a planilha de precificação não foi recebida** (sem ela não se sabe quais campos guardar) e **não se sabe como a área técnica recebe o cliente hoje**. Somam-se as sete lacunas de construção do bloco A, que ninguém havia levantado antes desta rodada.

---

## (b) Mapa de campos derivado do roteiro de entrevista

Derivado **da estrutura** das 6 notas conferidas. **Nenhum valor de cliente foi copiado** — só nomes de campo. Serve de ponto de partida para a modelagem em PF-04, não é modelo de dados aprovado.

### B.0 — Modelo de precificação (lido no SharePoint em 19/09/2026)

**Fontes.** `Planilha de Precificação.xlsx` — site Comercial, `General/01. Ponto de Partida/01_Modelos Comercial/01. Proposta/`, com cópia idêntica em `07. Kit Contábil/#01 - Diagnóstico & Checklist/`. E `Tabela de precificação de consultoria e auditoria 1.xlsx` — OneDrive de Eduardo, arquivos de chat do Teams.

> **Valores não replicados aqui.** Tabela de preço por hora, custo mensal por profissional e margem ficam no SharePoint. Este anexo guarda **a lógica e os direcionadores**, que é o que a modelagem precisa. Ao codificar, ler da fonte.

**Núcleo comum**

```
preço_bruto = Σ (horas_totais × alocação_perfil × preço_hora_perfil × (1 − desconto)) ÷ (1 − imposto)
margem_perfil = (preço_hora_c/desconto × (1 − imposto) − custo_hora_perfil) ÷ preço_hora_c/desconto
custo_hora    = custo_mensal_perfil ÷ 160
```

Seis perfis: Sócio Sênior, Sócio Júnior/Gerente, Supervisor/Especialista, Analista Sênior, Analista Pleno, Analista Júnior. Imposto parametrizado em 11%. Margem total é a média ponderada pela alocação.

**Caminho A — BPO contábil, fiscal e DP (por porte)**

- Entrada: **porte** (Micro, Pequeno, Médio, Grande, Extra Grande).
- Uma matriz guarda, por porte: horas/mês totais e o mix percentual dos seis perfis. O mix é puxado por `XLOOKUP` sobre o porte.
- Trava de consistência na própria planilha: a soma do mix precisa fechar 100%.
- **A regra que define o porte não existe na planilha.** É o elo faltante entre a ficha de volumetria e o preço.

**Caminho B — BPO Financeiro, BPO Plus e CFO as a Service (por faixa de volumetria)**

- Entrada: **três direcionadores explícitos** — documentos por mês, contas bancárias, conciliações de cartão de crédito.
- Três faixas: duas com preço de tabela por produto e a terceira "sob consulta".
- Cada produto tem carga horária semanal própria (mensal = semanal × 4) e mix fixo de três perfis (Analista Sênior, Sócio Júnior/Gerente, Sócio Sênior).
- O escopo de cada produto está listado por serviço, o que também serve de base para o contrato.
- **Este é o único caminho em que volumetria chega a preço sem intermediário.** É o modelo mais maduro, e cobre o produto prioritário.

**O que o CRM precisa guardar por oportunidade**

Porte ou faixa · horas contratadas · alocação por perfil · desconto aplicado · imposto vigente · versão da tabela de preço e de custo · preço líquido, preço bruto e margem resultante.

### B.1 — Direcionadores de preço (ficha de volumetria)

Confirmados nas planilhas (caminho B) e observados no questionário preenchido e nas seções de estrutura das notas:

| Grupo | Campos |
|---|---|
| Identificação | Razão social · CNPJ principal · CNPJs no escopo · filiais · localidades (municípios e UFs) |
| **Porte** | **Porte atribuído (Micro, Pequeno, Médio, Grande, Extra Grande) · quem atribuiu · quando** — campo humano, não derivado |
| Perfil | Faturamento anual ou mensal · regime tributário · segmento |
| Volume fiscal | NFs emitidas por mês · NFs recebidas por mês · tipos de operação (serviço, mercadoria, interestadual, exterior) |
| Volume financeiro | Pagamentos por mês · contas bancárias · lançamentos contábeis por mês |
| Volume de pessoal | Empregados CLT · PJs e estagiários · admissões e desligamentos por mês · sindicatos e CCTs · benefícios · tomadores de serviço |
| Complexidade | Consolidação de holding · centros de custo e rateios · plano de contas · auditoria externa · passivo tributário e parcelamentos · obrigações acessórias em aberto |
| Serviço | Escopo desejado (contábil, fiscal, DP, financeiro, consultoria) · prazo de fechamento esperado · SLAs |
| Procedência | Origem de cada número (entrevista ou questionário) · data · quem informou |

**Situação (atualizada em 19/09/2026).** Para BPO Financeiro, Plus e CFO, os direcionadores estão confirmados: documentos/mês, contas bancárias e conciliações de cartão. Para BPO contábil, fiscal e DP, **a regra que converte volumetria em porte não existe** — confirmado por Eduardo, não é inferência.

**Consequência para a modelagem.** O campo `porte` é preenchido por pessoa, não derivado. A oportunidade guarda **porte escolhido + volumetria que o sustentou + quem escolheu + quando**. Os pares acumulados são o que permite, mais adiante, derivar a regra a partir do histórico real em vez de inventá-la. Isso só funciona se o campo existir desde a Fase 1 — daí a decisão de mantê-lo mesmo com o cálculo adiado.

### B.1.1 — Defeitos e divergências encontrados nas planilhas

Achados de leitura direta, em 19/09/2026. Não são opinião sobre o modelo: são inconsistências internas. Nenhuma regra de preço deve ser codificada antes de uma pessoa decidir sobre cada uma.

| # | Achado | Efeito |
|---|---|---|
| 1 | **A coluna "Horas/mês (TOTAL)" da matriz de porte não é referenciada por nenhuma fórmula.** As horas vêm de uma célula digitada à mão; só o mix é puxado por `XLOOKUP` | No arquivo salvo, um cliente de porte Grande está precificado com **quatro vezes** as horas que a matriz prevê para esse porte. Risco concreto de erro de preço |
| 2 | **Custos de equipe divergem entre as duas planilhas.** No cálculo de margem do BPO Financeiro, três perfis usam custo mensal diferente do que consta na tabela de custos da Planilha de Precificação, e dois deles aparecem invertidos entre si | A margem reportada muda conforme a planilha usada |
| 3 | **Preço de tabela × preço calculado não reconciliam no BPO Financeiro.** A faixa maior fica próxima do valor que o modelo de horas calcula; a faixa menor fica bem abaixo. Não há fórmula ligando as duas coisas | Pode ser desconto intencional por volume menor, ou defasagem. Pergunta 4 |
| 4 | **A aba de consultoria está incompleta.** Sem porte, sem horas, mix zerado, hora média em `#DIV/0!`. Quatro das seis linhas perderam a fórmula que calcula o tempo a partir da alocação | Se alguém preencher a alocação nessas linhas, o tempo não calcula e o preço sai errado, **sem aviso** |
| 5 | **A célula de desconto está em posições diferentes** nas abas de BPO e de consultoria | Sinal de que a aba de consultoria é cópia adaptada e não acompanhou revisões |
| 6 | **Resíduo de caso específico** na aba de BPO: um bloco de rateio entre duas frentes, com divisão por cinco anos, fora do modelo genérico | Provavelmente sobra de um cliente. Confirmar antes de traduzir |
| 7 | **Custos fixos por cliente embutidos direto na fórmula** de margem, em vez de parametrizados | Mudar esses valores exige editar fórmula |
| 8 | **Uma cópia da planilha por proposta.** Encontradas cópias por cliente em pastas de proposta e de cliente; num caso, três cópias do mesmo cliente com horas diferentes, em pastas diferentes | Não há como saber qual versão sustentou a proposta enviada. **É o argumento mais forte para o módulo de precificação do CRM** |

**Consequência para a Fase 1:** o CRM registra porte, direcionadores e preço, mas **não traduz nenhuma fórmula**. A integração com a planilha foi **adiada por decisão de Eduardo em 19/09/2026**, e os itens 1 a 7 acima passam a ser pré-requisito dessa fase futura, não da Fase 1.

**Fora do CRM, mas urgente:** os itens 1 e 4 são risco de precificar errado **hoje**, na planilha em uso. Independem deste projeto.

### B.1.2 — Questionário oficial de volumetria

`Questionario_BPO_Full_2026_v2.docx` — SharePoint, site Comercial, `01_Modelos Comercial/01. Proposta/`. Lido em 19/09/2026. **É a ficha de volumetria do CRM, praticamente pronta.** Oito seções:

1. **Empresa, escopo e responsáveis** — razão social, CNPJ principal, nome fantasia, atividade, faturamento anual, regime tributário, CNPJs no escopo, filiais, contato, serviços no escopo (contábil/fiscal/folha/financeiro), operação atual (interna/terceirizada/mista), fornecedor atual e aviso prévio, equipe interna dedicada, **valor mensal pago ao fornecedor atual**.
2. **Sistemas, dados e integrações** — por processo (ERP/financeiro, contábil/fiscal, folha/eSocial, ponto/RH): sistema atual e forma de troca (API, arquivo, manual). Mais migrações em curso.
3. **Volumes mensais para dimensionamento** — notas emitidas, notas recebidas, lançamentos contábeis, pagamentos, contas bancárias, conciliações, empregados CLT, PJs, admissões, desligamentos, CNPJs/filiais, tomadores de serviço.
4. **Contábil e gerencial** — prazo de fechamento, plano de contas, rateio de folha, relatórios, auditoria.
5. **Fiscal e obrigações** — tributos, municípios/UFs, exterior, certidões, passivos e parcelamentos.
6. **Folha e DP** — distribuição por UF, sindicatos e CCTs, corte do ponto, eventos variáveis, sistema de ponto, exigências de tomadores, pendências de eSocial/SST.
7. **Financeiro** — escopo, alçadas, bancos, relatórios, inadimplência, volumes de boleto e cobrança.
8. **Dores, expectativas, transição e decisão** — erros dos últimos 12 meses, o que o parceiro deve antecipar, três critérios de sucesso, SLAs, decisor e influenciadores, **ponto focal da implantação**, documentos disponíveis.

**Observações para a modelagem**

- A seção 3 é exatamente o conjunto de direcionadores que a B.1 previa. **Confirmado, não inferido.**
- A seção 2 é o retrato de sistemas que o pacote de implantação precisa — o mesmo dado serve às duas etapas.
- A seção 8 já pede o **ponto focal da implantação**: o questionário comercial **já antecipa o handoff**, o que reforça a decisão de manter os dois no mesmo sistema.
- O campo "valor mensal pago ao fornecedor atual" é referência de preço, e não aparece em lugar nenhum da planilha de performance.
- Vários campos são caixas de seleção com opções fixas: viram listas controladas, não texto livre.

### B.2 — Pacote e acompanhamento de implantação

Observado nas seções de sistemas, processos e riscos das entrevistas, e na seção 8 do questionário:

| Grupo | Campos |
|---|---|
| Sistemas do cliente | ERP · sistema fiscal · folha e eSocial · ponto e RH · plataformas de recebimento · BI |
| Integrações | O que integra · o que não integra · o que é manual · consequência de cada lacuna |
| Processos | Plano de contas · centros de custo e projetos · rateios · conciliações · consolidação · controles paralelos em planilha |
| Prazos | Data de corte · fechamento esperado · calendário de folha · entregas periódicas |
| Pessoas do cliente | Ponto focal · quem decide · quem influencia · quem usa no dia a dia · contatos |
| Riscos herdados | Passivo fiscal · obrigações não entregues · erros históricos · dependência de pessoa · sistema em troca |
| Condicionantes de início | Aviso prévio do fornecedor atual · migração de ERP em curso · reestruturação societária |
| Pendências abertas | Itens de "Informações Faltantes para Proposta" ainda não respondidos |

**Situação (19/09/2026).** Responsáveis confirmados: Bruno Soares (contábil, fiscal e DP — área nova), Jefferson Souza (BPO Financeiro), Jefferson Cruz (consultoria).

### B.2.1 — Fluxo MP-SC-01 Implantação de Cliente, Rev.02

Recebido em 19/09/2026 (BPMN + legenda, `~/Downloads/Processo_de_Onboarding_de_Clientes/`). **RASCUNHO, não controlado, sem aprovação humana.** Não foi copiado para este workspace.

**Entidades que o fluxo exige do CRM**

| Entidade | Origem no fluxo | Observação |
|---|---|---|
| **Implantação** | Start "Contrato fechado" → End "Operação" | Disparada pela assinatura; fecha após 3 ciclos de fechamento revisados |
| **Ata de handoff** | `T0_Handoff` | Anexo obrigatório do pacote. Decisões, pendências, responsáveis |
| **Pacote de handoff** | `T1_EnviarEmail` | Três anexos obrigatórios: formulário da proposta, contrato assinado, ata. **Os três já estarão no CRM** |
| **Customer Outcomes** e **jornada do cliente** | `T_CS_Outcomes` | Marcos verificáveis, indicadores e cadência. Referência por **toda a vida contratual**, não só na implantação |
| **Checklist de implantação** | `T2_AnalisarContrato`, critério do gateway `GW1` | **Não existe.** Pendência do fluxo: conteúdo mínimo por setor, dono, formato |
| **Mapa de processo e sistema** + **riscos** | `T5`, `T6` | São a **especificação**, conferida contra a operação do 1º mês |
| **Desvio de escopo** | `GW_DesvPre`, `GW_DesvPos` | Registro: desvio, tratamento, responsável, data. Duas revisões — pré e pós |
| **Saldo de horas de conforto** | `T_TratDesvPre`, `T_TratDesvPos` | Débito por absorção. **Política não formalizada** — pendência do fluxo |
| **Aditivo contratual** | mesmo par de tarefas | Liga-se ao contrato; alçada presumida, a validar |
| **Ciclo de fechamento** | `T_RevFech`, `GW_Ciclos` | Três iterações antes do marco final |
| **Alinhamento de marco com o cliente** | `T_AlinhCli` | Mensagem ao cliente; gaps, gargalos, melhorias, feedback |

**Marcos, para KPI**

- `GW1` — checklist cumprido: fecha o **pacote de implantação**.
- `End_Operacao` — **Operação**: fecha a **implantação**, após 3 ciclos. É o marco de "cliente operando".

**O que o CRM elimina do fluxo atual**

O `T1_EnviarEmail` — handoff por e-mail livre — é marcado no próprio BPMN como "candidata a gatilho estruturado". Com o CRM, os três anexos obrigatórios já estão na oportunidade, e a regra "e-mail sem pacote completo devolve ao Comercial" vira **validação de sistema** em vez de convenção. É o ganho mais direto e imediato da integração comercial-implantação.

**Loop de retroalimentação**

O fluxo determina que **todo desvio, inclusive o absorvido, volta ao Comercial** para corrigir o formulário e a qualificação das próximas propostas. Isso fecha o ciclo volumetria → preço → desvio → melhoria do questionário, e confirma a arquitetura proposta na seção B.1: acumular pares de decisão para derivar regra depois.

**Notação da legenda:** `[H]` = executado por humano; `[H→IA]` = humano hoje, candidato a apoio ou automação por IA. Cinco tarefas marcadas `[H→IA]`, sendo "Conferir processamento vs. especificação" apontada como forte candidata.

**Pendências do fluxo que o CRM não resolve**

Política de horas de conforto · checklist padrão · alçadas de aditivo e absorção (presumidas) · item "UAT" do kick-off · ponto de retorno do gateway "Não" · paralelismo dos setores assumido.

**Risco de sequenciamento:** o fluxo é rascunho. Construir a tela de implantação antes da aprovação do MP-SC-01 é retrabalho provável. A parte comercial do CRM não depende dele e pode avançar.

### B.2.2 — Três processos, um desenhado

**Confirmado por Eduardo em 19/09/2026:** BPO Financeiro e consultoria **não seguem o MP-SC-01**. São processos distintos, ainda não desenhados.

| Serviço | Responsável | Processo |
|---|---|---|
| Contábil, fiscal e DP | Bruno Soares | MP-SC-01 Rev.02 — rascunho, não aprovado |
| BPO Financeiro | Jefferson Souza | **Não existe** |
| Consultoria | Jefferson Cruz | **Não existe** |

**Implicação de desenho (para PF-08, não decidida aqui).** O módulo de implantação **não pode ser modelado em cima do MP-SC-01**. Três processos distintos, um em rascunho e dois inexistentes, exigem que etapas, responsáveis, prazos e critérios de conclusão sejam **configuráveis por serviço**, e não fixos no código. Modelar o MP-SC-01 diretamente significaria reescrever o módulo duas vezes.

### B.2.3 — Lacunas do MP-SC-01

**Admitidas pelo próprio documento (seção 5 da legenda):** checklist padrão · política de horas de conforto · alçadas de aditivo e absorção (presumidas) · item "UAT" do kick-off · ponto de retorno do gateway "Não" · paralelismo dos setores assumido.

**Identificadas na análise, não mencionadas pelo documento:**

| Lacuna | Por que trava o CRM |
|---|---|
| **Nenhuma etapa tem prazo ou SLA** | "Implantação em atraso" não tem como ser calculado. Era um dos KPIs propostos |
| **Não há caminho de exceção** | Sem implantação suspensa, parada por falta de resposta do cliente, cancelada ou distratada. Na prática, ocorre |
| **Entregas do cliente não modeladas** | Acessos, procurações, certificado digital e saldos de migração aparecem na descrição dos setores, mas o pool Cliente só troca duas mensagens. É onde a implantação costuma travar |
| **Laço dos três ciclos sem escape** | Ciclo que nunca fecha gira sem escalonamento |
| **Vigência não amarrada a marco** | Começa na assinatura ou no marco Operação? O CRM controla renovação e precisa saber |
| **Analista de Implantação é papel, não pessoa** | Quantidade e distribuição de carga indefinidas; afeta atribuição e permissão |

### B.2.4 — Carteira e Sucesso do Cliente

Recebidos em 19/09/2026: `Macroprocesso - Comercial & Sucesso do Cliente.pptx` e `Categorizado de clientes Curva ABC_Final.pptx` (25 slides), no OneDrive. **Não copiados para este workspace.**

**Mudança estrutural: a unidade é o grupo econômico.**

Este é o achado com maior impacto no modelo de dados, e não estava em nenhuma versão anterior. A carteira opera sobre **31 unidades de análise** (15 grupos + 16 independentes), consolidadas a partir de **58 CNPJs**. A regra de agregação é explícita no deck:

| Atributo | Como agrega |
|---|---|
| Receita | Soma das empresas |
| Horas e custo | Soma — sem rateio |
| Complexidade, disciplina, risco | Média ponderada por horas |
| Adimplência | **Pior caso do grupo** |

O CNPJ permanece visível dentro do grupo: é onde a empresa deficitária aparece (um caso de −53% dentro de um grupo classificado B1).

**Entidades e campos**

| Entidade | Campos |
|---|---|
| **Grupo econômico** | Nome · CNPJs vinculados · receita mensal consolidada · margem consolidada |
| **Score** | 7 quesitos com peso fixo: rentabilidade 25% · receita recorrente 20% · adimplência 15% · complexidade 12% · cross-sell 12% · disciplina 9% · risco técnico 7%. Complexidade e risco **invertidos** como `(6 − nota)`. Resultado 1–5 → letra A/B/C |
| **Semáforo** | Avaliação operacional 1/2/3 → o número da classe |
| **Classe** e **Classe Efetiva** | Ex.: `B3` e `B3 (TRAVADO)`. A trava por inadimplência **não rebaixa a classe** |
| **Alertas** | ⚠ churn (só A e B) · $$$ inadimplência (trava) |
| **Eixo de ação** | Churn × classe → `RETER JÁ` · `RETER/VIGIAR` · `SAÍDA ORGANIZADA` · `COBRANÇA` |
| **Margem calculada** | Horas-base por porte e mix → **fator de atrito** (complexidade, indisciplina, risco aumentam horas) → custo de servir (horas × custo/hora por senioridade) → `(honorário − impostos − custo) ÷ honorário` → nota 1–5 por percentil |
| **Reunião de resultado** | Grupo · data · pauta · ata · encaminhamentos · cadência devida por classe |
| **Decisão de carteira** | Reter · reprecificar · sair — com data, responsável e motivo |

**Perfis de acesso — resolvido pelo próprio deck**

Três visões sobre **a mesma classificação**, o que responde a pergunta de alçada que estava aberta:

| Perfil | Colunas |
|---|---|
| Liderança | Score · margem · trava · alertas · eixo de ação — vê tudo |
| Customer Success | Classe · classe efetiva · alertas · eixo de ação |
| Operação | Classe (só a letra) · semáforo · complexidade · disciplina · risco técnico |

> O deck é explícito: "modelo único = manutenção única; dois modelos = duas atualizações, duas chances de divergir". Isso vira regra de implementação: **uma classificação, várias projeções de leitura** — nunca duas tabelas.

**Um só motor de horas — a maior oportunidade estrutural do CRM**

A mesma fórmula aparece em três lugares que não se comunicam:

| Onde | Para quê |
|---|---|
| Tabela de Precificação | Formar o preço da proposta |
| Fluxo MP-SC-01 | Debitar horas de conforto ao absorver desvio de escopo |
| Deck da carteira | Calcular a margem e alimentar 25% do Score |

Os três usam horas por porte, mix de equipe e custo/hora por senioridade (custo mensal ÷ 160h). O deck admite: *"a Critério já sabe calcular custo: a Tabela de Precificação faz isso todo dia para clientes NOVOS. Bastou virar a lente para a carteira existente."* **Unificar esse motor no CRM é o ganho estrutural mais relevante identificado até aqui** — e reforça a decisão de guardar porte e direcionadores desde a etapa 1, mesmo com o cálculo adiado.

**Macroprocesso de reuniões**

Duas fases: **Implantação** e **Em curso**. Implantação: pontos sensíveis captados no comercial · apresentação da Critério (ferramentas, comunicação, equipe, SLAs) · carta de rescisão do contador anterior e termo de transferência · lista de documentos iniciais e mensais · entendimento do fluxo de informações · **formulário KYC**. Em curso: apresentação mensal das demonstrações (gaps, acertos, ajustes) · óbices do cliente · **mapeamento das empresas de curva A** · revisão dos KPIs de fechamento · avaliação da entrega de documentos pelo cliente · **procedimentos de revisão analítica (PRA)** · definição do **dashboard contábil** do cliente.

> ⚠️ **Limite da extração.** O deck tem caixas sobrepostas na mesma coordenada, provavelmente camadas de animação. O conteúdo foi extraído, mas **a ordem exata das etapas de "Em curso" não é inequívoca**. Confirmar antes de modelar.

**Itens novos que o macroprocesso traz:** formulário **KYC**, **PRA** e **dashboard contábil do cliente** — nenhum deles aparecia no projeto até aqui.

### B.2.6 — Matriz de Objeções

Fonte: `matriz-objecoes.csv` — SharePoint, site Comercial, `01. Ponto de Partida/09_Governança comercial - IA/03_Matriz de objeções/`. Lida em 19/09/2026. **17 registros.** Conteúdo **não copiado** para este workspace: contém posições jurídicas e estratégia de negociação da casa.

**Esquema de origem — 18 campos**

`id` · `tipo` · `objecao_verbatim` · `quem_levantou` · `perfil_do_cliente` · `clausula_ou_item_afetado` · `grau_de_risco` · `analise_criterio` · `resposta_que_funcionou` · `resposta_que_nao_funcionou` · `desfecho` · `concessao_dada` · `texto_final_acordado` · `precedente` · `condicao_do_precedente` · `fonte_tipo` · `data` · `confianca`

**Domínios observados**

| Campo | Valores |
|---|---|
| `tipo` | cláusula contratual · LGPD · escopo · preço · multa |
| `quem_levantou` | cliente · jurídico do cliente |
| `grau_de_risco` | Alto · Médio |
| `desfecho` | aceito · concessão parcial · depende · sem resposta |
| `precedente` | sim · não · depende · A VALIDAR |
| `fonte_tipo` | playbook de objeções da casa · sumário contratual pós-revisão jurídica |
| `confianca` | alta |

**Faixas de tratamento** citadas nas condições de precedente: `ESCALAR` e `ACEITAR COM AJUSTE`. São alçada, não sugestão.

**Modelagem: catálogo ≠ ocorrência**

A decisão estrutural mais importante desta seção. A matriz atual é **catálogo**. Para "enriquecer com o tempo", como Eduardo pediu, o CRM precisa de **duas entidades**:

| Entidade | O que guarda | Cardinalidade |
|---|---|---|
| **Objeção (catálogo)** | Os 18 campos atuais — a posição da casa, o precedente, a faixa | 17 hoje, cresce devagar |
| **Ocorrência de objeção** | Oportunidade · objeção do catálogo (ou nova) · verbatim do caso · resposta usada · quem decidiu · concessão dada · desfecho · data | Cresce a cada negociação |

Sem essa separação, cada registro novo **sobrescreve** a experiência anterior em vez de acumulá-la. Os campos `resposta_que_funcionou` e `resposta_que_nao_funcionou` passam de afirmação baseada em um caso para estatística sobre muitos.

**Regras de comportamento derivadas do conteúdo**

- Objeção com `precedente = não` ou faixa `ESCALAR`: o CRM **avisa antes da concessão** e exige registro de quem autorizou. Nunca bloqueia sozinho nem concede sozinho.
- Objeção marcada como ponto em aberto da casa: escalar sempre, sem exceção.
- Objeção marcada como sensível: registro com sinalização para revisão de risco.
- `precedente = A VALIDAR`: aparece como pendência de decisão de Bruno, não como posição da casa.

**Ligações com o resto do modelo**

| Liga com | Como |
|---|---|
| **Motivo de recusa** | "Preço" é o motivo nº 1 no histórico. A matriz detalha qual objeção de preço e qual resposta funciona. Hoje o dado morre em "preço" |
| **Ficha de volumetria** | A resposta padrão da casa para objeção de preço é vender o diagnóstico e precificar depois da volumetria |
| **Motor de horas** | A defesa do teto de responsabilidade ancora-se na precificação por esforço de horas — quarta aparição do mesmo motor |
| **Contrato** | `texto_final_acordado` é cláusula negociada; alimenta versão e aditivo |
| **Desvio de escopo (MP-SC-01)** | Ver a tensão registrada na seção 5 do documento de negócio |

**Tensão a resolver antes de implementar**

A objeção sobre fatos novos descobertos em projeto e o tratamento de desvio do MP-SC-01 convergem para a mesma decisão com orientações distintas: a matriz alerta que absorver esforço extra "vira expectativa" e manda propor aditivo antes de executar; o fluxo institui a absorção com débito de horas de conforto. **Compatíveis se a absorção for limitada e medida — mas a política de horas de conforto não existe.** Enquanto não existir, o fluxo autoriza o que a matriz desaconselha.

### B.2.5 — KPIs oficiais e o que eles exigem

Fonte: `KPI de Head de Novos Negócios.xlsx` — SharePoint, site Comercial, `01. Ponto de Partida/04_Analises/`. Lida em 19/09/2026. **12 indicadores com fórmula, periodicidade, meta e alerta.** Adotados como estão, por decisão de Eduardo.

MRR · NRR · CAC · LTV · LTV/CAC · Taxa de conversão · Ticket médio · Ciclo médio de vendas · Churn rate · Sales velocity · NPS · **ISC (Índice de Saúde da Carteira)** · Forecast accuracy.

**O ISC amarra os dois módulos.** Sua fórmula é *"classe + semáforo + churn, ponderados por receita"* — exatamente as saídas do modelo de classificação da seção (b2.4). O comentário da planilha explica a escolha do peso: *"a receita como peso garante que a ação no grupo que mais importa economicamente seja a que mais move o ponteiro"*.

**Entidades novas que os KPIs exigem e que nenhuma versão anterior previa**

| Exigência | KPI que pede | Situação |
|---|---|---|
| **Encerramento de cliente** com data e motivo | Churn rate, LTV, NRR | Não modelado. Vigência existia; saída não |
| **Expansão, contração e reajuste** de contrato | NRR | Aditivo existia; redução de escopo e reajuste, não |
| **Previsão de receita** por oportunidade | Forecast accuracy | Não modelado. Exige probabilidade ou data esperada de fechamento no funil |
| **Pesquisa de NPS** — disparo, resposta e registro | NPS | Não modelado. A planilha sugere aplicá-la após momentos-chave, o que se encaixa nas reuniões de resultado |
| **Investimento em marketing e vendas** por período | CAC, LTV/CAC | Dado externo ao CRM. Lançamento manual ou o indicador fica fora |

**Ambiguidade a resolver antes de implementar**

A fórmula da taxa de conversão diz "vendas fechadas ÷ total de oportunidades trabalhadas". Sobre 2026:

- Denominador = propostas **decididas** (106) → **38%**, abaixo da meta de 50%, acima do alerta de 30%.
- Denominador = **todas** (154) → **26%**, **abaixo do alerta**.

Diagnósticos opostos a partir do mesmo dado. **Não implementar sem a definição fixada.**

Ambiguidade menor, também a confirmar: o ticket médio de R$ 3.000 refere-se a venda nova ou a receita média por grupo? A receita média por unidade de carteira hoje é de R$ 7.301.

**Linha de base apurada em 19/09/2026**

MRR de R$ 226.341 — 57% da meta, acima do alerta. ISC calculável com a classificação existente. Ciclo médio **não calculável** enquanto faltarem as 40 datas de aceite. Churn **não calculável** — saídas não são registradas.

**Observação sobre o MRR.** O indicador mede receita contratada. **41% dela está travada por inadimplência**, em 5 grupos. O MRR pode estar saudável enquanto o caixa não entra — daí o ISC existir em separado, com a adimplência pesando 15% no Score e acionando a trava.

### B.3 — Campos comerciais já cobertos pela planilha

Origem (tipo de canal, canal, captador) · linha C1 ou C2 · serviço e tipo de serviço · temperatura · situação · motivo da recusa · datas · preços (mensal, anual, mensalizado) · contrato assinado.

---

## (c) Bloco de dados

```json
{
  "versao_documento": "2.5",
  "necessidade_principal": "CRM proprio da Critério cobrindo o cliente do primeiro contato ate a carteira madura, tendo o GRUPO ECONOMICO como unidade: (1) comercial — entrevista no Granola, lead, ficha de volumetria, porte, preco, proposta, contrato no Clicksign; (2) implantacao acompanhada por responsavel de area ate o cliente operar; (3) carteira e Sucesso do Cliente — classificacao viva por score/semaforo/eixo de acao, alertas de churn e inadimplencia, e reunioes de resultado com cadencia ligada a classe.",
  "necessidades_secundarias": [
    "Cálculo automático de preço a partir dos direcionadores — depende de existir tabela ou fórmula hoje",
    "Roteiro 'Descoberta do Cliente' no CRM — serve à validação de produto; recomendação é ficar fora da Fase 1",
    "Acompanhamento da implantação pós-venda — fora do escopo recomendado",
    "Classificação para canais novos: tráfego pago e afiliados",
    "Envio de campanhas pelo próprio CRM (futuro)",
    "Contratos de parceria comercial (finder fee) — natureza distinta, entrada a confirmar",
    "Controle de vigência e renovação de contrato",
    "Painéis de performance (hipótese)",
    "Comissionamento de afiliados e parceiros (fora do escopo)"
  ],
  "resumo_executivo": "Substituir a planilha por um CRM que acompanha a oportunidade da entrevista até a entrega do cliente à área técnica. A entrevista, já capturada no Granola com roteiro estruturado, passa a alimentar campos do CRM: os números que determinam o preço e o retrato da operação que a equipe técnica precisa. O preço fica registrado com a justificativa. O contrato é emitido dos mesmos dados e assinado digitalmente. Assinado, a área técnica recebe um pacote pronto. Carga inicial apenas dos 154 registros de 2026.",
  "objetivos": [
    "Registro único e confiável das oportunidades comerciais",
    "Classificação da origem do lead em tipo de canal e canal específico",
    "Capturar a entrevista no Granola e ligá-la à oportunidade",
    "Aproveitar a entrevista como base da precificação, guardando os direcionadores",
    "Emissão de propostas a partir do CRM, em apresentação ou carta",
    "Emissão do contrato e coleta de assinatura digital dentro do fluxo",
    "Entregar à área técnica um pacote de onboarding montado com o que já foi levantado",
    "Follow-up semanal com lembretes para a equipe interna",
    "Geração de listas de campanha incluindo clientes e leads perdidos",
    "Abrir espaço para tráfego pago e afiliados como canais futuros"
  ],
  "problemas": [
    {
      "descricao": "Cadastro e controle das oportunidades em planilha, sem CRM",
      "tipo": "falta de controle",
      "impacto": "alto",
      "frequencia_volume": "154 propostas com Ano 2026"
    },
    {
      "descricao": "Sem acompanhamento estruturado: a planilha não tem próxima ação, data de retorno nem histórico",
      "tipo": "falta de controle",
      "impacto": "alto",
      "frequencia_volume": null
    },
    {
      "descricao": "Os números que determinam o preço ficam em texto, não em campo: são relidos e redigitados a cada proposta",
      "tipo": "retrabalho",
      "impacto": "alto",
      "frequencia_volume": "6 entrevistas de diagnóstico em 30 dias"
    },
    {
      "descricao": "A passagem para a área técnica não tem pacote: o que foi levantado na entrevista é redescoberto depois",
      "tipo": "retrabalho",
      "impacto": "alto",
      "frequencia_volume": "40 propostas aceitas em 2026"
    },
    {
      "descricao": "A lista de 'Informações Faltantes para Proposta' existe em cada nota mas não é acompanhada",
      "tipo": "falta de controle",
      "impacto": "alto",
      "frequencia_volume": "presente nas 6 notas conferidas"
    },
    {
      "descricao": "Contrato fora do controle comercial: só há uma marca de 'Contrato Assinado' preenchida de forma irregular",
      "tipo": "falta de controle",
      "impacto": "alto",
      "frequencia_volume": "40 aceitas em 2026; valores 'Sim', 'sim', 'Nao', '1' e texto livre"
    },
    {
      "descricao": "Assinatura tratada fora do fluxo, sem rastro de quem assinou e quando",
      "tipo": "risco",
      "impacto": "alto",
      "frequencia_volume": null
    },
    {
      "descricao": "Canais de origem em texto livre, com grafias duplicadas, e sem classificação para tráfego pago e afiliados",
      "tipo": "falta de controle",
      "impacto": "medio",
      "frequencia_volume": "33 canais distintos em 2026"
    },
    {
      "descricao": "Qualidade dos dados da planilha: empresa vazia, aceitas sem data, preço mensal vazio, status com duas grafias",
      "tipo": "risco",
      "impacto": "alto",
      "frequencia_volume": "Empresa vazia em 149/154; 40 aceitas sem data; 92 sem preço mensal"
    },
    {
      "descricao": "Modelos de proposta e de contrato em arquivos avulsos, sem ligação com a oportunidade",
      "tipo": "retrabalho",
      "impacto": "medio",
      "frequencia_volume": null
    },
    {
      "descricao": "Sem forma sistemática de manter contato com clientes e leads perdidos",
      "tipo": "falta de controle",
      "impacto": "medio",
      "frequencia_volume": null
    }
  ],
  "cenario_atual": "Planilha Excel com 11 abas; a aba Propostas é o registro operacional e não contém nenhum direcionador de preço, só o valor final. As entrevistas já são capturadas no Granola com roteiro fixo de diagnóstico comercial (perfil, estrutura contábil, fiscal e trabalhista, dores com evidência, impactos e riscos, sistemas e processos manuais, motivo para mudar, objeções, processo de decisão, aderência à Critério, informações faltantes para proposta, próximos passos, resumo executivo comercial), com marcadores de autoria separando fala do cliente, fala da Critério e interpretação. Existe um questionário de volumetria enviado ao cliente após a entrevista. Um segundo roteiro, da Descoberta do Cliente, é usado para validação de produto. Como o preço é formado hoje e como a área técnica recebe o cliente hoje não foram informados. Propostas e contratos produzidos fora da planilha. Duas pessoas operam o comercial; sete captadores aparecem em 2026.",
  "cenario_desejado": "O que a entrevista levanta entra no CRM como campo: os números viram direcionadores do preço, o retrato da operação vira base do onboarding, e o que ficou faltando vira lista acompanhada com responsável e prazo. A proposta nasce desses números e o preço fica registrado com a justificativa. Aceita a proposta, o contrato é emitido dos mesmos dados e assinado digitalmente. Assinado, a área técnica recebe um pacote pronto com sistemas, integrações faltantes, processos manuais, prazos, riscos, pendências e pessoas do cliente — sem nova rodada de perguntas. Follow-up semanal com lembretes internos; listas de campanha geradas pelo CRM e enviadas em outra ferramenta.",
  "processos": [
    "Chegada do lead e classificação da origem",
    "Entrevista com o cliente capturada no Granola e ligada à oportunidade",
    "Levantamento de volumetria via questionário complementar",
    "Acompanhamento das informações que faltam para a proposta, com responsável e prazo",
    "Qualificação da oportunidade com temperatura",
    "Precificação a partir dos direcionadores levantados",
    "Elaboração e emissão da proposta (apresentação ou carta)",
    "Follow-up semanal das oportunidades em aberto",
    "Registro da decisão: aceita, recusada, on hold ou perdida, com motivo",
    "Emissão do contrato a partir dos dados da oportunidade",
    "Envio para assinatura digital e acompanhamento até a conclusão",
    "Guarda do contrato assinado",
    "Passagem para a área técnica com o pacote de onboarding montado",
    "Relacionamento contínuo e geração de listas para campanha",
    "Acompanhamento de performance comercial"
  ],
  "stakeholders": [
    {
      "papel": "solicitante, usuário e aprovador",
      "area": "Comercial e Customer Success",
      "responsabilidade": "Eduardo Luiz Silva — valida requisitos, telas e entregas"
    },
    {
      "papel": "administradora do CRM",
      "area": "Comercial",
      "responsabilidade": "Karine Nascimento — vê tudo"
    },
    {
      "papel": "responsáveis pela captação",
      "area": "Comercial",
      "responsabilidade": "BO, TC, FS, JC, MO, JS"
    },
    {
      "papel": "signatário pela Critério",
      "area": "Sócios",
      "responsabilidade": "Bruno Oliveira assina os contratos"
    },
    {
      "papel": "implantação — contábil, fiscal e DP",
      "area": "Implantação (área nova)",
      "responsabilidade": "Bruno Soares"
    },
    {
      "papel": "implantação — BPO Financeiro",
      "area": "Operação",
      "responsabilidade": "Jefferson Souza"
    },
    {
      "papel": "implantação — consultoria",
      "area": "Consultoria",
      "responsabilidade": "Jefferson Cruz"
    },
    {
      "papel": "demais usuários",
      "area": null,
      "responsabilidade": "Alçada restrita; regra pendente"
    }
  ],
  "sistemas_ferramentas": [
    "Excel — planilha de performance comercial e questionário de volumetria",
    "Granola (granola.app) — em uso hoje, com dois roteiros distintos (verificado em 19/09/2026)",
    "Ferramenta de assinatura digital — não definida",
    "WhatsApp Business — lembretes internos",
    "E-mail — lembretes internos",
    "Ferramenta de campanha externa — não definida",
    "PostgreSQL, Python, React — stack definida pelo cliente",
    "Omie — explicitamente fora de escopo",
    "OBSERVAÇÃO: os ERPs e sistemas citados nas entrevistas são dos clientes, não integrações da Critério; são carga do pacote de onboarding"
  ],
  "documentos_dados": [
    "matriz-objecoes.csv — 17 objecoes com 18 campos (SharePoint, 09_Governanca comercial - IA)",
    "KPI de Head de Novos Negocios.xlsx — 12 indicadores oficiais",
    "Macroprocesso - Comercial & Sucesso do Cliente.pptx",
    "Categorizado de clientes Curva ABC_Final.pptx — classificacao por grupo economico",
    "MP-SC-01 Implantacao de Cliente Rev.02 — BPMN e legenda (rascunho nao aprovado)",
    "Questionario_BPO_Full_2026_v2.docx — ficha de volumetria, 8 secoes",
    "Planilha de Precificacao.xlsx — modelo por horas e porte",
    "Planilha de performance comercial (recorte 2026, 154 linhas)",
    "Notas de entrevista do Granola em dois roteiros (diagnóstico comercial e Descoberta do Cliente)",
    "Contrato de prestação de serviço — DOCX e PDF",
    "Contratos de parceria comercial (finder fee) — natureza distinta",
    "Contrato assinado e trilha de assinatura",
    "Dados de contato — inexistentes hoje, entram depois"
  ],
  "magnitude": {
    "volume": "154 propostas em 2026 (66 recusadas, 40 aceitas, 22 on hold, 14 em avaliação, 12 a enviar). 6 entrevistas de diagnóstico em 30 dias (21/08 a 18/09/2026), de 39 reuniões no período. 33 canais distintos. Contratos e onboardings por ano não informados; referência de 40 aceitas",
    "frequencia": "Follow-up semanal",
    "tempo_gasto": null,
    "pessoas_envolvidas": "2 usuários no comercial; 7 captadores na base de 2026; área técnica não dimensionada",
    "custo_estimado": null
  },
  "criterios_sucesso": [
    "OFICIAL: 12 KPIs da planilha 'KPI de Head de Novos Negocios' adotados como estao — MRR (meta 400k, alerta <200k) · NRR (>110%, <90%) · CAC · LTV (3x CAC) · LTV/CAC (>=3:1, <2:1) · Taxa de conversao (50%, <30%) · Ticket medio (3000, 2000) · Ciclo medio (21-45d, >90d) · Churn (5%, >7%) · Sales velocity (30d, >60d) · NPS (50-74, <50) · ISC (65-100, <65) · Forecast accuracy (85-110%, <70%)",
    "AMBIGUIDADE A RESOLVER: denominador da taxa de conversao — decididas (38%) ou todas as trabalhadas (26%). Um esta acima do alerta, o outro abaixo",
    "COBERTURA (sugestao da analise): grupos com reuniao na cadencia devida · dias desde o ultimo contato · migracao de classe entre periodos · oportunidades com proxima acao · implantacoes no prazo · vigencias a vencer em 90 dias"
  ],
  "restricoes": {
    "orcamento": null,
    "prazo": null,
    "infraestrutura": "Nuvem já reservada para esta aplicação. Ambientes separados de teste e produção. Backup automático, nunca dependente de pessoa. Autenticação pela conta corporativa Microsoft. Provedor e região do servidor pendentes.",
    "aprovador": "Eduardo Luiz Silva valida requisitos, telas e entregas (decisão de 19/09/2026).",
    "precificacao": "DECISAO 19/09/2026: integracao com a planilha adiada para um segundo momento; o porte da empresa entra como campo do CRM, preenchido por pessoa. Modelo lido em 19/09/2026. Baseado em horas de equipe: horas × mix por senioridade × preço/hora, com desconto e imposto de 11%. Dois caminhos: BPO contábil/fiscal/DP parte do porte do cliente (regra de porte não existe escrita); BPO Financeiro, Plus e CFO partem de faixas de volumetria explícitas (documentos/mês, contas bancárias, conciliações de cartão). Oito divergências entre planilhas registradas na seção b1.1 do anexo. Confirmado por Eduardo que o elo entre o questionario e a planilha nao existe hoje: o porte e julgado por pessoa. Fase 1 guarda porte, direcionadores e preco; nenhuma formula e traduzida.",
    "compliance_lgpd": "RISCO ACEITO PELO CLIENTE em 19/09/2026: Eduardo decidiu não submeter ao jurídico a base legal para contatar lead perdido nem a guarda das transcrições. Hoje não se pede autorização de gravação das entrevistas, e ele reconhece que deveria. O CRM implementa marcador 'não contatar', guarda apenas o resumo da entrevista e controle de acesso — medidas técnicas, não parecer jurídico.",
    "sistemas_intocaveis": [],
    "integracoes_obrigatorias": [
      "E-mail",
      "WhatsApp Business (número único da empresa)",
      "Granola (granola.app) — automático, só resumo, template [Potencial Cliente]",
      "Clicksign — assinatura digital",
      "Conta corporativa Microsoft — autenticação"
    ],
    "escopo_implantacao": "DENTRO do escopo por decisão de Eduardo em 19/09/2026: o CRM acompanha a implantação até o cliente estar operando, com etapas, responsável e prazo. Responsáveis: Bruno Soares (contábil, fiscal e DP), Jefferson Souza (BPO Financeiro), Jefferson Cruz (consultoria). Checklist de onboarding não existe e precisa ser criado. Fluxo MP-SC-01 Rev.02 recebido em 19/09/2026 (BPMN + legenda): RASCUNHO nao aprovado, com 6 pendencias proprias — checklist padrao, politica de horas de conforto, alcadas de aditivo e absorcao, item UAT do kick-off, ponto de retorno do gateway e paralelismo dos setores. Marco final 'Operacao' = cliente estabilizado apos 3 ciclos de fechamento revisados. Construir a tela de implantacao antes da aprovacao do fluxo e retrabalho provavel.",
    "unidade_de_cliente": "Grupo economico, nao CNPJ. Receita e custo somados sem rateio; complexidade, disciplina e risco por media ponderada por horas; adimplencia pelo pior caso do grupo. O CNPJ permanece visivel dentro do grupo. Carteira atual: 31 unidades de analise a partir de 58 CNPJs.",
    "perfis_de_acesso": "Tres visoes sobre a MESMA classificacao, conforme o deck da carteira: Lideranca (score, margem, trava, alertas, eixo de acao), Customer Success (classe, classe efetiva, alertas, eixo de acao), Operacao (letra, semaforo, complexidade, disciplina, risco tecnico). Uma classificacao, varias projecoes de leitura — nunca duas tabelas.",
    "cadencia_reunioes": "Mensal para classe A, trimestral para B, semestral para C (decisao de Eduardo, 19/09/2026).",
    "notas_humanas_score": "Area tecnica atribui complexidade operacional, disciplina do cliente e risco tecnico. Comercial atribui potencial de cross-sell. Frequencia mensal.",
    "matriz_de_objecoes": "Entra no CRM como base viva (decisao de Eduardo, 19/09/2026). Duas entidades: catalogo (17 objecoes, 18 campos) e ocorrencia (cada aparicao numa negociacao real). A matriz orienta e registra alcada — precedente 'nao' ou faixa ESCALAR avisam antes da concessao e exigem registro de quem decidiu; o CRM nunca concede automaticamente. Nao substitui parecer juridico; itens 'A VALIDAR' seguem pendentes de decisao humana."
  },
  "oportunidades": {
    "melhoria": [
      "Listas controladas no lugar de texto livre",
      "Separar situação da proposta do motivo da recusa",
      "Empresa como cadastro único com propostas, contratos e onboarding ligados",
      "Um único lugar com a conversa, os números, a proposta, o contrato e a passagem para a operação",
      "Preço rastreável: saber de que volume e de que complexidade ele saiu",
      "Reaproveitar a entrevista em vez de repetir perguntas ao cliente",
      "Situação da assinatura visível no funil",
      "Visão única de aceitas, em curso e recusadas"
    ],
    "automacao": [
      "Levar os números da entrevista e do questionário direto para os campos de volumetria",
      "Calcular o preço sugerido a partir dos direcionadores (depende de existir a regra)",
      "Montar o pacote de onboarding com o que já está preenchido",
      "Avisar quando a lista de informações faltantes trava a proposta",
      "Montagem da proposta e do contrato a partir dos mesmos dados",
      "Envio automático para assinatura quando a proposta é aceita",
      "Lembrete de contrato enviado e não assinado",
      "Lembretes semanais de follow-up",
      "Geração da lista de campanha já filtrada",
      "Carga e padronização dos dados de 2026"
    ],
    "ia": [
      "SUGESTAO: extrair da nota da entrevista os campos de volumetria e o retrato da operação, com revisão humana",
      "SUGESTAO: apontar o que ainda falta para precificar",
      "SUGESTAO: rascunhar o resumo de onboarding para a área técnica, com revisão humana",
      "SUGESTAO: apontar diferenças entre o combinado na entrevista e o escrito na proposta ou no contrato",
      "SUGESTAO: resumir o histórico da oportunidade antes do contato",
      "SUGESTAO: sugerir a próxima ação de follow-up",
      "SUGESTAO: apontar oportunidades paradas",
      "SUGESTAO: apoiar a padronização dos dados na carga",
      "SUGESTAO: esboçar a carta de consultoria a partir do escopo",
      "LIMITE: a IA não define preço, não aprova contrato, não altera cláusula e não fecha escopo. O roteiro de entrevista já separa fala do cliente de interpretação; o CRM preserva essa separação e trata o extraído como sugestão a revisar"
    ]
  },
  "necessidades_ocultas": [
    "SUGESTAO: ficha de volumetria como campo estruturado, não anexo",
    "SUGESTAO: registro do porquê do preço — quais direcionadores o sustentaram",
    "SUGESTAO: histórico de preço quando a proposta é reajustada ('Proposta reajustada' aparece como motivo na planilha)",
    "SUGESTAO: lista de pendências da oportunidade com responsável e prazo",
    "SUGESTAO: marco de passagem para a operação, com data e quem recebeu",
    "SUGESTAO: riscos identificados na entrevista viajando até o onboarding",
    "SUGESTAO: prazo do fornecedor atual do cliente como data que condiciona o início",
    "SUGESTAO: versões e histórico do contrato",
    "SUGESTAO: guarda do contrato assinado e da nota de entrevista com controle de acesso",
    "SUGESTAO: controle de vigência e renovação",
    "SUGESTAO: registro da ciência dos participantes sobre a gravação",
    "SUGESTAO: marcador 'não contatar'",
    "SUGESTAO: data de aceite obrigatória quando a proposta é marcada como aceita",
    "SUGESTAO: histórico de mudanças de situação",
    "SUGESTAO: perfis de acesso para usuários futuros",
    "SUGESTAO: cadastro de canais e parceiros como lista controlada",
    "SUGESTAO: relatório de conferência da carga"
  ],
  "glossario": [
    {
      "termo": "C1",
      "significado": "Linha de serviços de BPO contábil, fiscal e departamento pessoal"
    },
    {
      "termo": "C2",
      "significado": "Linha de serviços de consultoria em geral"
    },
    {
      "termo": "FUP",
      "significado": "Follow-up"
    },
    {
      "termo": "FSCP",
      "significado": "Financial Statement Closing Procedure — mapeamento dos processos e controles para fechamento das informações contábeis"
    },
    {
      "termo": "BPO Plus",
      "significado": "Produto distinto do BPO Financeiro e do CFO as a Service; fronteiras em validação na Critério"
    },
    {
      "termo": "CFO as a Service",
      "significado": "Serviço de direção financeira prestado pela Critério; fronteiras em validação"
    },
    {
      "termo": "Granola",
      "significado": "granola.app — captura e resumo de reuniões; em uso na Critério com dois roteiros distintos"
    },
    {
      "termo": "Ficha de volumetria",
      "significado": "Conjunto de números do cliente que sustentam a precificação: CNPJs, faturamento, regime, notas, pagamentos, pessoas, complexidade"
    },
    {
      "termo": "Direcionador de preço",
      "significado": "Campo da volumetria que influencia o valor da proposta; quais e com que peso é pendência"
    },
    {
      "termo": "Pacote de onboarding",
      "significado": "Conjunto estruturado entregue à área técnica após o contrato assinado: sistemas, integrações, processos manuais, prazos, riscos, pendências e pessoas do cliente"
    },
    {
      "termo": "Informações Faltantes para Proposta",
      "significado": "Seção do roteiro de entrevista que lista o que ainda falta levantar; no CRM vira lista acompanhada"
    },
    {
      "termo": "Descoberta do Cliente",
      "significado": "Metodologia de Steve Blank; segundo roteiro de entrevista, voltado à validação do produto e não à venda"
    },
    {
      "termo": "Assinatura digital",
      "significado": "Coleta eletrônica de assinatura com valor jurídico e trilha de auditoria; ferramenta não escolhida"
    },
    {
      "termo": "Finder fee",
      "significado": "Remuneração por indicação prevista nos contratos de parceria comercial"
    },
    {
      "termo": "Temperatura",
      "significado": "Qualificação da oportunidade: Frio, Morno ou Quente"
    },
    {
      "termo": "Tipo de canal",
      "significado": "Categoria da origem do lead: Sócios, Parceiros, Advogados, Carteira, Interno, Colaboradores e, futuramente, Tráfego pago e Afiliados"
    },
    {
      "termo": "Valor mensalizado",
      "significado": "Coluna da planilha que distribui o valor do contrato ao longo do ano"
    }
  ],
  "pontos_a_confirmar": [
    "Tensao a resolver: a matriz alerta que absorver esforco extra 'vira expectativa'; o MP-SC-01 institui absorcao com debito de horas de conforto. Compativeis so se a politica de horas existir — e ela nao existe",
    "As 3 objecoes com precedente 'A VALIDAR' aguardam decisao de Bruno — entram no CRM como pendencia, nao como posicao da casa",
    "Quem pode registrar objecao nova no catalogo, e quem aprova a promocao de 'ocorrencia' para 'precedente'?",
    "As faixas de tratamento (ESCALAR, ACEITAR COM AJUSTE) tem lista completa em algum lugar? So duas aparecem na matriz",
    "URGENTE: definicao do denominador da taxa de conversao (38% x 26%)",
    "Ticket medio de R$3.000 refere-se a venda nova ou a receita media por grupo? Media atual por unidade: R$7.301",
    "CAC e NPS dependem de dados externos — investimento em marketing/vendas entra como lancamento manual? A pesquisa de NPS e disparada pelo CRM?",
    "Motivos de saida de cliente (churn) — lista controlada, como a de motivos de recusa",
    "Responsaveis de implantacao: visao Operacao ou perfil proprio?",
    "O que dispara a reclassificacao: fechamento mensal, mudanca de contrato, decisao em reuniao?",
    "A margem da carteira segue estimada por porte ou o CRM registra horas reais (timesheet — outro projeto)?",
    "Os responsaveis de implantacao entram na visao Operacao ou tem perfil proprio?",
    "Confirmar a ordem das etapas de 'Em curso' no macroprocesso — o deck tem caixas sobrepostas e a extracao nao e inequivoca",
    "A etapa 3 (carteira) sobe de prioridade? Ela nao depende da etapa 2 e e o objetivo declarado",
    "Os processos de implantacao de BPO Financeiro e de consultoria serao desenhados? Por quem e quando? Sao dois dos tres, e nenhum existe",
    "Prazo por etapa da implantacao — sem ele nao ha como medir atraso",
    "A vigencia do contrato comeca na assinatura ou no marco Operacao?",
    "Caminho de excecao: implantacao suspensa, parada por falta de resposta do cliente, cancelada ou distratada",
    "Entregas do cliente (acessos, procuracoes, certificado digital, saldos de migracao) entram como dependencia rastreada?",
    "Quando o MP-SC-01 sera aprovado? A tela de implantacao deveria esperar",
    "Checklist de implantacao: quem escreve e ate quando? E pendencia do proprio fluxo",
    "Politica de horas de conforto: saldo por cliente, unidade, registro do debito, quem autoriza",
    "Alcadas de aditivo e de absorcao: o fluxo as marca como presumidas, a validar com a Alta Direcao",
    "Regra de alçada dos demais usuários; responsáveis de implantação veem o comercial?",
    "Checklist de implantação: quem escreve, um por serviço ou um só?",
    "O que caracteriza 'cliente operando' e fecha a implantação?",
    "Ordem das etapas (seção 18 do documento) está aprovada?",
    "KPIs propostos na seção 12.2 estão corretos?",
    "Critérios de sucesso da seção 12.1 estão corretos?",
    "Região do servidor e provedor da nuvem já reservada",
    "Virada: paralelo com a planilha ou corte seco? A planilha fica como consulta?",
    "Prazo e orçamento",
    "Modelos de contrato: caminho no SharePoint (o link do Outlook não abre pelo conector)",
    "Texto de ciência de gravação para as entrevistas — Eduardo reconheceu que deveria pedir",
    "As oito divergências das planilhas de precificação são todas não intencionais, incluindo a matriz de porte desligada e as fórmulas faltando na aba de consultoria?",
    "ADIADO: integração com a planilha de precificação e cálculo automático"
  ],
  "nivel_confianca_geral": "alto para o comercial; medio para a implantacao, que e escopo novo e sem checklist existente"
}
```
