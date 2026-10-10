# Apresentações no template da Critério

Toda apresentação feita para a Critério usa o design de `template-criterio.pptx`
(decisão de Eduardo em 09/10/2026), seja PowerPoint ou deck web.

## O que tem aqui

| Arquivo | Para que serve |
|---|---|
| `template-criterio.pptx` | O template original (25 slides, 13,33" × 7,5"). É a fonte da verdade. |
| `fundos/` | Os fundos do template já extraídos. Trazem o rodapé "Advisory \| Tax \| Accounting" e a logomarca. |
| `estilo-template.js` | Tema, layouts e funções de desenho para o `pptxgenjs`. |
| `exemplo.js` | Um slide de cada layout, com texto de demonstração. |
| `extrair-fundos.py` | Regera `fundos/` se o template mudar. |

```bash
cd apresentacoes && npm install
PPTX_SKILL_DIR=<pasta da skill pptx> node exemplo.js saida/exemplo.pptx
```

Sem `PPTX_SKILL_DIR` o arquivo sai, mas as cores de esquema ficam no padrão do Office.
A pasta `saida/` não é versionada.

## Layouts

| Layout | Fundo | Uso |
|---|---|---|
| `CAPA` | degradê azul | eyebrow, título, subtítulo e autor |
| `CONTEUDO` | branco | slide de conteúdo, título no topo |
| `COLUNA` | branco | título estreito à esquerda e gráfico ou visual à direita |
| `ESCURO` | preto | números grandes de destaque |
| `NAVY` | navy | decisões e encerramento do conteúdo |
| `DIVISOR_1` a `DIVISOR_5` | fotográficos | abertura de seção |
| `OBRIGADO` | blocos azuis | encerramento, com o texto e os contatos do template |

`definirLayouts(pres, { comEyebrow: true })` põe uma linha de eyebrow acima do título nos
layouts de conteúdo.

## Regras do design

- **Fonte:** Delight. SemBd nos títulos e destaques (`HEAD`), Regular no corpo, Light em apoio.
- **Cores:**
  - preto `0B0E17`, navy `1A2338` e branco;
  - azul-claro `CAE3F7` para números e destaques sobre fundo escuro;
  - os estados do PAD-002 (atenção, ganho) só com rótulo de texto junto.
- **Grade:**
  - margem esquerda 0,47";
  - conteúdo até 6,72" de altura (a linha do rodapé fica em 6,93");
  - título em 32 pt à esquerda;
  - número da página em x 9,95", y 7,0".
- **Elementos:**
  - números grandes com réguas finas;
  - linha do tempo com pontos;
  - régua vertical entre texto e gráfico;
  - tabelas com cabeçalho navy e só réguas horizontais.
- **Não usar:** cartões arredondados, sombras, faixas coloridas ou uma segunda logomarca. A logomarca já está no fundo e fica sempre sozinha.
- **Quebra de linha:** espaço não separável em "R$ 1.000" e "1º trimestre", para o valor não se separar.

## Conferência

- Validar o `.pptx` e olhar a imagem de todos os slides antes de entregar.
- A Delight não existe no ambiente de conferência e é trocada por uma fonte mais larga. Deixe folga: no PowerPoint com a Delight o texto ocupa um pouco menos.
- Revisar três vezes: fórmulas, design e incorreções.
- **Dado de cliente não entra aqui.** O gerador de cada apresentação, com nomes e valores de clientes, fica fora do repositório. Só o template e o estilo são versionados.
