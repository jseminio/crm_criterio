# Critério CRM — Documento de Negócio

**Versão 2.7 · 19/09/2026 · Status: ✅ validado por Eduardo Luiz Silva em 19/09/2026**

> **O que mudou da 2.6 para a 2.7.** **Dois gates humanos cumpridos:** a amostra das telas e o PAD-002, ambos aprovados por Eduardo em 19/09/2026. O projeto passa de PF-07 para PF-08.
> **Correção de um defeito meu:** as restrições de **design das telas** e de **marca** — logomarca sempre sozinha — tinham desaparecido do documento na reescrita da versão 2.0. Foram repostas na seção 13.

> **O que mudou da 2.5 para a 2.6.** Recebidas as três planilhas auditáveis da classificação da carteira. O modelo deixou de ser descrição de deck e virou **especificação completa**, em [`modelo-classificacao-carteira.md`](modelo-classificacao-carteira.md). **Decisão sua:** a classificação passa a ser **calculada dentro do CRM**, com as notas alimentadas nele — não mais mantida em planilha. Dois defeitos foram encontrados nas fórmulas e estão registrados. Entraram também as telas de entrada de lead na amostra.

> **O que mudou da 2.4 para a 2.5.** Recebida a **Matriz de Objeções** — 17 objeções registradas com esquema de 18 campos. Entra no CRM como **base viva**, enriquecida a cada negociação. Ela fecha o laço do maior motivo de recusa da Critério e revela **uma tensão entre dois documentos da casa**, descrita na seção 5.

> **O que mudou da 2.3 para a 2.4.** Adotados os **12 KPIs oficiais da Critério**, com metas e alertas — substituem a proposta que eu tinha feito. Decididos: cadência de reunião (A mensal · B trimestral · C semestral), quem atribui as notas humanas do Score, e a entrada de KYC, PRA e dashboard contábil. Os KPIs exigem quatro entidades que não estavam previstas: encerramento de cliente, expansão/contração de contrato, previsão de receita e pesquisa de NPS.

> **O que mudou da 2.2 para a 2.3.** Recebi o **Macroprocesso Comercial & Sucesso do Cliente** e o deck **Classificação da Carteira por Grupo Econômico**. Duas consequências grandes:
> (1) **A unidade de cliente passa a ser o grupo econômico, não o CNPJ.** Isso muda a base do modelo de dados e não estava em nenhuma versão anterior.
> (2) **Entra um terceiro módulo — Carteira e Sucesso do Cliente** — com classificação, alertas e cadência de reuniões de resultado. O ciclo deixa de terminar na implantação.
> Mudaram as seções 1 a 13, 17, 18 e 19.

> **O que mudou da 2.1 para a 2.2.** Confirmado por você: **BPO Financeiro e consultoria têm processos de implantação próprios**, diferentes do MP-SC-01. São **três processos**, e só um está desenhado — em rascunho. A avaliação de completude do MP-SC-01 está na seção 5.

> **O que mudou da 2.0 para a 2.1.** Recebi o fluxo **MP-SC-01 Implantação de Cliente, Rev.02 (15/09/2026)** — BPMN e legenda. Ele **responde duas perguntas que estavam abertas** (o que marca "cliente operando" e onde nasce o checklist) e traz um conceito novo que entra no modelo: **horas de conforto**. Mudaram as seções 5, 7, 8, 9, 10, 13, 17 e 19.
> ⚠️ **O fluxo é RASCUNHO, não controlado e não aprovado.** Tratado aqui como o melhor retrato disponível, não como processo vigente.

> **Por que 2.0 e não 1.6.** Suas 34 respostas fecharam quase todas as lacunas, mas uma delas **muda o que o produto é**: o CRM passa a **acompanhar a implantação**, e não apenas entregá-la à área técnica. Deixa de ser um CRM comercial e vira **comercial + Customer Success**. Isso está na seção 13 e redesenha as fases.
>
> *Histórico: 1.0 base · 1.1 contrato e Granola · 1.2 precificação e onboarding · 1.3 nuvem e aprovador · 1.4 planilhas lidas · 1.5 precificação adiada · 2.0 respostas ao questionário.*

> Como ler: **decisão tomada** = você disse ou aprovou · **hipótese** = ainda a validar · **pendência** = falta informação.
> Inferências vêm marcadas como *Sugestão identificada pela análise.*

---

## 1. Resumo Executivo

Você quer um CRM próprio da Critério que acompanhe o cliente **do primeiro contato até a carteira madura**, no lugar da planilha de performance comercial. São três momentos encadeados:

1. **Comercial** — entrevista no Granola → lead classificado por origem → ficha de volumetria → porte e preço → proposta → contrato assinado no Clicksign.
2. **Implantação** — acompanhada pelo responsável da área, até o cliente estar operando.
3. **Carteira e Sucesso do Cliente** — o grupo econômico classificado em A, B ou C, com alertas de churn e de inadimplência, e **reuniões de resultado com cadência ligada à classe**. É aqui que está o seu objetivo declarado: aumentar os pontos de contato, com prioridade para os grupos melhor classificados.

A unidade de cliente é o **grupo econômico**, não o CNPJ. Hoje operam você e Karine. A carga inicial usa os 154 registros de 2026. A infraestrutura já está reservada em nuvem e o acesso será pela conta corporativa da Critério.

## 2. Entendimento da Necessidade

A planilha registra o resultado, não o caminho. Não tem follow-up, o contrato vive fora dela, e o que o cliente diz na entrevista não chega a lugar nenhum.

Por outro lado, quase tudo o que o CRM precisa **já existe em forma de documento**: o roteiro de entrevista no Granola, o questionário de volumetria em oito seções, a planilha de precificação, os dois modelos de proposta e os modelos de contrato. O problema não é falta de método — é que cada etapa recomeça do zero, relendo o que a anterior produziu.

E o ciclo não termina na assinatura. Como o seu chapéu é comercial **e** Customer Success, o que vem depois do contrato também é seu: a implantação e, depois dela, a vida do cliente na carteira.

A classificação da carteira já existe e é sofisticada — score de sete quesitos, semáforo operacional, eixo de ação, margem calculada por grupo. **O que não existe é onde ela vive.** Hoje é um deck e uma planilha, atualizados por alguém, de tempos em tempos. Sem sistema, a classificação envelhece no dia seguinte à apresentação, e a cadência de reuniões que ela deveria comandar não tem onde ser registrada nem cobrada.

## 3. Objetivos de Negócio

1. Registro único e confiável das oportunidades, no lugar da planilha. **(decisão tomada)**
2. Classificar a origem de cada lead em tipo de canal e canal específico. **(decisão tomada)**
3. Puxar automaticamente do Granola o resumo da entrevista e ligá-lo à oportunidade. **(decisão tomada)**
4. Estruturar a ficha de volumetria a partir do questionário oficial. **(decisão tomada)**
5. Registrar o porte do cliente e os direcionadores que sustentaram o preço. **(decisão tomada)**
6. Emitir propostas a partir do CRM. **(decisão tomada)**
7. Emitir o contrato e coletar assinatura digital pelo Clicksign. **(decisão tomada)**
8. **Acompanhar a implantação até o cliente estar operando.** **(decisão tomada)**
9. Controlar vigência e renovação dos contratos. **(decisão tomada)**
10. Follow-up semanal com lembretes internos. **(decisão tomada)**
11. Acompanhar KPIs do processo comercial. **(decisão tomada — indicadores na seção 12)**
12. **Tratar o cliente como grupo econômico**, somando receita e custo, sem rateio. **(decisão tomada)**
13. **Manter viva a classificação da carteira** — score, classe, semáforo, alertas e eixo de ação — em vez de recalculá-la em planilha de tempos em tempos. **(decisão tomada)**
14. **Aumentar os pontos de contato com reuniões de resultado**, com cadência ligada à classe e prioridade para os melhor classificados. **(decisão tomada — objetivo declarado por você)**
15. Gerar listas para campanhas feitas em outra ferramenta. **(decisão tomada)**
16. Abrir espaço para tráfego pago e afiliados. **(hipótese)**

## 4. Problemas e Dores (matriz consolidada)

| Problema / Dor | Tipo | Impacto | Frequência ou volume |
|---|---|---|---|
| Cadastro e controle em planilha, sem CRM | Falta de controle | Alto | 154 propostas de 2026 |
| Sem acompanhamento estruturado: nem próxima ação, nem data de retorno, nem histórico | Falta de controle | Alto | Não identificado |
| Os números que determinam o preço ficam em documento, não em campo, e são redigitados a cada etapa | Retrabalho | Alto | 6 entrevistas de diagnóstico em 30 dias |
| **A implantação tem fluxo desenhado, mas sem sistema que o sustente: handoff por e-mail livre, checklist de implantação inexistente e saldo de horas de conforto sem registro** | Falta de controle | Alto | 40 propostas aceitas em 2026 |
| A lista de "Informações Faltantes para Proposta" existe em cada entrevista, mas ninguém acompanha | Falta de controle | Alto | Nas 6 notas conferidas |
| **Os 12 KPIs oficiais existem em planilha, mas metade não é calculável hoje** — faltam datas de aceite, registro de saída de cliente e previsão de receita | Falta de controle | Alto | 12 KPIs definidos |
| **A classificação da carteira vive em deck e planilha, fora de qualquer sistema** — envelhece assim que é apresentada | Falta de controle | Alto | 31 unidades de análise |
| **Não há onde registrar nem cobrar a cadência de reuniões de resultado** — o ponto de contato depende de lembrança | Falta de controle | Alto | 6 grupos classe A |
| **A receita travada por inadimplência não tem acompanhamento sistemático** | Risco | Alto | **41% da receita mensal recorrente**, em 5 grupos |
| **A mesma lógica de horas é recalculada em quatro lugares sem se falar**: proposta, horas de conforto, margem da carteira e defesa do teto de responsabilidade | Retrabalho | Alto | — |
| **O motivo de recusa é registrado sem a objeção que o causou** — sabe-se que o cliente recusou por preço, não qual argumento foi usado nem se funcionou | Falta de controle | Alto | "Preço" é o motivo nº 1 de recusa |
| **A Matriz de Objeções vive num CSV** — não é consultada durante a negociação, não registra ocorrência e não aprende com o desfecho | Retrabalho | Alto | 17 objeções catalogadas |
| O contrato vive fora do controle comercial: só uma marca de "Contrato Assinado", preenchida como "Sim", "sim", "Nao", "1" e texto livre | Falta de controle | Alto | 40 aceitas em 2026 |
| Cada proposta gera uma cópia da planilha de precificação, e as cópias divergem entre si | Risco | Alto | Um cliente com três cópias e horas diferentes |
| As planilhas de precificação têm divergências que **você confirmou não serem intencionais** | Risco | Alto | Oito achados no anexo técnico |
| Canais em texto livre, com grafias duplicadas, e sem classificação para tráfego pago e afiliados | Falta de controle | Médio | 33 canais distintos |
| Dados da carga com falhas: nome do cliente não preenchido, aceitas sem data, valores heterogêneos | Risco | Alto | 149 de 154 sem empresa; 40 sem data |
| Sem forma sistemática de manter contato com clientes e leads perdidos | Falta de controle | Médio | Não identificado |

## 5. Cenário Atual

**A planilha.** Excel com 11 abas; a aba *Propostas* é o registro. Em 2026: 154 propostas, 75 em C1 (BPO contábil, fiscal e DP) e 79 em C2 (consultorias).

**As entrevistas.** O Granola já é usado, com o template **"[Potencial Cliente]"** **(confirmado por você)**. Nos últimos 30 dias, 6 das 39 reuniões usaram esse roteiro, que levanta perfil, estrutura contábil, fiscal e de DP, dores com evidência, impactos, sistemas, motivo para mudar, objeções, processo de decisão, aderência aos serviços, informações faltantes e resumo executivo comercial. Um segundo roteiro, da Descoberta do Cliente, **fica fora do CRM** **(decisão tomada)**.

**O questionário de volumetria.** `Questionario_BPO_Full_2026_v2.docx`, no SharePoint. Oito seções: empresa e escopo; sistemas e integrações; volumes mensais; contábil e gerencial; fiscal e obrigações; folha e DP; financeiro; dores, transição e decisão. **É a ficha de volumetria do CRM, quase pronta.**

**A precificação.** Modelo por horas de equipe. Planilha oficial: `Planilha de Precificação.xlsx`, em `01_Modelos Comercial/01. Proposta/`. O caminho do BPO contábil parte do **porte** (Micro a Extra Grande); o do BPO Financeiro parte de faixas de volumetria. **Você confirmou que não existe elo entre o questionário e a planilha** — o porte é julgado por quem conduz. As divergências entre planilhas **não são intencionais**.

**As propostas.** Dois modelos: BPO Full e BPO Financeiro, em PowerPoint. Mais a carta para consultorias fora do padrão.

**Os contratos.** Assinados hoje por **Bruno Oliveira**. Ferramenta: **Clicksign** **(decisão tomada)**.

**A implantação.** Por área: **Contábil, fiscal e DP → Bruno Soares**, numa área nova de implantação. **BPO Financeiro → Jefferson Souza. Consultoria → Jefferson Cruz.**

**O fluxo de implantação existe e está desenhado.** `MP-SC-01 — Implantação de Cliente, Rev.02`, de 15/09/2026, em BPMN com legenda. **É rascunho, não controlado, sem aprovação.** Quatro raias — Comercial, Analista de Implantação, Times Operacionais e Sucesso do Cliente — mais o Cliente como participante externo. O caminho, em resumo:

1. **Contrato assinado** dispara o processo.
2. **Reunião de handoff** (Comercial + CS + Implantação), com **ata obrigatória**.
3. Duas frentes em paralelo: o Comercial envia o **pacote de handoff** (formulário da proposta, contrato assinado e ata) à Implantação e ao CS; o **CS mapeia os Customer Outcomes e define a jornada do cliente**, referência de monitoramento por toda a vida contratual.
4. A Implantação **analisa contrato e contexto** e monta o **checklist de implantação do cliente**.
5. **Kick-off** com o cliente e **alinhamento operacional**.
6. **Revisão de aderência ao escopo, pré-implantação**, conduzida pelo CS. Desvio vira **aditivo** ou é **absorvido com débito de horas de conforto**.
7. **Implantação por setor** — Contábil, Fiscal, DP e Financeiro em paralelo — seguida de mapa de processo e sistema e identificação de riscos.
8. Gateway **"Checklist de implantação cumprido?"**.
9. **Revisão de aderência pós-implantação**, com o mesmo tratamento de desvio.
10. **Operação do 1º mês**, conferida pela Implantação contra a especificação.
11. **Revisão dos ciclos de fechamento** pelo CS, com alinhamento de marco com o cliente, até **3 ciclos aprovados**.
12. **Marco final: "Operação"** — cliente estabilizado, sai da implantação e entra na rotina.

**São três processos, não um.** **(confirmado por você em 19/09/2026)** Contábil, fiscal e DP seguem o MP-SC-01. **BPO Financeiro e consultoria têm processos próprios, ainda não desenhados.** Dos três, só um existe — e em rascunho.

### O que falta no MP-SC-01

**O próprio documento admite cinco pendências:** o checklist de implantação padrão; a política de horas de conforto; as alçadas de aditivo e de absorção, hoje presumidas; o item "UAT" do kick-off, ilegível no desenho original; e o ponto exato de retorno quando o checklist não fecha. Some-se o paralelismo dos setores, assumido na modelagem e não validado.

**O que a análise notou e o documento não menciona** — *Sugestão identificada pela análise*, tudo relevante para o CRM:

- **Nenhuma etapa tem prazo.** Não há SLA por etapa nem duração esperada da implantação. Sem isso, "implantação em atraso" não tem como ser calculado.
- **Não há caminho de exceção.** O fluxo só tem o caminho feliz e os laços de ajuste. Não existe implantação suspensa, parada por falta de resposta do cliente, cancelada ou distratada no meio.
- **As entregas do cliente não são modeladas.** Acessos, procurações, certificado digital e saldos de migração aparecem na descrição dos setores, mas o cliente só troca duas mensagens com a Critério: kick-off e alinhamento de marco. Na prática, a implantação costuma travar exatamente esperando o cliente.
- **O laço dos três ciclos não tem saída de escape.** Se um ciclo nunca é aprovado, o fluxo gira sem escalonamento.
- **A vigência do contrato não é amarrada.** Ela começa na assinatura ou no marco Operação? O CRM precisa saber, porque controla renovação.
- **O Analista de Implantação é papel, não pessoa.** Quantos existem e como a carga é distribuída não está definido.

**Horas de conforto.** Quando um desvio de escopo é absorvido pela Critério em vez de virar aditivo, ele é **debitado de um saldo de horas de conforto do cliente**. **A política não está formalizada** — falta definir o saldo por cliente, a unidade, o registro do débito e quem autoriza.

**Canais em 2026.** Sócios 86, Parceiros 38, Interno 12, Advogados 9, Carteira 8, Colaboradores 1.

### A Matriz de Objeções

Recebida em 19/09/2026: `matriz-objecoes.csv`, no SharePoint, em `09_Governança comercial - IA / 03_Matriz de objeções`. **17 objeções registradas**, cada uma com 18 campos.

**Não é uma lista de respostas prontas.** Cada objeção guarda o que o cliente disse literalmente, quem levantou, o perfil do cliente, a cláusula ou item afetado, o grau de risco, a análise da Critério, **a resposta que funcionou e a que não funcionou**, o desfecho, a concessão dada, o texto final acordado, se vira **precedente** e sob qual condição, a fonte, a data e o grau de confiança.

**Os tipos de objeção:** cláusula contratual, LGPD, escopo, preço e multa.

**Três camadas de governança embutidas.** É o que mais me chamou atenção:

- **Status de precedente** — `sim` (posição estável da casa), `não` (nunca aceitar), `a validar` (aguarda decisão do Bruno) ou `depende`.
- **Faixas de tratamento** — a matriz menciona `ESCALAR` (nunca decidir sozinho) e `ACEITAR COM AJUSTE`.
- **Pontos em aberto** — uma das objeções está marcada como a posição mais frágil do modelo atual, com instrução explícita de escalar sempre que aparecer.

Isso significa que a matriz **não é só conhecimento: é alçada**. Ela diz o que pode ser concedido, por quem, e o que precisa subir.

**Onde ela conecta com o resto do projeto**

- **Fecha o laço do maior motivo de recusa.** "Preço" é o motivo número um de recusa no histórico da Critério. A matriz tem a objeção de preço mapeada, e a resposta que funciona é vender o diagnóstico como produto e fixar o preço depois da volumetria. Hoje o CRM registraria "recusou por preço" e pararia ali. Com a matriz, registra **qual objeção apareceu, qual resposta foi tentada e se funcionou**.
- **Volta ao motor de horas.** A defesa do teto de responsabilidade se ancora explicitamente na precificação por esforço de horas. É o mesmo motor da proposta, das horas de conforto e da margem da carteira — agora aparecendo também na negociação jurídica.
- **Reforça a ficha de volumetria.** A resposta padrão da casa para preço é: diagnóstico primeiro, preço depois. O questionário de volumetria é esse diagnóstico.

### Uma tensão entre dois documentos da casa

*Sugestão identificada pela análise. Não é contradição, mas vale decidir antes de virar sistema.*

A objeção sobre **fatos novos descobertos durante o projeto** e a etapa de **tratamento de desvio** do fluxo MP-SC-01 chegaram à mesma encruzilhada por caminhos diferentes — e apontam para lados distintos:

- A **matriz** diz que absorver o esforço extra para preservar a relação **vira expectativa**, e que o caminho é registrar o fato, estimar o impacto, suspender a parte afetada e propor aditivo antes de executar.
- O **MP-SC-01** institucionaliza a absorção como alternativa legítima, com débito das horas de conforto.

Os dois convivem se a absorção for limitada e medida — que é justamente o que o saldo de horas de conforto faz. Mas **a política de horas de conforto ainda não existe**, e sem ela a absorção não tem limite nem registro. Nesse estado, o fluxo autoriza exatamente o que a matriz alerta contra.

### A carteira e o Sucesso do Cliente

Recebido em 19/09/2026: o **Macroprocesso Comercial & Sucesso do Cliente** e o deck **Classificação da Carteira por Grupo Econômico**.

**A unidade de análise é o grupo econômico.** A carteira passou de 58 CNPJs para **31 unidades** — 15 grupos e 16 empresas independentes. A justificativa é sólida: as mesmas pessoas decidem por todas as empresas, a equipe atende o conjunto, e somar receita e custo revela a margem real sem a distorção do rateio. A consolidação expôs o que a visão por CNPJ escondia — um grupo com 1% de margem consolidada, outro com margem real de 79%, e um terceiro onde o grupo está saudável mas uma empresa dentro dele está a −53%.

**O retrato atual:** R$ 226.341 de receita mensal recorrente. Classe A com 6 unidades (19%), B com 12 (39%), C com 13 (42%), dentro da meta declarada. **69% da receita está na classe B.** E **41% da receita está travada por inadimplência**, concentrada em 5 grupos — incluindo os dois maiores, que têm margem alta e relação saudável, mas caixa retido.

**Como a classificação funciona.** Três instrumentos separados, cada um respondendo uma pergunta:

- **Score** — quanto vale, pela média ponderada de sete quesitos de estado: rentabilidade 25%, receita recorrente 20%, adimplência 15%, complexidade operacional 12%, potencial de cross-sell 12%, disciplina do cliente 9% e risco técnico 7%. Complexidade e risco entram invertidos. Gera a **letra A, B ou C**.
- **Semáforo** — como está a operação. Gera o **número 1, 2 ou 3**.
- **Eixo de ação** — com que urgência agir, cruzando risco de churn com a classe. Gera a **ação**, não a nota: classe A com churn alto é "reter já"; classe B, "reter e vigiar"; classe C, "saída organizada".

Dois alertas convivem com isso: **churn**, que só acende em A e B, porque só ali há o que salvar; e **inadimplência**, que aciona a **trava** — o grupo mantém a classe, recebe a marca "TRAVADO" e vai para cobrança.

**A margem é calculada, não estimada por percepção.** O método é o mesmo da Tabela de Precificação: horas-base por porte e mix de equipe, ajustadas por um **fator de atrito** (complexidade, indisciplina e risco técnico aumentam as horas), multiplicadas pelo custo/hora real por senioridade. Segue sendo estimativa, mas com memória de cálculo por cliente. **Sete clientes já aparecem como destruidores de valor.**

**Três públicos, uma classificação.** Liderança vê tudo e decide reter, reprecificar ou sair. Customer Success vê classe, classe efetiva, alertas e eixo de ação. Operação vê só a letra, o semáforo e os quesitos de esforço. **Mesmo dado, colunas diferentes.**

**O macroprocesso de reuniões.** Separa **Implantação** de **Em curso**. Na implantação: apresentar pontos sensíveis captados no comercial, apresentar a Critério (ferramentas, comunicação, equipe e SLAs), carta de rescisão do contador anterior, lista de documentos, entender o fluxo de informações e preencher o **KYC**. Em curso: apresentação mensal das demonstrações com gaps e ajustes, entender os óbices do cliente, **mapear as empresas de curva "A"**, revisar KPIs do fechamento, avaliar a entrega de documentos pelo cliente, discutir os **procedimentos de revisão analítica (PRA)** e definir o **dashboard contábil** do cliente.

> *Sugestão identificada pela análise:* o deck do macroprocesso tem caixas sobrepostas na mesma posição, o que sugere camadas de animação. Extraí o conteúdo, mas **a ordem exata das etapas de "Em curso" não é inequívoca**. Vale confirmar antes de virar tela.

## 6. Cenário Desejado

A entrevista é capturada no Granola e o resumo chega sozinho à oportunidade. A ficha de volumetria nasce do questionário e o que falta nela vira lista com responsável e prazo. O porte é registrado junto com os números que o sustentaram.

A proposta sai do CRM. Aceita, o contrato é emitido dos mesmos dados e vai ao Clicksign, com acompanhamento até voltar assinado. Assinado, a implantação começa e é acompanhada pelo responsável da área, com etapas visíveis e prazo.

Toda semana a equipe recebe lembretes de follow-up. Os KPIs do processo comercial ficam visíveis sem ninguém montar planilha. E quando você quiser fazer uma campanha, o CRM entrega a lista pronta.

## 7. Processos Identificados

1. Chegada do lead e classificação da origem.
2. Entrevista capturada no Granola, puxada para a oportunidade.
3. Preenchimento da ficha de volumetria.
4. Acompanhamento das informações que faltam para a proposta.
5. Qualificação: temperatura e porte.
6. Precificação registrada, com os direcionadores.
7. Emissão da proposta.
8. Follow-up semanal.
9. Decisão: aceita, recusada, on hold ou perdida, com motivo.
10. Emissão do contrato.
11. Assinatura pelo Clicksign, com acompanhamento.
12. Guarda do contrato assinado e controle de vigência.
13. **Reunião de handoff, com ata** (Comercial + CS + Implantação).
14. **Envio do pacote de handoff** à Implantação e ao CS.
15. **Mapeamento dos Customer Outcomes e da jornada do cliente**, pelo CS.
16. **Montagem do checklist de implantação** do cliente.
17. **Kick-off e alinhamento operacional.**
18. **Revisão de aderência ao escopo, pré-implantação**, com tratamento de desvio.
19. **Implantação por setor** — Contábil, Fiscal, DP e Financeiro.
20. **Revisão de aderência pós-implantação**, com tratamento de desvio.
21. **Operação do 1º mês e conferência contra a especificação.**
22. **Revisão dos ciclos de fechamento**, até três aprovados, com alinhamento de marco com o cliente.
23. **Marco "Operação"** — fim da implantação.
24. **Classificação do grupo econômico** — score, semáforo, classe efetiva e eixo de ação.
25. **Reuniões de resultado com o cliente**, com cadência ligada à classe.
26. **Tratamento dos alertas** — retenção para churn, cobrança para inadimplência.
27. **Decisão de carteira** — reter, reprecificar ou sair.
28. Relacionamento contínuo e listas para campanha.
29. Acompanhamento dos KPIs comerciais e de carteira.

## 8. Pessoas, Áreas e Papéis

| Pessoa ou área | Papel | Responsabilidade |
|---|---|---|
| Eduardo Luiz Silva | Solicitante, usuário e **aprovador das entregas** | Comercial e Customer Success; captação (EL) |
| Karine Nascimento | **Administradora do CRM** **(decisão tomada)** | Vê tudo |
| Demais usuários | **Alçada restrita** **(decisão tomada)** | Regra de alçada por perfil: pendência |
| BO, TC, FS, JC, MO, JS | Responsáveis pela captação | Origem das oportunidades |
| **Bruno Oliveira** | **Assina os contratos pela Critério** | — |
| **Bruno Soares** | **Implantação de contábil, fiscal e DP** (área nova) | Recebe o cliente |
| **Jefferson Souza** | **Implantação de BPO Financeiro** | Recebe o cliente |
| **Jefferson Cruz** | **Implantação de consultoria** | Recebe o cliente |
| **Analista de Implantação** | Papel do fluxo MP-SC-01 | Analisa contrato e contexto, monta o checklist, coordena os setores, confere a operação contra a especificação |
| **Times Operacionais** | Contábil, Fiscal, DP e Financeiro | Alinham o próprio setor e executam a operação do 1º mês |
| **Sucesso do Cliente (CS)** | Papel do fluxo MP-SC-01 | Mapeia outcomes e jornada, conduz as revisões de aderência, decide o débito de horas de conforto, revisa os ciclos de fechamento |

> **Ponto de atenção.** O fluxo separa **Comercial** e **CS** em duas raias, com papéis distintos: o CS conduz a revisão de aderência e decide a absorção; o Comercial é **consultado** quando há impacto contratual. Hoje os dois chapéus são seus. Isso não invalida o processo, mas o CRM deve registrar **em qual papel** cada decisão foi tomada — senão a distinção desaparece quando outra pessoa assumir uma das pontas.

## 9. Sistemas e Ferramentas Identificados

- **Granola (granola.app)** — entrevistas, com integração automática. **(decisão tomada)**
- **Clicksign** — assinatura digital. **(decisão tomada)**
- **Microsoft 365** — conta corporativa para login no CRM. **(decisão tomada)**
- **SharePoint** — onde vivem questionário, planilha de precificação, modelos de proposta e contratos.
- **WhatsApp Business** (número único da empresa) e **e-mail** — lembretes internos. **(decisão tomada)**
- **Nuvem já reservada** para esta aplicação. **(decisão tomada)** Provedor e região: pendência.
- **Excel** — planilha de performance comercial, fonte da carga de 2026.
- **Ferramenta de campanhas:** ainda não escolhida.
- **Omie:** sem integração. **(decisão tomada)**
- **PostgreSQL, Python e React.**

## 10. Documentos e Dados Utilizados

- Planilha de performance comercial (recorte de 2026).
- Notas de entrevista do Granola, template "[Potencial Cliente]" — **só o resumo entra no CRM** **(decisão tomada)**.
- `Questionario_BPO_Full_2026_v2.docx` — ficha de volumetria, 8 seções.
- `Planilha de Precificação.xlsx` — oficial.
- Modelos de proposta: BPO Full e BPO Financeiro (PowerPoint), mais a carta de consultoria.
- Modelos de contrato (pasta indicada por você).
- Contrato assinado e trilha de assinatura do Clicksign.
- **`matriz-objecoes.csv`** — 17 objeções com 18 campos, no SharePoint. **Entra no CRM como base viva. (decisão tomada)**
- **`KPI de Head de Novos Negócios.xlsx`** — 12 indicadores oficiais.
- **Macroprocesso Comercial & CS** e **deck de Classificação da Carteira**.
- **`MP-SC-01 — Implantação de Cliente, Rev.02`** — BPMN e legenda, recebidos em 19/09/2026. **Rascunho não aprovado.**
- **Ata de handoff**, **checklist de implantação** (a criar), **mapa de processo e sistema**, **lista de riscos**, **Customer Outcomes e jornada do cliente**, **registro de desvios de escopo** e **saldo de horas de conforto**.

## 11. Magnitude e Volume

| Item | Informação |
|---|---|
| Propostas em 2026 | 154: 66 recusadas, 40 aceitas, 22 on hold, 14 em avaliação, 12 a enviar |
| Implantações por ano | Referência: 40 aceitas em 2026 |
| Entrevistas de diagnóstico | 6 em 30 dias, de 39 reuniões |
| Por serviço em 2026 | BPO Contábil 68, Consultoria 60, Legalização 14, BPO Financeiro 7, Auditoria 3, outros 2 |
| Captação por pessoa | BO 57, EL 53, TC 17, FS 11, JC 7, MO 6, JS 3 |
| Canais distintos | 33 |
| Usuários hoje | 2 |
| Follow-up | Semanal |
| Tempo entre entrevista e proposta | Não identificado — vira KPI |
| Ciclo de venda | Não identificado — vira KPI |
| Prazo e orçamento do projeto | *Não identificado na fala do cliente* |

## 12. Resultado Esperado e Critérios de Sucesso

### 12.1 Critérios de sucesso do CRM

São os que você pediu para rever. *Sugestão identificada pela análise* — confirme ou corrija:

- 100% das oportunidades abertas com próxima ação e data de retorno.
- Nenhuma proposta marcada como aceita sem data de aceite.
- Todo preço registrado com porte e direcionadores, não só o valor final.
- Nenhuma informação perguntada duas vezes ao cliente entre a entrevista e a implantação.
- Toda oportunidade com entrevista tem o resumo do Granola ligado a ela.
- Toda implantação com responsável, etapas e prazo visíveis.
- Origem de todo lead classificada, sem grafias duplicadas.
- Carga de 2026 conferida contra a planilha (154 propostas) antes de abandonar o Excel.
- Ninguém mais abre a planilha de performance para consultar ou registrar.

### 12.2 KPIs — a lista oficial da Critério

**Substitui a proposta que eu tinha feito.** Fonte: `KPI de Head de Novos Negócios.xlsx`, SharePoint, lida em 19/09/2026. São **12 indicadores com fórmula, periodicidade, meta e alerta** já definidos. **(decisão tomada — adotados como estão)**

| # | KPI | Período | Meta | Alerta | O CRM calcula? |
|---|---|---|---|---|---|
| 1 | **MRR** — receita recorrente mensal | Mensal | R$ 400.000 | < R$ 200.000 | Sim, a partir dos contratos ativos |
| 2 | **NRR** — retenção líquida de receita | Trimestral | > 110% | < 90% | Sim, **se** registrar expansões, contrações e saídas |
| 3 | **CAC** — custo de aquisição | Mensal | — | — | **Não sozinho.** Depende de investimento em marketing e vendas, que o CRM não tem |
| 4 | **LTV** | Mensal | 3× o CAC | — | Sim, com histórico de retenção |
| 4b | **LTV / CAC** | Mensal | ≥ 3:1 | < 2:1 | Depende do CAC |
| 5 | **Taxa de conversão** | Semanal | 50% | < 30% | Sim |
| 6 | **Ticket médio** | Mensal | R$ 3.000 | R$ 2.000 | Sim |
| 7 | **Ciclo médio de vendas** | Mensal | 21–45 dias | > 90 dias | Sim, **assim que as datas existirem** |
| 8 | **Churn rate** | Mensal | 5% | > 7% | Sim, **se** registrar a saída do cliente |
| 9 | **Sales velocity** | Trimestral | 30 dias | > 60 dias | Sim, é derivado dos outros |
| 10 | **NPS** | Mensal | 50–74 | < 50 | **Não sozinho.** Exige pesquisa com o cliente |
| 11 | **ISC** — Índice de Saúde da Carteira | Mensal | 65–100 | < 65 | Sim — classe + semáforo + churn, ponderados por receita |
| 12 | **Forecast accuracy** | Trimestral | 85–110% | < 70% | **Não sozinho.** Exige previsão de receita no funil |

### 12.3 O que a lista de KPIs exige do CRM — e ainda não estava previsto

Quatro indicadores pedem coisas que nenhuma versão anterior modelava:

- **Encerramento de cliente.** O churn rate precisa de saída registrada, com data e motivo. O CRM controlava vigência, mas não a saída.
- **Expansão e contração de contrato.** O NRR separa expansão, contração e churn. Aditivo já estava previsto; **redução de escopo e reajuste, não.**
- **Previsão de receita.** O forecast accuracy compara realizado contra previsto. Sem previsão por oportunidade — probabilidade ou data esperada de fechamento — o indicador não existe.
- **Pesquisa de NPS.** Precisa ser disparada, respondida e registrada. A própria planilha sugere aplicá-la após momentos-chave, como o fechamento de balanço — o que se encaixa nas reuniões de resultado.
- **Investimento em marketing e vendas.** O CAC depende disso, e é dado que vive fora do CRM. Entra como lançamento manual por período, ou o indicador fica de fora.

### 12.4 Linha de base — onde a Critério está hoje

Cálculo meu sobre os dados de 2026 e o deck da carteira. **Confirme antes de usar:**

| KPI | Situação atual | Leitura |
|---|---|---|
| **MRR** | R$ 226.341 | **57% da meta** de R$ 400.000, acima do alerta de R$ 200.000 |
| **Taxa de conversão** | **38% ou 26%** | Ver abaixo — a definição muda o diagnóstico |
| **ISC** | Calculável hoje | A classificação já existe: A 19%, B 39%, C 42% |
| **Ciclo médio** | Não calculável | Faltam as 40 datas de aceite de 2026 |
| **Churn** | Não calculável | Saídas não são registradas em lugar nenhum |

> ⚠️ **A taxa de conversão depende de uma definição que precisa ser sua.** A fórmula da planilha diz "vendas fechadas ÷ **total de oportunidades trabalhadas**". Se o denominador forem só as propostas **já decididas** (106 em 2026), a taxa é **38%** — abaixo da meta de 50%, mas confortavelmente acima do alerta. Se forem **todas as 154**, incluindo as que seguem em aberto, a taxa é **26%** — **abaixo do alerta de 30%**.
>
> São diagnósticos opostos a partir do mesmo dado. Vale fixar a definição antes de o indicador ir para a tela, senão o alerta acende ou apaga conforme quem calculou.

### 12.5 Recortes e indicadores de cobertura

Os 12 KPIs medem **resultado**. Faltam os que medem se o processo está sendo seguido — e é neles que mora o seu objetivo de aumentar os pontos de contato. *Sugestão identificada pela análise*, complementar à lista oficial:

**Recortes dos KPIs oficiais.** Conversão, ticket médio e ciclo por **serviço**, por **tipo de canal** e por **captador**. O indicador total esconde onde está o problema — a conversão pode estar em 38% no agregado e em 15% num canal específico.

**Cobertura do processo**

| Indicador | Existe hoje |
|---|---|
| **Grupos com reunião de resultado na cadência devida** | Não |
| **Dias desde o último contato**, por grupo e por classe | Não |
| Migração de classe entre períodos — quem subiu, quem caiu | Não |
| Oportunidades abertas com próxima ação definida | Não |
| Oportunidades com ficha de volumetria completa | Não |
| Oportunidades com entrevista ligada | Não |
| Implantações no prazo e em atraso, por responsável | Não |
| Contratos com vigência a vencer em 90 dias | Não |

> **Os dois primeiros são o seu objetivo virando número.** "Aumentar os pontos de contato" só é verificável se houver onde registrar o contato e qual era a cadência devida.

**Dois recortes que a base de 2026 já permite**

- **Dependência de canal:** 86 das 154 oportunidades — **56%** — nasceram da rede dos sócios. É exatamente o que tráfego pago e afiliados tentariam reduzir.
- **Receita travada:** **41% do MRR** está retido por inadimplência, em 5 grupos. Isso não aparece no KPI de MRR, que conta a receita contratada. **O MRR pode estar saudável enquanto o caixa não entra.**

## 13. Restrições e Premissas

- **Escopo — implantação acompanhada. (decisão tomada, 19/09/2026)** O CRM não entrega o cliente e sai: acompanha até ele estar operando, com responsável, etapas e prazo. **Isso amplia o produto** de comercial para comercial + Customer Success. Duas consequências: o projeto cresce, e os responsáveis de implantação viram usuários do CRM, com alçada própria.
- **O fluxo de implantação é rascunho.** `MP-SC-01 Rev.02` não foi aprovado e traz cinco pendências próprias. **Construir tela de implantação antes da aprovação é retrabalho provável.** Recomendo que a parte comercial do CRM avance sem esperar, e a de implantação espere o fluxo ser aprovado.
- **Não existe checklist de implantação.** É pendência do próprio fluxo, não do CRM: falta conteúdo mínimo por setor, dono e formato. Sem ele, o gateway "Checklist cumprido?" não tem critério e a tela não tem o que mostrar.
- **Política de horas de conforto não formalizada.** Também pendência do fluxo: falta saldo por cliente, unidade, registro do débito e quem autoriza. O CRM precisa dela para controlar o saldo.
- **Alçadas de aprovação são presumidas** no fluxo, a validar com a Alta Direção. Isso inclui quem aprova aditivo e quem aprova absorção fora da política.
- **Tecnologias:** PostgreSQL, Python e React.
- **Design das telas: padrão Critério CRM (PAD-002), aprovado por Eduardo em 19/09/2026.** **(decisão tomada)** A fonte da verdade é o artefato do sistema, não a nota. *Ressalva:* a nota do PAD-002 vive na branch `docs/PAD-002-design-criterio-crm`, **ainda não mesclada à `main`** — enquanto isso não for feito, o padrão está aprovado mas não publicado para a casa.
- **Proposta e contrato seguem o manual da marca da Critério**, não o design do CRM. **A logomarca aparece sempre sozinha.**
- **Amostra das telas aprovada por Eduardo em 19/09/2026** — gate PF-07 cumprido. Seis telas em <https://claude.ai/artifact/2EiCBrFhPdvbniQWZgtgTK>. *As amostras de `Skeleton` e `Combobox` citadas no PAD-002 são item separado e seguem pendentes.*
- **Infraestrutura:** nuvem já reservada para esta aplicação. **(decisão tomada)** Provedor e **região do servidor** ainda pendentes — a região é onde ficam dados de clientes.
- **Ambientes separados** para teste e produção. **(decisão tomada)**
- **Backup automático**, nunca dependente de pessoa. **(decisão tomada)**
- **Login pela conta corporativa** Microsoft. **(decisão tomada)**
- **Quem aprova:** Eduardo. **(decisão tomada)**
- **O questionário de volumetria ganha uma seção 9, para a implantação.** **(decisão tomada, 19/09/2026)** Oito campos pedidos por Bruno Soares: estrutura societária, reestruturação em curso, certificado digital, procuração eletrônica, domicílios eletrônicos, documentos para transição, saldos a migrar e quem concede acessos. **Sete deles também alimentam porte ou risco técnico** — o pedido da implantação melhora a precificação de quebra. Texto pronto em [`onboarding-anexos/proposta-secao-9-questionario.md`](onboarding-anexos/proposta-secao-9-questionario.md). **Colado em 25/09/2026:** subiu como `Questionario_BPO_Full_2026_v3.docx` na mesma pasta do SharePoint, sem sobrescrever o v2. Falta o conferido visual antes de promover a v3 a oficial.
- **Unidade de cliente: grupo econômico.** **(decisão tomada)** Receita e custo somados, sem rateio. O CNPJ continua visível dentro do grupo, porque é onde a empresa deficitária aparece.
- **Perfis:** Karine administradora; demais usuários com alçada restrita. **(decisão tomada)** **O deck da carteira já resolve boa parte dessa regra:** são três visões sobre o mesmo dado — Liderança vê tudo, CS vê classe e ação, Operação vê só a letra e os quesitos de esforço. Adoto isso como ponto de partida dos perfis.
- **A classificação da carteira é calculada dentro do CRM.** **(decisão tomada, 19/09/2026)** As notas humanas são alimentadas no CRM; score, classe, classe efetiva, alertas, eixo de ação e ISC são calculados por ele. A planilha deixa de ser o sistema de registro. Modelo completo em [`modelo-classificacao-carteira.md`](modelo-classificacao-carteira.md).
- **Parâmetros versionados, não constantes de código.** Pesos, cortes de classe, réguas, matriz de horas e fator de atrito mudam com o tempo. Cada classificação guarda **qual versão dos parâmetros a produziu** — senão reclassificar o passado apaga a história.
- **Nenhuma fórmula é traduzida antes de decisão sobre os dois defeitos** encontrados nas planilhas (seção 7 do modelo). **A classe é uma só; o que muda é a coluna que cada perfil enxerga.**
- **Cadência de reuniões de resultado: mensal para A, trimestral para B, semestral para C.** **(decisão tomada, 19/09/2026)**
- **Quem atribui as notas humanas do Score, uma vez por mês:** **área técnica** avalia complexidade operacional, disciplina do cliente e risco técnico; **comercial** avalia potencial de cross-sell. **(decisão tomada)**
- **KYC, PRA e dashboard contábil do cliente entram no CRM**, como parte da avaliação de sucesso do cliente. **(decisão tomada)**
- **Os 12 KPIs oficiais são adotados como estão**, com fórmula, periodicidade, meta e alerta da planilha `KPI de Head de Novos Negócios`. **(decisão tomada)**
- **A Matriz de Objeções entra no CRM como base viva**, enriquecida a cada negociação. **(decisão tomada)**
- **A matriz orienta, a pessoa decide.** Ela carrega posições jurídicas e comerciais da casa, com faixas de escalonamento. O CRM **mostra** o precedente e **exige o registro** de quem decidiu — nunca concede automaticamente. Objeção com precedente `não` ou faixa `ESCALAR` avisa antes, não depois.
- **A matriz não substitui parecer jurídico.** É registro de negociação da casa, e as posições marcadas como "a validar" ou "ponto em aberto" continuam pendentes de decisão humana.
- **Precificação:** o CRM registra porte, direcionadores e preço, **guardando os dois valores quando há reajuste**, para medir o desconto concedido. **(decisão tomada)** A integração com a planilha fica para um segundo momento. **A IA não define preço.**
- **Preço de tabela** é o praticado, sujeito a desconto em negociação. **(decisão tomada)**
- **Fases:** a divisão em três fases **não ficou clara para você** e será rediscutida antes da construção. **(pendência)** A seção 18 traz uma explicação nova.
- **LGPD — decisão sua, registrada.** Você não pretende submeter ao jurídico a base legal para contatar lead perdido nem a guarda das transcrições. Fica registrado que: as listas de campanha incluirão leads perdidos; o CRM guardará resumos de entrevista com dado pessoal; e hoje **não se pede autorização de gravação**, embora você reconheça que deveria. O CRM terá marcador "não contatar" e controle de acesso, mas isso é medida técnica, não parecer jurídico. **Risco aceito por você.**
- **Fora do escopo:** envio de campanhas pelo CRM; dados de 2023 a 2025; comissionamento; roteiro da Descoberta do Cliente.

## 14. Oportunidades de Melhoria

- Listas padronizadas no lugar de texto livre.
- Empresa como cadastro único, com propostas, contratos e implantação ligados.
- Um único lugar com a conversa, os números, a proposta, o contrato e a implantação.
- Uma precificação por oportunidade, no lugar de uma cópia de planilha por proposta.
- Desconto medido, e não estimado.
- Visão de funil sem abas manuais.

## 15. Oportunidades de Automação

- Puxar o resumo da entrevista do Granola.
- Levar os números do questionário direto para a ficha de volumetria.
- Montar proposta e contrato a partir dos mesmos dados.
- Enviar ao Clicksign quando a proposta é aceita e atualizar a oportunidade quando volta assinada.
- Abrir a implantação automaticamente na assinatura, já com o responsável certo por serviço.
- Lembrete de contrato enviado e não assinado; de contrato com vigência a vencer; de implantação em atraso.
- Lembretes semanais de follow-up.
- Carga e padronização dos dados de 2026.

## 16. Oportunidades de Uso de IA

*Sugestão identificada pela análise.* A IA apoia; uma pessoa decide.

- Extrair do resumo da entrevista os campos da ficha de volumetria, para revisão.
- Apontar o que ainda falta para a proposta.
- Rascunhar o plano de implantação a partir do que a entrevista levantou.
- Apontar diferenças entre o combinado na entrevista e o escrito na proposta ou no contrato.
- **Reconhecer, no resumo da entrevista ou na negociação, qual objeção da matriz o cliente levantou** — e trazer o precedente da casa para quem está conduzindo. *É o uso de IA com maior retorno identificado até aqui: conhecimento que hoje depende de quem está na sala lembrar.*
- **Rascunhar a ficha de uma objeção nova** a partir do relato, para revisão antes de entrar no catálogo.
- Resumir o histórico antes do contato; sugerir próxima ação; apontar oportunidades paradas.
- Apoiar a padronização dos dados na carga.

> **A IA não define preço, não aprova contrato, não altera cláusula e não fecha escopo.** O roteiro de entrevista de vocês já separa o que o cliente disse do que é interpretação; o CRM preserva essa separação.

## 17. Necessidades Ocultas Identificadas

- **O CRM pode construir a regra de porte que hoje não existe.** Guardando o porte escolhido ao lado da volumetria que o sustentou, em alguns meses vocês terão dezenas de pares decididos por gente experiente — e a regra passa a ser leitura do que já fazem, em vez de invenção. Só funciona se o campo existir desde o começo.
- **Tabela de preço versionada**, com data de vigência, para que reabrir proposta antiga não mostre o preço de hoje.
- **Checklist de implantação por serviço**, já que os responsáveis e as áreas são diferentes.
- **Um só motor de horas.** *Sugestão identificada pela análise, e é a maior da versão.* A mesma lógica — horas por porte × mix de equipe × custo/hora — aparece hoje em **três lugares que não se falam**: a Tabela de Precificação define o preço da proposta; o fluxo de implantação debita horas de conforto quando absorve desvio; e o deck da carteira calcula a margem do grupo com horas-base ajustadas por fator de atrito. **É o mesmo cálculo, mantido três vezes.** Unificá-lo no CRM fecha o ciclo: o preço nasce de horas, o desvio consome horas, a margem revela se o preço estava certo, e a classe da carteira reflete isso. Nenhuma das três pontas hoje enxerga as outras duas.
- **Saldo de horas de conforto por cliente**, com cada débito ligado ao desvio que o causou.
- **Cadência de reunião por classe**, com data da última, data devida da próxima e alerta de atraso. *Sugestão identificada pela análise.* É o que transforma "aumentar os pontos de contato" em algo verificável.
- **Registro da reunião de resultado** — pauta, ata e encaminhamentos — ligado ao grupo. O Granola já faz isso para entrevistas comerciais; a mesma mecânica serve aqui.
- **Ocorrência de objeção**, separada do catálogo. *Sugestão identificada pela análise, e é o que faz a matriz aprender.* O catálogo tem 17 entradas; a ocorrência registra **cada vez que uma delas aparece numa negociação real** — com a resposta usada, quem decidiu e o desfecho. Em alguns meses, a matriz deixa de dizer "a resposta que funcionou" com base em um caso e passa a dizer com base em dezenas. **Sem separar catálogo de ocorrência, a matriz não enriquece: só é reescrita.**
- **Objeção ligada ao motivo de recusa.** Hoje se sabe que o cliente recusou por preço. Com a ligação, sabe-se qual objeção de preço, qual resposta foi tentada e se a casa tinha precedente para ela.
- **Histórico de classe**, para ver quem subiu e quem caiu entre períodos. Sem histórico, a classificação é uma foto.
- **Decisão de carteira registrada** — reter, reprecificar ou sair — com data, responsável e motivo.
- **Registro de desvios de escopo** com tratamento, responsável e data — e o retorno ao Comercial que o próprio fluxo exige, para corrigir o questionário e a qualificação das próximas propostas. *Sugestão identificada pela análise.*
- **Dois marcos, não um:** "checklist cumprido" fecha o pacote de implantação; **"Operação"** fecha a implantação inteira, depois de três ciclos de fechamento revisados. São indicadores diferentes.
- **Lista de pendências da oportunidade**, com responsável e prazo.
- **Riscos vistos na entrevista** viajando até a implantação.
- **Prazo de aviso prévio do fornecedor atual do cliente** como data que condiciona o início.
- Marcador "não contatar"; histórico de situações; cadastro de canais; relatório de conferência da carga.

## 18. O Que Será Realizado (Visão da Solução)

"Queremos construir o CRM da Critério para cuidar do cliente desde a primeira conversa até ele estar operando conosco.

A entrevista é capturada no Granola e o resumo chega sozinho à oportunidade. A partir dele e do nosso questionário, preenchemos a ficha de volumetria — o mesmo conteúdo que hoje vive em Word. Registramos o porte do cliente e os números que sustentaram esse julgamento.

A proposta sai do CRM, nos nossos dois modelos de BPO ou na carta de consultoria. Quando é aceita, o contrato é emitido com os mesmos dados e vai para o Clicksign, onde o Bruno Oliveira assina pela Critério. Acompanhamos até voltar assinado.

Aí começa a implantação, e o CRM continua. Contábil, fiscal e DP vão para o Bruno Soares; BPO Financeiro para o Jefferson Souza; consultoria para o Jefferson Cruz. Cada um vê o que precisa, com etapas e prazo, até o cliente estar operando.

Toda semana recebemos lembretes de follow-up. Os indicadores do comercial ficam à vista, sem ninguém montar planilha. E quando quisermos falar com a base, o CRM gera a lista.

Começamos pelos dados de 2026. Roda em nuvem, entramos pela conta da empresa, e a Karine administra."

### Sobre as fases — nova explicação

Você disse que a lógica não ficou clara. A divisão anterior era por dependência técnica, o que não ajuda a decidir. Refaço pelo **que você consegue fazer ao fim de cada etapa**:

| Etapa | Ao final dela, você consegue… | Por que nesta ordem |
|---|---|---|
| **1. Sair da planilha** | Registrar **grupo econômico** e seus CNPJs, lead, origem, volumetria, porte, preço e proposta. Ver o funil e os KPIs. A planilha de 2026 já dentro | É o núcleo. Tudo o mais se pendura aqui. O grupo econômico entra já nesta etapa: retrofitar a estrutura depois seria caro |
| **2. Fechar o ciclo** | Emitir contrato, assinar no Clicksign, acompanhar a implantação, receber lembretes de follow-up | Depende da oportunidade da etapa 1. Traz as integrações externas, com custo e prazo próprios. A parte de implantação espera o MP-SC-01 ser aprovado |
| **3. Cuidar da carteira** | Classificação viva do grupo, alertas de churn e inadimplência, eixo de ação, **cadência de reuniões de resultado** e decisões de carteira | **É o seu objetivo declarado.** Precisa da base de clientes da etapa 1, mas **não depende da etapa 2** — a carteira atual já existe e pode ser classificada antes de qualquer implantação nova |
| **4. Tirar trabalho manual** | Resumo do Granola chegando sozinho, listas de campanha, canais novos, cálculo de preço | Ganhos de produtividade sobre um sistema que já funciona |

> **A etapa 3 pode andar em paralelo com a 2.** São 31 unidades de análise que já existem e já estão classificadas em planilha — a carteira não espera a próxima venda. Se aumentar os pontos de contato é a prioridade, essa etapa sobe.

A regra é simples: **cada etapa entrega algo usável sozinho.** Se a etapa 2 nunca viesse, a 1 já substituiria a planilha. Se a 3 nunca viesse, vocês teriam o ciclo inteiro funcionando com um pouco mais de digitação.

Se a ordem não bate com a sua urgência, ela muda — mas vale decidir antes da construção, não durante.

## 19. Pontos que Precisam de Confirmação

**Decisões que ainda faltam**

1. **Definição da taxa de conversão** — o denominador são as oportunidades **decididas** (38%) ou **todas as trabalhadas** (26%)? *Um número está acima do alerta, o outro abaixo. Esta é a pergunta mais urgente da seção.*
1b. **Ticket médio de quê?** A meta é R$ 3.000. Venda nova, ou receita média por grupo na carteira? Hoje a receita média por unidade é de R$ 7.301 — muito acima da meta, o que sugere que a meta se refere a outra coisa.
1c. **Responsáveis de implantação** entram na visão Operação ou têm perfil próprio?
1d. **A margem da carteira segue estimada por porte, ou o CRM deve registrar horas reais?** *Registrar horas é outro projeto — timesheet. Não estou propondo, só nomeando a bifurcação.*
1e. **O que dispara a reclassificação?** Fechamento mensal, mudança de contrato, decisão em reunião?
1f. **CAC e NPS** dependem de dados que o CRM não tem. O investimento em marketing e vendas entra como lançamento manual? A pesquisa de NPS é disparada pelo CRM ou por fora?
1g. **Motivos de saída de cliente** — o churn precisa de lista controlada, como a de motivos de recusa. Quais são?
2. **Checklist, horas de conforto e aprovação do MP-SC-01** — sem resposta hoje. Ficam como dependência externa do módulo de implantação.
2b. **Os processos de BPO Financeiro e de consultoria** serão desenhados? Por quem e quando? *São dois dos três processos, e nenhum existe.*
2c. **Prazo por etapa** — sem ele, não há como medir atraso de implantação. Quem define?
2d. **A vigência do contrato começa na assinatura ou no marco Operação?**
3. **Etapas e fases** — a ordem da seção 18 está aprovada?
4. **KPIs** — a lista da seção 12.2 está correta? Falta algum? Sobra algum?
5. **Critérios de sucesso** — os da seção 12.1 estão certos?
6. **Região do servidor e provedor** da nuvem já reservada.
7. **A virada** — sua resposta "sim" ficou ambígua: rodar em paralelo com a planilha por um tempo, **ou** corte seco? E a planilha fica como consulta depois?
8. **Prazo e orçamento.**
9. ✅ *Respondido pelo fluxo:* "cliente operando" é o marco **Operação**, após três ciclos de fechamento revisados. Só falta confirmar que o CRM deve usar esse marco, e não o fechamento do checklist.

**Para eu buscar ou você me enviar**

10. **Modelos de contrato** — o link que você mandou é do Outlook e não consegui abrir. Me diga o caminho no SharePoint ou me mande os arquivos.
11. **Autorização de gravação** — você disse que deveria pedir. Quer que eu proponha um texto curto de ciência para usar antes das entrevistas?

**Confirmação sobre as planilhas**

12. Você disse que as divergências **não são intencionais**. Confirma que isso vale para as oito que listei no anexo técnico, incluindo a matriz de porte desligada do cálculo e as fórmulas faltando na aba de consultoria? *Essas duas geram preço errado hoje, na planilha em uso.*

## 20. Texto Final para Aprovação

A Critério vai construir um CRM próprio, em PostgreSQL, Python e React, rodando em nuvem e acessado pela conta corporativa, para substituir a planilha de performance comercial e cobrir o ciclo do cliente da primeira conversa até ele estar operando.

A entrevista, capturada no Granola com o template "[Potencial Cliente]", alimenta a oportunidade. A ficha de volumetria segue o questionário oficial da Critério. O porte do cliente e os direcionadores ficam registrados junto ao preço, com histórico quando há reajuste, o que permite medir o desconto concedido.

A proposta é emitida pelo CRM. Aceita, o contrato é emitido dos mesmos dados e assinado no Clicksign por Bruno Oliveira. Assinado, abre-se a implantação, acompanhada pelo responsável da área — Bruno Soares para contábil, fiscal e DP; Jefferson Souza para BPO Financeiro; Jefferson Cruz para consultoria — até o cliente estar operando. A vigência dos contratos é controlada.

O follow-up é semanal, com lembretes por e-mail e pelo WhatsApp Business da empresa. Os KPIs do processo comercial ficam disponíveis no próprio CRM. As campanhas são enviadas por ferramenta externa, a partir de listas geradas aqui. A carga inicial usa os 154 registros de 2026. Karine é administradora; os demais usuários têm alçada restrita. Sem integração com o Omie.

> Esse entendimento representa corretamente o que você deseja? Há algum ponto que você gostaria de corrigir, complementar ou remover?
