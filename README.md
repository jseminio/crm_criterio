# 📦 criterio-crm

CRM próprio para a atividade comercial da Critério. Substitui a planilha
"Relatório Performance Comercial 2026" e cobre o ciclo do começo ao fim:
entrevista capturada no Granola, lead, volumetria e precificação, proposta,
contrato com assinatura digital, passagem para a área técnica, follow-up e
listas para campanha.

## Onde estamos

| Item | Situação |
|---|---|
| Fase do pipeline | 🟪 Entendimento PF-01 Discovery |
| Gate à frente | ✅ Suficiência — o documento de negócio precisa da validação de Eduardo |
| Classe | a definir na próxima fase |
| Branch | `feat/crm-descoberta-negocio` |

## Conteúdo

- `documento-de-negocio.md` — versão 2.5, para leitura e aprovação de Eduardo.
- `anexo-tecnico.md` — versão 2.5, uso interno: resumo estruturado, mapa de
  campos derivado do roteiro de entrevista e bloco JSON.
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
- `tests/` — estrutura de testes criada no dia zero (seção 16.1 do Documento Fundador).

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

**Carteira e CS:** `Macroprocesso - Comercial & Sucesso do Cliente.pptx` e
`Categorizado de clientes Curva ABC_Final.pptx`, no OneDrive Frame Capital,
lidos em 19/09/2026. Nomes de cliente, receitas e margens **não** foram
copiados para cá — só o método de classificação.

**Entrevistas:** conector do Granola, consultado em 19/09/2026. Janela
disponível no plano atual: 21/08 a 18/09/2026, 39 reuniões, das quais 6 com o
roteiro de diagnóstico comercial.

Nem a planilha nem as notas do Granola estão copiadas para este workspace:
contêm dados de clientes. O `anexo-tecnico.md` guarda **apenas nomes de campo**
derivados da estrutura das notas, sem nenhum valor de cliente.

## Travas deste workspace

- Contexto isolado: nada daqui alimenta outro workspace, e nada de
  `workspaces/comercial-omie` entra aqui.
- Nada de `framework/` é copiado para cá.
- Dados de cliente nunca vão para `vault/09-Conhecimento/`.
- Nota de entrevista e contrato assinado exigem controle de acesso quando o
  sistema existir.
- Segredos (banco, provedor de e-mail, API de WhatsApp, API de assinatura,
  token do Granola) só em `.env` ou cofre.

## Pendências que travam o avanço

1. Validação do `documento-de-negocio.md` por Eduardo (gate de Suficiência).
2. As perguntas da seção 19 do documento, em dois blocos: as que travam o
   código (bloco A) e as que travam a modelagem.
3. **Decidir sobre as divergências das planilhas de precificação** (anexo
   técnico, seção b1.1) e **definir a regra de porte do cliente**. Nenhuma
   fórmula de preço é traduzida antes disso.
4. **Como a área técnica recebe o cliente hoje** — e se existe checklist.
5. Aprovação do PAD-002 antes de construir tela.
6. Versões oficiais do questionário de volumetria, dos modelos de proposta e
   do contrato.
7. Escolha da ferramenta de assinatura digital, com validade jurídica, trilha
   de auditoria e custo — e se há exigência de ICP-Brasil.
8. Forma de integrar o Granola: automática ou resumo colado à mão.
9. Viabilidade da API do WhatsApp Business para lembretes internos.
10. Validação jurídica: base legal para contatar lead perdido e guarda das
    notas e transcrições de entrevista.
