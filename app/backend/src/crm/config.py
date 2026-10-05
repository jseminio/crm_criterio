"""O catálogo único das variáveis de ambiente que o CRM lê (#93, 05/10/2026).

Regra do dono: nenhuma mudança de configuração exige comando manual no servidor. Toda variável que o
código (Python ou os `.sh` do container) lê está aqui, com: obrigatória ou não, o padrão que o código
usa quando ela falta, se é segredo e como chega no container. Os testes (`tests/test_ambiente.py`)
obrigam a regra: variável lida e fora do catálogo, ou fora do `app/backend/.env.example` e do
`docker-compose.coolify.yml`, derruba a suíte.

`conferir(valores)` é a etapa AMBIENTE do `atualizador.sh` (`scripts/conferir_ambiente.py`): obrigatória
ausente ou inválida aborta a subida dizendo qual e onde configurar; opcional ausente é relatada com o
padrão. **Nenhuma linha leva o valor de um segredo** — só o nome da variável.

Variável nova: nasce aqui com padrão seguro (`obrigatoria=False`), no `.env.example` e no compose do
Coolify como `${NOME:-padrão}`. Configuração que não é segredo e muda com o negócio vai para o código
ou para o banco, não para o painel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Literal

__all__ = ["Variavel", "CATALOGO", "POR_NOME", "ONDE_CONFIGURAR", "Conferencia", "conferir", "padrao_de"]

ONDE_CONFIGURAR = "configure em Coolify › crmcs › Environment Variables"

#: Como a variável chega no container (`docker-compose.coolify.yml`):
#: - "painel": vem do painel do Coolify, `${NOME:?…}` se obrigatória ou `${NOME:-padrão}`;
#: - "fixa": valor fixo no compose (não se cria no painel);
#: - "local": só no desenvolvimento, fora do container (o compose não a repassa de propósito).
Origem = Literal["painel", "fixa", "local"]


def _minimo(n: int) -> Callable[[str], str | None]:
    return lambda valor: None if len(valor.strip()) >= n else f"precisa de pelo menos {n} caracteres"


def _email(valor: str) -> str | None:
    return None if "@" in valor else "não parece um e-mail"


def _inteiro_positivo(valor: str) -> str | None:
    return None if valor.strip().isdigit() and int(valor) >= 1 else "precisa ser um número inteiro de 1 para cima"


def _liga_desliga(valor: str) -> str | None:
    return None if valor.strip().lower() in {"true", "false", "1", "0", "sim", "nao", "não", "yes", "no", "on", "off"} \
        else "use true ou false"


@dataclass(frozen=True)
class Variavel:
    nome: str
    descricao: str
    obrigatoria: bool = False
    padrao: str = ""
    """O que o código usa quando ela falta. Vazio = a função fica desligada."""
    segredo: bool = False
    origem: Origem = "painel"
    valor_fixo: str = ""
    """Só para origem "fixa": o valor que o compose do Coolify põe."""
    grupo: str = ""
    """Variáveis que só valem juntas (todas ou nenhuma)."""
    alternativa: tuple[str, ...] = ()
    """Obrigatória que também se satisfaz com estas, todas presentes (ex.: a URL ou as partes)."""
    validar: Callable[[str], str | None] | None = None


CATALOGO: tuple[Variavel, ...] = (
    # --- Obrigatórias no container -------------------------------------------------------------
    Variavel("CRM_DATABASE_URL", "endereço do PostgreSQL (a Postgres URL (internal) do banco do painel)",
             obrigatoria=True, segredo=True, alternativa=("CRM_DB_HOST", "CRM_DB_USER", "CRM_DB_PASSWORD")),
    Variavel("CRM_SEGREDO_SESSAO", "assina as sessões; gere com openssl rand -hex 32",
             obrigatoria=True, segredo=True, validar=_minimo(32)),
    Variavel("CRM_ADMIN_EMAIL", "a conta que nasce Administrador na primeira subida",
             obrigatoria=True, validar=_email),
    Variavel("CRM_ADMIN_SENHA_INICIAL", "a senha dessa conta ao nascer (8 caracteres ou mais)",
             obrigatoria=True, segredo=True),
    # --- Opcionais (vazias = a função fica desligada) ------------------------------------------
    Variavel("ANTHROPIC_API_KEY", "ata pela IA, agente SDR e análise da carteira", segredo=True),
    Variavel("CRM_AGENTE_MODELO", "modelo do agente SDR", padrao="claude-opus-5"),
    Variavel("CRM_M365_TENANT_ID", "envio de e-mail pelo Microsoft 365", grupo="m365"),
    Variavel("CRM_M365_CLIENT_ID", "envio de e-mail pelo Microsoft 365", grupo="m365"),
    Variavel("CRM_M365_CLIENT_SECRET", "envio de e-mail pelo Microsoft 365", segredo=True, grupo="m365"),
    Variavel("CRM_M365_REMETENTE", "envio de e-mail pelo Microsoft 365", grupo="m365"),
    Variavel("CRM_QUESTIONARIO_URL", "busca dos questionários do site", grupo="questionario"),
    Variavel("CRM_QUESTIONARIO_CHAVE", "busca dos questionários do site", segredo=True, grupo="questionario"),
    # --- Atualizador e entrypoint (app/backend/*.sh) -------------------------------------------
    Variavel("SKIP_MIGRATIONS", "1 pula migrações e manutenção numa subida (restauração à mão)", padrao="0",
             validar=_liga_desliga),
    Variavel("RUN_ENV_CHECK", "confere as variáveis antes de subir", padrao="true", validar=_liga_desliga),
    Variavel("RUN_BACKUP", "pg_dump antes de aplicar migração pendente", padrao="true", validar=_liga_desliga),
    Variavel("RUN_MIGRATIONS", "aplica as migrações pendentes; false só informa", padrao="true",
             validar=_liga_desliga),
    Variavel("RUN_MAINTENANCE", "aplica as tarefas de manutenção de dados pendentes", padrao="true",
             validar=_liga_desliga),
    Variavel("RUN_CHECKS", "conferências que só relatam (esquema, admin, contagens, espaço)", padrao="true",
             validar=_liga_desliga),
    Variavel("STRICT_UPDATER", "falha de backup, migração ou manutenção impede a API de subir", padrao="true",
             validar=_liga_desliga),
    Variavel("BACKUP_ANTES_DIAS", "por quantos dias guardar os backups de antes da migração em /app/backups",
             padrao="7", validar=_inteiro_positivo),
    Variavel("ESPERA_BANCO_SEGUNDOS", "quanto o entrypoint espera o PostgreSQL responder", padrao="60",
             validar=_inteiro_positivo),
    # --- Fixas no compose (scripts/servir_producao.py) -----------------------------------------
    Variavel("CRM_HOST", "onde a API escuta", padrao="127.0.0.1", origem="fixa", valor_fixo="0.0.0.0"),
    Variavel("CRM_PORTA", "porta da API", padrao="8000", origem="fixa", valor_fixo="8000"),
    Variavel("CRM_PROXY_CONFIAVEL", "de quem a API aceita X-Forwarded-For (\"*\" é recusado)",
             padrao="127.0.0.1", origem="fixa", valor_fixo="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"),
    # --- Só no desenvolvimento local (o container usa CRM_DATABASE_URL e o login por senha) ------
    Variavel("CRM_DB_HOST", "partes do banco, no lugar da URL", padrao="localhost", origem="local"),
    Variavel("CRM_DB_PORT", "partes do banco, no lugar da URL", padrao="5432", origem="local"),
    Variavel("CRM_DB_NAME", "partes do banco, no lugar da URL", padrao="criterio_crm", origem="local"),
    Variavel("CRM_DB_USER", "partes do banco, no lugar da URL", origem="local"),
    Variavel("CRM_DB_PASSWORD", "partes do banco, no lugar da URL (crua)", segredo=True, origem="local"),
    Variavel("CRM_ENTRA_TENANT_ID", "login pela conta Microsoft (só sem CRM_ADMIN_EMAIL)", origem="local",
             grupo="entra"),
    Variavel("CRM_ENTRA_CLIENT_ID", "login pela conta Microsoft (só sem CRM_ADMIN_EMAIL)", origem="local",
             grupo="entra"),
    Variavel("CRM_ADMINISTRADORES", "e-mails que entram como Administrador no login Microsoft", origem="local"),
)

POR_NOME: dict[str, Variavel] = {v.nome: v for v in CATALOGO}


def padrao_de(nome: str) -> str:
    """O padrão do catálogo, para o código não repetir o literal. `KeyError` se não estiver catalogada."""
    return POR_NOME[nome].padrao


@dataclass
class Conferencia:
    erros: list[str]
    avisos: list[str]
    no_padrao: list[str]
    presentes: list[str]

    @property
    def ok(self) -> bool:
        return not self.erros

    def linhas(self) -> list[str]:
        saida = [f"ERRO: {e}" for e in self.erros]
        saida += [f"AVISO: {a}" for a in self.avisos]
        saida += self.no_padrao
        obrigatorias = [v.nome for v in CATALOGO if v.obrigatoria]
        saida.append(f"obrigatórias presentes: {sum(n in self.presentes for n in obrigatorias)} de {len(obrigatorias)}")
        saida.append("ambiente em dia: nada a fazer." if self.ok and not self.avisos else
                     ("ambiente com avisos (a API sobe)." if self.ok else "ambiente incompleto: a API NÃO sobe."))
        return saida


def conferir(valores: dict[str, str], catalogo: Iterable[Variavel] = CATALOGO) -> Conferencia:
    """Confere as variáveis do container (origem "painel" e "fixa"); as "local" não são cobradas aqui.

    Nunca põe valor em mensagem: só o nome, o problema e onde configurar."""
    catalogo = tuple(catalogo)
    presente = lambda nome: bool((valores.get(nome) or "").strip())  # noqa: E731
    r = Conferencia(erros=[], avisos=[], no_padrao=[], presentes=[])
    for v in catalogo:
        if v.origem == "local":
            continue
        if presente(v.nome):
            r.presentes.append(v.nome)
            problema = v.validar(valores[v.nome]) if v.validar else None
            if problema:
                r.erros.append(f"{v.nome} {problema} ({v.descricao}) — {ONDE_CONFIGURAR}.")
            continue
        if v.obrigatoria:
            if v.alternativa and all(presente(n) for n in v.alternativa):
                r.presentes.append(v.nome)
                continue
            r.erros.append(f"falta {v.nome} (obrigatória: {v.descricao}) — {ONDE_CONFIGURAR}.")
        elif v.padrao:
            r.no_padrao.append(f"{v.nome} ausente: usa o padrão ({v.padrao}).")
        else:
            r.no_padrao.append(f"{v.nome} ausente: desligada ({v.descricao}).")
    grupos: dict[str, list[Variavel]] = {}
    for v in catalogo:
        if v.grupo and v.origem != "local":
            grupos.setdefault(v.grupo, []).append(v)
    for nomes in grupos.values():
        com = [v.nome for v in nomes if presente(v.nome)]
        if com and len(com) < len(nomes):
            faltam = ", ".join(v.nome for v in nomes if v.nome not in com)
            r.avisos.append(f"{nomes[0].descricao}: só vale com todas juntas; falta {faltam} — {ONDE_CONFIGURAR}.")
    return r
