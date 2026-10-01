# Questionário para proposta — fora do Lovable (01/10/2026)

Página única (`index.html`), sem build. Grava as respostas no projeto Supabase **da Critério**;
o CRM busca de lá com a chave secreta ("Buscar questionários" no Funil).

## Pôr no ar (uma vez)

1. **Banco.** Em supabase.com, entre com a conta da Critério e crie um projeto (plano gratuito,
   região São Paulo). No menu **SQL Editor**, cole todo o `banco.sql` e clique em **Run**.
2. **Chaves.** Em *Project Settings → API Keys*, anote:
   - a **URL do projeto** (`https://xxxx.supabase.co`) e a chave **publicável** (`sb_publishable_…`):
     vão no topo do `index.html` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`). São públicas por natureza;
   - a chave **secreta** (`sb_secret_…`): vai **só** no `backend/.env` do CRM, nunca na página nem no chat:
     ```
     CRM_QUESTIONARIO_URL=https://xxxx.supabase.co
     CRM_QUESTIONARIO_CHAVE=sb_secret_…
     ```
3. **Logomarca.** Ponha `logo_branca.png` nesta pasta (a mesma do site atual). Sem ela a página
   funciona, só sem a logo no topo e no PDF.
4. **Publicar.** Em app.netlify.com/drop, arraste esta pasta. O Netlify devolve o endereço
   (`https://<nome>.netlify.app`). Para mudar o texto ou as perguntas depois, edite o `index.html`
   e arraste de novo. Um endereço da Critério (ex.: `questionario.grupocriterio.com.br`) pode ser
   ligado no Netlify depois.

Enquanto a URL e a chave publicável não forem preenchidas, a página abre mas **não envia**: avisa
o cliente para baixar o PDF e mandar por e-mail.

## Regras do banco (banco.sql)
- O site só **insere**, e só com o consentimento LGPD marcado. Ninguém de fora lê, altera ou apaga.
- O CRM lê os pendentes e marca `importado_crm_em` com a chave secreta.
