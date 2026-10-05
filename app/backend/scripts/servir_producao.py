"""Sobe a API no servidor (05/10/2026), atrás do proxy que serve a tela e o HTTPS.

    python scripts/servir_producao.py

Passo a passo completo em `app/IMPLANTACAO.md`. Diferenças do `servir.py` (desenvolvimento):

- **Recusa subir sem login.** Aceita a entrada com e-mail e senha (`CRM_ADMIN_EMAIL`,
  `CRM_ADMIN_SENHA_INICIAL` e `CRM_SEGREDO_SESSAO` com 32 caracteres ou mais; decisão de Eduardo em
  05/10/2026, #89) ou a da Microsoft (`CRM_ENTRA_TENANT_ID` e `CRM_ENTRA_CLIENT_ID`), no ambiente ou
  no `backend/.env`. Sem nenhuma, a API não pede entrada: no servidor, isso publicaria a carteira
  inteira sem senha.
- Sem recarga automática e com **um processo só**: a busca automática dos questionários roda dentro
  da API, e vários processos a repetiriam (e o bloqueio de tentativas erradas de senha vive na
  memória do processo).
- Escuta em `CRM_HOST`:`CRM_PORTA` (padrão `127.0.0.1:8000`): só o proxy da mesma máquina fala com
  ela. Confia nos cabeçalhos `X-Forwarded-*` só desse proxy.
- `CRM_PROXY_CONFIAVEL` (padrão `127.0.0.1`): de quem a API aceita `X-Forwarded-For`, em IPs ou faixas
  separados por vírgula. No container (`docker-compose*.yml`) são as faixas privadas, porque o IP do
  nginx da tela muda a cada subida e a API só é alcançável pela rede interna do compose. **Não use
  `*`:** com ele o uvicorn pega o primeiro IP do cabeçalho, que o próprio navegador escreve, e o
  bloqueio de senha por IP deixa de valer. Com faixas, ele anda da direita para a esquerda e fica com
  o primeiro IP fora delas: o do cliente, como o proxy de borda anotou.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.acesso.entrada import ConfiguracaoDeSenha, EntradaMalConfigurada, ler_configuracao  # noqa: E402
from crm.config import padrao_de  # noqa: E402
from crm.db.sessao import ler_ambiente  # noqa: E402

NADA = "Veja app/IMPLANTACAO.md, passo 4. Nada foi iniciado."
SEM_LOGIN = (
    "✗ Falta o login no backend/.env: CRM_ADMIN_EMAIL, CRM_ADMIN_SENHA_INICIAL e CRM_SEGREDO_SESSAO "
    "(e-mail e senha) ou CRM_ENTRA_TENANT_ID e CRM_ENTRA_CLIENT_ID (Microsoft). Sem login a API sobe aberta "
    f"e a carteira fica à vista de quem achar o endereço. {NADA}"
)
SEGREDO_MINIMO = 32
# Os padrões vêm do catálogo único das variáveis (crm/config.py, #93): um lugar só para o literal.
HOST_PADRAO = padrao_de("CRM_HOST")
PORTA_PADRAO = padrao_de("CRM_PORTA")
PROXY_PADRAO = padrao_de("CRM_PROXY_CONFIAVEL")


def parametros(ambiente: dict[str, str]) -> dict:
    """O que o uvicorn recebe, ou `SystemExit` quando falta o login. Separado para o teste.
    Nenhuma mensagem leva o valor de senha ou segredo, só o nome da variável."""
    try:
        config = ler_configuracao(ambiente)
    except EntradaMalConfigurada as falha:
        raise SystemExit(f"✗ {falha} {NADA}") from None
    if config is None:
        raise SystemExit(SEM_LOGIN)
    if isinstance(config, ConfiguracaoDeSenha):
        if not config.admin_senha_inicial:
            raise SystemExit(f"✗ Falta CRM_ADMIN_SENHA_INICIAL no backend/.env. {NADA}")
        if len(config.segredo) < SEGREDO_MINIMO:
            raise SystemExit(
                f"✗ CRM_SEGREDO_SESSAO precisa de pelo menos {SEGREDO_MINIMO} caracteres "
                f"(gere com: openssl rand -hex 32). {NADA}"
            )
    host = (ambiente.get("CRM_HOST") or HOST_PADRAO).strip()
    confiavel = (ambiente.get("CRM_PROXY_CONFIAVEL") or "").strip() or PROXY_PADRAO
    if "*" in (parte.strip() for parte in confiavel.split(",")):
        raise SystemExit(
            "✗ CRM_PROXY_CONFIAVEL=* deixa o navegador escolher o IP que a API vê, e o bloqueio de tentativas "
            f"de senha por IP deixa de valer. Use IPs ou faixas (ex.: 172.16.0.0/12). {NADA}"
        )
    return {
        "host": host,
        "port": int((ambiente.get("CRM_PORTA") or PORTA_PADRAO).strip()),
        "workers": 1,
        "proxy_headers": True,
        "forwarded_allow_ips": confiavel,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("crm.api.app:app", **parametros(ler_ambiente()))
