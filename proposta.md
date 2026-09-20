# Critério CRM — Proposta da Etapa 1

**PF-09.5 · 20/09/2026 · ✅ APROVADA por Eduardo em 20/09/2026**

> **Gate cumprido.** Eduardo aprovou a proposta **e a inversão E1 ↔ E2/E3** da
> seção 2, em 20/09/2026. A construção está liberada. Quem aprovou não foi quem
> escreveu — RN-10 respeitada.

Última peça antes da construção. Fecha as quatro decisões pendentes e diz o
que existe na sexta-feira, **25/09/2026**.

---

## 1. As decisões que fecharam

| Decisão | Resposta de Eduardo | Data |
|---|---|---|
| Região do servidor | **Brasil** | 19/09/2026 |
| De-para dos grupos econômicos | **Caminho 2** — carregar como grupo próprio, reagrupar depois | 20/09/2026 |
| A virada | **Paralelo com a planilha** | 20/09/2026 |
| Sequência dos incrementos | **Aprovada** | 20/09/2026 |
| Prazo | **Primeira versão pronta até sexta, 25/09/2026** | 20/09/2026 |
| Orçamento | **Sem teto declarado** — o ganho de produtividade, transparência e eficiência supera o gasto | 20/09/2026 |

**Sobre o orçamento.** A resposta foi um princípio, não um número, e isso é
suficiente para decidir: escolho a opção mais barata que atenda região Brasil e
backup automático, e **digo o valor antes de qualquer contratação**. Nenhuma
conta é criada e nenhum meio de pagamento é usado por mim — isso é seu, sempre.

## 2. O que muda no plano por causa do prazo

**A sequência aprovada era E1 → E2 → E3.** Para a sexta, ela se inverte:
**E2 e E3 primeiro, rodando na sua máquina; E1 depois.**

### Por que

O E1 — nuvem, login Microsoft, backup com restauração testada — não é código.
É contratação e configuração, depende de escolha de provedor, criação de conta
e acesso administrativo que só você tem. Se ele vier primeiro, a semana vira
espera e na sexta não há CRM para olhar.

### Por que a alternativa é melhor

O que você pediu para sexta é **usar o CRM**, não hospedá-lo. Rodando local,
você abre o sistema, vê as 154 propostas de 2026, mexe no funil e julga. O E1
vira um deploy — não uma reescrita — porque o código já nasce preparado:
conexão por variável de ambiente, migrações versionadas, nada preso à máquina.

### O que isso custa, e o alcance

Durante essa semana os dados ficam **no seu computador**, sem backup
automático, sem login corporativo e **com um único usuário: você**.

- **A Karine não usa o CRM até o E1 estar pronto.** A planilha segue sendo a
  fonte dela.
- Nenhum dado de cliente sai da sua máquina nesse período.
- O fluxo volta ao padrão no E1, que é o próximo depois da sexta.

> **Isto é um desvio da sequência que você aprovou hoje.** Não reduz segurança,
> não atravessa gate e não é silencioso: está escrito aqui para você aprovar ou
> recusar. Recusando, a sexta entrega fundação sem CRM visível.

## 3. O que existe na sexta

| Você consegue | Vem de |
|---|---|
| Abrir o CRM no navegador e navegar | base do E2/E3 |
| Ver os 157 registros de 2026 carregados, por grupo econômico | E2 |
| Ler o relatório de conferência: o que entrou, o que foi corrigido, o que ficou pendente | E2 |
| Fundir dois grupos que na verdade são um | E2, caminho 2 |
| Cadastrar um lead novo com origem em duas camadas | E3 |
| Trabalhar o funil em lista e em kanban, mudar situação, registrar motivo de recusa e próxima ação | E3 |
| Rodar a carga de novo sem duplicar nada | chave de identidade |

**Meta esticada, só se sobrar tempo:** quatro números no topo da tela — MRR
proposto, propostas no funil, taxa de conversão e ticket médio. É o pedaço do
E5 que custa pouco depois que o dado existe. **Não é promessa.**

## 4. O que não existe na sexta

- **Nuvem, login Microsoft e backup** — é o E1, logo depois.
- **Emissão de proposta** — é o E4.
- **Painel de KPIs completo** — é o E5.
- **Contrato, Clicksign, implantação, classificação da carteira** — Etapas 2 e 3.
- **Cálculo automático de preço** — adiado por decisão sua.

## 5. O que depende de você nesta semana

| Quando | O quê | Por quê |
|---|---|---|
| **Segunda, antes de tudo** | **Instalar o PostgreSQL na sua máquina** | Não há Postgres, Docker nem Homebrew instalados. Sem banco não há CRM. É download e instalação — não faço por você |
| Segunda ou terça | Confirmar com a Karine as **duas linhas duplicadas** (317 e 318) | Inflam a contagem e o valor do funil. Só quem digitou sabe se foi erro |
| Quarta | Olhar a primeira carga e dizer se a base está reconhecível | É o que permite abandonar a planilha |
| Quando puder | Escolher o provedor de nuvem | Destrava o E1, não bloqueia a semana |

**A taxa de conversão (38% ou 26%) só é necessária se a meta esticada entrar.**

## 6. Riscos desta semana

| Risco | Efeito | O que fazer |
|---|---|---|
| **O Postgres não ser instalado na segunda** | Some um dia de cinco | É o primeiro item da lista acima |
| **A carga revelar mais defeitos na planilha** | Consome tempo de análise | Aviso não bloqueia: o registro entra marcado e você decide depois |
| **Sua disponibilidade na semana** | O prazo é seu, o ritmo também | Os pontos de contato estão na tabela acima e são curtos |
| **Escopo crescendo durante a semana** | A sexta não acontece | O que aparecer entra na lista do E4 em diante. Esta seção é a linha |

## 7. A aprovação

**Aprovada por Eduardo em 20/09/2026**, com estas palavras: *"aprovo a proposta,
inclusive a inversão"*.

Isso libera a construção do E2 e do E3 fora da ordem originalmente aprovada, com
o custo declarado na seção 2: durante a semana os dados ficam na máquina do
Eduardo, sem backup automático, com um único usuário. **O fluxo volta ao padrão
no E1**, logo depois da sexta.
