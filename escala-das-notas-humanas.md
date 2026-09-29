# Escala das Notas Humanas — Complexidade, Disciplina e Risco Técnico

> ⚠️ **PROPOSTA PARA VALIDAÇÃO. HIPÓTESE, NÃO DECISÃO.**
> Escrita em 27/09/2026 a pedido de Eduardo, fechando a pendência 2 de
> `modelo-classificacao-carteira.md`: as réguas de receita e rentabilidade já
> existem, mas o que faz um grupo ser nota 3 em complexidade, disciplina ou
> risco técnico nunca foi escrito. Nenhum corte aqui entra em código antes de
> decisão humana — mesma regra do `regua-de-porte-e-plano-de-teste.md`.

**O problema que isto resolve.** Hoje quem atribui estas três notas do Score
não tem régua — é opinião de quem preenche, igual era o porte antes da seção 2
do documento de porte. E o segundo problema, tão real quanto: se a régua virar
um questionário longo, todo mês, para 31 unidades, a área técnica vai deixar
de fazer operação para preencher formulário — e vai reclamar, com razão.

## 1. Princípio: cada fator tem o timing que merece

Nem todo fator muda no mesmo ritmo. Perguntar toda vez sobre o que quase nunca
muda é desperdício; deixar de medir o que muda toda hora é achismo disfarçado
de régua. Três categorias:

| Categoria | Muda quando | Como se mede | Quem preenche, quando |
|---|---|---|---|
| **Estrutural** | O contrato ou a estrutura societária muda | Checklist sim/não, uma vez | No cadastro; revisita só em mudança de escopo |
| **Do meio-termo** | Muda devagar (trimestre a trimestre) | Checklist sim/não, curto | Área técnica, revisão trimestral |
| **Operacional** | Muda todo mês, é o próprio trabalho acontecendo | Calculado de um registro que já existe | Ninguém preenche — é subproduto da operação |

Complexidade é quase toda estrutural. Risco técnico é do meio-termo. Disciplina
é operacional — é exatamente o caso em que perguntar é pior do que medir.

## 2. Complexidade (12% do Score, entra invertida)

Fatores já levantados em `anexo-tecnico.md` (linha 220), agora com corte.
Checklist sim/não, no cadastro do grupo:

| # | Fator | Sim conta |
|---|---|---|
| 1 | Holding com consolidação de mais de uma empresa | 1 |
| 2 | Mais de um centro de custo ou rateio entre unidades | 1 |
| 3 | Plano de contas fora do padrão (customizado) | 1 |
| 4 | Auditoria externa (obrigatória ou contratada) | 1 |
| 5 | Mais de um regime tributário no grupo | 1 |
| 6 | Parcelamento tributário ativo | 1 |

| Total de "sim" | Nota |
|---|---|
| 0 | 1 |
| 1 | 2 |
| 2–3 | 3 |
| 4 | 4 |
| 5–6 | 5 |

**Cadência: no cadastro, revisita só quando o contrato muda de escopo ou a
estrutura societária muda.** Sem formulário mensal.

## 3. Risco técnico (7% do Score, entra invertida)

Fatores da seção 5 do questionário de volumetria (`regua-de-porte-e-plano-de-teste.md`)
mais os dois campos de risco de `anexo-tecnico.md` (linha 206-213):

| # | Fator | Sim conta |
|---|---|---|
| 1 | Auto de infração ou processo fiscal em andamento | 1 |
| 2 | Parcelamento tributário em atraso, ou já quebrado antes | 1 |
| 3 | Obrigação acessória entregue com atraso nos últimos 3 meses | 1 |
| 4 | Certificado digital vencendo em 60 dias, sem renovação agendada | 1 |
| 5 | Passivo tributário sem provisionamento | 1 |

| Total de "sim" | Nota |
|---|---|
| 0 | 1 |
| 1 | 2 |
| 2 | 3 |
| 3 | 4 |
| 4–5 | 5 |

**Corrigido em 29/09/2026, com autorização de Eduardo.** A versão anterior
desta tabela saía invertida (0 fatores = nota 5), e o Score aplicava a inversão
`6 − nota` por cima, assim como a tabela de atrito da rentabilidade trata 5
como o risco mais alto. Resultado: cliente sem risco nenhum era tratado como
risco máximo — Score mais baixo e 50% a mais de horas. Agora a nota anda como
a de Complexidade: mais risco encontrado = nota mais alta.

**Cadência: revisão trimestral pela área técnica.** Nenhum destes fatores
muda mês a mês; revisar toda semana só cansa sem ganhar precisão.

## 4. Disciplina (9% do Score, entra direta)

Esta é a diferente: o `regua-de-porte-e-plano-de-teste.md` (seção 3) já
registrou que disciplina **não dá para estimar antes de operar** — só se
descobre operando. A proposta aqui é não perguntar, **medir**.

### 4.1 — Como devia ser (meta)

Se o CRM passar a registrar duas datas por documento mensal esperado —
**prazo combinado** e **data de chegada** — a nota sai sozinha, sem ninguém
preencher nada sobre disciplina:

| Atrasos no trimestre | Nota |
|---|---|
| 0 | 5 |
| 1 | 4 |
| 2 | 3 |
| 3–4 | 2 |
| 5 ou mais, ou atraso recorrente no mesmo documento | 1 |

Isso vira **subproduto** do trabalho que a operação já faz (recebe
documento, dá baixa) — zero formulário extra. O custo é construir esse
registro; não existe hoje.

### 4.2 — Interino, até o registro existir

Enquanto a data de entrega não é capturada, três perguntas objetivas por
trimestre — não cinco notas subjetivas por mês:

1. Quantos meses, dos últimos três, o cliente entregou tudo no prazo
   combinado? (0, 1, 2 ou 3)
2. Algum documento precisou de mais de uma cobrança para chegar?
3. O mesmo documento atrasou mais de uma vez?

Nota: 3 meses completos e sem cobrança dobrada = 5; cada furo reduz um
ponto, piso em 1. Mesma lógica do corte final, só que por recordação em vez
de registro — **é pior que medir, mas é imensamente melhor que opinião**.

**Cadência: trimestral, três perguntas, até existir o registro por data —
aí vira automático e a régua interina se aposenta.**

Para cliente novo (proposta, ainda sem operação), continua valendo a
premissa já registrada no `regua-de-porte-e-plano-de-teste.md`: nota 3
declarada por escrito na proposta.

## 5. O que isto muda no CRM

**Nada ainda calcula sozinho** — mesma cautela do porte: a régua **sugere**,
a área técnica confirma ou sobrepõe, com autor e data, e a sobreposição é o
material que recalibra os cortes depois.

**Guardar por grupo:**

- Complexidade: os 6 sim/não + nota resultante + quem preencheu + quando.
- Risco técnico: os 5 sim/não + nota + quem + quando (revisão trimestral).
- Disciplina: interino, as 3 respostas trimestrais; meta, o log de
  prazo × entrega por documento (fora de escopo até decidir construir).

**Quem preenche:** área técnica, como já decidido para complexidade e risco
(`documento-de-negocio.md`, linha 415). A mesma regra vale aqui: quem
atribui a nota não é quem precifica ou avalia a performance daquele
técnico — evita o incentivo de inflar ou deflar nota.

## 6. O que decidir antes de construir

1. **Os cortes acima estão certos**, ou Eduardo quer outro ponto de corte
   por fator?
2. **A régua sugere e a pessoa confirma** — mesmo padrão do porte — ou
   decide sozinha? *Recomendo sugerir, sempre, mesma razão do porte.*
3. **Vale a pena construir o registro de prazo × entrega de documento** (a
   versão "de verdade" da disciplina), ou o interino trimestral fica valendo
   por ora?
4. **Cadência trimestral de risco técnico e complexidade**: quem dispara a
   revisão e como o CRM lembra que está na hora.
5. **Aferir contra casos reais**, como foi feito (uma vez só) com o porte,
   antes de considerar os cortes calibrados.
