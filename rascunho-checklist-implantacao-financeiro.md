# Rascunho — Checklist de Implantação · Setor Financeiro (FIN)

> ⚠️ **RASCUNHO PARA VALIDAÇÃO. NÃO É PROCESSO APROVADO.**
> Proposta preparada em 19/09/2026 para **Bruno Soares** validar, cortar ou corrigir.
> Quarta e última das listas de setor — fecha o conjunto com Contábil, Fiscal e DP.

**Fonte de cada item:** `Q` = já perguntado no `Questionario_BPO_Full_2026_v2` · `B` = do BPMN `MP-SC-01` · `P` = do escopo do produto na tabela de precificação do BPO Financeiro · `A` = proposta da análise, a partir das entrevistas.

**Cada item tem:** situação · responsável · prazo · evidência. "Não se aplica" exige justificativa.

> 🔴 **Por que o Financeiro é diferente dos outros três.** O contábil registra o passado. O fiscal responde ao Estado. O DP paga pessoas, com erro que aparece no mesmo dia mas é corrigível. **O financeiro movimenta dinheiro que sai da conta do cliente e não volta.** É o único setor onde a Critério opera dentro do caixa de terceiro — e por isso o bloco de governança e alçadas vem antes de qualquer operação, não depois.

---

## Bloco A — Pré-requisitos e fronteira do escopo

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| A1 | Pacote de handoff completo | Critério | B | Anexos |
| A2 | Escopo financeiro contratado: contas a pagar, contas a receber, faturamento, cobrança, conciliação, fluxo de caixa | Ambos | Q7 | Lista marcada |
| A3 | Produto contratado: **BPO Financeiro, BPO Plus ou CFO as a Service** | Ambos | P | Registro |
| A4 | O que **não** está no escopo financeiro | Critério | A | Lista de exclusões |
| A5 | **Fronteira da movimentação bancária:** a Critério inclui pagamentos no banco, ou apenas prepara e submete à aprovação? | Ambos | P | Regra escrita |
| A6 | **Fronteira da cobrança:** até onde vai a Critério? | Ambos | A | Regra escrita |
| A7 | Competência de início da responsabilidade financeira | Ambos | A | Registro |

> 🔺 **A5 e A6 são as duas perguntas que definem o risco de todo o setor.**
>
> **A5** — o escopo do produto prevê inclusão de pagamentos no banco, numa frequência definida, sempre após submissão à aprovação. Isso significa que a Critério toca o caixa do cliente. **Quem aprova, com que alçada e com qual evidência precisa estar escrito antes do primeiro pagamento**, não depois do primeiro problema.
>
> **A6** — aqui há um ponto a esclarecer. O escopo do produto menciona **cobrança automática de valores inadimplentes**, enquanto a prática que conheço da Critério é **entregar o relatório e o cliente cobrar**. São coisas diferentes: emitir régua automática em nome do cliente, ou apontar quem está devendo. **Confirme qual é a fronteira, por cliente**, e registre. Isso muda esforço, risco reputacional e precificação.

## Bloco B — Bancos, contas e acessos

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| B1 | **Contas bancárias no escopo**, por banco e por CNPJ | Cliente | Q3 | Lista |
| B2 | Perfil de acesso de cada usuário da Critério, por conta | Cliente | A | Registro nominal |
| B3 | Acesso concedido e **testado**, com nível de permissão conferido | Cliente | A | Confirmação |
| B4 | **Nenhum acesso com poder de movimentação além do previsto em A5** | Ambos | A | Conferência formal |
| B5 | Tokens, certificados e dispositivos: titular e guarda | Cliente | A | Registro |
| B6 | Contas em plataformas de recebimento e gateways | Cliente | A | Lista |
| B7 | Aplicações, investimentos e contas de reserva | Cliente | A | Registro |
| B8 | Linhas de crédito, limites e garantias vigentes | Cliente | Q7 | Registro |

> **B4 é conferência, não confiança.** Perfil bancário costuma vir mais amplo do que o combinado, por comodidade de quem libera. A implantação é o momento de reduzir ao mínimo necessário — depois, ninguém mexe.
> **B1 dimensiona o serviço.** As faixas de preço do BPO Financeiro usam número de contas bancárias como um dos três direcionadores. Se a contagem real diferir da proposta, é desvio de escopo.

## Bloco C — Governança, alçadas e segregação

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| C1 | **Alçadas de aprovação de pagamento**, por valor e por tipo | Cliente | Q7 | Matriz de alçadas |
| C2 | Quem aprova, e substituto em ausência | Cliente | Q7 | Registro nominal |
| C3 | Forma de evidenciar a aprovação | Ambos | A | Regra escrita |
| C4 | **Segregação: quem prepara não aprova; quem aprova não executa** | Ambos | A | Desenho do fluxo |
| C5 | Calendário e prazos críticos de pagamento | Cliente | Q7 | Calendário |
| C6 | Tratamento de pagamento urgente fora do calendário | Ambos | A | Regra escrita |
| C7 | Política de guarda e envio de comprovantes | Ambos | A | Regra |
| C8 | Canal seguro para troca de dados bancários | Ambos | A | Registro |

> **C4 e C8 vêm de um diagnóstico direto.** Numa entrevista, um CFO experiente descreveu a realidade de empresas de médio porte como falta de governança: pagamentos feitos em cima da hora, arquivos sem criptografia, saldo de caixa não conciliado com a contabilidade. **Não é exceção — é o estado normal de quem contrata BPO Financeiro.** A implantação não pode assumir que o cliente já tem alçada formalizada; na maioria dos casos, a Critério vai ajudar a criar a primeira.
> **C6 é a válvula que costuma virar rotina.** Sem regra, todo pagamento vira urgente.

## Bloco D — Contas a pagar

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| D1 | **Cadastro de fornecedores conferido**: dados bancários, CNPJ, contato | Ambos | A | Amostra conferida |
| D2 | Origem e forma de entrada dos documentos a pagar | Ambos | Q7 | Registro |
| D3 | Regra de conferência antes da programação | Critério | A | Regra escrita |
| D4 | **Controle de duplicidade de pagamento** | Critério | A | Regra e teste |
| D5 | Programação de pagamentos: periodicidade e corte | Ambos | P | Calendário |
| D6 | Emissão de guias de retenção e impostos | Ambos | P | Registro |
| D7 | Pagamentos recorrentes e contratos de débito automático | Cliente | A | Lista |
| D8 | **Pagamentos ao exterior** | Cliente | Q7 | Registro com tratamento |
| D9 | Obrigações em atraso ou protestos pendentes | Cliente | A | Lista |

> 🔺 **D4 parece burocracia até acontecer.** Numa entrevista, um pagamento duplicado numa empresa de porte relevante só foi descoberto **por um terceiro**, meses depois. Controle de duplicidade é dos poucos itens que se pagam sozinhos na primeira ocorrência evitada.
> **D1 é pré-condição de D4.** Fornecedor cadastrado duas vezes, com grafias diferentes, é a origem mais comum da duplicidade.

## Bloco E — Contas a receber, faturamento e cobrança

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| E1 | **Cadastro de clientes conferido**: e-mail, telefone, endereço de cobrança | Ambos | A | Amostra conferida |
| E2 | Emissão de boletos e notas: sistema, volume e responsável | Ambos | P | Registro |
| E3 | Canais de recebimento mapeados: boleto, Pix, cartão, plataformas, recorrência | Cliente | A | Lista |
| E4 | **Conciliação e conferência dos valores recebidos** | Critério | P | Papel de trabalho |
| E5 | **Régua de cobrança: existe? qual? quem executa cada etapa?** | Ambos | A | Régua escrita |
| E6 | **Critério de classificação de inadimplência, e tratamento de renegociação** | Ambos | A | Regra escrita |
| E7 | Inadimplência atual e atraso médio | Cliente | Q7 | Número com data-base |
| E8 | **Duplicatas descontadas e antecipação de recebíveis** | Cliente | P | Registro com saldo |
| E9 | Política de negativação e protesto, se houver | Cliente | A | Regra |
| E10 | Volume mensal de boletos emitidos e cobranças realizadas | Cliente | Q7 | Números |

> 🔺 **E6 é o item que mais distorce número no financeiro.** Numa entrevista, o gestor descreveu com clareza como a renegociação mascara a inadimplência: o cliente deve R$ 500 mil, paga R$ 50 mil de entrada e renegocia o resto — e os R$ 450 mil **não entram como inadimplência do ano**. No fechamento, o caixa esperado não aparece e ninguém sabe por quê. **Se a regra de classificação não for escrita na implantação, o relatório de inadimplência nasce errado.**
>
> **E1 parece trivial e não é.** O mesmo diagnóstico apontou base de cadastro desatualizada — e-mail errado, telefone errado — como causa direta de cobrança falha. **Régua de cobrança impecável sobre cadastro sujo não cobra ninguém.**
>
> **E8 muda a leitura do caixa.** Num cliente, a antecipação de recebíveis era o mecanismo de sustentação da operação corrente. Quem assume o financeiro sem saber disso lê o extrato errado.

## Bloco F — Conciliação

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| F1 | **Conciliação bancária: frequência, responsável e forma** | Ambos | P | Regra escrita |
| F2 | Conciliação de cartão de crédito e adquirentes | Critério | P | Papel de trabalho |
| F3 | Conciliação de plataformas de recebimento e splits | Critério | A | Papel de trabalho |
| F4 | **Tratamento de lançamentos não identificados** | Ambos | A | Regra escrita |
| F5 | Tratamento de estornos, devoluções e cancelamentos | Ambos | A | Regra |
| F6 | **Conciliação entre o saldo financeiro e o contábil** | Ambos | A | Papel de trabalho |
| F7 | Operações trianguladas ou por parceria, que não passam pelo caixa | Cliente | A | Registro |

> **F2 dimensiona o preço.** Conciliações de cartão de crédito são o terceiro direcionador das faixas do BPO Financeiro, junto com documentos e contas bancárias.
> **F6 é a costura com o contábil.** Um dos diagnósticos apontou saldo de caixa que não batia com a contabilidade, sem que ninguém conciliasse os dois. Se o financeiro e o contábil da Critério não se conciliarem, a Critério reproduz o problema que veio resolver.
> **F7 vem de um caso real:** parceria em que as notas eram emitidas por terceiros e só a diferença passava pela empresa. A solução do cliente foi criar uma conta fictícia de ajuste no sistema, com lançamentos manuais. Funciona no contábil e mente no gerencial. Se existir, precisa aparecer aqui.

## Bloco G — Posição inicial e migração

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| G1 | **Saldos bancários iniciais conferidos com extrato**, por conta | Critério | A | Extratos na data-base |
| G2 | Contas a pagar em aberto na data-base | Cliente | A | Relatório conferido |
| G3 | Contas a receber em aberto na data-base | Cliente | A | Relatório conferido |
| G4 | Saldo de antecipações e duplicatas descontadas | Cliente | A | Extrato |
| G5 | Cheques, pagamentos agendados e débitos programados | Cliente | A | Lista |
| G6 | **Posição inicial conciliada com o Balanço de Abertura do contábil** | Ambos | A | Papel de trabalho |
| G7 | Divergências registradas e tratadas | Ambos | A | Lista com dono |

> **G6 é item compartilhado com o checklist contábil (bloco D).** Mesma data-base, mesmos saldos. Conferir uma vez e referenciar nos dois — se divergirem, o problema aparece no primeiro fechamento.

## Bloco H — Sistema financeiro

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| H1 | Sistema definido: do cliente ou implantado pela Critério | Ambos | P | Registro |
| H2 | **Se implantado pela Critério: usuários previstos no escopo** | Ambos | P | Lista nominal |
| H3 | Integração com o sistema contábil testada | Critério | Q2 | Teste |
| H4 | Integração bancária: extrato automático, remessa e retorno | Critério | A | Teste |
| H5 | Integração com plataformas de recebimento | Critério | A | Teste |
| H6 | Processos que seguirão manuais, e por quê | Ambos | Q7 | Lista |
| H7 | Controles paralelos em planilha que o sistema não cobre | Cliente | Q7 | Lista |

> **H2 é fronteira contratada.** O escopo do produto prevê implantação de sistema financeiro para um número limitado de usuários. Usuário a mais é desvio de escopo, não cortesia.
> **H6 e H7 valem mais do que parecem.** Nas entrevistas, os controles paralelos eram sempre a parte invisível do esforço — planilhas que ninguém menciona na proposta e que consomem horas todo mês. Listar na implantação é o que permite precificar ou eliminar.

## Bloco I — Fluxo de caixa e relatórios

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| I1 | Relatórios contratados e periodicidade | Ambos | Q7 | Lista |
| I2 | **Horizonte da projeção de caixa** | Ambos | A | Registro |
| I3 | Premissas da projeção: quem define e com que frequência revisa | Ambos | A | Regra escrita |
| I4 | Cenários, quando contratados | Ambos | P | Registro |
| I5 | Regra de alerta de furo de caixa: gatilho e destinatário | Ambos | P | Regra escrita |
| I6 | Reunião de acompanhamento: cadência e participantes | Ambos | P | Calendário |
| I7 | Dashboard financeiro: escopo e indicadores | Ambos | P | Desenho aprovado |

> **I3 protege a Critério e o cliente.** As premissas da projeção são do cliente — a Critério organiza, calcula e alerta. **Nenhuma premissa é criada pela Critério sem validação de quem responde pelo negócio**, e isso vale com ou sem apoio de ferramenta. Registrar quem define evita que a projeção vire opinião da contabilidade.
> **I5 é o entregável que o cliente mais valoriza**, segundo os diagnósticos: saber com antecedência quando vai faltar caixa. Definir o gatilho e o destinatário transforma isso em serviço, não em boa vontade.

## Bloco J — Aderência ao escopo

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| J1 | **Volumetria real conferida contra a faixa contratada:** documentos por mês, contas bancárias e conciliações de cartão | Critério | P | Comparativo |
| J2 | Divergências classificadas: aditivo ou horas de conforto | CS | B | Registro |
| J3 | Divergências comunicadas ao Comercial | CS | B | Registro |

> **J1 é o mais objetivo dos quatro setores.** O BPO Financeiro é o único produto da Critério em que a volumetria leva direto ao preço, por faixas explícitas. Conferir volume real contra faixa contratada é conta simples — e é a defesa mais limpa numa conversa de aditivo.

## Bloco K — O que fecha o setor financeiro

1. Nenhum item obrigatório dos blocos A a J pendente.
2. **Fronteiras de movimentação bancária e de cobrança escritas e acordadas.**
3. **Matriz de alçadas formalizada, com aprovador e substituto nomeados.**
4. Acessos bancários testados e **reduzidos ao mínimo necessário**.
5. Cadastros de clientes e fornecedores conferidos por amostra.
6. Posição inicial conciliada com extrato **e** com o Balanço de Abertura do contábil.
7. Régua de cobrança e critério de inadimplência escritos.
8. Rotina de conciliação definida, com tratamento de não identificados.
9. Sistema e integrações testados; controles paralelos listados.
10. Projeção de caixa rodando, com premissas validadas pelo cliente.
11. **Primeiro ciclo de pagamento executado em conferência dupla.**
12. Mapa de processo e riscos do financeiro entregues.

> **O item 11 é o equivalente financeiro da folha paralela do DP.** O primeiro ciclo com quatro olhos custa algumas horas. Um pagamento errado custa a confiança inteira — e, diferente da folha, não se corrige com acerto no mês seguinte.

## Prazos sugeridos

Contados do kick-off. **Proposta para contestar.**

| Bloco | Prazo |
|---|---|
| A — Fronteiras do escopo | Antes do kick-off |
| B — Bancos e acessos | D+10 — depende do cliente, costuma ser o gargalo |
| C — Governança e alçadas | D+10 — **antes de qualquer operação** |
| D — Contas a pagar | D+15 |
| E — Receber e cobrança | D+20 |
| F — Conciliação | D+20 |
| G — Posição inicial | D+15 — amarrada ao contábil |
| H — Sistema | D+20, ou mais se a Critério implantar |
| I — Fluxo de caixa | D+25 |
| J — Aderência | Contínuo |
| **Primeiro ciclo em conferência dupla** | **D+25** |
| **Setor implantado** | **D+30** |

> **C vem antes de D e E de propósito.** Nenhuma operação de pagamento começa antes da alçada estar escrita.

## Perguntas para o Bruno Soares

1. **A fronteira da cobrança (A6) é padrão da casa ou varia por cliente?** *O escopo do produto menciona cobrança automática de inadimplentes; a prática que conheço é entregar o relatório e o cliente cobrar. Preciso saber qual vale.*
2. **A Critério inclui pagamento no banco em toda implantação, ou existem clientes em que só prepara e submete?**
3. Existe matriz de alçadas padrão da Critério, ou cada cliente monta a sua?
4. Quando a Critério implanta o sistema financeiro, isso é etapa da implantação ou projeto à parte com prazo próprio?
5. O financeiro pode fechar antes do contábil, dado que o item G6 depende do Balanço de Abertura?
6. Este checklist muda entre **BPO Financeiro, BPO Plus e CFO as a Service**? *Os três têm escopos diferentes na tabela de precificação, e a fronteira entre eles ainda é hipótese em validação na Critério.*

## Pendências

- **A6 e A5 não são detalhe operacional: são fronteira de produto.** Nenhum dos dois se resolve no checklist.
- O item G6 é **compartilhado com o checklist contábil**. Definir onde mora.
- As faixas de volumetria do BPO Financeiro usam três direcionadores; confirmar se são os mesmos em 2026.
- Prazos são proposta, não medição.
- Este checklist assume o fluxo MP-SC-01, que cobre o setor Financeiro como um dos quatro. **Mas você confirmou que o BPO Financeiro tem processo de implantação próprio, com Jefferson Souza** — ainda não desenhado. Se o processo dele for diferente, este checklist serve ao setor FIN dentro de uma implantação de BPO contábil, e **não** a uma implantação de BPO Financeiro contratado sozinho. **Vale esclarecer antes de usar.**
