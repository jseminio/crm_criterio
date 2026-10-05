# Implantação do Critério CRM no servidor

Para a equipe que cuida do servidor. Escrito em 05/10/2026, para a `main` dessa data em diante.
Hoje o CRM roda só no Mac de Eduardo; este guia o leva para o servidor da Critério.
Dúvida sobre o funcionamento do CRM: `app/README.md`.

## 0. Regras que não mudam

São decisões de Eduardo, registradas em `arquitetura.md` e `CLAUDE.md`:

1. **Tudo no Brasil:** banco, arquivos e backup ficam em data center brasileiro (decisão de 19/09/2026).
2. **Login obrigatório, com e-mail e senha do próprio CRM** (decisão de 05/10/2026, #89; o login
   Microsoft fica desligado). Sem login, a API não pede entrada. O script de produção
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

> **No servidor da Critério (Coolify), siga a seção 13.** Os passos 2 a 11 são o caminho manual
> (systemd + nginx na máquina), para um servidor sem Coolify. As regras do passo 0 e a conferência do
> passo 12 valem para os dois.

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
| `CRM_ADMIN_EMAIL` | liga o login com e-mail e senha; a conta nasce Administrador ao subir a API, se ainda não existir | **sim: sem login a API não sobe** |
| `CRM_ADMIN_SENHA_INICIAL` | a senha dessa conta quando ela nasce (8 caracteres ou mais). O `.env` só semeia: depois de trocada na tela, mudar aqui não muda nada | **sim** |
| `CRM_SEGREDO_SESSAO` | assina as sessões (12 horas). Gere **no servidor** com `openssl rand -hex 32`; precisa de 32 caracteres ou mais. Trocá-lo encerra todas as sessões | **sim** |
| `CRM_ENTRA_TENANT_ID`, `CRM_ENTRA_CLIENT_ID`, `CRM_ADMINISTRADORES` | login Microsoft, **desligado**: com `CRM_ADMIN_EMAIL` presente, é ignorado | não |
| `ANTHROPIC_API_KEY` | ata pela IA, agente SDR, análise da carteira | para essas funções |
| `CRM_M365_*` (4) | envio de e-mail pelo Microsoft 365 | para aprovar abordagem por e-mail |
| `CRM_QUESTIONARIO_URL`, `CRM_QUESTIONARIO_CHAVE` | busca dos questionários do site | para a busca |
| `CRM_HOST`, `CRM_PORTA` | onde a API escuta (padrão `127.0.0.1` e `8000`) | não |
| `CRM_PROXY_CONFIAVEL` | de quem a API aceita `X-Forwarded-For` (IPs ou faixas, por vírgula; padrão `127.0.0.1`). `*` é recusado | não |

## 5. Primeiro acesso e as contas das pessoas

Não há nada a configurar fora do servidor: o login com e-mail e senha é do próprio CRM.

1. Ao subir (passo 8), a API cria a conta de `CRM_ADMIN_EMAIL` como **Administrador**, com
   `CRM_ADMIN_SENHA_INICIAL`. Se a conta já existir (veio no backup do passo 7, por exemplo), a senha
   dela **não** muda; se existir sem senha nenhuma (do tempo do login Microsoft), recebe a inicial.
2. Quem administra entra com essa conta e, em **Configurações › Perfis e acesso**, cadastra cada
   pessoa com uma senha provisória (sem perfil escolhido, ela nasce Administrador). A pessoa pode
   trocar a própria senha depois; não é obrigatório.
3. As contas que vieram do Mac (do tempo da Microsoft) **não têm senha**: quem administra define
   uma para cada, na mesma tela.
4. Passe cada senha provisória por canal seguro, nunca por e-mail ou chat aberto.

Errar a senha 5 vezes seguidas em 15 minutos bloqueia aquele e-mail, só para aquele IP, por 15 minutos;
20 erros de um IP com quaisquer e-mails bloqueiam o IP (redefinir a senha tira o bloqueio do e-mail).
O IP vem do proxy (`X-Forwarded-For`), por isso o nginx do passo 8 precisa mandar esse cabeçalho.
Trocar ou redefinir a senha encerra as sessões abertas com a senha anterior. Com login ligado, a API
não publica `/docs` nem `/openapi.json`. Desativar a pessoa corta o acesso no pedido seguinte, mesmo com a sessão aberta.

O login Microsoft fica no código, desligado. Para voltar a ele, tire `CRM_ADMIN_EMAIL` do `.env`,
preencha o bloco da Microsoft e cadastre o endereço do CRM como URI de redirecionamento (SPA) no
aplicativo do Entra; o passo a passo está no `README.md`, "Ligar a entrada pela conta Microsoft".

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
        client_max_body_size 200m;    # backup e matrizes de proposta sobem por arquivo (a API aceita até 200 MB)
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
Use outro `CRM_SEGREDO_SESSAO` no teste: assim uma sessão aberta no teste não vale na produção. É nele
que se testa a restauração do backup e cada atualização antes da produção.

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

- [ ] Abrir o endereço pede e-mail e senha. Sem entrar, `https://<endereço>/api/listas` responde 401,
      e `https://<endereço>/api/acesso/entrada` responde `{"modo":"senha"}`.
- [ ] A conta de `CRM_ADMIN_EMAIL` entra como Administrador e vê os mesmos números do Mac:
      oportunidades, contratos, MRR. Uma senha errada responde "E-mail ou senha incorretos.".
- [ ] Cada pessoa que vai usar o CRM tem senha (as contas vindas do Mac começam sem) e consegue entrar.
- [ ] `app/backend/.env` com permissão 600 e `CRM_SEGREDO_SESSAO` gerado no servidor, diferente do teste.
- [ ] A porta 8000 não responde de fora do servidor.
- [ ] O backup diário aparece na pasta e na cópia em outro data center.
- [ ] A restauração no ambiente de teste foi feita uma vez, com os totais conferidos.
- [ ] Os servidores, o banco e o backup ficam em data center no Brasil.

## 13. Coolify (Docker Compose)

Servidor da Critério com Coolify v4, endereço `https://crmcs.criterioconsultores.com.br`, a partir da
`main` do repositório público. Depois de configurado, **atualizar é só clicar em Deploy**: a imagem é
refeita, o atualizador aplica sozinho o que estiver pendente (13.3) e a API e a tela voltam.

**Regra (#93, 05/10/2026): nada manual no servidor.** Nenhuma mudança de banco, dado, configuração ou
variável exige comando no terminal do servidor: tudo vem no Redeploy, pelo `app/backend/atualizador.sh`.
Se uma versão pedir "rode X depois do deploy", ela está errada (checklist no `CLAUDE.md` da raiz).

```
navegador ─HTTPS─▶ proxy do Coolify (Traefik, certificado automático)
                    └─▶ crmcs-web :8080 (nginx sem root: a tela + /api/ repassado)
                          └─▶ crmcs-api :8000 (servir_producao.py, 1 processo; sem domínio)
                                └─▶ PostgreSQL criado no painel do Coolify
```

Arquivos: `docker-compose.coolify.yml` (raiz), `app/backend/Dockerfile`, `app/backend/entrypoint.sh`,
`app/backend/atualizador.sh`, `app/frontend/Dockerfile`, `app/frontend/nginx.conf`. Para ensaiar no
computador, o `docker-compose.yml` da raiz sobe tudo, com um PostgreSQL próprio (ver `.env.example`).

### 13.1 Passo a passo (uma vez)

1. **Banco.** No projeto do Coolify: *+ New › Database › PostgreSQL* (16 ou mais nova), no mesmo
   servidor. Deixe **desligado** o *Make it publicly available*: o banco só é visto pela rede interna.
   Inicie o banco e copie a **Postgres URL (internal)**, no formato
   `postgres://usuario:senha@host:5432/postgres`. A API e as migrações aceitam esse formato como vem
   (convertem para o driver do projeto); não é preciso editar.
2. **Recurso.** *+ New › Public Repository* → `https://github.com/jseminio/crm_criterio`, branch
   `main`, **Build Pack: Docker Compose**, **Base Directory: `/`**, **Docker Compose Location:
   `/docker-compose.coolify.yml`**, e **ligue *Connect to Predefined Network*** (13.2). Salve: o
   Coolify lê o compose e mostra os serviços `crmcs-api` e `crmcs-web`.
3. **Variáveis** (*Environment Variables* do recurso). As obrigatórias aparecem marcadas; sem elas o
   deploy recusa com a frase do que falta:

   | Variável | Obrigatória | Valor / como gerar |
   |---|---|---|
   | `CRM_DATABASE_URL` | sim | a Postgres URL (internal) do passo 1 |
   | `CRM_SEGREDO_SESSAO` | sim | `openssl rand -hex 32`, gerado na hora (64 caracteres; mínimo 32). Trocá-lo encerra todas as sessões |
   | `CRM_ADMIN_EMAIL` | sim | o e-mail de quem administra; a conta nasce Administrador na primeira subida |
   | `CRM_ADMIN_SENHA_INICIAL` | sim | 8 caracteres ou mais. Só semeia: depois de trocada na tela, mudar aqui não muda nada |
   | `ANTHROPIC_API_KEY` | não | ata pela IA, agente SDR, análise da carteira |
   | `CRM_AGENTE_MODELO` | não | vazio = modelo padrão do código |
   | `CRM_M365_TENANT_ID`, `CRM_M365_CLIENT_ID`, `CRM_M365_CLIENT_SECRET`, `CRM_M365_REMETENTE` | não | envio de e-mail pelo Microsoft 365 (as quatro juntas) |
   | `CRM_QUESTIONARIO_URL`, `CRM_QUESTIONARIO_CHAVE` | não | busca dos questionários do site (as duas juntas) |
   | `SKIP_MIGRATIONS` | não | `1`: nesta subida nada mexe no banco (sem backup, migração nem manutenção), para restauração à mão. Padrão `0` |
   | `RUN_ENV_CHECK`, `RUN_BACKUP`, `RUN_MIGRATIONS`, `RUN_MAINTENANCE`, `RUN_CHECKS`, `STRICT_UPDATER` | não | padrão `true`; ver 13.3 e o cabeçalho de `app/backend/atualizador.sh` |
   | `BACKUP_ANTES_DIAS` | não | por quantos dias guardar no volume local os backups de antes da migração (o mais recente fica sempre). Padrão `7` |
   | `ESPERA_BANCO_SEGUNDOS` | não | quanto esperar o banco responder na subida. Padrão `60` |

   Marque as de segredo como *Secret* (não aparecem no log do deploy). `CRM_HOST`, `CRM_PORTA` e
   `CRM_PROXY_CONFIAVEL` já vêm fixas no compose: não as crie no painel. A lista completa, com o
   padrão de cada uma, é o catálogo `app/backend/src/crm/config.py`; o atualizador confere o
   ambiente contra ele a cada subida.
4. **Domínio.** No serviço **`crmcs-web`**: `https://crmcs.criterioconsultores.com.br:8080`. O `:8080`
   diz ao Coolify a porta do container; o público continua entrando pelo 443, com certificado
   automático. O serviço **`crmcs-api` fica sem domínio**. Antes, o DNS de
   `crmcs.criterioconsultores.com.br` precisa apontar (registro A) para `179.198.104.21`.
5. **Deploy.** Na primeira vez, o log do `crmcs-api` mostra, nesta ordem: `aguardando PostgreSQL` →
   `[atualizador] ambiente: ambiente em dia` → `[atualizador] backup: [backup] OK` → `há migração
   pendente — aplicando` → `manutenção: nenhuma tarefa registrada — nada a fazer` → `conferência: …` →
   `Uvicorn running`. Os dois serviços ficam *healthy*. O volume `crmcs_backups` aparece em
   *Persistent Storage* do recurso.
6. **Conferência:** o passo 12. Entre com `CRM_ADMIN_EMAIL` e troque a senha inicial na tela.
7. **Dados do Mac:** em vez do passo 7 por linha de comando, use a tela: **Configurações › Backup**,
   com o `.zip` exportado no Mac (`backup.py exportar`): ela confere o arquivo antes, e substituir os
   dados exige confirmação (a mesma regra do `backup.py importar --substituir`). O limite é 200 MB.
   Apague o `.zip` depois.

### 13.2 Rede, porta e IP do cliente

- **Ligue *Connect to Predefined Network*.** O PostgreSQL criado no painel fica na rede `coolify` do
  servidor, e a URL interna usa o nome do container dele: sem a opção, a API não acha o banco.
- **Por que os nomes `crmcs-api` e `crmcs-web`:** a rede `coolify` é compartilhada com os outros
  projetos do servidor (Comercial, N8N, pensheet e outros), e nela o nome do serviço vira nome de DNS.
  Com um `backend` genérico, o nginx da tela poderia mandar `/api` para a API de outro projeto (ou o
  contrário). O prefixo `crmcs` evita a colisão. Não renomeie para nomes genéricos.
- O `crmcs-api` só tem `expose`, sem `ports` e sem domínio: ninguém de fora do servidor chega nele.
  **Dentro** do servidor, os containers dos outros projetos na rede `coolify` alcançam
  `crmcs-api:8000` direto. O login continua valendo para eles, mas, por estarem em IP privado, podem
  escolher o IP que a API vê e escapar do bloqueio de tentativas por IP. Esse é o preço da rede
  compartilhada: um container comprometido de outro projeto poderia tentar senhas sem esse freio.
- IP do cliente: o Traefik anota o IP em `X-Forwarded-For`; o nginx da tela o aceita só de IP privado
  e o repassa; a API (`CRM_PROXY_CONFIAVEL` = faixas privadas) faz a mesma leitura, da direita para a
  esquerda. Um IP forjado pelo navegador no começo do cabeçalho não vale. O bloqueio de tentativas de
  senha por IP (passo 5) depende disso. **Não troque `CRM_PROXY_CONFIAVEL` por `*`**: a API recusa
  subir, porque com `*` valeria o IP que o navegador escrevesse.
- Se um dia houver Cloudflare (ou outro proxy) na frente do Coolify, o IP que chega passa a ser o do
  Cloudflare: aí é preciso configurar o IP real no Traefik antes.

### 13.3 Atualizar (o dia a dia)

PR mesclada na `main` → **Deploy** no Coolify. Nada mais. A cada subida, o `atualizador.sh` faz, em
ordem (log com o prefixo `[atualizador]`):

1. **Ambiente:** confere as variáveis contra o catálogo. Obrigatória ausente ou inválida: a API não
   sobe e o log diz qual e "configure em Coolify › crmcs › Environment Variables". Opcional ausente:
   diz que usa o padrão.
2. **Backup:** só quando há migração pendente, `pg_dump -Fc` do banco em `/app/backups` (volume
   `crmcs_backups`, gravado local), conferido com `pg_restore -l`; apaga os com mais de
   `BACKUP_ANTES_DIAS` dias (7). O mais recente fica sempre, por mais velho que seja.
3. **Migrações:** só se o banco está atrás do head (`esquema em dia: nada a migrar` quando não está).
4. **Manutenção:** tarefas de dados novas (`crm/manutencao/registro.py`), cada uma uma vez só,
   registrada em `manutencao_aplicada`.
5. **Conferências** (só relatam): esquema = head, conta de `CRM_ADMIN_EMAIL`, contagens de
   oportunidades, contratos e usuários, espaço em `/app/backups`.

Falha no backup, numa migração ou numa tarefa: a API **não sobe** (`STRICT_UPDATER=true`) e a tela
responde 502 até corrigir: melhor que gravar em esquema desalinhado. A versão anterior do banco está
no backup da etapa 2. Durante o Deploy, o CRM fica fora por alguns segundos.

**Voltar ao backup de antes da migração** (só em incidente, decisão de quem responde pelo CRM):
o arquivo está em *Persistent Storage › crmcs_backups*; a restauração é `pg_restore --clean
--if-exists -d <banco>` com o cliente 18, numa subida com `SKIP_MIGRATIONS=1`, e a imagem da versão
anterior. Ensaie no ambiente de teste (13.5) antes de precisar.

### 13.4 Backup do banco

- No recurso do PostgreSQL: *Backups* → agendamento diário **`0 6 * * *`**. O Coolify agenda em
  UTC: 6h UTC = **3h de Brasília**. O backup é gravado **localmente** no servidor, com retenção de
  **7 dias** (regra do dono, 05/10/2026). É o mesmo prazo do backup de antes da migração (13.3).
- Gravado local quer dizer na mesma máquina do banco: um problema no servidor leva o banco e os
  backups juntos. A cópia em outro data center brasileiro (passo 9, item 2) continua pendente, e
  cabe ao dono decidir.
- **Teste a restauração** uma vez na implantação e depois todo mês, num banco de teste: backup que
  nunca foi restaurado é hipótese.
- O backup lógico do próprio CRM (Configurações › Backup › Exportar) continua valendo como segunda
  cópia, e é o formato que o passo 7 usa.

### 13.5 Teste separado da produção (passo 0, regra 5)

Outro recurso no Coolify, com outro banco do painel, outro `CRM_SEGREDO_SESSAO` e outro domínio
(por exemplo `crmcs-teste.criterioconsultores.com.br:8080`). É nele que se ensaia a restauração e
cada atualização antes da produção.

## O que não fazer

- Não subir com `servir.py` nem com `iniciar.sh`: são do modo de desenvolvimento, sem as travas
  de produção.
- Não abrir a porta 8000 nem usar ngrok/túnel.
- Não versionar `.env`, backup, planilha ou qualquer arquivo com dado de cliente.
- Não rodar mais de um processo da API no mesmo banco (no Coolify: não escale o `crmcs-api`).
- Não deixar o banco do Coolify público nem dar domínio ao serviço `crmcs-api`.
