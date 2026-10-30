# Laravel 13 no CRM da Critério: vale a pena?

> Análise pedida por Eduardo em 30/10/2026, para discussão. **Não é decisão.** Nada no CRM muda por causa
> deste documento.

## 1. Primeiro: as falhas de segurança do PHP (outubro de 2026)

**A notícia procede.** Em agosto de 2026, pesquisadores usando ferramentas de IA encontraram duas falhas
graves no "motor" do PHP. O nome técnico é CVE-2026-109618 e CVE-2026-109619, e o apelido é **PHP2Shell**.
As duas foram divulgadas em 21/10/2026, no mesmo dia em que saiu a correção.

- **O que permitem:** um invasor consegue executar comandos no servidor pela internet, sem senha.
- **Alcance:** quase todas as versões do PHP dos últimos dez anos (5.4 a 8.5). O PHP roda em cerca de 70% dos sites.
- **Já estão sendo exploradas:** em 27/10/2026 o governo americano (CISA) avisou que há ataques em curso e
  mandou os órgãos federais corrigirem em três dias.
- **Correção:** PHP 8.5.12, 8.4.27, 8.3.36 e 8.2.35, publicadas em 21/10/2026.
- **Por que a IA importa aqui:** a IA ajudou a achar a falha e também ajuda quem ataca a explorá-la mais
  rápido. A imprensa chamou o período de "Outubro Negro". A tendência é aparecerem mais falhas desse tipo,
  em todas as linguagens, não só no PHP.

### E o nosso CRM?

**O CRM em si não é afetado: ele não tem PHP.** É feito em Python (a parte do servidor) e TypeScript (as
telas). Conferido em 30/10/2026: nenhum arquivo PHP no repositório.

**Mas o Coolify é feito em PHP** (com o próprio Laravel). Ele é o painel que publica o CRM no servidor e tem
acesso a tudo o que roda lá. **Ação para a equipe do servidor, agora:** atualizar o Coolify para a versão
**v4.4.7 ou mais nova** (Settings › Update), que já vem com o PHP corrigido (8.4.27). Até atualizar, o
próprio Coolify recomenda desligar o painel. Isso não depende de nenhuma mudança no CRM.

## 2. O que é o Laravel 13

O Laravel é um "kit de construção" de sistemas web para a linguagem PHP: traz pronto o login, o envio de
e-mail, as filas de tarefas, a conversa com o banco de dados. O Laravel 13 saiu em 17/03/2026 e exige PHP
8.3 ou mais novo. Novidades principais: um kit próprio para usar IA (texto, agentes, busca por
significado) e modelos prontos de sistema para várias empresas.

Para o nosso CRM, **adotar o Laravel significaria reescrever o CRM inteiro em outra linguagem.** Não é um
complemento que se "liga" ao que já existe.

## 3. Prós e contras, em português claro

### A favor

| | O que quer dizer na prática |
|---|---|
| Muita gente sabe | No Brasil há muitos programadores de PHP e Laravel. Contratar ou trocar de fornecedor seria mais fácil e, em geral, mais barato. |
| Muita coisa pronta | Telas de administração, login, cobrança e relatórios têm pacotes prontos e conhecidos (por exemplo, o Filament para painéis). |
| Fácil de hospedar | Quase toda hospedagem roda PHP, inclusive o Coolify que já temos. |
| IA embutida | O Laravel 13 traz um kit oficial para usar IA. |
| Suporte longo | Correções de segurança do Laravel 13 até o começo de 2028. |

### Contra

| | O que quer dizer na prática |
|---|---|
| Recomeçar do zero | O CRM tem hoje funil, contratos, carteira, propostas, SDR de IA, WhatsApp, Granola, login Microsoft e quase 2.000 testes automáticos. Reescrever leva **meses** e, nesse tempo, nada novo sai. |
| Risco de perder regras | Cada regra do negócio (travas de preço, alçadas, "não contatar", cálculo da carteira) teria de ser refeita e conferida de novo. É onde os erros entram. |
| Nada que falte hoje | O que o Laravel 13 traz de novo (IA, busca por significado, login, filas) o CRM já tem ou pode ter com o que usa hoje. O Python, aliás, é a linguagem mais usada para IA. |
| PHP sob holofote | Depois do PHP2Shell, o PHP está no centro das atenções dos atacantes. Toda linguagem tem falhas, mas trocar agora seria aumentar a superfície exposta sem ganho. |
| Dois sistemas por um tempo | Numa troca, o antigo e o novo conviveriam: dois lugares para corrigir, dois bancos para conferir. |
| A IA que constrói o CRM | Quem vem construindo o CRM (Claude Code) trabalha bem nas duas linguagens. Não há ganho de velocidade em trocar. |

## 4. Recomendação

**Não migrar o CRM para Laravel.** O custo (meses de reescrita e o risco de errar regras já testadas) é
muito maior que o ganho, e nada do que o Laravel 13 oferece falta ao CRM hoje.

Faria sentido reabrir a conversa se:

- a Critério decidir terceirizar a manutenção para uma equipe que só trabalha com PHP; ou
- surgir uma necessidade que só exista pronta no mundo Laravel (até aqui, nenhuma).

**O que fazer já, independentemente disso:** atualizar o Coolify para a v4.4.7 ou mais nova, por causa do
PHP2Shell (seção 1).

## Fontes (consultadas em 30/10/2026)

- Wiz: [PHP2Shell: AI uncovers critical RCE vulnerabilities](https://www.wiz.io/blog/php2shell-php-rce)
- Fortune: [AI helped discover the PHP vulnerability…](https://fortune.com/2026/10/21/ai-tools-discovered-the-php-vulnerability-that-could-take-down-70-of-the-internet-now-the-race-is-on-to-patch-it-before-ai-powered-hackers-attack/)
- TechCrunch: [US government says hackers are now exploiting critical PHP web bugs](https://techcrunch.com/2026/10/27/us-government-says-hackers-are-now-exploiting-critical-php-web-bugs/)
- CNBC: [AI's 'Black October'](https://www.cnbc.com/2026/10/23/php-vulnerabilities-ai-cybersecurity.html)
- Coolify: [release v4.4.7](https://github.com/coollabsio/coolify/releases/tag/v4.4.7) e
  [PHP Security Advisory 2026](https://coolify.io/docs/knowledge-base/php-security-advisory-2026)
- Laravel News: [Laravel 13](https://laravel-news.com/laravel-13)
