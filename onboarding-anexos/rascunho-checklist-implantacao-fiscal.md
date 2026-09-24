# Rascunho — Checklist de Implantação · Setor Fiscal (FISCAL)

> ⚠️ **RASCUNHO PARA VALIDAÇÃO. NÃO É PROCESSO APROVADO.**
> Proposta preparada em 19/09/2026 para **Bruno Soares** validar, cortar ou corrigir.
> Segunda das quatro listas de setor. A primeira é a do Contábil.

**Fonte de cada item:** `Q` = já perguntado no `Questionario_BPO_Full_2026_v2` · `B` = do BPMN `MP-SC-01` · `A` = proposta da análise, a partir das entrevistas de diagnóstico.

**Cada item tem:** situação · responsável (Critério ou Cliente) · prazo · evidência. "Não se aplica" exige justificativa.

> 🔴 **Aviso sobre legislação.** Este checklist **confirma quais obrigações se aplicam a cada cliente** — ele não é calendário fiscal nem fonte legal. O calendário de obrigações e prazos é mantido pela equipe fiscal da Critério, que acompanha a legislação vigente. As notas regulatórias da seção G trazem data de consulta e fonte.

---

## Bloco A — Pré-requisitos do handoff

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| A1 | Pacote de handoff completo (formulário, contrato, ata) | Critério | B | Anexos |
| A2 | Escopo fiscal contratado identificado, item a item | Critério | B | Trecho do contrato |
| A3 | O que **não** está no escopo fiscal, explicitado | Critério | A | Lista de exclusões |
| A4 | **Data-base de início da responsabilidade fiscal da Critério** | Ambos | A | Registro no plano |

> **A4 é diferente da data contábil.** A responsabilidade fiscal costuma começar numa competência específica, e obrigação entregue a menor não tem dono claro se a data não estiver escrita.

## Bloco B — Enquadramento e tributos

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| B1 | Regime tributário confirmado **por CNPJ** | Cliente | Q1 | Comprovante de enquadramento |
| B2 | Tributos incidentes mapeados: ISS, ICMS, IPI, retenções e demais | Ambos | Q5 | Lista por CNPJ |
| B3 | Municípios e UFs com atividade | Cliente | Q5 | Lista com inscrições |
| B4 | Inscrições estadual e municipal ativas e conferidas | Cliente | A | Comprovantes |
| B5 | Atividades e CNAEs conferidos contra a operação real | Ambos | A | Registro de divergências |
| B6 | Benefícios fiscais, regimes especiais ou incentivos vigentes | Cliente | Q5 | Ato concessório ou registro |
| B7 | Substituição tributária aplicável, quando houver | Ambos | A | Registro |

> **B5 vale o esforço.** CNAE que não reflete a operação real é origem de enquadramento errado. Numa das entrevistas, o cliente estava em regime inadequado havia anos e a correção gerou economia relevante — descoberta pelo CFO, não pelo contador.

## Bloco C — Acessos, certificado e domicílios eletrônicos

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| C1 | Certificado digital: tipo, titular, validade e forma de uso | Cliente | A | Registro com vencimento |
| C2 | Procuração eletrônica emitida, com escopo e prazo | Cliente | A | Comprovante |
| C3 | Acesso ao e-CAC concedido e **testado** | Cliente | A | Confirmação do analista |
| C4 | Acessos a SEFAZ estadual e prefeituras, conforme atividade | Cliente | A | Lista com teste |
| C5 | **Domicílios eletrônicos mapeados, com responsável por monitorar cada um** | Ambos | A | Lista nominal |
| C6 | Acesso ao sistema emissor de notas | Cliente | Q2 | Teste |
| C7 | Caixas de e-mail e canais que recebem comunicação de fisco | Cliente | A | Lista |

> 🔺 **C5 é o item mais sensível de todo o checklist, e conecta com a Matriz de Objeções.**
> A matriz registra uma objeção recorrente sobre a responsabilidade pelo controle de prazos tributários e domicílios eletrônicos — e a marca como **ponto em aberto da casa**, com instrução de escalar sempre que aparecer, porque a posição institucional sobre o dever de alerta ainda não está pacificada.
> Enquanto essa posição não existir, **o checklist não resolve a questão: ele a torna visível**. Registrar quem monitora cada domicílio, por escrito e por cliente, é a única proteção disponível hoje — para os dois lados.

## Bloco D — Obrigações acessórias

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| D1 | **Lista de obrigações aplicáveis a este cliente**, por CNPJ | Ambos | Q5 | Lista conferida com a equipe fiscal |
| D2 | Quem entregava cada obrigação antes, e em qual sistema | Cliente | A | Registro |
| D3 | **Obrigações em atraso ou não entregues** | Cliente | Q5 | Lista com competências |
| D4 | Histórico de entregas disponível, por competência | Cliente | A | Arquivos ou recibos |
| D5 | Obrigações com tratamento especial ou maior esforço | Cliente | Q5 | Registro |
| D6 | Calendário de obrigações montado para este cliente | Critério | A | Calendário no sistema |
| D7 | Primeira competência sob responsabilidade da Critério definida | Ambos | A | Registro |

> **D3 é passivo herdado.** Numa entrevista apareceu cliente com declarações não entregues e dívidas fiscais, atribuídas à omissão do fornecedor anterior — descobertas depois da troca. Quem assume o fiscal assume o passado; o mínimo é saber o tamanho dele antes.

## Bloco E — Parametrização e sistemas

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| E1 | Sistema fiscal definido e forma de troca de dados | Ambos | Q2 | Registro |
| E2 | Parametrização fiscal revisada: CFOP, CST, alíquotas, naturezas | Critério | A | Evidência de revisão |
| E3 | Captura automática de documentos fiscais configurada | Critério | A | Teste |
| E4 | Conciliação entre notas emitidas, recebidas e escrituração | Critério | A | Papel de trabalho |
| E5 | Integração entre sistema fiscal e contábil testada | Critério | Q2 | Teste com amostra |
| E6 | Tratamento de notas canceladas, denegadas e inutilizadas | Critério | A | Regra escrita |

> **E2 aparece nas entrevistas como lacuna recorrente:** sistema pouco parametrizado, com ajuste manual todo mês. Revisar na implantação custa horas uma vez; não revisar custa horas todo mês.

## Bloco F — Passivo e regularidade

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| F1 | Parcelamentos vigentes: valor, parcelas, vencimento | Cliente | Q5 | Extrato |
| F2 | Autos de infração e processos administrativos | Cliente | Q5 | Lista |
| F3 | Processos judiciais tributários | Cliente | Q5 | Lista |
| F4 | Certidões negativas: situação atual por esfera | Ambos | A | Certidões |
| F5 | **Certidões exigidas por clientes do cliente**, com frequência | Cliente | Q5 | Lista |
| F6 | Responsável por emitir e renovar certidões | Ambos | A | Registro |

> **F5 tem impacto comercial no cliente.** Numa entrevista, certidão vencida travava faturamento junto a um tomador. Isso não é rotina fiscal: é caixa do cliente.

## Bloco G — Reforma tributária (CBS e IBS)

*Bloco novo, específico do momento atual. Aplica-se a implantações a partir de 2026.*

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| G1 | Emissão de documentos fiscais eletrônicos **já preenche os campos de IBS e CBS** | Ambos | A | Amostra de documento emitido |
| G2 | Sistema emissor do cliente atualizado para os novos campos | Cliente | A | Versão e data |
| G3 | Impacto do novo modelo sobre a operação mapeado | Critério | A | Nota técnica ao cliente |
| G4 | Cliente com fornecedores PJ do Simples: impacto de crédito avaliado | Critério | A | Registro |
| G5 | Responsável por acompanhar a transição definido | Ambos | A | Registro |

> **📅 Referência regulatória — consultada em 19/09/2026.** 2026 é ano de transição, com alíquotas de teste de **0,9% de CBS e 0,1% de IBS**, em vigor desde 1º de janeiro. **Desde 3 de agosto de 2026, empresas do regime regular não podem emitir documento fiscal eletrônico sem preencher os campos de IBS e CBS**, e o período de carência de multas terminou em 1º de agosto. A apuração é informativa, e o valor pode ser compensado com PIS e Cofins — a dispensa de recolhimento depende do cumprimento das obrigações acessórias.
>
> **Isto é contexto para a implantação, não parecer.** Confirme com a equipe fiscal antes de usar com cliente.

> **G3 e G4 nascem de uma demanda de cliente, não de teoria.** Nas entrevistas, mais de um cliente disse esperar que o parceiro traga o impacto da reforma **proativamente**, sem ser provocado. E num caso de empresa de tecnologia, a Critério apontou que a maioria dos desenvolvedores é PJ do Simples, com impacto relevante de crédito. Isso é diferencial comercial, não obrigação.

## Bloco H — Operações específicas

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| H1 | Remessas e retornos | Cliente | Q5 | Registro |
| H2 | Importação e exportação | Cliente | Q5 | Registro |
| H3 | **Pagamentos de software ou serviços ao exterior** | Cliente | Q5 | Registro com tratamento |
| H4 | Operações interestaduais | Cliente | Q5 | Registro |
| H5 | **Retenções: volume, tipos e responsável pela apuração** | Ambos | Q5 | Registro |
| H6 | Notas de terceiros com tratamento especial | Ambos | A | Registro |

> **H3 e H5 vêm de casos reais.** Num cliente, pagamentos de software ao exterior recolhiam tributo indevido havia um ano — descoberto pelo próprio cliente, não pelo contador. Em outro, a apuração de impostos retidos foi declarada como **o maior esforço fiscal**, pelo volume de notas recebidas. Se isso não for dimensionado na implantação, aparece como desvio de escopo depois.

## Bloco I — Aderência ao escopo

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| I1 | Volume fiscal real conferido contra o formulário da proposta | Critério | B | Comparativo |
| I2 | Divergências classificadas: aditivo ou horas de conforto | CS | B | Registro da decisão |
| I3 | Divergências comunicadas ao Comercial | CS | B | Registro |

## Bloco J — O que fecha o setor fiscal

1. Nenhum item obrigatório dos blocos A a I pendente.
2. Enquadramento confirmado por CNPJ, com tributos e inscrições conferidos.
3. Certificado, procuração e acessos **testados**.
4. **Domicílios eletrônicos mapeados, com responsável nominal por cada um.**
5. Calendário de obrigações montado, com a primeira competência da Critério definida.
6. Obrigações em atraso levantadas e com plano de tratamento acordado.
7. Parametrização fiscal revisada e testada com amostra.
8. Campos de IBS e CBS preenchidos na emissão, verificado em documento real.
9. Passivo e certidões mapeados.
10. Mapa de processo e riscos do fiscal entregues.

## Prazos sugeridos

Contados do kick-off. **Proposta para contestar** — o fluxo MP-SC-01 não define prazo algum.

| Bloco | Prazo |
|---|---|
| A — Pré-requisitos | Antes do kick-off |
| B — Enquadramento | D+5 |
| C — Acessos e domicílios | D+10 — depende do cliente |
| D — Obrigações | D+15 |
| E — Parametrização | D+20 |
| F — Passivo | D+15 |
| G — Reforma tributária | D+15 |
| H — Operações específicas | D+15 |
| I — Aderência | Contínuo |
| **Setor implantado** | **D+30** |

## Perguntas para o Bruno Soares

1. A lista de obrigações (D1) deve ser um catálogo mantido pela equipe fiscal, e o checklist só marca quais se aplicam? *É o desenho que recomendo — evita duplicar legislação em cada cliente.*
2. Quem, na Critério, é dono do calendário de obrigações e o mantém atualizado?
3. O bloco G é permanente ou some quando a transição terminar?
4. O monitoramento de domicílio eletrônico entra no escopo padrão ou é serviço à parte? *Esta é a pergunta comercial escondida no item C5.*
5. Há itens do fiscal que dependem do contábil estar pronto? Isso muda a ordem dos setores.

## Pendências

- **O item C5 não tem solução técnica.** Depende da posição da casa sobre o dever de alerta, que a própria Matriz de Objeções marca como ponto em aberto.
- Os prazos são proposta, não medição.
- As notas regulatórias têm data de consulta e devem ser reconferidas antes de cada uso com cliente.

**Fontes das notas regulatórias:** [CGIBS — novo marco da Reforma Tributária](https://www.cgibs.gov.br/novo-marco-da-reforma-tributaria-inicia-em-03-de-agosto-com-preenchimento-obrigatorio-dos-campos-relativos-ao-ibs-e-a-cbs) · [FENACON — fase de testes em 2026](https://fenacon.org.br/reforma-tributaria/reforma-tributaria-entra-em-fase-de-testes-em-2026/) · [TecnoSpeed — destaque de IBS e CBS a partir de agosto/2026](https://blog.tecnospeed.com.br/destaque-de-ibs-e-cbs-agosto/)
