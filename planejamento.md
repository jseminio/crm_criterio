# Critério CRM — Planejamento da Etapa 1

**PF-09 · 19/09/2026 · atualizado em 20/09/2026 · Status: sequência aprovada**

> **Decisões de Eduardo em 20/09/2026:** a sequência dos cinco incrementos está
> **aprovada**; a virada será **em paralelo com a planilha**; o de-para dos
> grupos segue o **caminho 2** — carregar e reagrupar depois.

Recorta a Etapa 1 — *"sair da planilha"* — em cinco incrementos, cada um
entregando algo que você usa e valida. Alimenta a proposta do PF-09.5, onde
está o próximo gate humano.

---

## 1. Como este plano é montado

**Quem constrói é você, comigo.** Não há equipe, não há sprint. O ritmo é o da
sua disponibilidade, e o risco não é atraso de cronograma — é construir algo
que você não valida.

Por isso o plano tem uma regra: **cada incremento entrega uma coisa que você
consegue usar e julgar**. Nada de "a fundação está 60% pronta". Ou você entra
no sistema e faz uma tarefa inteira, ou o incremento não acabou.

**Sobre estimativas.** Não coloco horas. Elas dependem de quanto você toca, e um
número inventado aqui viraria compromisso falso. Uso tamanho relativo — **P, M,
G** — que serve para ordenar e negociar escopo, que é o que o planejamento
precisa fazer.

## 2. Os cinco incrementos

### E1 · Fundação

**Tamanho:** M · **Você consegue:** entrar no sistema. Nada mais.

Banco em região brasileira, ambientes de teste e produção separados, entrada
pela conta corporativa Microsoft, backup automático com restauração testada,
perfis de acesso.

> É o único incremento sem valor visível — e o único que não dá para pular.
> **A restauração precisa ser testada, não configurada.** Backup que nunca foi
> restaurado é esperança, não backup.

### E2 · A carteira existe

**Tamanho:** G · **Você consegue:** consultar no CRM todo o histórico comercial
de 2026, por grupo econômico.

Grupo econômico, empresas, contatos. Carga das 154 propostas de 2026, com a
normalização já mapeada: situações, tipos de canal, temperatura e motivos de
recusa virando listas controladas; "AN" convertido para "BO"; empresa vazia
tratada; aceitas entrando sem data, para você completar.

Fecha com um **relatório de conferência**: o que entrou, o que foi corrigido, o
que ficou pendente. Sem ele, ninguém confia na base — e confiar na base é o que
permite abandonar a planilha.

### E3 · O funil funciona

**Tamanho:** G · **Você consegue:** parar de registrar na planilha.

Cadastro de lead com origem em duas camadas, fila por canal, conversão em
oportunidade. Funil em kanban e em lista, com filtros, situações padronizadas,
motivo de recusa e próxima ação.

> **É aqui que a planilha vira consulta.** O incremento anterior traz o passado;
> este traz o presente.

### E4 · A proposta nasce do CRM

**Tamanho:** G · **Você consegue:** emitir uma proposta sem sair do sistema.

Ficha de volumetria com as nove seções do questionário, cada campo sabendo se
veio da entrevista ou do questionário. Porte atribuído com autor e data. Preço
registrado com os direcionadores que o sustentaram e histórico quando há
reajuste. Lista do que falta para a proposta, com responsável e prazo. Geração
do documento.

> **Sem cálculo automático de preço** — adiado por decisão sua. O CRM registra
> e guarda a memória; o cálculo vem depois.

### E5 · Os números aparecem

**Tamanho:** M · **Você consegue:** medir, e discutir com número em vez de
impressão.

Os KPIs oficiais que a Etapa 1 permite calcular — MRR, conversão, ticket médio,
ciclo de venda — mais os recortes por serviço, canal e captador, e os
indicadores de cobertura do processo.

> Alguns dos doze só ficam calculáveis nas etapas seguintes: churn e NRR
> precisam do encerramento de contrato, forecast precisa da previsão, NPS
> precisa da pesquisa, CAC precisa de dado externo.

## 3. Sequência e dependências

```
E1 Fundação
   └─ E2 A carteira existe
         ├─ E3 O funil funciona
         │     └─ E4 A proposta nasce do CRM
         └─────────┴─ E5 Os números aparecem
```

**E2 antes de E3** porque a oportunidade pertence a um grupo. Inverter obrigaria
a criar oportunidades órfãs e reconciliar depois — que é exatamente o problema
que a planilha tem hoje.

**E5 depois de E3 e E4** porque indicador sem dado é tela vazia.

**O que pode andar em paralelo, fora do código:** a normalização das listas, o
de-para dos grupos econômicos e a conferência da carga. São trabalho de
decisão, não de programação.

## 4. O que cada incremento precisa de você

| Incremento | Precisa | Situação |
|---|---|---|
| **E1** | Provedor de nuvem e acesso para criar o ambiente | Nuvem reservada; provedor a confirmar |
| **E2** | **O de-para dos grupos econômicos** — quais empresas formam quais grupos, nas 154 propostas | ⚠️ Ver seção 5 |
| **E2** | Aprovar as listas padronizadas | Você autorizou eu propor |
| **E2** | A virada | ✅ **Paralelo com a planilha** — decisão de 20/09/2026 |
| **E3** | Confirmar que "Nome da oportunidade" é o nome do cliente | Respondido: falta preencher |
| **E4** | Modelos oficiais de proposta | Dois PPTX recebidos, a confirmar como oficiais |
| **E4** | Questionário v3 | ✅ Pronto, em Downloads |
| **E5** | **A definição da taxa de conversão** — 38% ou 26% | ⚠️ Urgente |

## 5. O trabalho escondido no E2

**A carga de 2026 não tem grupo econômico.** A planilha registra oportunidades
por nome, sem CNPJ e sem grupo. A carteira tem 31 unidades já agrupadas — mas
ela cobre **clientes**, e as 154 propostas incluem prospects que nunca fecharam.

Então alguém precisa decidir, caso a caso, a qual grupo cada uma pertence — ou
se é grupo de uma empresa só.

**É trabalho humano, não de código, e não sei o tamanho.** Depende de quantas
das 154 são reconhecíveis. Três caminhos:

1. **Agrupar tudo antes de carregar** — base limpa de saída, mais trabalho antes.
2. **Carregar cada proposta como grupo próprio e reagrupar depois**, com uma
   função de fundir grupos no CRM. ✅ **Caminho escolhido por Eduardo em
   20/09/2026.** O trabalho vira contínuo em vez de bloqueante, e a fusão de
   grupos é útil de qualquer forma — empresas mudam de mão.
3. **Carregar só as 40 aceitas**, que viraram cliente e já estão na carteira.
   Rápido, mas perde a história das recusas — que é justamente onde estão os
   motivos e a matriz de objeções.

## 6. Riscos deste plano

| Risco | Efeito | O que fazer |
|---|---|---|
| **O de-para de grupos é maior do que parece** | Trava o E2, que trava tudo | Caminho 2 da seção 5: carregar e reagrupar depois |
| **Gerar PowerPoint programaticamente** | O E4 estica sem aviso | Decidir cedo: gerar PDF, preencher um modelo, ou manter o documento fora e só registrar |
| **Carga rodando mais de uma vez** | Paralelo significa reimportar enquanto a planilha continua viva. Sem identidade estável, a segunda carga duplica tudo | A carga precisa ser **idempotente**: identidade por conteúdo, não por número de linha. Ver seção 9 |
| **Construção intermitente** | Um incremento longo atravessa semanas e perde o fio | Foi por isso que E2 e E3 não viraram um só |
| **Escopo crescendo durante a construção** | Cada material novo trouxe escopo — e foi bom | A Etapa 1 está fechada aqui. O que aparecer entra na lista da Etapa 2 |

> O último risco merece franqueza: **nesta sessão o escopo cresceu cinco vezes**
> — contrato, implantação, carteira, objeções, classificação. Cada crescimento
> foi justificado. Mas planejamento só vale se houver uma linha, e esta é a
> linha.

## 7. O que fica para as etapas seguintes

**Etapa 2 — fechar o ciclo:** contrato, Clicksign, vigência, follow-up com
lembretes, implantação acompanhada.

**Etapa 3 — cuidar da carteira:** classificação viva, alertas, eixo de ação,
cadência de reuniões, ISC, decisões de carteira.

**Etapa 4 — tirar trabalho manual:** Granola automático, listas de campanha,
canais novos, cálculo de preço.

> **A Etapa 3 não depende da 2.** Os 31 grupos já existem e já estão
> classificados em planilha. Se aumentar os pontos de contato for a prioridade,
> ela sobe.

## 8. O que falta para a proposta (PF-09.5)

Três das quatro estão fechadas. Resta uma:

1. **Prazo e orçamento** — ver seção 10, que explica o que a pergunta quer dizer
   num projeto construído pelo próprio dono.

## 9. O que a virada em paralelo exige do código

Rodar em paralelo significa que **a planilha continua viva enquanto o CRM já
existe**, e que a carga vai rodar mais de uma vez — a cada rodada trazendo o que
mudou na planilha desde a anterior.

Isso impõe uma exigência que o corte seco não teria: **a carga precisa ser
idempotente.** Importar duas vezes a mesma planilha não pode gerar duas
oportunidades.

O código escrito hoje ainda **não** atende a isso: ele identifica cada proposta
pelo número da linha, e número de linha muda quando alguém insere uma linha no
meio. A identidade precisa vir do conteúdo — nome da oportunidade, data de
colocação e serviço, ou uma chave que a planilha passe a carregar.

**É a primeira coisa a resolver no E2.** Está registrado como dívida do código
em `app/README.md`.

## 10. O que "prazo e orçamento" quer dizer aqui

A pergunta estava mal formulada: num projeto contratado, prazo e orçamento são
contrato. Aqui **quem constrói é o dono**, então as duas palavras significam
outra coisa.

**Orçamento** são duas contas, e só a segunda costuma doer:

- **Dinheiro recorrente:** nuvem, Clicksign, eventual API de WhatsApp, plano do
  Granola. É o custo de manter o CRM no ar, todo mês, para sempre.
- **Seu tempo:** quantas horas por semana você consegue dedicar de fato. É a
  restrição real — o projeto anda na velocidade disso, e nada mais.

**Prazo** é uma pergunta só: **existe uma data que importa?** Fechamento de
dezembro, contratação de alguém, uma reunião de sócios. Se existir, ela define
o que cabe. Se não existir, o plano é ordem sem calendário — o que é legítimo,
mas significa que não há compromisso a cobrar.
