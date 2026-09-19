# Modelo de Classificação da Carteira — especificação para o CRM

**Levantado em 19/09/2026** a partir das três planilhas auditáveis em
`…/Classificação Curva ABC/Final/`: `Classificacao_Grupo_COMPLETO.xlsx`,
`Rentabilidade_Grupo_COMPLETO.xlsx` e `Faturamento_Grupo_COMPLETO.xlsx`.

**Todas as fórmulas abaixo foram lidas das células, não inferidas do deck.**
Este documento é a especificação do que o CRM deve calcular. **Dois defeitos
foram encontrados e estão na seção 7** — nenhum deles é traduzido para código
antes de decisão humana.

---

## 1. Score

```
Score = NotaReceita    × 0,20
      + NotaRentab.    × 0,25
      + Cross-sell     × 0,12
      + (6 − Compl.)   × 0,12
      + Disciplina     × 0,09
      + (6 − Risco)    × 0,07
      + Adimplência    × 0,15
```

Todas as notas na escala **1 a 5**. Complexidade e risco técnico entram
invertidos como `(6 − nota)`, para que maior signifique melhor em todos os
quesitos. A soma dos pesos é 100%.

## 2. Classe

```
Classe = A  se Score ≥ 3,95
         B  se Score ≥ 3,35
         C  caso contrário
```

**Cortes fixos**, não percentis. Ao valor soma-se o sufixo do **semáforo
operacional** (1, 2 ou 3), formando `A1`, `B3`, `C2` e assim por diante.

> ⚠️ **Assimetria a decidir.** A classe usa **corte fixo**; a nota de receita
> usa **percentil da carteira** (seção 4). Quando a carteira mudar, a nota de
> receita se recalibra sozinha e o corte de classe não. Isso pode ser
> intencional — ou não.

## 3. Trava, alertas e eixo de ação

| Regra | Condição | Efeito |
|---|---|---|
| **Trava de inadimplência** | Adimplência ≤ 2 | Classe recebe o sufixo `(TRAVADO)`. **Não rebaixa a classe** |
| **Alerta `$$$`** | Adimplência ≤ 2 | Marca de cobrança |
| **Alerta de churn** | Churn ≥ 4 | `⚠` se classe A ou B · `⚑` se classe C |

**Eixo de ação**, nesta ordem de precedência:

1. `$$$` → **Cobrança — sem tratamento preferencial**
2. `⚠` + classe A → **Reter já (crítico)**
3. `⚠` + classe B → **Reter / vigiar**
4. `⚑` → **Saída organizada**
5. nenhum → **Sem urgência de churn**

## 4. Nota de receita — régua por percentil

Cortes apurados sobre as 31 unidades da carteira:

| Nota | Honorário mensal |
|---|---|
| 1 | abaixo de R$ 1.368,07 (p20) |
| 2 | até R$ 2.104,73 (p40) |
| 3 | até R$ 4.735,63 (p60) |
| 4 | até R$ 9.652,39 (p80) |
| 5 | acima disso |

**No CRM, estes valores são parâmetros**, recalculáveis quando a carteira mudar.

## 5. Nota de rentabilidade — régua por margem

| Nota | Margem |
|---|---|
| 1 | abaixo de 30% — destrói valor |
| 2 | 30% a 45% |
| 3 | 45% a 60% — aceitável |
| 4 | 60% a 70% |
| 5 | 70% ou mais |

### Como a margem é calculada

```
horas_base      = matriz de horas por porte
atrito          = MIN( atrito_complexidade
                     + atrito_indisciplina
                     + atrito_risco, teto )
horas_ajustadas = horas_base × (1 + atrito)
custo_servir    = horas_ajustadas × custo_hora_ponderado(porte)
margem          = (honorário − impostos − custo_servir) ÷ honorário
```

Impostos a **11%**. Teto de atrito: **1,5**.

**Matriz de horas por porte:** Micro 5 · Pequeno 10 · Médio 16 · Grande 40 ·
Extra Grande 80 horas por mês, cada porte com seu mix de senioridade, que
define o custo/hora ponderado.

**Fator de atrito por nota**, idêntico nos três quesitos:

| Nota | Acréscimo de horas |
|---|---|
| 1 — cliente ótimo | 0% |
| 2 | 5% |
| 3 — normal | 10% |
| 4 | 30% |
| 5 — cliente crítico | 50% |

Os três acréscimos **somam**. A planilha registra: *"Indisciplina é o inverso da
nota de Disciplina"* — ou seja, o índice correto é `6 − disciplina`.

**Há um ajuste manual de horas** que sobrepõe a matriz quando preenchido.

## 6. ISC — Índice de Saúde da Carteira

Indicador único de 0 a 100, ponderado pela **participação de cada grupo na
receita total**.

**Réguas de conversão**

| Dimensão | Conversão |
|---|---|
| Classe | A = 100 · B = 60 · C = 20 |
| Semáforo | 1 = 100 · 2 = 50 · 3 = 0 |
| Churn | 1 = 100 · 2 = 80 · 3 = 60 · 4 = 20 · 5 = 0 |

**Pesos:** classe 33% · semáforo 33% · churn 34%.

```
peso_grupo = receita_grupo ÷ receita_total
ISC = Σ ( (classe×33% + semáforo×33% + churn×34%) × peso_grupo )
```

Meta 65–100; alerta abaixo de 65 (planilha oficial de KPIs).

## 7. Defeitos encontrados nas planilhas

**Nenhuma fórmula é traduzida para código antes de decisão humana sobre estes
dois itens.**

### 7.1 — O churn não tem célula: está escrito dentro da fórmula

A coluna de alerta de churn traz o valor **literal na própria fórmula**:
`=IF(5>=4; …)`, `=IF(1>=4; …)`. **Não existe coluna de churn na planilha.**

Distribuição dos literais nas 31 unidades: 18 com `1`, 9 com `5`, 2 com `2`,
1 com `4`, 1 com `3`.

**Consequências**

- O dado que comanda o eixo de ação **não tem onde ser editado** — mudar o
  churn de um grupo exige editar a fórmula.
- A regra de agregação declara *"churn: maior do grupo"*, mas não há células
  para agregar.
- A aba do ISC lê o churn de **outra fonte**, numa coluna própria. As duas
  podem divergir sem que nada acuse.

**No CRM isso se resolve sozinho:** churn vira campo, com dono, data e
histórico — e passa a alimentar tanto o eixo de ação quanto o ISC.

### 7.2 — O fator de atrito parece usar disciplina sem inverter

A planilha de rentabilidade documenta, na própria aba de auditoria, que o
índice deve ser `6 − disciplina`. A fórmula da coluna de atrito, porém, indexa
a tabela de indisciplina **diretamente com a coluna Disciplina**, sem a
inversão.

**Se estiver mesmo invertido, o efeito é grave e silencioso:**

| Cliente | Disciplina | Atrito aplicado | Atrito correto |
|---|---|---|---|
| Muito organizado | 5 | **+50%** | 0% |
| Muito desorganizado | 1 | **0%** | +50% |

O cliente disciplinado carregaria o custo do bagunçado, e vice-versa. Como a
margem alimenta 25% do Score, o erro propaga para a nota de rentabilidade, o
Score, a classe e o ISC.

**Não confirmei se a coluna Disciplina já é preenchida invertida na prática.**
Se for, a fórmula está certa e a documentação é que engana. **Precisa de
conferência humana** — basta olhar um cliente reconhecidamente organizado e
ver que nota ele tem.

## 8. O que o CRM precisa guardar

**Por unidade (grupo econômico ou empresa independente)**

Honorário mensal · porte · ajuste manual de horas · notas 1–5 de complexidade,
disciplina, risco técnico, cross-sell, adimplência e churn · semáforo
operacional · quem atribuiu cada nota humana e quando.

**Calculado pelo CRM**

Horas-base · atrito · horas ajustadas · custo de servir · margem · nota de
receita · nota de rentabilidade · Score · classe · classe efetiva · alertas ·
eixo de ação · ISC.

**Parametrizável, com histórico de vigência**

Pesos do Score · cortes de classe (3,95 e 3,35) · limiares de trava (≤2) e de
churn (≥4) · réguas de receita, rentabilidade e ISC · matriz de horas e mix por
porte · tabela de custo/hora · fator de atrito · teto de atrito · alíquota de
impostos.

> **Por que parametrizável:** reclassificar o passado com os parâmetros de hoje
> apaga a história. Cada classificação guarda **qual versão dos parâmetros** a
> produziu.

## 9. Agregação por grupo

| Campo | Regra |
|---|---|
| Receita e horas | **Soma** |
| Complexidade, disciplina, risco | **Média ponderada por horas** |
| Adimplência | **Pior caso do grupo** |
| Churn | **Maior do grupo** |
| Semáforo | **Pior do grupo** |
| Margem | **Recalculada sobre os totais**, nunca média das margens |

## 10. Pendências

1. **Confirmar o defeito 7.2** — olhar um cliente organizado e ver a nota.
2. **Definir a escala 1–5 de cada nota humana.** As planilhas trazem as réguas
   de receita e rentabilidade, mas **não o que é nota 3 em disciplina, risco
   técnico ou cross-sell**. Sem isso, quem avalia não tem régua — e a área
   técnica assume essa tarefa mensalmente.
3. **Definir o critério do semáforo operacional** (1, 2 ou 3).
4. **Definir a escala de churn** (1 a 5), hoje inexistente como campo.
5. **Decidir sobre a assimetria** entre corte fixo de classe e percentil de
   receita.
6. **Confirmar a periodicidade** de recálculo e o que a dispara.
