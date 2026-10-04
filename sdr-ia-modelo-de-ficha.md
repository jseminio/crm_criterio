# SDR de IA — Modelo de ficha da base de conhecimento

> ⚠️ **PROPOSTA PARA VALIDAÇÃO. HIPÓTESE, NÃO DECISÃO.**
> Escrita em 04/10/2026 a pedido de Eduardo. É o **passo 3** da base de
> conhecimento do SDR de IA. Passos anteriores: `sdr-ia-limites-de-atuacao.md`
> (passo 1) e `sdr-ia-inventario-de-fontes.md` (passo 2). Parte das decisões
> pendentes do passo 2 ainda não foi tomada; onde este modelo depende delas,
> está marcado.

**Como ler.** Cada regra traz uma marca de status:

- **[no CRM]**: já existe na tela ou no servidor.
- **[decisão]**: decisão tomada em outro documento.
- **[proposta]**: regra nova, à espera de aprovação.
- **[pendência]**: falta informação para fechar.

---

## 1. A conclusão

**Os campos que a tela já tem bastam para recepcionar a base. O que falta é
um padrão de escrita e um checklist de aprovação.** **[proposta]**

Nos passos 1 e 2 foram escritas cerca de 55 fichas: as 46 da carga e as propostas do inventário,
e todas couberam nos campos de hoje. O que variou foi o jeito de escrever:
umas terminam oferecendo a equipe, outras não; umas têm exemplos de como o
lead pergunta, outras não; o código só existe nas que vieram da carga.
Este modelo fixa esse padrão.

Três mudanças na tela ajudariam, mas **não são urgentes** (seção 7). A
principal: hoje a ficha criada pela tela nasce sem código, porque só a
carga inicial grava o código.

## 2. A ficha, campo a campo

| Campo | O que é | Como escrever | Erro comum |
|---|---|---|---|
| **Título** | O assunto da ficha, em uma linha | Para objeção e pergunta frequente: a fala do lead, entre aspas ("Estou trocando de sistema"). Para os demais: o tema ("Quem é a Critério") | Título genérico ("Preço", "Dúvidas") |
| **Bloco** | Um dos nove blocos **[no CRM]** | Ver a seção 3 | Objeção cadastrada como pergunta frequente |
| **Serviço** | Preencha só se a ficha vale para um serviço | O nome exato do catálogo | Preencher "Todos": basta deixar em branco |
| **O que a IA pode dizer** | O texto que a IA usa | Seção 4 | Texto longo, com dois assuntos, ou sem próximo passo |
| **O que a IA nunca diz** | O limite da ficha | O que está perto do assunto e não pode ser dito: números, promessas, nomes. Obrigatório em Regras, Objeções e Serviços **[proposta]** | Repetir o texto ao contrário ("nunca dizer que não...") |
| **Como o lead pergunta** | As formas reais como o lead fala do assunto | De 2 a 5 frases curtas, entre aspas, separadas por " · ". Com as palavras do lead, nunca da Critério. Cada uma vira pergunta do teste do passo 5 **[proposta]** | Escrever a pergunta como a equipe a escreveria |
| **Fonte** | De onde veio o conteúdo, com data | Documento ou arquivo e data de leitura. Para a Matriz, o ID (OBJ-011). Para entrevista, "Granola, N entrevistas de [mês]", nunca o nome do cliente | "Conversa interna" sem data |
| **Dono** | Quem responde pela ficha e a revisa | Uma pessoa, pelo nome | Uma área ("Comercial") |
| **Depende de hipótese** | Marque se a ficha toca ICP, preço ou as fronteiras entre BPO Financeiro, BPO Plus e CFO as a Service **[no CRM]** | Marcada, a validade cai para 60 dias | Esquecer de marcar em ficha de qualificação |

## 3. Regras por bloco

| Bloco | A ficha responde | Código | Termina com | Aprova |
|---|---|---|---|---|
| Regras de atuação | O que a IA não pode fazer, e o que diz no lugar | P1, P2… | A frase substituta | Eduardo e Bruno |
| Transbordo | Quando a IA passa a conversa, para quem e com que frase | T1, T2… | "Vou passar para…" | Eduardo e Bruno |
| Serviços | O que é o serviço, para quem é e quando está fora do perfil | S01, S02… | Uma pergunta de qualificação do roteiro do serviço | Eduardo |
| Objeções | A resposta aprovada a uma objeção | O1, O2… | Oferta de conversa com a equipe | Eduardo; o Bruno, se tocar precedente da Matriz |
| Tom de voz | Como a IA fala | V1, V2… | — | Eduardo |
| Quem é a Critério | Fatos institucionais | C1, C2… | — | Eduardo |
| Qualificação | O que perguntar e que dor reconhecer | Q1, Q2… | Uma pergunta ao lead | Eduardo |
| Perguntas frequentes | Respostas curtas a dúvidas comuns | F1, F2… | Oferta de seguir a conversa | Eduardo |
| Referências | Fontes e estudos para a equipe (não vão para a IA) | R1, R2… | — | Eduardo |

**O código segue o bloco.** **[proposta]** Por isso, a ficha "Onde fica a
Critério", proposta como C2 no passo 2 mas colocada em Perguntas
frequentes, passa a ser **F1**. A C2 fica livre.

**Objeção da Matriz só vira ficha se o precedente for "sim".** Regra
proposta no passo 2, seção 8 **[pendência: aprovar]**.

## 4. Como escrever "o que a IA pode dizer"

Seis regras. **[proposta]**

1. **Um assunto só.** Se a resposta precisa de "além disso", são duas fichas.
2. **A resposta vem na primeira frase.** O contexto, se houver, vem depois.
3. **De 2 a 4 frases**, no máximo 8 linhas na tela.
4. **Fala com o lead**, usando "você", na voz da Critério ("cuidamos",
   "a nossa equipe"). Nada de "o cliente" ou "a empresa contratante".
5. **Termina com o próximo passo** que a seção 3 indica para o bloco: uma
   pergunta de qualificação ou a oferta de conversa com a equipe.
6. **Passa no checklist da seção 5.**

**Exemplo completo.**

| Campo | Conteúdo |
|---|---|
| Título | "Estou trocando de sistema; agora não é o momento" |
| Bloco | Objeções |
| Código | O2 |
| O que a IA pode dizer | A troca de sistema muda o que a contabilidade precisa receber, então vale conversar antes, para nada ser feito duas vezes. Posso marcar uma conversa com a equipe para entender o seu calendário? |
| O que a IA nunca diz | Que a Critério implanta ou parametriza o sistema; prazo de migração |
| Como o lead pergunta | "Estamos trocando de ERP" · "Vamos esperar o sistema estabilizar" · "Agora não é o momento" |
| Fonte | Granola, 2 entrevistas com potencial cliente, set e out/2026 |
| Dono | Eduardo |
| Depende de hipótese | Não |

**Antes e depois.**

- **Antes:** "A Critério tem 30 anos e equipe de sócios vindos de grandes
  auditorias, e já captou mais de 300 milhões para clientes, então pode
  ficar tranquilo que a gente resolve o seu problema de contabilidade e
  ainda reduz seus custos."
- **O que está errado:** número de resultado (fica fora da IA, passo 2);
  promessa de resultado (P4); três assuntos numa ficha; nenhum próximo passo.
- **Depois:** "Somos uma consultoria com 30 anos no Rio de Janeiro e
  cuidamos da contabilidade, do fiscal, do pessoal e do financeiro das
  empresas. Quer me contar o que mais pesa hoje na sua rotina?"

## 5. Checklist de aprovação

Quem aprova confere estes dez itens. A tela já barra três deles: falta de
fonte, falta de dono e menção a preço **[no CRM]**. Os outros sete dependem
de quem aprova **[proposta]**.

1. Um assunto só.
2. A resposta está na primeira frase.
3. No máximo 8 linhas e termina com o próximo passo do bloco.
4. Sem preço, faixa de valor, desconto ou condição comercial (a tela barra).
5. Sem número de resultado, prazo prometido ou garantia (P4).
6. Sem nome de cliente, nem detalhe que identifique um (P9).
7. Não anuncia hipótese em validação: régua do ICP, fronteiras entre os
   produtos (P6). Se tocar nelas, "depende de hipótese" está marcado.
8. Sem termo proibido do tom de voz (V2).
9. "Como o lead pergunta" tem ao menos 2 exemplos com as palavras do lead.
10. Fonte com data e dono com nome (a tela barra a falta).

**Reprovou em algum item?** Não aprove: ajuste o texto ou devolva ao dono
com o número do item.

## 6. O ciclo de vida da ficha

| Etapa | Quem | O que acontece |
|---|---|---|
| Escrever | O dono | Cria a ficha pela tela; ela nasce **Rascunho** **[no CRM]** |
| Pedir revisão | O dono | "Enviar para revisão"; a ficha fica **Em revisão** **[no CRM]** |
| Aprovar | Quem tem `sdr.base_aprovar` | Confere o checklist e aprova; a validade é carimbada **[no CRM]** |
| Usar | A IA | Só fichas aprovadas e dentro da validade **[no CRM]** |
| Mudar | O dono | Editar o conteúdo devolve a ficha para **Em revisão** **[no CRM]** |
| Revisar | O dono | Quando vence (6 meses, ou 60 dias se depende de hipótese), revisa e pede aprovação de novo **[no CRM]** |
| Aprender | Quem faz a revisão semanal | Conversa com transbordo, falha ou nota baixa vira ficha nova ou ajuste **[proposta, quando o canal existir]** |
| Arquivar | O dono | O assunto deixou de valer; a ficha sai da base da IA **[no CRM]** |

## 7. O que mudaria na tela

Três mudanças, nenhuma urgente. **Nenhuma está construída**: cada uma
depende de amostra e aprovação antes. **[proposta]**

| # | Mudança | Por quê | Quando |
|---|---|---|---|
| M1 | **Código editável** na ficha criada pela tela | Hoje só a carga grava código. Sem ele, a ficha nova não segue a convenção da seção 3 e não é citada pelo código no teste do passo 5 | Antes de cadastrar as objeções |
| M2 | Campo **"Se o lead insistir"**, com o gatilho de transbordo (T1 a T12) | Várias fichas dizem "se insiste, passa para a equipe" dentro do texto. Separado, a integração lê sem interpretar | Quando o canal for construído |
| M3 | **Motivo e destino de transbordo** como listas nas fichas do bloco Transbordo | Hoje estão no texto. Como lista, a integração grava direto na conversa, com as listas que o CRM já tem | Quando o canal for construído |

**Recomendação:** fazer só a M1 agora, numa demanda pequena. M2 e M3 entram
junto com a integração do canal, quando ficar claro o formato que ela
precisa.

---

## Decisões, pendências e próximos passos

**Para aprovar (Eduardo e Bruno):**

- [ ] O padrão campo a campo (seção 2) e as regras de escrita (seção 4).
- [ ] O código por bloco, com a troca de C2 para F1 (seção 3).
- [ ] O checklist de aprovação (seção 5).
- [ ] Fazer a M1 (código editável) agora e deixar M2 e M3 para o canal.

**Pendências herdadas do passo 2:** o que prometer sobre quem executa o dia
a dia (O3); a regra do precedente "sim"; os números de resultado e o
"terceirizamos" da apresentação; se a Critério atende fora do Rio.

**Próximos passos:** aprovar este modelo; se aprovada, construir a M1;
reescrever pelo modelo as fichas da carga que ainda não o seguem; depois, o
passo 5 (conjunto de perguntas-teste), que usa o campo "como o lead
pergunta" de cada ficha.

**A revalidar:** o limite de 8 linhas e os dez itens do checklist, depois
das primeiras 30 fichas aprovadas.
