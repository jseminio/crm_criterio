# Régua de Porte, Atrito na Proposta e Plano de Teste

> ⚠️ **PROPOSTA PARA VALIDAÇÃO. HIPÓTESE, NÃO DECISÃO.**
> Escrita em 19/09/2026 a pedido de Eduardo. Nenhuma fórmula entra no CRM antes
> do teste da seção 4 e da decisão humana.

**O problema que isto resolve.** Hoje o porte do cliente é julgado por pessoa,
sem regra escrita — confirmado por Eduardo. E a proposta de cliente novo
precifica **sem fator de atrito**, enquanto a margem da carteira o aplica. Na
prática, **todo cliente novo é precificado como se fosse organizado**, e o
atrito só aparece meses depois.

---

## 1. Dois eixos, não um

| Eixo | O que mede | De onde vem | Resultado |
|---|---|---|---|
| **Volume** | Quanto trabalho a operação dá | Seção 3 do questionário de volumetria | **Porte** → horas-base |
| **Atrito** | Quão difícil é esse trabalho | Complexidade, risco técnico e disciplina | **Multiplicador** das horas |

Porte e complexidade **não são a mesma coisa**. Um cliente pode ser grande e
simples — muitas notas, um CNPJ, regime único — ou pequeno e complexo, com
holding, eliminações e três regimes. Fundir os dois numa nota só erra
exatamente nos casos que mais importam.

## 2. Régua de porte por volume

**Cada direcionador vale de 0 a 4 pontos.** Só entram os direcionadores
**aplicáveis ao escopo contratado** — quem contrata apenas DP não pontua em
notas fiscais.

| Direcionador | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Documentos fiscais/mês (emitidas + recebidas) | ≤ 50 | 51–150 | 151–300 | 301–600 | > 600 |
| Lançamentos contábeis/mês | ≤ 100 | 101–300 | 301–800 | 801–2.000 | > 2.000 |
| Pagamentos/mês | ≤ 50 | 51–150 | 151–400 | 401–1.000 | > 1.000 |
| Contas bancárias | 1 | 2 | 3–4 | 5–10 | > 10 |
| Conciliações de cartão/mês | nenhuma | ≤ 150 | 151–300 | 301–800 | > 800 |
| Empregados CLT | ≤ 5 | 6–20 | 21–50 | 51–150 | > 150 |
| Admissões + desligamentos/mês | ≤ 1 | 2–4 | 5–10 | 11–25 | > 25 |
| CNPJs no escopo | 1 | 2 | 3–4 | 5–10 | > 10 |
| Tomadores de serviço | ≤ 5 | 6–30 | 31–100 | 101–300 | > 300 |

**De onde vieram estes cortes.** Os de documentos, contas bancárias e
conciliações de cartão são **os mesmos das faixas do BPO Financeiro** que a
Critério já pratica. Os demais foram propostos por analogia e **precisam do
teste da seção 4** para virar régua.

### Cálculo

```
base    = média dos direcionadores aplicáveis          (0 a 4)
escopo  = +0,25 por serviço contratado além do primeiro (máx. +0,75)
grupo   = +0,50 se houver consolidação de grupo
audit   = +0,25 se a empresa for auditada
─────────────────────────────────────────────────────────
pontuação = base + escopo + grupo + audit
```

**Média, não soma.** A soma penalizaria quem contrata escopo amplo duas vezes —
o escopo já é precificado por quais serviços entram. Os três ajustes existem
porque amplitude, consolidação e auditoria consomem horas que os volumes não
capturam.

### Cortes de porte

| Pontuação | Porte | Horas-base/mês |
|---|---|---|
| < 0,75 | Micro | 5 |
| 0,75 – 1,50 | Pequeno | 10 |
| 1,50 – 2,25 | Médio | 16 |
| 2,25 – 3,25 | Grande | 40 |
| ≥ 3,25 | Extra Grande | 80 |

> **Aferição contra um caso real.** Apliquei a régua ao único questionário
> preenchido que encontrei — um grupo de home care com quatro CNPJs, auditoria
> externa e consolidação. Resultado: **Extra Grande**, que é o porte coerente
> com a operação descrita. É um caso só: confirma que a escala não está
> grosseiramente errada, não que está calibrada.

**O porte continua editável.** A régua sugere; a pessoa confirma ou
sobrepõe — e o CRM registra **quem sobrepôs, quando e por quê**. Os casos de
sobreposição são o material que recalibra a régua.

## 3. Atrito na proposta

Mesma tabela que a carteira já usa:

| Nota | Acréscimo de horas |
|---|---|
| 1 — ótimo | 0% |
| 2 | 5% |
| 3 — normal | 10% |
| 4 | 30% |
| 5 — crítico | 50% |

```
horas_propostas = horas_base(porte) × (1 + atrito_complexidade
                                         + atrito_risco
                                         + atrito_indisciplina)
```

### O que dá e o que não dá para estimar antes de operar

| Quesito | Na proposta | Origem |
|---|---|---|
| **Complexidade** | ✅ estimável | Entrevista e seções 1, 2 e 4 do questionário |
| **Risco técnico** | ✅ estimável | Seção 5 — parcelamentos, autos, obrigações em atraso |
| **Disciplina** | ❌ **não estimável** | Só se descobre operando |

**Proposta para a disciplina: assumir nota 3 como premissa declarada.** Escrita
na proposta, não escondida — "esta proposta assume um cliente de disciplina
normal na entrega de documentos". Quando a nota real entrar no primeiro
trimestre, a diferença vira evidência objetiva: justifica reajuste, ou explica
o consumo de horas de conforto.

Isso conversa com a sua Matriz de Objeções, que já registra a premissa como a
base do reequilíbrio: *"sem premissa não há reequilíbrio defensável"*.

### A trava contra o incentivo

Se o preço sobe com a complexidade, e a complexidade é nota humana, quem
atribui a nota passa a ter incentivo. Duas travas:

1. **A nota exige evidência registrada** — o critério da escala é observável.
2. **Quem precifica não é quem atribui.** Mesma lógica que o Bruno já adotou no
   MP-SC-01 para a conferência: quem confere não é quem executou.

## 4. Plano de teste

**Três passos, antes de qualquer fórmula virar código.**

### Passo 1 — Coletar a volumetria de uma amostra

**Obstáculo real:** a planilha de rentabilidade traz porte, honorário e as três
notas de atrito, **mas não os direcionadores de volume**. Eles não existem para
os clientes atuais — o questionário é instrumento de proposta, não de carteira.

Testar as 31 unidades exigiria levantar volumetria de todas. **Não recomendo.**

**Amostra sugerida: 10 unidades**, escolhidas para dar sinal máximo:

- **Os 7 grupos que aparecem destruindo valor.** Se a hipótese estiver certa,
  eles estão com porte subestimado.
- **3 grupos com margem alta**, como contraprova. Se a régua também os mudar de
  porte, o problema não é o porte.

Levantar, por unidade, os nove direcionadores da seção 2. A maior parte já está
em sistema — notas, lançamentos, pagamentos, contas, empregados.

### Passo 2 — Comparar

Para cada unidade da amostra, uma linha:

| Grupo | Porte atribuído hoje | Porte pela régua | Diferença | Margem atual | Nota de rentabilidade |
|---|---|---|---|---|---|

### Passo 3 — Ler o resultado

| O que aparecer | O que significa | O que fazer |
|---|---|---|
| Destruidores de valor **subestimados**, os de margem alta **estáveis** | **Hipótese confirmada.** O porte errado explica a margem ruim | Calibrar os cortes e adotar a régua |
| Diferenças espalhadas, sem relação com a margem | A régua não explica nada | Descartar. O problema está no atrito ou no preço, não no porte |
| Todos deslocados na mesma direção | Os cortes estão fora de escala | Recalibrar os cortes, manter a lógica |
| Destruidores **superestimados** | O porte não é a causa | Investigar atrito e desconto concedido |

> **O que faz este teste valer a pena** é que ele pode **derrubar** a hipótese.
> Um teste que só pode confirmar não é teste.

### Custo estimado

Levantar nove números para dez unidades. A parte cara não é a conta: é ir aos
sistemas buscar volume de quem já é cliente. **Quem faz isso precisa ser
definido** — sugiro a área técnica, que tem os acessos, com a lista saindo do
comercial.

## 5. Um questionário, três usos

Bruno Soares pediu que o questionário de avaliação carregue o que a implantação
precisa. **Isso não conflita com a precificação — reforça.** É o mesmo
levantamento servindo a três destinos.

| Seção do questionário | Preço e porte | Atrito | Implantação |
|---|---|---|---|
| 1 · Empresa, escopo e responsáveis | ✅ CNPJs, escopo, ajustes | ✅ estrutura | ✅ aviso prévio, fornecedor atual |
| 2 · Sistemas, dados e integrações | — | ✅ integração ou manual | ✅ **é o retrato de sistemas da implantação** |
| 3 · Volumes mensais | ✅ **os nove direcionadores** | — | ✅ dimensiona a equipe |
| 4 · Contábil e gerencial | ✅ consolidação, auditoria | ✅ plano de contas, rateio | ✅ blocos E e F do checklist contábil |
| 5 · Fiscal e obrigações | — | ✅ **passivo = risco técnico** | ✅ bloco D e F do checklist fiscal |
| 6 · Folha e DP | ✅ empregados, admissões | ✅ CCT de outra localidade | ✅ blocos C, E e H do checklist de DP |
| 7 · Financeiro | ✅ pagamentos, contas, conciliações | — | ✅ blocos B a F do checklist financeiro |
| 8 · Dores, transição e decisão | — | ✅ erros dos últimos 12 meses | ✅ **já pede o ponto focal da implantação** |

**A seção 8 já antecipa o handoff.** O questionário comercial de vocês pede o
ponto focal da implantação desde antes de o MP-SC-01 existir. A ligação que o
Bruno quer **já está começada**.

### O que falta perguntar — pedido da implantação

Campos que os quatro checklists exigem, **são conhecidos no momento da
proposta**, e o questionário ainda não pede:

| Campo | Serve à implantação | Serve também a |
|---|---|---|
| **Certificado digital** — tipo, titular, validade | Bloco C de fiscal e DP | Risco: certificado vencendo trava o início |
| **Procuração eletrônica** — existe, escopo, prazo | Bloco C do fiscal | — |
| **Domicílios eletrônicos** — quais e quem monitora hoje | Bloco C do fiscal | **Risco técnico**, e é o ponto em aberto da Matriz de Objeções |
| **Estrutura societária e participações** | Bloco B do contábil | **Porte** — define se há consolidação |
| **Reestruturação societária em curso** | Bloco B do contábil | Condiciona a data de início |
| **Balanço de Abertura e balancete de encerramento** — disponíveis? | Bloco D do contábil | Risco: indisponível atrasa tudo |
| **Saldos a migrar** — férias, banco de horas, provisões | Bloco E do DP | Risco técnico |
| **Quem concede os acessos** no cliente | Blocos C de todos | Prazo: é o gargalo mais comum |

**Oito campos.** Sete deles também alimentam porte ou risco técnico — ou seja,
**o pedido do Bruno melhora a precificação de quebra**.

> **Recomendação de desenho:** estes campos entram numa seção 9, marcada como
> *"para a implantação"*. O cliente responde uma vez só, no mesmo momento, e o
> CRM entrega o mesmo dado às três etapas. É o critério de sucesso de nunca
> perguntar duas vezes, virando estrutura.

## 6. O que decidir antes de construir

1. **Rodar o teste da seção 4?** Se sim, quem levanta a volumetria da amostra.
2. **Os oito campos novos entram no questionário?** Decisão do Bruno Soares,
   com o Eduardo, porque muda um instrumento comercial.
3. **A premissa de disciplina 3 vai escrita na proposta?** Muda o texto do
   documento que o cliente recebe.
4. **Quem atribui complexidade e risco na fase comercial**, já que a regra é que
   não seja quem precifica.
5. **A régua sugere e a pessoa confirma** — ou a régua decide? *Recomendo
   sugerir, sempre.*

## 7. O que isto muda no CRM agora

**Nada no cálculo** — a precificação automática segue adiada por decisão sua.

**Mas muda o que a Etapa 1 precisa capturar.** Complexidade e risco técnico
deixam de ser campos só da carteira e passam a ser preenchidos **na
oportunidade, antes da proposta**. Sem isso, quando a precificação entrar não
haverá histórico para calibrar nada — e o teste da seção 4 só poderá ser
repetido à mão.
