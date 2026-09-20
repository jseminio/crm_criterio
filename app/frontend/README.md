# frontend — telas do Critério CRM

React com TypeScript, servido pelo Vite. Cobre o E3: funil em kanban, lista de
oportunidades, fila de leads e a junção de grupos econômicos.

## Como rodar

Dois processos. Primeiro a API, no `backend/`:

```bash
~/.venvs/criterio-crm/bin/python scripts/servir.py
```

Depois a tela, aqui:

```bash
npm install
npm run dev
```

Abre em `http://localhost:5173`. O Vite encaminha `/api` para a API em
`127.0.0.1:8000`, de modo que tudo fica na mesma origem no desenvolvimento.

## Como o design é seguido

Os tokens vêm do **PAD-002**, aprovado por Eduardo em 19/09/2026, e estão em
`src/tokens.css`. As cores da marca são exatas do manual e **nunca
reajustadas**. Se esta folha e o artefato do design system divergirem, vale o
artefato — a nota do padrão é explícita nisso.

As regras do PAD-002 que aparecem no código:

| Regra | Onde |
|---|---|
| Navegação e barra superior em `surface-brand` | `.lateral` e `.topo` |
| **Uma** ação primária por tela ou painel | A fila vazia de leads esconde o botão da barra: a ação mora dentro do estado vazio |
| Destrutiva ou de muito alcance pede confirmação | Juntar grupos exige dois cliques |
| Estado nunca só por cor | `Etiqueta` sempre traz a palavra; o prazo diz "atrasado 3 d", não só vermelho |
| Toda lista tem quatro estados | `componentes/estados.tsx` — carregando, vazio sem dados, vazio por filtro, erro com "tentar de novo" |
| Números em `R$ 1.248.300,00` | `formato.ts` |
| Logomarca sozinha | `.marca` — nada ao lado. Sem o arquivo oficial, o nome é composto, nunca redesenhado |
| Sem emoji na interface | — |

**Vazio sem dados e vazio por filtro são telas diferentes**, de propósito. O
primeiro se resolve cadastrando, o segundo limpando filtro. Dizer "nada
encontrado" nos dois casos manda a pessoa para o lado errado.

## O que a tela não deixa fazer

**Editar preço, serviço e datas de origem.** Enquanto a planilha roda em
paralelo, ela é a fonte desses campos, e editá-los nos dois lugares criaria
divergência que ninguém saberia resolver. O painel de detalhe mostra esses
valores e explica por que estão travados. Eles se abrem no E4, quando a
proposta passar a nascer no CRM.

**Marcar como aceita sem data de aceite.** É o defeito mais comum da planilha de
2026. O botão fica desabilitado e a API recusa — as duas travas, porque tela
some e API fica.

**Fixar as listas controladas.** Elas vêm de `/api/listas`. Declará-las aqui
criaria a segunda cópia da mesma regra, e ela envelheceria calada.

## Duas lacunas da verificação da plataforma

A varredura de vazamento lê o disco, não o índice do git, e só abre arquivos
cuja extensão está numa lista fechada. Este workspace expõe as duas
consequências:

**`.tsx` não está na lista.** Nenhum arquivo do frontend é varrido em busca de
vazamento da engine ou de dado de cliente — onze arquivos em amarelo permanente.
Não é ruído: é **cobertura de segurança ausente** numa parte inteira do sistema.
`.jsx` tem o mesmo problema.

**`node_modules/` é varrido.** Ele é ignorado pelo git, mas a varredura o
encontra no disco: cerca de 130 pendências falsas que enterram as verdadeiras.

**Não alterei nada disso: a varredura é Zona Núcleo.** Duas emendas possíveis,
ambas decisão de Eduardo: respeitar o `.gitignore`, e aceitar `.tsx` e `.jsx`
como texto. A primeira resolve o `node_modules`; a segunda devolve a cobertura
ao frontend. O registro detalhado, com os nomes dos arquivos da plataforma,
pertence ao repositório da engine — **não a este workspace**, e foi a
verificação que me lembrou disso.

## Sem autenticação

A API que esta tela consome não tem login enquanto o E1 não existir. Roda em
`127.0.0.1`, uma máquina, um usuário. **Não abra na rede antes disso.** O aviso
está na navegação lateral, à vista de quem usa.
