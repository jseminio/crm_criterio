# Rascunho — Checklist de Implantação · Departamento Pessoal (DP)

> ⚠️ **RASCUNHO PARA VALIDAÇÃO. NÃO É PROCESSO APROVADO.**
> Proposta preparada em 19/09/2026 para **Bruno Soares** validar, cortar ou corrigir.
> Terceira das quatro listas de setor. Falta o Financeiro.

**Fonte de cada item:** `Q` = já perguntado no `Questionario_BPO_Full_2026_v2` · `B` = do BPMN `MP-SC-01` · `A` = proposta da análise, a partir das entrevistas.

**Cada item tem:** situação · responsável · prazo · evidência. "Não se aplica" exige justificativa.

> 🔴 **Por que o DP é o setor mais arriscado da implantação.** Erro contábil aparece no fechamento; erro fiscal aparece na obrigação. **Erro de folha aparece no bolso do funcionário, no mesmo dia.** Nas entrevistas, foi o setor com as falhas mais concretas e o maior desgaste de relação — em um caso, uma correção para três colaboradores foi reprocessada e errou nove, com funcionários ligando para reclamar de desconto indevido. Desde então, o cliente confere 100% da folha à mão.

---

## Bloco A — Pré-requisitos do handoff

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| A1 | Pacote de handoff completo | Critério | B | Anexos |
| A2 | Escopo de DP contratado, item a item | Critério | B | Trecho do contrato |
| A3 | O que **não** está no escopo de DP | Critério | A | Lista de exclusões |
| A4 | **Competência de início da responsabilidade da Critério pela folha** | Ambos | A | Registro |
| A5 | **Primeira folha sob responsabilidade da Critério identificada** | Ambos | A | Mês e ano |

> **A5 não é detalhe.** Assumir a folha no meio de um mês, ou no mês do 13º, ou perto das férias coletivas, muda completamente o risco da primeira entrega. Vale escolher a competência, não herdá-la por acaso.

## Bloco B — Quadro e estrutura

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| B1 | Número de empregados CLT, por CNPJ | Cliente | Q3 | Lista |
| B2 | PJs e estagiários | Cliente | Q3 | Lista |
| B3 | **Distribuição por UF e localidade** | Cliente | Q6 | Lista |
| B4 | Modalidade: presencial, híbrido, remoto ou alocado em cliente | Cliente | Q6 | Registro |
| B5 | Volume médio de admissões e desligamentos por mês | Cliente | Q3 | Registro |
| B6 | Admissões, desligamentos ou afastamentos em curso na transição | Cliente | A | Lista nominal |
| B7 | Cargos, funções e estrutura hierárquica | Cliente | A | Organograma ou lista |

> **B6 é a armadilha clássica da virada.** Processo de admissão ou rescisão a meio caminho, com uma parte feita pelo fornecedor anterior e outra pela Critério. Precisa de dono nominal antes da virada.

## Bloco C — Sindicatos e convenções

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| C1 | Sindicatos aplicáveis, por categoria e localidade | Cliente | Q6 | Lista |
| C2 | CCTs vigentes, com data-base e vigência | Cliente | Q6 | Instrumentos |
| C3 | **Colaboradores sujeitos a CCT de outra localidade** | Cliente | Q6 | Lista nominal |
| C4 | Cláusulas com impacto em folha: piso, reajuste, benefícios, adicionais | Ambos | A | Resumo por CCT |
| C5 | Contribuições sindicais e assistenciais aplicáveis | Ambos | A | Registro |
| C6 | Calendário de data-base e reajustes | Critério | A | Calendário |

> 🔺 **C3 merece destaque.** Numa entrevista, o cliente reconheceu abertamente que "conta com a sorte" de a CCT da sede se aplicar a colaboradores em outros estados, por nunca ter sido questionado. **Isso é passivo latente, não rotina.** A implantação é o momento de registrar — e a decisão de tratar ou não é do cliente, não da Critério. O checklist garante que ela seja tomada com consciência, e por escrito.

## Bloco D — Acessos e sistemas

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| D1 | Sistema de folha definido: do cliente ou da Critério | Ambos | Q2 | Registro |
| D2 | Acesso ao sistema de folha concedido e **testado** | Cliente | A | Confirmação |
| D3 | Sistema de ponto identificado, com acesso testado | Cliente | Q2 | Confirmação |
| D4 | Integração ponto → folha testada | Critério | Q2 | Teste com amostra |
| D5 | Integração folha → contabilidade definida e testada | Critério | Q2 | Teste |
| D6 | Acesso ao eSocial, FGTS Digital e demais portais | Cliente | A | Teste |
| D7 | Certificado e procuração com escopo que cubra o DP | Cliente | A | Comprovante |
| D8 | Sistema de benefícios, quando houver | Cliente | Q6 | Registro |

> **D5 resolve um problema apontado nas entrevistas:** a folha sobe para a contabilidade por lançamento manual, e quando é alterada depois do fechamento, a contabilidade não fica sabendo. O resultado aparece errado e ninguém entende por quê. Integração testada, ou pelo menos regra de comunicação escrita.

## Bloco E — Migração de histórico

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| E1 | Histórico de folha disponível: quantos períodos e em que formato | Cliente | Q6 | Registro |
| E2 | Migração de cadastro de colaboradores conferida | Critério | A | Amostra conferida |
| E3 | **Saldos de férias conferidos, colaborador a colaborador** | Critério | A | Papel de trabalho |
| E4 | **Provisões de férias e 13º conferidas contra a folha real** | Critério | A | Papel de trabalho |
| E5 | Saldos de banco de horas migrados e conferidos | Critério | A | Papel de trabalho |
| E6 | Afastamentos, estabilidades e acordos em vigor | Cliente | A | Lista nominal |
| E7 | Rescisões em aberto ou verbas a pagar | Cliente | A | Lista |
| E8 | Divergências da migração registradas e tratadas | Ambos | A | Lista com dono |

> 🔺 **E4 vem de um caso documentado.** Numa entrevista, uma provisão de férias foi lançada com base em relatório de folha errado — cerca de 30% abaixo da folha real — e a contabilidade anterior lançou sem questionar. Só apareceu depois. **Conferir provisão contra folha real, na migração, é barato. Descobrir na auditoria, não.**
> **E5 também pesa:** banco de horas semestral com liquidação em datas fixas é passivo com valor. Migrado errado, vira discussão com o funcionário.

## Bloco F — Rotinas e calendário

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| F1 | **Corte do ponto**: dia e forma de envio | Ambos | Q6 | Registro |
| F2 | Data de fechamento da folha | Ambos | Q6 | Registro |
| F3 | Data de pagamento e antecedência exigida pelo financeiro | Ambos | Q6 | Registro |
| F4 | Adiantamento quinzenal ou folha complementar | Cliente | Q6 | Registro |
| F5 | Nível de conferência do ponto: quem confere e como | Ambos | Q6 | Registro |
| F6 | Responsável do cliente pelo envio de informações | Cliente | Q8 | Nome e contato |
| F7 | Canal e formato de envio das variáveis | Ambos | A | Registro |
| F8 | **Rotina de conferência da folha antes do pagamento** | Ambos | A | Regra escrita |
| F9 | Calendário anual: 13º, férias coletivas, data-base | Critério | A | Calendário |

> **F8 é onde a confiança se ganha ou se perde.** Se o cliente hoje confere 100% da folha à mão — como apareceu numa entrevista — isso é sintoma, não processo. A pergunta a fazer na implantação é: **o que precisa acontecer para ele parar de conferir tudo?** A resposta vira critério de sucesso do setor.

## Bloco G — Eventos variáveis e benefícios

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| G1 | Horas extras e banco de horas: regra, percentuais e liquidação | Ambos | Q6 | Regra escrita |
| G2 | Adicional noturno | Ambos | Q6 | Regra |
| G3 | Sobreaviso, com regra de acionamento | Ambos | Q6 | Regra |
| G4 | Periculosidade e insalubridade, com particularidades por colaborador | Ambos | Q6 | Lista nominal |
| G5 | Comissões e variáveis | Ambos | Q6 | Regra |
| G6 | Benefícios administrados no escopo | Ambos | Q6 | Lista |
| G7 | Descontos recorrentes | Ambos | A | Lista |
| G8 | Regras de rateio da folha por centro de custo ou projeto | Ambos | Q4 | **Mesma regra do checklist contábil (E4)** |

> **G4 aparece como causa de erro recorrente nas entrevistas:** adicional aplicado a quem não tinha direito, ou não aplicado a quem tinha. Lista nominal, não regra geral.
> **G8 é item compartilhado com o contábil.** Se as duas listas divergirem, a folha entra na contabilidade de um jeito e o gerencial espera outro. Preencher uma vez, referenciar nas duas.

## Bloco H — Tomadores e exigências externas

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| H1 | **Tomadores de serviço que exigem dados de folha** | Cliente | Q6 | Lista |
| H2 | Quais dados, em qual sistema e com qual prazo | Cliente | Q6 | Registro por tomador |
| H3 | **Faturamento do cliente condicionado a esse envio?** | Cliente | Q6 | Sim/não, com descrição |
| H4 | Responsável pelo envio a cada tomador | Ambos | A | Registro |
| H5 | Exigências de SST e documentos correlatos | Cliente | Q6 | Registro |

> 🔺 **H3 é o item de maior impacto comercial de todo o checklist de DP.** Numa entrevista, o cliente precisava fazer upload mensal de folha e encargos no sistema de um tomador — **sem isso, não conseguia faturar**. Uma entrega de DP atrasada não atrasa uma obrigação: trava o caixa do cliente. Se existir, isso muda a prioridade de toda a operação de folha.

## Bloco I — Obrigações e pendências

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| I1 | **Lista de obrigações de DP aplicáveis**, por CNPJ | Ambos | Q6 | Lista conferida com a equipe |
| I2 | Situação do eSocial: eventos pendentes, inconsistências, rejeições | Cliente | Q6 | Relatório |
| I3 | Situação do FGTS Digital | Cliente | A | Registro |
| I4 | Obrigações em atraso ou não entregues | Cliente | Q6 | Lista com competências |
| I5 | Quem entregava cada obrigação antes | Cliente | A | Registro |
| I6 | Ocorrências trabalhistas relevantes: processos, acordos, fiscalizações | Cliente | Q6 | Lista |
| I7 | Primeira competência de cada obrigação sob a Critério | Ambos | A | Registro |

> **📅 Referência regulatória — consultada em 19/09/2026.** A **DIRF foi extinta**, para fatos geradores a partir de 1º de janeiro de 2025. As informações que iam na declaração anual passaram a ser prestadas **mensalmente**: o **eSocial** cobre rendimentos e retenções de pessoas físicas, a **EFD-Reinf** cobre pagamentos e retenções envolvendo pessoas jurídicas, e a **DCTFWeb** consolida os débitos.
>
> **A consequência para a implantação é direta:** o que antes só aparecia na conferência anual agora aparece todo mês. Inconsistência de cadastro migrado não espera dezembro para doer. Isso reforça os blocos E e I.
>
> Contexto para implantação, não parecer. Confirme com a equipe antes de usar com cliente.

## Bloco J — Aderência ao escopo

| # | Item | Resp. | Fonte | Evidência |
|---|---|---|---|---|
| J1 | Volume real de DP conferido contra o formulário da proposta | Critério | B | Comparativo |
| J2 | Divergências classificadas: aditivo ou horas de conforto | CS | B | Registro |
| J3 | Divergências comunicadas ao Comercial | CS | B | Registro |

## Bloco K — O que fecha o setor de DP

1. Nenhum item obrigatório dos blocos A a J pendente.
2. Quadro conferido, com sindicatos e CCTs mapeados e colaboradores fora da sede tratados.
3. Acessos a folha, ponto, eSocial e FGTS Digital **testados**.
4. Integração ponto → folha → contabilidade testada, ou regra de comunicação escrita.
5. **Migração conferida**: cadastro, saldos de férias, provisões, banco de horas e afastamentos.
6. Calendário de folha acordado, com responsáveis nomeados dos dois lados.
7. Eventos variáveis com regra escrita, e periculosidade por lista nominal.
8. Exigências de tomadores mapeadas, com responsável por cada envio.
9. Situação do eSocial e obrigações em atraso levantadas, com plano.
10. **Primeira folha processada em paralelo ou simulação, conferida contra a do fornecedor anterior.**
11. Mapa de processo e riscos do DP entregues.

> **O item 10 é a única proteção real contra o erro de primeira folha.** Custa uma rodada de processamento. Vale a pena, e é o que eu mais recomendaria manter se a lista precisar encolher.

## Prazos sugeridos

| Bloco | Prazo |
|---|---|
| A — Pré-requisitos | Antes do kick-off |
| B — Quadro | D+5 |
| C — Sindicatos e CCTs | D+15 |
| D — Acessos | D+10 |
| E — Migração | D+20 — maior risco de atraso |
| F — Rotinas | D+10 |
| G — Variáveis | D+15 |
| H — Tomadores | D+10 |
| I — Obrigações | D+15 |
| **Folha paralela / simulação** | **D+25** |
| **Setor implantado** | **D+30**, antes da primeira folha real |

## Perguntas para o Bruno Soares

1. **A folha paralela (item 10) é viável em toda implantação, ou só acima de certo porte?** *É o item de maior proteção e maior custo.*
2. Quem, na Critério, é dono do calendário de obrigações de DP?
3. A análise de CCT para colaboradores fora da sede (C3) entra no escopo padrão ou é consultoria à parte? *É a pergunta comercial escondida neste checklist.*
4. Existe ordem obrigatória entre DP, contábil e fiscal? O DP alimenta a contabilidade, o que sugere que ele não pode fechar por último.
5. Este checklist muda conforme o cliente tenha 10 ou 300 empregados?

## Pendências

- A lista de obrigações (I1) deve vir de catálogo mantido pela equipe, não ser reescrita por cliente.
- O item G8, rateio de folha, é **compartilhado com o checklist contábil**. Definir onde ele mora.
- Prazos são proposta, não medição.
- As notas regulatórias têm data de consulta e devem ser reconferidas antes de cada uso.

**Fontes das notas regulatórias:** [Praxio — DIRF em 2026 após a extinção](https://blog.praxio.com.br/dirf/) · [Escola Superior SN — eSocial 2026 e fim da DIRF](https://escolasuperioresn.com.br/esocial-2026-mudancas-novos-eventos-obrigatorios/) · [THS Brasil — DCTFWeb, eSocial e EFD-Reinf](https://thsbrasil.com.br/dctfweb-esocial-efd-reinf-diferencas-o-que-vai-em-cada-obrigacao/)
