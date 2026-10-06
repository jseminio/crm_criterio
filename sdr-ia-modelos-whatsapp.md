# SDR de IA · modelos de mensagem do WhatsApp para a Meta aprovar

**06/10/2026 · [proposta] para Eduardo aprovar e cadastrar no WhatsApp Manager.**

## Por que modelos

Fora da janela de 24 horas desde a última mensagem do lead, o WhatsApp só aceita **modelo aprovado
pela Meta**. O lembrete sai 2 dias úteis depois do envio do link, e o agradecimento sai quando o
questionário chega pelo site (o lead não escreveu no WhatsApp). Os dois quase sempre caem fora da
janela. Dentro dela, vale o texto livre da IA, com as regras da seção 7 de `sdr-ia-roteiro-spin.md`.

## A escolha da categoria

Regra da Meta (consultada em 06/10/2026, fontes no fim): é **Utilidade** a mensagem que não é
promocional **e** está ligada a um pedido do próprio usuário. O exemplo oficial é um lembrete de
formulário pendente. Se o texto ganha "intenção persuasiva", oferta ou venda, a Meta o
**reclassifica como Marketing**, que custa mais por mensagem e é mais sujeito a bloqueio e a
descadastro.

**Recomendação:** cadastrar o lembrete como **Utilidade (A)**. A persuasão vem do que é fato e foi
pedido pelo lead: a proposta que ele pediu depende das respostas. Elogio ao serviço e promessa de
benefício ficam fora. A versão **Marketing (B)** fica de reserva, caso Eduardo prefira o tom mais
vendedor e aceite o custo.

## 1 · Lembrete · Utilidade (recomendado)

| Campo | Valor |
|---|---|
| Nome | `criterio_lembrete_questionario` |
| Categoria | Utilidade |
| Idioma | Português (BR) · `pt_BR` |
| Variáveis | nomeadas: `{{nome}}`, `{{servico}}` |

**Corpo**

> Olá, {{nome}}! Aqui é a assistente virtual da Critério. Para a nossa equipe preparar a proposta de
> {{servico}} que você pediu, ainda falta o questionário de volumetria: é por ele que a proposta fica
> do tamanho da sua operação. Se alguma pergunta gerar dúvida, é só responder esta mensagem que eu
> ajudo.

**Rodapé:** Critério Consultores

**Botão** (link, estático): `Responder o questionário` →
`https://criterio-questionario-proposta.netlify.app/questionario`

**Exemplos para a Meta:** `nome` = Camila · `servico` = BPO Financeiro

## 2 · Agradecimento · Utilidade

| Campo | Valor |
|---|---|
| Nome | `criterio_agradecimento_questionario` |
| Categoria | Utilidade |
| Idioma | Português (BR) · `pt_BR` |
| Variáveis | nomeadas: `{{nome}}`, `{{servico}}` |

**Corpo**

> Olá, {{nome}}! Aqui é a assistente virtual da Critério. Recebemos as respostas do questionário de
> volumetria, obrigada pelo envio. A nossa equipe vai preparar a proposta de {{servico}} e alguém do
> time entra em contato com você para apresentá-la.

**Rodapé:** Critério Consultores

**Botão:** nenhum.

**Exemplos para a Meta:** `nome` = Camila · `servico` = BPO Financeiro

## 3 · Lembrete · Marketing (reserva)

| Campo | Valor |
|---|---|
| Nome | `criterio_lembrete_questionario_mkt` |
| Categoria | Marketing |
| Idioma | Português (BR) · `pt_BR` |
| Variáveis | nomeadas: `{{nome}}`, `{{servico}}` |

**Corpo**

> Olá, {{nome}}! Aqui é a assistente virtual da Critério. A proposta de {{servico}} que você pediu
> está esperando só o questionário de volumetria. Com as suas respostas, a equipe chega à conversa
> com uma proposta pensada para a realidade da sua empresa, sem tomar o seu tempo com perguntas que
> o questionário já responde. Posso contar com o seu preenchimento? Se tiver dúvida em alguma
> pergunta, me escreva aqui.

**Rodapé:** Critério Consultores · Para não receber mais mensagens, responda SAIR.

**Botão** (link, estático): `Responder o questionário` →
`https://criterio-questionario-proposta.netlify.app/questionario`

## Cuidados que valem para os três

- **Travas da IA:** nenhum texto traz preço, valor, prazo, desconto ou promessa de resultado. Todos
  passam pela trava de preço do servidor (`fala_de_preco`).
- **Variáveis:** nenhuma no começo nem no fim do corpo, e nenhuma ao lado de outra. É motivo comum
  de recusa. Mudar o texto pede nova aprovação.
- **`{{servico}}`** vem do interesse do lead no CRM (BPO Financeiro, BPO Contábil...). Sem
  interesse registrado, a integração usa "BPO".
- **Domínio da Critério:** o link do botão é fixo no modelo. Quando o questionário mudar de
  endereço, além de `CRM_LINK_DO_QUESTIONARIO`, é preciso **enviar nova versão dos modelos 1 e 3**
  para a Meta aprovar. Alternativa: deixar o endereço antigo redirecionando para o novo.
- **Identificação como IA:** os três se apresentam como "assistente virtual da Critério", em linha
  com a política da Meta para assistentes de IA de propósito específico (ficha R4 da base).

## Pendências

- Eduardo aprova os textos e cadastra os modelos no WhatsApp Manager da conta da Critério.
- Conferir no WhatsApp Manager o valor atual por mensagem de Utilidade e de Marketing no Brasil.
  Não registramos valor aqui para não fixar número que muda.
- A integração do canal envia o modelo fora da janela de 24 horas e o texto livre da IA dentro
  dela, e registra a mensagem no CRM com `"questionario": "Lembrete"` ou `"Agradecimento"`.

## Fontes (consultadas em 06/10/2026)

- Meta, *Message templates*: https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/
- Meta, *Template categorization guidelines*: https://developers.facebook.com/docs/whatsapp/updates-to-pricing/new-template-guidelines/
