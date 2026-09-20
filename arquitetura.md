# Critério CRM — Arquitetura

**PF-08 · 19/09/2026 · Status: para revisão**

Escrito depois dos gates de Suficiência e Amostra aprovada. Define **o que o
sistema precisa sustentar**, não como cada tela é escrita. Nenhuma linha de
código foi escrita.

---

## 1. Premissas a confirmar

**As três foram fechadas.**

| Premissa | Situação | Consequência |
|---|---|---|
| **Região do servidor** | ✅ **Brasil — decisão de Eduardo em 19/09/2026** | Banco, arquivos e backup ficam em região brasileira. Vale também para os serviços que tocam dado de cliente |
| **A virada** | ✅ **Paralelo com a planilha — decisão de 20/09/2026** | A carga roda mais de uma vez: precisa ser **idempotente**, com identidade por conteúdo e não por número de linha |
| **Prazo** | ✅ **Primeira versão até sexta, 25/09/2026** — decisão de 20/09/2026 | Inverte E1 e E2/E3: o CRM roda local na semana, a nuvem vem depois. Ver `proposta.md`, seção 2 |
| **Orçamento** | ✅ **Sem teto declarado** — decisão de 20/09/2026: o ganho supera o gasto | Escolho a opção mais barata que atenda região Brasil e backup, e informo o valor **antes** de qualquer contratação |

Outras premissas menores estão marcadas ao longo do texto com *(a confirmar)*.

## 2. O que este modelo precisa sustentar

Seis exigências saíram do entendimento e mandam no desenho. Elas não são
desejáveis: são o que faz o sistema servir ou não.

**1 · O cliente é um grupo, a operação é por empresa.** A classificação, a
relação e a decisão são do grupo. O passivo, a nota fiscal e a folha são do
CNPJ. Os dois níveis coexistem, sempre.

**2 · Nada se pergunta duas vezes.** O que a entrevista levantou alimenta a
volumetria; a volumetria alimenta o preço, o contrato e a implantação. Um dado
tem uma origem e viaja.

**3 · Todo número precisa de memória de cálculo.** Preço, margem, score e ISC
são derivados. Quem olha precisa ver de onde vieram — é o que as planilhas
auditáveis da casa já fazem.

**4 · Toda nota humana tem dono, data e evidência.** Complexidade, disciplina,
risco, porte, churn e semáforo são julgamento. Sem procedência, viram opinião
anônima e o incentivo se instala.

**5 · Reclassificar o presente não pode reescrever o passado.** Parâmetros
mudam. A classificação de março tem que continuar sendo a de março.

**6 · Quem decide fica registrado, e em qual papel.** O fluxo separa Comercial
de CS; hoje as duas pontas são a mesma pessoa. O papel da decisão precisa
sobreviver à troca de gente.

## 3. Três padrões transversais

O modelo inteiro se apoia em três padrões que aparecem em quase toda entidade.
Vale implementá-los uma vez, bem.

### 3.1 Parâmetro versionado

Tudo que é régua tem vigência: pesos do Score, cortes de classe, réguas de
receita, rentabilidade e ISC, matriz de horas, mix por senioridade, custo/hora,
fator de atrito, teto de atrito, alíquota de imposto, cadência de reunião por
classe, faixas de porte.

```
parametro(chave, valor, vigente_de, vigente_ate, autor, motivo)
```

Todo cálculo guarda **qual conjunto de parâmetros usou**. Sem isso, a exigência
5 não se cumpre e o KPI de migração de classe fica sem sentido.

### 3.2 Nota humana com procedência

```
nota(entidade, quesito, valor, atribuida_por, atribuida_em, evidencia, observacao)
```

Guarda o histórico, não só o valor corrente. É o que permite ver a nota mudar,
e é a base do teste da régua de porte.

### 3.3 Derivado com memória

Valores calculados — preço, margem, Score, classe, ISC — são **armazenados**,
não recalculados na leitura, junto com as entradas que os produziram e a versão
de parâmetros. Recalcular na hora daria números que mudam sozinhos quando a
régua muda, que é exatamente o que não pode acontecer.

## 4. O modelo de dados

Cinco blocos. As entidades abaixo descrevem **o que guardar**, não o esquema
final — nomes e tipos ficam para a implementação.

### 4.1 Cliente

| Entidade | Guarda | Relações |
|---|---|---|
| **Grupo econômico** | Nome, situação, responsável de CS, data de entrada | 1 grupo → N empresas |
| **Empresa** | Razão social, CNPJ, regime, inscrições, localidade, situação | pertence a 1 grupo |
| **Pessoa de contato** | Nome, cargo, e-mail, telefone, papel (decisor, influenciador, usuário, ponto focal), **marcador "não contatar"** | ligada a empresa ou grupo |

> **Um grupo pode ter uma empresa só.** Isso não é exceção: é o caso mais comum
> da carteira, e tratá-lo como grupo desde o início evita a migração depois.

### 4.2 Comercial

| Entidade | Guarda |
|---|---|
| **Lead** | Origem em duas camadas (tipo de canal, canal), captador, interesse, temperatura, situação, próxima ação. Campos de campanha quando a origem for tráfego pago ou afiliado |
| **Oportunidade** | Grupo, serviços, situação, temperatura, responsável, datas de envio e decisão, motivo quando não avança |
| **Entrevista** | Referência ao Granola, data, participantes, **apenas o resumo**, ciência de gravação |
| **Ficha de volumetria** | As nove seções do questionário, cada campo com **origem** (entrevista ou questionário) e data |
| **Pendência da oportunidade** | O que falta para a proposta: item, responsável, prazo, situação |
| **Precificação** | Porte atribuído, direcionadores, horas-base, atrito, desconto, preço mensal e anual, margem estimada, **versão de parâmetros**, autor |
| **Proposta** | Modelo usado, versão, situação, documento gerado, histórico de preço quando há reajuste |
| **Ocorrência de objeção** | Oportunidade, objeção do catálogo, verbatim do caso, resposta usada, quem decidiu, concessão, desfecho |
| **Objeção (catálogo)** | Os 18 campos da matriz, incluindo precedente e faixa de tratamento |

> **Catálogo e ocorrência são separados.** É o que faz a matriz aprender em vez
> de ser reescrita.

### 4.3 Contrato

| Entidade | Guarda |
|---|---|
| **Contrato** | Grupo, escopo, valor, vigência, situação, documento assinado, trilha do Clicksign, signatários |
| **Evento de contrato** | Aditivo, reajuste, expansão, contração, renovação, **encerramento com motivo** |
| **Saldo de horas de conforto** | Saldo por cliente, com cada débito ligado ao desvio que o causou |

> O **evento de contrato** é o que torna o NRR calculável: ele separa expansão,
> contração e saída, que hoje não existem em lugar nenhum.

### 4.4 Implantação

| Entidade | Guarda |
|---|---|
| **Implantação** | Contrato, responsável, situação, datas, **marco "cliente operando"** |
| **Etapa** | Nome, ordem, responsável, prazo, situação — **configuráveis por serviço** |
| **Item de checklist** | Bloco, descrição, obrigatório, responsável (Critério ou cliente), prazo, evidência |
| **Desvio de escopo** | Descrição, momento (pré ou pós), tratamento (aditivo ou absorção), quem decidiu, data |
| **Customer Outcomes e jornada** | Resultados contratados na visão do cliente, marcos verificáveis, cadência |

> **Nada aqui é modelado em cima do MP-SC-01.** São três processos — contábil e
> fiscal e DP, BPO Financeiro, consultoria —, um em rascunho e dois
> inexistentes. Etapas, checklist e critério de conclusão são **dados**, não
> código.

### 4.5 Carteira e Sucesso do Cliente

| Entidade | Guarda |
|---|---|
| **Classificação** | Grupo, período, notas dos sete quesitos, semáforo, churn, Score, classe, classe efetiva, alertas, eixo de ação, **versão de parâmetros**, memória de cálculo |
| **Margem apurada** | Horas-base, atrito, horas ajustadas, custo de servir, honorário, impostos, margem, nota |
| **Reunião de resultado** | Grupo, data, pauta, ata, encaminhamentos, cadência devida |
| **Decisão de carteira** | Reter, reprecificar ou sair — com data, responsável, motivo e **papel em que decidiu** |
| **ISC** | Por período, com o peso de cada grupo e as três dimensões |

## 5. O motor de horas

**A descoberta estrutural mais relevante do projeto.** A mesma fórmula existe
hoje em quatro lugares que não se comunicam:

| Onde | Para quê |
|---|---|
| Tabela de Precificação | Formar o preço da proposta |
| Fluxo MP-SC-01 | Debitar horas de conforto ao absorver desvio |
| Planilha da carteira | Calcular margem e alimentar 25% do Score |
| Matriz de Objeções | Sustentar o teto de responsabilidade na negociação |

Todos usam horas por porte, mix de equipe e custo/hora por senioridade.

**No CRM isso é um serviço único**, com uma entrada e uma saída:

```
entrada:  porte ou horas manuais · notas de atrito · versão de parâmetros
saída:    horas-base · atrito · horas ajustadas · custo de servir · margem
```

Chamado pela precificação, pela classificação da carteira e pelo tratamento de
desvio. **Mantido uma vez.**

> ⚠️ **Nenhuma fórmula é traduzida antes de decisão humana** sobre os dois
> defeitos das planilhas: o churn sem célula e a possível inversão da
> disciplina no atrito.

## 6. Decisões técnicas

| Decisão | Escolha | Por quê |
|---|---|---|
| Banco | PostgreSQL | Definido por Eduardo |
| **Região** | **Brasil** | Decisão de Eduardo em 19/09/2026. Banco, arquivos e backup em região brasileira |
| Backend e frontend | Python e React | Definido por Eduardo |
| Autenticação | Conta corporativa Microsoft | Definido. Ninguém gerencia senha |
| Perfis | Liderança, Customer Success, Operação, Comercial, Implantação | As três primeiras vêm do deck da carteira: **uma classificação, três leituras** |
| Ambientes | Teste e produção separados | Definido por Eduardo |
| Backup | Automático, com restauração testada | Exigência explícita: "não funcionará se for humano" |
| Documentos | Guardados com controle de acesso | Contrato assinado e resumo de entrevista são dado sensível |
| Exclusão | **Nunca física.** Situação e histórico | Auditoria e a exigência 5 |
| Integrações | Granola, Clicksign, e-mail, WhatsApp Business | Sem Omie |

**Sobre permissão:** o deck da carteira dá a regra — *"modelo único = manutenção
única; dois modelos = duas atualizações, duas chances de divergir"*. O sistema
tem **uma classificação e uma base**; o perfil decide **quais colunas** se
enxerga, nunca qual tabela se lê.

## 7. O que fica fora

- **Cálculo automático de preço** — adiado por decisão de Eduardo. O CRM
  registra; a etapa seguinte calcula.
- **Envio de campanhas** — o CRM gera a lista, outra ferramenta envia.
- **Gestão da operação recorrente do cliente** — a implantação termina no marco
  "cliente operando".
- **Timesheet** — a margem segue estimada por porte e atrito. Registrar horas
  reais é outro projeto, e a bifurcação está nomeada.
- **Dados de 2023 a 2025** e **comissionamento**.
- **Roteiro da Descoberta do Cliente** no CRM.

## 8. Riscos

| Risco | Onde dói | Mitigação |
|---|---|---|
| **Dois defeitos nas planilhas** | Preço, margem, Score e classe | Nenhuma fórmula traduzida antes de decisão |
| **Escalas humanas inexistentes** | O CRM calcula, mas ninguém sabe o que avaliar | Escalas propostas, aguardando validação |
| **Três processos de implantação, um em rascunho** | Retrabalho no módulo | Etapas como dado, não código |
| **Risco de LGPD aceito por Eduardo** | Campanha com lead perdido e guarda de resumos sem validação jurídica | Marcador "não contatar", controle de acesso e só o resumo. Medida técnica, não parecer |
| **Comercial e CS na mesma pessoa** | A segregação some quando outra pessoa assumir | Registrar o papel da decisão, não só o autor |

## 9. O que falta para o planejamento

2. **Alçada dos perfis** — o que cada um vê e edita.
3. **Checklist de implantação** e **política de horas de conforto** — pendências
   do MP-SC-01, fora do controle deste projeto.
4. **Escalas humanas** validadas.
5. **Decisão sobre os defeitos** das planilhas.

**Nada disso trava o núcleo comercial.** Lead, grupo, oportunidade, volumetria,
proposta, funil, KPIs e a carga de 2026 podem ser planejados já — é a Etapa 1.
