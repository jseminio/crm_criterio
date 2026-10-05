# Implantação do Critério CRM no servidor

Para a equipe que cuida do servidor. Escrito em 05/10/2026, para a `main` dessa data em diante.
Hoje o CRM roda só no Mac de Eduardo; este guia o leva para o servidor da Critério.
Dúvida sobre o funcionamento do CRM: `app/README.md`.

## 0. Regras que não mudam

São decisões de Eduardo, registradas em `arquitetura.md` e `CLAUDE.md`:

1. **Tudo no Brasil:** banco, arquivos e backup ficam em data center brasileiro (decisão de 19/09/2026).
2. **Login Microsoft obrigatório.** Sem ele, a API não pede entrada. O script de produção
   (`servir_producao.py`) se recusa a subir sem a configuração.
3. **Segredo só no `.env` do servidor** (permissão 600) ou num cofre. Nunca no GitHub, em e-mail,
   em chat ou em log.
4. **Dado de cliente nunca passa pelo GitHub.** O repositório tem só código e documentos. Os dados
   chegam por arquivo de backup, por canal seguro (passo 7).
5. **Teste e produção separados:** dois bancos, dois processos da API, dois endereços (passo 10).
6. **A `main` só muda por PR mesclada.** No servidor, só `git pull`; nada de commit lá.

## 1. Como fica

```
navegador ──HTTPS──▶ proxy (nginx ou equivalente)
                      ├─ /        → arquivos da tela (app/frontend/dist)
                      └─ /api/... → API em 127.0.0.1:8000 (servir_producao.py, 1 processo)
                                       └─ PostgreSQL
```

- A tela chama a API no mesmo endereço (`/api/...`), então não é preciso configurar CORS.
- A API não serve a tela; quem serve é o proxy.
- **Um processo só da API:** a busca automática dos questionários do site roda dentro dela, e
  vários processos repetiriam a busca.

## 2. O que instalar

| Peça | Versão | Observação |
|---|---|---|
| Python | 3.12 ou mais nova | |
| Node.js | 22 LTS | só para gerar a tela (`npm run build`); não roda em produção |
| PostgreSQL | 16 ou mais novo | o Mac usa a 18; a API foi conferida na 16 em 05/10/2026. Pode ser banco gerenciado do provedor, no Brasil |
| nginx (ou equivalente) | qualquer atual | HTTPS e proxy |
| git | | para baixar o código |

## 3. Banco e código

```bash
# Banco (ajuste usuário e senha; a senha vai só para o .env do passo 4)
sudo -u postgres psql -c "CREATE USER criterio_crm WITH PASSWORD '<senha>';"
sudo -u postgres psql -c "CREATE DATABASE criterio_crm OWNER criterio_crm;"

# Código
git clone https://github.com/jseminio/crm_criterio.git /srv/crm_criterio
cd /srv/crm_criterio/app/backend
python3.12 -m venv /srv/venv-crm
/srv/venv-crm/bin/pip install -e .

cd ../frontend
npm ci
npm run build          # gera app/frontend/dist
```

## 4. O arquivo `app/backend/.env`

Copie `app/backend/.env.example` para `app/backend/.env`, rode `chmod 600 .env` e preencha.
**Eduardo passa os valores por canal seguro, nunca pelo GitHub.**

| Variável | Para quê | Obrigatória |
|---|---|---|
| `CRM_DATABASE_URL` | `postgresql+psycopg://usuario:senha@servidor:5432/banco`. Tem precedência sobre `CRM_DB_*` | sim |
| `CRM_ENTRA_TENANT_ID`, `CRM_ENTRA_CLIENT_ID` | login Microsoft (os mesmos do Mac; são IDs, não senha) | **sim: sem elas a API não sobe** |
| `CRM_ADMINISTRADORES` | e-mails que entram como Administrador na primeira vez | sim |
| `ANTHROPIC_API_KEY` | ata pela IA, agente SDR, análise da carteira | para essas funções |
| `CRM_M365_*` (4) | envio de e-mail pelo Microsoft 365 | para aprovar abordagem por e-mail |
| `CRM_QUESTIONARIO_URL`, `CRM_QUESTIONARIO_CHAVE` | busca dos questionários do site | para a busca |
| `CRM_HOST`, `CRM_PORTA` | onde a API escuta (padrão `127.0.0.1` e `8000`) | não |

## 5. Microsoft Entra (feito por quem administra o Microsoft 365)

O login hoje funciona para `http://localhost:5173/`. Para o servidor:

1. Entre em portal.azure.com › Microsoft Entra ID › Registros de aplicativo › o aplicativo do CRM
   (o mesmo de `CRM_ENTRA_CLIENT_ID`).
2. Abra **Autenticação** › plataforma **Aplicativo de página única (SPA)**.
3. Acrescente o URI de redirecionamento `https://<endereço do CRM>/`, com a barra no fim. Faça o
   mesmo para o endereço de teste.

Sem isso, a Microsoft recusa a entrada com o erro "redirect URI mismatch".

## 6. Criar as tabelas

```bash
cd /srv/crm_criterio/app/backend
/srv/venv-crm/bin/alembic upgrade head
```

## 7. Trazer os dados do Mac

Ensaiado em 05/10/2026 com dados fictícios: os totais da origem e do destino bateram.

1. **No Mac**, pare de usar o CRM a partir daqui, para ninguém gravar nos dois lugares. Depois:
   ```bash
   cd ~/Projetos/crm_criterio && git pull         # mesma versão do servidor
   cd app/backend && ~/.venvs/criterio-crm/bin/alembic upgrade head
   ~/.venvs/criterio-crm/bin/python scripts/backup.py exportar ~/Backups-CRM/para-servidor.zip
   ```
2. Leve o `.zip` ao servidor por canal seguro (`scp`, `sftp` ou pasta cifrada). **Nunca pelo GitHub
   nem por e-mail:** o arquivo tem todos os dados de cliente, sem criptografia.
3. **No servidor**, com o código na mesma versão do Mac:
   ```bash
   cd /srv/crm_criterio/app/backend
   /srv/venv-crm/bin/python scripts/backup.py verificar /caminho/para-servidor.zip
   /srv/venv-crm/bin/python scripts/backup.py importar /caminho/para-servidor.zip --substituir
   ```
   - O banco recém-criado já tem algumas linhas iniciais das migrações (perfis, metas,
     parâmetros). Por isso precisa do `--substituir`, que pede para digitar `SUBSTITUIR`.
   - A importação é tudo ou nada.
   - Ela recusa backup feito em outra versão do esquema; nesse caso, alinhe as versões e repita.
4. Apague o `.zip` do servidor e do caminho por onde ele passou.

## 8. Deixar a API rodando

Unidade do systemd (`/etc/systemd/system/crm-criterio.service`):

```ini
[Unit]
Description=Critério CRM (API)
After=network.target postgresql.service

[Service]
User=crm
WorkingDirectory=/srv/crm_criterio/app/backend
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/srv/venv-crm/bin/python scripts/servir_producao.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Crie antes um usuário de sistema `crm`, sem login (`useradd --system crm`), dono da pasta do código, para ele ler `app/backend/.env`. Depois:

```bash
systemctl enable --now crm-criterio
```

Proxy (nginx), com HTTPS (Let's Encrypt ou o certificado do provedor):

```nginx
server {
    listen 443 ssl;
    server_name <endereço do CRM>;
    # ssl_certificate ... ; ssl_certificate_key ... ;

    root /srv/crm_criterio/app/frontend/dist;
    location / { try_files $uri /index.html; }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;      # a IA da ata e a proposta em PowerPoint demoram
        client_max_body_size 50m;     # backup e matrizes de proposta sobem por arquivo
    }
}
```

A porta 8000 **não** deve ficar aberta para fora; só o proxy fala com ela.

## 9. Backup fora da máquina (o que fecha o E1)

1. Rode diariamente, por cron ou timer do systemd:
   ```bash
   /srv/venv-crm/bin/python /srv/crm_criterio/app/backend/scripts/backup_agendado.py --pasta /var/backups/crm-criterio --manter 14
   ```
   Ele confere cada arquivo e guarda os últimos 14.
2. Copie a pasta para um armazenamento **em outro data center brasileiro** (object storage do
   provedor, por exemplo), cifrado. Assim, um problema no servidor não leva o backup junto.
3. **Teste a restauração** no banco de teste (passo 10) na implantação e depois uma vez por mês.
   Backup só vale se restaurar. Use `backup.py verificar` e `backup.py importar --substituir`
   **no banco de teste**.

## 10. Ambiente de teste

O mesmo código em outro banco (`criterio_crm_teste`), outro `.env` e outra porta (`CRM_PORTA=8001`).
Use outra pasta do código, outra unidade do systemd e outro endereço (por exemplo, `teste.<endereço>`).
O endereço de teste também precisa estar cadastrado no Entra (passo 5). É nele que se testa a
restauração do backup e cada atualização antes da produção.

## 11. Atualizar quando sair versão nova na `main`

```bash
cd /srv/crm_criterio && git pull
/srv/venv-crm/bin/pip install -e app/backend
(cd app/frontend && npm ci && npm run build)
cd app/backend
/srv/venv-crm/bin/python scripts/backup.py exportar /var/backups/crm-criterio/antes-da-atualizacao.zip
/srv/venv-crm/bin/alembic upgrade head
systemctl restart crm-criterio
```

Faça primeiro no ambiente de teste.

## 12. Conferência final

- [ ] Abrir o endereço pede a conta Microsoft. Sem entrar, `https://<endereço>/api/listas` responde 401.
- [ ] Eduardo entra como Administrador e vê os mesmos números do Mac: oportunidades, contratos, MRR.
- [ ] A porta 8000 não responde de fora do servidor.
- [ ] O backup diário aparece na pasta e na cópia em outro data center.
- [ ] A restauração no ambiente de teste foi feita uma vez, com os totais conferidos.
- [ ] Os servidores, o banco e o backup ficam em data center no Brasil.

## O que não fazer

- Não subir com `servir.py` nem com `iniciar.sh`: são do modo de desenvolvimento, sem as travas
  de produção.
- Não abrir a porta 8000 nem usar ngrok/túnel.
- Não versionar `.env`, backup, planilha ou qualquer arquivo com dado de cliente.
- Não rodar mais de um processo da API no mesmo banco.
