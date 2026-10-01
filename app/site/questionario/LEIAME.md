# Questionário para proposta — fora do Lovable (01/10/2026)

**Configurado em 01/10/2026:** projeto Supabase `fowkrqvcawdkackanjfh` (conta da Critério), tabela criada
com o `banco.sql`, chave publicável já na página e o CRM conectado (`definir_questionario.py`).
Falta só publicar (passo 4).

Página única (`index.html`), sem build. Grava as respostas no projeto Supabase **da Critério**;
o CRM busca de lá com a chave secreta ("Buscar questionários" no Funil).

## Pôr no ar (uma vez)

1. **Banco.** Em supabase.com, entre com a conta da Critério e crie um projeto (plano gratuito,
   região São Paulo). No menu **SQL Editor**, cole todo o `banco.sql` e clique em **Run**.
2. **Chaves.** Em *Project Settings → API Keys*, anote:
   - a **URL do projeto** (`https://xxxx.supabase.co`) e a chave **publicável** (`sb_publishable_…`):
     vão no topo do `index.html` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`). São públicas por natureza;
   - a chave **secreta** (`sb_secret_…`): vai **só** no `backend/.env` do CRM, nunca na página nem no chat.
     No Terminal, este comando pergunta a URL e a chave, grava no `.env` e testa a busca:
     ```
     cd app/backend && ~/.venvs/criterio-crm/bin/python scripts/definir_questionario.py
     ```
3. **Logomarca.** Embutida no próprio `index.html` (letras brancas, fundo transparente); o `logo_branca.png` fica aqui só como original. Publicar só o
   `index.html` já basta para a logo aparecer no topo e no PDF.
4. **Publicar.** Em app.netlify.com/drop, arraste esta pasta. O Netlify devolve o endereço
   (`https://<nome>.netlify.app`). Para mudar o texto ou as perguntas depois, edite o `index.html`
   e arraste de novo. Um endereço da Critério (ex.: `questionario.grupocriterio.com.br`) pode ser
   ligado no Netlify depois.

Enquanto a URL e a chave publicável não forem preenchidas, a página abre mas **não envia**: avisa
o cliente para baixar o PDF e mandar por e-mail.

## Publicar uma versão nova (no ar desde 01/10/2026)

Site: https://criterio-questionario-proposta.netlify.app (Netlify, ID `6515cf4d-79c7-4b07-b448-155eb73f9171`).
No Terminal, depois do `git pull`:

```
cd app/site/questionario
npx netlify-cli deploy --prod --no-build --dir . --site 6515cf4d-79c7-4b07-b448-155eb73f9171
```

Use o **ID**, não o nome: com o nome o CLI respondeu "Not Found". Na primeira vez numa máquina,
rode antes `npx netlify-cli login` e autorize no navegador.

## Link para os clientes

**https://criterio-questionario-proposta.netlify.app/questionario** — o arquivo `_redirects` faz esse
caminho abrir a mesma página. O WhatsApp de quem envia guarda a prévia de cada endereço: o endereço sem
`/questionario` ficou guardado com a prévia antiga (sem imagem) e por isso não é o que se manda.

## Prévia do link (WhatsApp, e-mail)
O cartão com imagem e título que aparece ao colar o link vem das etiquetas Open Graph no topo do
`index.html` e da imagem `og-image.png` (1200×630). Por isso publique a **pasta inteira**, não só o
`index.html`. As etiquetas apontam para `https://criterio-questionario-proposta.netlify.app/`: se o
endereço mudar (por exemplo, um domínio da Critério), troque-o nelas. O WhatsApp guarda a prévia de
um link por algum tempo; para conferir logo após publicar, teste com o link seguido de `?v=3`.

## Regras do banco (banco.sql)
- O site só **insere**, e só com o consentimento LGPD marcado. Ninguém de fora lê, altera ou apaga.
- O CRM lê os pendentes e marca `importado_crm_em` com a chave secreta.
