# Rascunho — Checklist de Implantação · Setor Contábil (CONT)

> ⚠️ **RASCUNHO PARA VALIDAÇÃO. NÃO É PROCESSO APROVADO.**
> Proposta preparada em 19/09/2026 a pedido de Eduardo Luiz, para **Bruno Soares** (responsável pela implantação de contábil, fiscal e DP) validar, cortar ou corrigir.
> Quem escreve não aprova: nada aqui vira regra sem o aceite de quem toca a implantação.

**Preenche qual lacuna.** O fluxo `MP-SC-01 Rev.02` tem o gateway **"Checklist de implantação cumprido?"** sem que o checklist exista. Esta é a primeira das quatro listas de setor (CONT, FISCAL, DP, FIN).

**De onde veio cada item.** A coluna *Fonte* diz a origem:

| Sigla | Significa |
|---|---|
| **Q** | Já é perguntado no `Questionario_BPO_Full_2026_v2` — **não se pergunta de novo**, só se confirma contra a realidade |
| **B** | Está no BPMN `MP-SC-01 Rev.02` |
| **A** | Proposta da análise, a partir das seis entrevistas de diagnóstico. **É o que mais precisa do seu crivo** |

**Como cada item se comporta.** Todo item tem: situação (pendente · concluído · não se aplica) · responsável (Critério ou Cliente) · prazo · evidência que comprova. Item marcado "não se aplica" exige justificativa — senão vira porta dos fundos.

---

## Bloco A — Pré-requisitos do handoff

*Sem este bloco completo, o setor contábil não abre. Espelha a regra do fluxo: pacote incompleto volta ao Comercial.*

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| A1 | Formulário da proposta recebido e completo | Critério | B | Documento anexado |
| A2 | Contrato assinado anexado | Critério | B | PDF do Clicksign |
| A3 | Ata da reunião de handoff anexada | Critério | B | Ata com decisões e pendências |
| A4 | Escopo contábil contratado identificado, item a item | Critério | B | Trecho do contrato |
| A5 | O que **não** está no escopo, explicitado por escrito | Critério | A | Lista de exclusões |

> **A5 merece atenção.** O contrato costuma dizer o que está incluído. O que gera desvio, aditivo e consumo de horas de conforto é justamente o que ninguém escreveu que estava fora.

## Bloco B — Identificação e estrutura

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| B1 | CNPJs no escopo confirmados, um a um | Cliente | Q1 | Lista conferida contra o contrato |
| B2 | Regime tributário confirmado **por CNPJ** | Cliente | Q1 | Comprovante de enquadramento |
| B3 | Filiais e localidades confirmadas | Cliente | Q1 | Lista com inscrições |
| B4 | Estrutura societária e participações mapeadas | Cliente | A | Contrato social ou organograma |
| B5 | **Data-base de início da responsabilidade da Critério** | Ambos | A | Registro no plano de implantação |
| B6 | Contabilidade anterior: responsável, contato e prazo de aviso prévio | Cliente | Q1 | Registro no CRM |
| B7 | Reestruturação societária em curso? | Cliente | A | Sim/não, com descrição |

> **B5 é o item mais importante do bloco.** A partir de qual competência a Critério responde pela contabilidade? Sem essa data escrita, a zona cinzenta entre a contabilidade anterior e a nova vira problema no primeiro fechamento. Nas entrevistas apareceu mais de uma vez contabilidade reapresentada de exercício anterior.

## Bloco C — Acessos e sistemas

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| C1 | Sistema contábil definido: do cliente ou da Critério | Ambos | Q2 | Registro no plano |
| C2 | Acesso concedido **e testado**, por usuário nomeado | Cliente | A | Print ou confirmação do analista |
| C3 | Certificado digital: tipo, titular, validade e forma de uso | Cliente | A | Registro com data de vencimento |
| C4 | Procuração eletrônica emitida, quando aplicável | Cliente | A | Comprovante |
| C5 | Forma de troca de dados: integração, arquivo ou manual | Ambos | Q2 | Registro por origem |
| C6 | Sistema de folha identificado e forma de contabilização definida | Ambos | Q2 | Registro |
| C7 | Sistema financeiro identificado e forma de integração definida | Ambos | Q2 | Registro |
| C8 | Migrações de sistema em curso do lado do cliente | Cliente | Q2 | Descrição e prazo |

> **C2 pede teste, não concessão.** "Acesso liberado" e "acesso funcionando" não são a mesma coisa, e a diferença só aparece no dia do fechamento.
> **C8 é condicionante de prazo.** Em uma das entrevistas, o cliente negociava troca de ERP ao mesmo tempo em que trocava de contabilidade. Implantar duas vezes é o risco.

## Bloco D — Balanço de Abertura e migração

*O bloco mais pesado, e o que mais atrasa implantação.*

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| D1 | **Balanço de Abertura** recebido, com data-base | Cliente | A | Arquivo |
| D2 | Balancete de encerramento da contabilidade anterior recebido | Cliente | A | Arquivo |
| D3 | Saldos conciliados — caixa e bancos | Critério | A | Papel de trabalho |
| D4 | Saldos conciliados — clientes | Critério | A | Papel de trabalho |
| D5 | Saldos conciliados — fornecedores | Critério | A | Papel de trabalho |
| D6 | Saldos conciliados — estoques, quando aplicável | Critério | A | Papel de trabalho |
| D7 | Saldos conciliados — imobilizado e depreciação acumulada | Critério | A | Papel de trabalho |
| D8 | Saldos conciliados — empréstimos e financiamentos | Critério | A | Papel de trabalho |
| D9 | Saldos conciliados — obrigações trabalhistas e provisões | Critério | A | Papel de trabalho |
| D10 | Saldos conciliados — tributos a recolher e parcelamentos | Critério | Q5 | Papel de trabalho |
| D11 | Divergências do Balanço de Abertura registradas e tratadas | Ambos | A | Lista com tratamento e responsável |
| D12 | Histórico contábil disponível: exercícios e formato | Cliente | Q2 | Registro |

> **D9 e D11 nascem de casos reais.** Numa das entrevistas, uma provisão de férias entrou com base em relatório de folha errado e a contabilidade anterior lançou sem questionar. O item D11 existe para que divergência vire registro com dono, e não silêncio.
> **D12 importa mais do que parece.** Se o histórico não vier, análise comparativa e fechamento anual ficam comprometidos — e isso deveria virar risco registrado, não surpresa.

## Bloco E — Plano de contas e estrutura gerencial

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| E1 | Plano de contas definido: do cliente, da Critério ou adaptado | Ambos | Q4 | Arquivo aprovado |
| E2 | Plano contempla natureza de serviço, centro de custo e projeto | Ambos | Q4 | Estrutura conferida |
| E3 | Centros de custo e projetos cadastrados, com quantidade confirmada | Ambos | Q4 | Cadastro no sistema |
| E4 | **Regra de rateio da folha formalizada por escrito** | Ambos | Q4 | Documento |
| E5 | Regra de rateio de despesas compartilhadas definida | Ambos | A | Documento |
| E6 | De-para entre plano antigo e novo concluído | Critério | A | Planilha de-para |
| E7 | Parametrização testada com lançamentos de amostra | Critério | A | Evidência de teste |

> **E4 é a que mais aparece nas entrevistas.** "O fornecedor não consegue ratear a folha por centro de custo" apareceu em mais de um diagnóstico, e o próprio questionário já pergunta se a regra é formalizada. Se a resposta lá foi "não", o item nasce como desvio de escopo, não como tarefa.
> **E7 evita o pior cenário:** descobrir erro de parametrização no primeiro fechamento real.

## Bloco F — Rotinas e calendário

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| F1 | Prazo de fechamento acordado e registrado | Ambos | Q4/Q8 | SLA no plano |
| F2 | Calendário de entregas do cliente definido | Ambos | A | Calendário compartilhado |
| F3 | Canal e formato de envio de documentos definidos | Ambos | A | Registro |
| F4 | Responsável do cliente pelo envio, nomeado | Cliente | Q8 | Nome, cargo e contato |
| F5 | Conciliação bancária: frequência e responsável | Ambos | Q3 | Registro |
| F6 | Tratamento de lançamentos não identificados definido | Ambos | A | Regra escrita |
| F7 | Relatórios contratados e periodicidade | Ambos | Q4 | Lista |
| F8 | Reunião de fechamento: existe, com que cadência e quem participa | Ambos | A | Registro |

## Bloco G — Auditoria e exigências externas

*Aplica-se quando houver. "Não se aplica" exige justificativa.*

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| G1 | Empresa é auditada: auditor, frequência e exigências | Cliente | Q4 | Registro |
| G2 | Exigências de fechamento da auditoria mapeadas | Ambos | Q4 | Lista |
| G3 | Padrão de notas explicativas exigido | Ambos | A | Registro |
| G4 | Certidões exigidas por clientes do cliente | Cliente | Q5 | Lista com frequência |
| G5 | Ressalvas ou reapresentações em exercícios anteriores | Cliente | A | Registro com descrição |

> **G5 é passivo herdado.** Uma das entrevistas trazia histórico de ressalvas e reapresentação de balanço. Quem assume a contabilidade assume esse histórico — e precisa saber disso antes, não durante a auditoria.
> Se o cliente contratar também o **FSCP**, os blocos E, F e G são o ponto de partida natural do mapeamento.

## Bloco H — Consolidação

*Só quando houver grupo econômico.*

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| H1 | Empresas do grupo no escopo identificadas | Cliente | A | Lista |
| H2 | Eliminações intercompany mapeadas | Ambos | A | Papel de trabalho |
| H3 | Movimentação de investimentos e equivalência definida | Ambos | A | Registro |
| H4 | Responsável pela consolidação: Critério ou cliente | Ambos | A | Registro |
| H5 | O sistema consolida ou a consolidação é manual | Ambos | A | Registro |

> **H5 vale a pergunta explícita.** Numa entrevista, a consolidação de um grupo de três empresas era feita inteiramente em Excel pelo próprio CEO, porque o ERP não suportava. Consolidação manual é esforço recorrente — se não estiver precificada, é desvio de escopo já na implantação.

## Bloco I — Aderência ao escopo

*Conecta o checklist às duas revisões de aderência do fluxo.*

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| I1 | Volumetria real conferida contra o formulário da proposta | Critério | B | Comparativo |
| I2 | Divergências classificadas: aditivo ou horas de conforto | CS | B | Registro da decisão |
| I3 | Divergências comunicadas ao Comercial | CS | B | Registro |

> O fluxo exige que **todo desvio, inclusive o absorvido**, volte ao Comercial para corrigir o formulário e a qualificação das próximas propostas. I3 é o que faz o aprendizado circular.

## Bloco J — O que fecha o setor contábil

*Proposta de critério objetivo para o gateway. Este bloco é o que mais precisa da sua decisão.*

O setor CONT só é dado como implantado quando:

1. Nenhum item obrigatório dos blocos A a I está pendente.
2. **Balanço de Abertura** registrado e conciliado, com divergências tratadas.
3. Plano de contas parametrizado e **testado** com lançamentos de amostra.
4. Acessos ativos e testados, com certificado digital válido.
5. Calendário de fechamento acordado com o cliente e com responsável nomeado dos dois lados.
6. **Primeiro balancete gerado**, ainda que em ambiente de teste.
7. Mapa de processo e sistema e lista de riscos do contábil entregues.
8. Desvios de escopo do setor tratados e comunicados.

---

## Prazos sugeridos

**O fluxo MP-SC-01 não define prazo para nenhuma etapa.** Sem prazo, "implantação em atraso" não existe como indicador. A proposta abaixo é ponto de partida para você contestar, contados a partir do kick-off:

| Bloco | Prazo sugerido |
|---|---|
| A — Pré-requisitos | Antes do kick-off. É condição de entrada |
| B — Identificação | D+3 |
| C — Acessos | D+10 — depende do cliente, costuma ser o primeiro gargalo |
| D — Balanço de Abertura | D+20 — depende da contabilidade anterior, é o maior risco de atraso |
| E — Plano de contas | D+15 |
| F — Rotinas | D+10 |
| G — Auditoria | D+15 |
| H — Consolidação | D+20 |
| I — Aderência | Contínuo, com fechamento junto do bloco J |
| **Setor implantado** | **D+30**, antes da operação do 1º mês |

## O que isso vira no CRM

Cada item é um registro com: bloco · descrição · obrigatório ou não · responsável (Critério ou Cliente) · situação · prazo · data de conclusão · evidência anexada · observação.

Três coisas caem de graça:

- **Item atrasado** e **implantação em atraso** passam a ser calculáveis.
- **Pendências do cliente** ficam separadas das da Critério — hoje tudo é "a implantação está atrasada", sem distinguir de quem é a bola.
- **Itens de fonte Q** podem vir **pré-preenchidos do questionário**, cumprindo o critério de nunca perguntar duas vezes ao cliente.

## Perguntas para o Bruno Soares

1. Algum bloco sobra ou falta?
2. Quais itens são **obrigatórios** e quais são opcionais? Eu não marquei nenhum — é decisão de quem toca.
3. Os oito critérios do bloco J fecham o setor, ou falta algo?
4. Os prazos fazem sentido? O D+30 é realista?
5. O checklist é **um só** ou muda conforme o porte do cliente?
6. Quem mantém a lista atualizada quando o processo mudar?

## Pendências que este rascunho não resolve

- **Não usei fonte regulatória.** Obrigações acessórias, prazos legais e exigências fiscais específicas ficaram deliberadamente fora: entram no checklist **Fiscal**, e devem ser escritas por quem acompanha a legislação vigente. Não inventei nenhuma.
- **Os prazos são proposta**, não medição. Ninguém mediu quanto leva uma implantação contábil na Critério.
- **Não sei quantos analistas de implantação existem**, o que afeta qualquer prazo.
- **Este checklist não serve para BPO Financeiro nem consultoria** — são processos distintos, ainda não desenhados.
