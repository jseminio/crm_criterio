# Critério CRM — aplicação

Primeiro código da **Etapa 1**, o incremento E2 (*a carteira existe*):
as listas controladas do funil e a carga das propostas de 2026.

## Estado

| | |
|---|---|
| O que roda | Normalização das listas e carga da planilha, com relatório de conferência |
| Testes | 86, todos passando |
| Banco | **ainda não** — o domínio é testável sem ele |
| API e telas | **ainda não** |

## Como rodar

```bash
cd backend
python3 -m venv ~/.venvs/criterio-crm
~/.venvs/criterio-crm/bin/pip install -e ".[dev]" openpyxl
~/.venvs/criterio-crm/bin/python -m pytest
```

> **Por que o ambiente virtual fica fora do repositório.** A verificação do
> vortexOS varre `workspaces/` inteiro à procura de vazamento da engine, e não
> consegue ler binário. Um `.venv` dentro do workspace gera **1887 pendências
> falsas** e enterra as reais. Pelo mesmo motivo o pytest roda sem cache em
> disco (`-p no:cacheprovider`).

Conferir a carga contra uma planilha real — **lê e mostra, não grava nada**:

```bash
~/.venvs/criterio-crm/bin/python scripts/conferir_carga.py "/caminho/Relatório Performance Comercial 2026.xlsx"
```

## Desenho

```
backend/src/crm/
  domain/listas.py        listas controladas e de-para — lógica pura
  carga/planilha_2026.py  normalização e relatório — lógica pura
  carga/arquivo.py        leitura do .xlsx — a única camada que sabe de arquivo
```

A separação é proposital: a normalização é testada sem abrir arquivo nenhum, e
os testes usam os valores que **existem de verdade** na planilha — as duas
grafias de "Sócio", o "Captação de recursos" no campo de temperatura, o
"#DIV/0!" numa célula de valor.

## Princípios que o código sustenta

**Nada é descartado em silêncio.** Todo valor que não converte vira aviso no
relatório, com o texto original preservado.

**O relatório de conferência é entregável, não log.** Sem ele ninguém confia na
base — e confiar na base é a condição para abandonar a planilha.

**Aviso ≠ bloqueio.** Aceita sem data de aceite avisa e entra; situação
desconhecida bloqueia. A distinção é do negócio, não do código.

## O que este código deliberadamente não faz

- **Não calcula preço nem margem.** As fórmulas seguem travadas pelos dois
  defeitos das planilhas — o churn sem célula e a possível inversão da
  disciplina no atrito. Ver `../modelo-classificacao-carteira.md`.
- **Não agrupa em grupo econômico.** A planilha não traz o grupo. Decisão de
  Eduardo em 20/09/2026: **carregar cada proposta como grupo próprio e reagrupar
  depois**, com função de fundir grupos no CRM. Ver `../planejamento.md`, seção 5.
- **Não calcula a taxa de conversão.** O denominador é decisão pendente — 38%
  ou 26%. `Situacao.decidida` marca o conceito e para por aí.

## A identidade da proposta — resolvida em 20/09/2026

Eduardo decidiu **rodar o CRM em paralelo com a planilha**. A carga passa a
rodar mais de uma vez, então cada proposta precisa de uma **identidade estável**:
reimportar não pode duplicar.

`Proposta.linha` não serve — número de linha muda quando alguém insere uma linha
no meio. Testei quatro candidatos contra as 157 propostas reais:

| Chave | Chaves distintas | Colisões |
|---|---|---|
| nome | 141 | 16 |
| nome + data de colocação | 146 | 11 |
| nome + data + serviço | 151 | 6 |
| **nome + data + serviço + tipo de serviço** | **156** | **1** |

**A chave adotada é a última.** Cinco das seis colisões anteriores eram
propostas legítimas e distintas — mesmo cliente, mesma data, mesmo serviço,
**valores diferentes**: são cenários alternativos oferecidos ao cliente, e o
tipo de serviço os separa. Preservá-los é correto; fundi-los apagaria a
negociação.

`linha` continua no modelo para apontar a origem no relatório de conferência.
Deixa de ser identidade.

> **Defeito encontrado na planilha.** Sobra **uma colisão real**: as linhas
> **317 e 318** da aba são idênticas em todos os dezessete campos — mesmo
> cliente, data, serviço, tipo, captador, canal, situação e valores. É linha
> duplicada, não cenário alternativo. Efeito: a contagem de propostas e o valor
> total do funil estão **inflados em uma proposta de consultoria**. A carga vai
> avisar e importar uma só; **confirme com a Karine antes**, porque só quem
> digitou sabe se era duplicação ou dois contratos iguais de verdade.

**O que falta implementar:** a chave e o aviso de duplicata. É a primeira coisa
do E2, antes dos modelos do banco.

## Ressalva de processo

Escrito em 20/09/2026, depois de Eduardo dizer "pode codar agora". **A proposta
do PF-09.5 não foi escrita** — o gate foi atravessado por instrução direta.

Das quatro decisões então abertas, três foram fechadas no mesmo dia: o de-para
segue o caminho 2, a virada é em paralelo e a sequência dos cinco incrementos
está aprovada. **Segue aberta prazo e orçamento.**
