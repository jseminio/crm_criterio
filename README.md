# 📦 criterio-crm

CRM próprio para a atividade comercial da Critério. Substitui a planilha
"Relatório Performance Comercial 2026" e cobre o ciclo do começo ao fim:
entrevista capturada no Granola, lead, volumetria e precificação, proposta,
contrato com assinatura digital, passagem para a área técnica, follow-up e
listas para campanha.

## Onde estamos

| Item | Situação |
|---|---|
| Fase | Construção — E2 e E3 entregues; E4, E5 e Etapa 2 (contratos) começados |
| Documento de negócio | Validado por Eduardo em 19/09/2026 |
| Amostra das telas | Aprovada por Eduardo em 19/09/2026 — https://claude.ai/artifact/2EiCBrFhPdvbniQWZgtgTK (6 telas, privada) |
| Proposta | Aprovada por Eduardo em 20/09/2026, inclusive a inversão E1 ↔ E2/E3 |
| Prazo | **Primeira versão até 25/09/2026**, decisão de Eduardo em 20/09/2026 |
| Design | **PAD-002, aprovado por Eduardo em 19/09/2026.** A fonte da verdade é o código: `app/frontend/src/tokens.css`. A nota original ficou no repositório do vortexOS e não é mais consultada |
| Regras de trabalho | [`CLAUDE.md`](CLAUDE.md) |

> **Projeto independente desde 23/09/2026.** O CRM nasceu dentro do vortexOS
> (`workspaces/criterio-crm`) e foi separado por decisão de Eduardo. Os
> documentos anteriores a essa data — documento de negócio, anexo técnico,
> proposta, planejamento, arquitetura — usam o vocabulário de lá (PF-xx, gates,
> RN-xx, "workspace"). São **registro histórico** das decisões e ficam como
> estão. As regras que valem daqui em diante estão no `CLAUDE.md`.

## Conteúdo

- `documento-de-negocio.md` — versão 2.7, **validado por Eduardo em 19/09/2026**.
- `anexo-tecnico.md` — versão 2.7, uso interno: resumo estruturado, mapa de
  campos derivado do roteiro de entrevista e bloco JSON.
- `proposta.md` — o que existe na sexta, o que não existe, o que depende de
  você e a inversão E1 ↔ E2/E3. **PF-09.5, ✅ aprovada em 20/09/2026.**
- `planejamento.md` — a Etapa 1 em cinco incrementos, com sequência,
  dependências e riscos. **PF-09.**
- `arquitetura.md` — modelo de dados, padrões transversais, decisões técnicas,
  o motor de horas unificado e os riscos. **PF-08, para revisão.**
- `proposta-secao-9-questionario.md` — texto pronto dos oito campos que entram
  no questionário (**decisão de 19/09/2026**), pedidos pela implantação.
  **O arquivo oficial no SharePoint não foi alterado.**
- `regua-de-porte-e-plano-de-teste.md` — **hipótese**: régua de porte por
  volume, fator de atrito na proposta, plano de teste em 3 passos e o mapa do
  questionário servindo preço, atrito e implantação (pedido de Bruno Soares).
  Nada entra no CRM antes do teste.
- `modelo-classificacao-carteira.md` — especificação do modelo de saúde da
  carteira, extraída das planilhas auditáveis: fórmulas, cortes, réguas,
  agregação por grupo e **dois defeitos encontrados**. É o que o CRM implementa.
- `rascunho-checklist-implantacao-contabil.md`
- `rascunho-checklist-implantacao-fiscal.md`
- `rascunho-checklist-implantacao-dp.md`
- `rascunho-checklist-implantacao-financeiro.md`
  — os quatro checklists de setor do `MP-SC-01`, para **Bruno Soares** validar.
  **Rascunhos, não aprovados.** Preenchem uma pendência do fluxo, não do CRM.
  Fiscal e DP trazem notas regulatórias com data de consulta (19/09/2026) e
  fonte — **não são calendário fiscal nem parecer**; o catálogo de obrigações é
  da equipe da Critério. O Financeiro deixa em aberto duas fronteiras de
  produto: movimentação bancária e cobrança.

**Itens compartilhados entre checklists** — preencher uma vez, referenciar nos dois:
rateio de folha por centro de custo (Contábil E4 ↔ DP G8) · posição inicial
conciliada com o Balanço de Abertura (Contábil D ↔ Financeiro G6).
- `tests/` — plano original de organização dos testes. Os testes que rodam estão em `app/`.

## Fonte dos dados

**Planilha:** `~/Downloads/03.Relatório Performance Comercial 2026 (1).xlsx`,
versão de 18/09/2026 às 14:57. Existe outra cópia, de 14:39, não utilizada.

**Precificação:** SharePoint, lido em 19/09/2026 — `Planilha de Precificação.xlsx`
(site Comercial, `01_Modelos Comercial/01. Proposta/`) e `Tabela de precificação
de consultoria e auditoria 1.xlsx` (OneDrive de Eduardo). Preços por hora,
custos e margens **não** foram copiados para cá: só a lógica e os direcionadores.

**Matriz de Objeções:** `matriz-objecoes.csv` — SharePoint, site Comercial,
`09_Governança comercial - IA/03_Matriz de objeções/`. Lida em 19/09/2026.
17 objeções, 18 campos. **Conteúdo não copiado para cá** — posições jurídicas e
estratégia de negociação. Só o esquema e as regras de comportamento.

**KPIs:** `KPI de Head de Novos Negócios.xlsx` — SharePoint, site Comercial,
`01. Ponto de Partida/04_Analises/`. Lida em 19/09/2026. 12 indicadores oficiais.

**Classificação da carteira:** três planilhas auditáveis em
`…/Classificação Curva ABC/Final/` — `Classificacao_Grupo_COMPLETO.xlsx`,
`Rentabilidade_Grupo_COMPLETO.xlsx` e `Faturamento_Grupo_COMPLETO.xlsx`.
Lidas em 19/09/2026. **Fórmulas e parâmetros** foram extraídos para
`modelo-classificacao-carteira.md`; **nenhum nome de cliente ou valor
individual** foi copiado.

**Carteira e CS:** `Macroprocesso - Comercial & Sucesso do Cliente.pptx` e
`Categorizado de clientes Curva ABC_Final.pptx`, no OneDrive Frame Capital,
lidos em 19/09/2026. Nomes de cliente, receitas e margens **não** foram
copiados para cá — só o método de classificação.

**Entrevistas:** conector do Granola, consultado em 19/09/2026. Janela
disponível no plano atual: 21/08 a 18/09/2026, 39 reuniões, das quais 6 com o
roteiro de diagnóstico comercial.

Nem a planilha nem as notas do Granola estão copiadas para este projeto:
contêm dados de clientes. O `anexo-tecnico.md` guarda **apenas nomes de campo**
derivados da estrutura das notas, sem nenhum valor de cliente.

## Travas deste projeto

- Dados de cliente não entram no repositório: nem planilha, nem nota de
  entrevista, nem saída de script de conferência.
- Nota de entrevista e contrato assinado exigem controle de acesso quando o
  sistema existir.
- Segredos (banco, provedor de e-mail, API de WhatsApp, API de assinatura,
  token do Granola) só em `.env` ou cofre.

## Pendências que travam o avanço

1. **Instalar o PostgreSQL** na máquina de Eduardo. Não há Postgres, Docker nem
   Homebrew — sem banco a semana não anda.
2. **Confirmar as linhas 317 e 318 da planilha** com a Karine: idênticas em
   todos os campos, inflam contagem e valor do funil.
2. As perguntas da seção 19 do documento, em dois blocos: as que travam o
   código (bloco A) e as que travam a modelagem.
3. **Decidir sobre as divergências das planilhas de precificação** (anexo
   técnico, seção b1.1) e **definir a regra de porte do cliente**. Nenhuma
   fórmula de preço é traduzida antes disso.
4. **Conferir o defeito 7.2 do modelo de carteira** — se o fator de atrito
   inverte a disciplina. Afeta margem, Score e classe.
5. **Definir as escalas 1–5 das notas humanas**, o critério do semáforo e a
   escala de churn. Sem elas o CRM calcula, mas ninguém sabe o que avaliar.
6. Versões oficiais do questionário de volumetria, dos modelos de proposta e
   do contrato.
7. Escolha da ferramenta de assinatura digital, com validade jurídica, trilha
   de auditoria e custo — e se há exigência de ICP-Brasil.
8. Forma de integrar o Granola: automática ou resumo colado à mão.
9. Viabilidade da API do WhatsApp Business para lembretes internos.
10. Validação jurídica: base legal para contatar lead perdido e guarda das
    notas e transcrições de entrevista.
