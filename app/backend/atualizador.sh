#!/usr/bin/env bash
# =============================================================================
# Critério CRM (crmcs) — atualizador.sh
# -----------------------------------------------------------------------------
# Atualizador IDEMPOTENTE do banco e do ambiente, executado em TODO Redeploy
# (Coolify): o app/backend/entrypoint.sh o chama antes de subir a API.
#
# Regra do dono (#93, 05/10/2026): NENHUMA mudança estrutural (banco, dados,
# configuração, variáveis) exige comando manual no servidor. O que estiver
# pendente é aplicado aqui, sozinho, nesta ordem:
#   1) AMBIENTE      confere as variáveis contra o catálogo único (crm/config.py).
#                    Obrigatória ausente ou inválida aborta a subida dizendo qual
#                    e onde configurar. Vem antes de tudo: com o container mal
#                    configurado, não se mexe no banco.
#   2) BACKUP        pg_dump -Fc no volume /app/backups (crmcs_backups), só quando
#                    há migração pendente; guarda os dos últimos BACKUP_ANTES_DIAS
#                    dias (padrão 7), e o mais recente sempre fica.
#   3) MIGRAÇÕES     alembic upgrade head, só se o banco está atrás do head.
#   4) MANUTENÇÃO    tarefas de dados versionadas, rodadas UMA vez e registradas em
#                    manutencao_aplicada (lista em crm/manutencao/registro.py).
#   5) CONFERÊNCIAS  só relatam: esquema = head, conta do admin, contagens, espaço.
#
# Sem nada pendente, cada etapa diz "nada a fazer": é seguro rodar sempre.
#
# Seed: NÃO há seed aqui. As linhas iniciais (perfis, metas, parâmetros) vêm das
# migrações, e a conta de CRM_ADMIN_EMAIL é criada pela API ao subir (lifespan,
# semear_administrador), só se ainda não existir. Dado novo ou corrigido em banco
# que já existe: tarefa de manutenção (etapa 4), nunca comando à mão.
#
# Como é disparado:
#   - Automaticamente: entrypoint.sh, a cada subida do container (todo Redeploy).
#   - À mão (nunca necessário): terminal do crmcs-api no Coolify,
#     bash /app/atualizador.sh
#
# Controles (todos opcionais, com padrão seguro; catalogados em crm/config.py e
# presentes no .env.example e no docker-compose.coolify.yml):
#   RUN_ENV_CHECK=true|false    conferir as variáveis (padrão: true)
#   RUN_BACKUP=true|false       backup antes de migração pendente (padrão: true)
#   RUN_MIGRATIONS=true|false   aplicar migrações pendentes; false só informa (padrão: true)
#   RUN_MAINTENANCE=true|false  aplicar tarefas de manutenção pendentes (padrão: true)
#   RUN_CHECKS=true|false       conferências de relato (padrão: true)
#   STRICT_UPDATER=true|false   falha de backup, migração ou manutenção impede a API
#                               de subir (padrão: true): subir com esquema desalinhado
#                               gravaria dado de cliente em tabela errada. Variável
#                               obrigatória ausente aborta SEMPRE.
#   BACKUP_ANTES_DIAS=N         dias que os backups de antes da migração ficam no
#                               volume local; o mais recente nunca é apagado (padrão: 7)
#   SKIP_MIGRATIONS=1           compat.: nada mexe no banco nesta subida (sem backup,
#                               migração nem manutenção). Para restauração à mão.
#
# Saída: 0 = ok (atualizou algo OU nada a fazer); != 0 = a API não sobe.
# Nada aqui imprime a URL do banco, senha ou valor de segredo.
# =============================================================================
set -uo pipefail

log()  { echo "[atualizador] $*"; }
warn() { echo "[atualizador][AVISO] $*" >&2; }
err()  { echo "[atualizador][ERRO] $*" >&2; }

# O diretório do backend (onde fica alembic.ini), relativo ao script: /app no
# container, ou qualquer caminho quando rodado de fora.
diretorio="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$diretorio" || { err "não consegui entrar em ${diretorio}"; exit 1; }

verdade() { case "${1,,}" in 1|true|sim|yes|on) return 0 ;; *) return 1 ;; esac; }

pular_banco=0
if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then
    pular_banco=1
    RUN_MIGRATIONS="false"
    RUN_MAINTENANCE="false"
fi
RUN_ENV_CHECK="${RUN_ENV_CHECK:-true}"
RUN_BACKUP="${RUN_BACKUP:-true}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
RUN_MAINTENANCE="${RUN_MAINTENANCE:-true}"
RUN_CHECKS="${RUN_CHECKS:-true}"
STRICT_UPDATER="${STRICT_UPDATER:-true}"
BACKUP_ANTES_DIAS="${BACKUP_ANTES_DIAS:-7}"

houve_mudanca=0
esquema_em_dia=0
motivo_da_falha=""
ultima_saida=""

# As revisões, uma por linha, ordenadas: a primeira palavra de cada linha que parece revisão.
revisoes() { awk '$1 ~ /^[0-9A-Za-z_]+$/ {print $1}' | sort -u; }

# relatar <rótulo> <comando...>: roda o comando, repassa cada linha com o prefixo
# (ERRO:/AVISO: vão para o stderr), guarda a saída em ultima_saida e devolve o código dele.
relatar() {
    local rotulo="$1"; shift
    local arquivo linha status
    arquivo="$(mktemp)"
    "$@" 2>&1 | tee "$arquivo" | while IFS= read -r linha; do
        case "$linha" in
            ERRO:*)  err "${rotulo}: ${linha#ERRO: }" ;;
            AVISO:*) warn "${rotulo}: ${linha#AVISO: }" ;;
            *)       log "${rotulo}: ${linha}" ;;
        esac
    done
    status="${PIPESTATUS[0]}"
    ultima_saida="$(cat "$arquivo")"
    rm -f "$arquivo"
    return "$status"
}

# -----------------------------------------------------------------------------
# 1) AMBIENTE — as variáveis contra o catálogo (scripts/conferir_ambiente.py).
# -----------------------------------------------------------------------------
conferir_ambiente() {
    if ! verdade "${RUN_ENV_CHECK}"; then
        log "RUN_ENV_CHECK=false — pulando a conferência das variáveis."
        return 0
    fi
    relatar "ambiente" python scripts/conferir_ambiente.py
}

# -----------------------------------------------------------------------------
# 2) BACKUP — pg_dump antes da migração pendente (crm/backup/antes_da_migracao.py).
#    Só é chamado por aplicar_migracoes, quando o banco está atrás do head.
#    Grava no volume local e apaga os com mais de BACKUP_ANTES_DIAS dias.
#    Devolve 0 = feito ou dispensado; != 0 = falhou (quem chama decide por STRICT_UPDATER).
# -----------------------------------------------------------------------------
fazer_backup_antes() {
    local de="${1:-}" para="${2:-}"
    if ! verdade "${RUN_BACKUP}"; then
        warn "RUN_BACKUP=false — a migração vai ser aplicada SEM backup antes."
        return 0
    fi
    log "backup do banco antes da migração (${de:-<nenhuma>} -> ${para})..."
    relatar "backup" python -m crm.backup.antes_da_migracao --de "${de}" --para "${para}" \
        --dias "${BACKUP_ANTES_DIAS}"
}

# -----------------------------------------------------------------------------
# 3) MIGRAÇÕES — só aplica se o banco estiver atrás do head do Alembic.
# -----------------------------------------------------------------------------
aplicar_migracoes() {
    if [ "${pular_banco}" -eq 1 ]; then
        log "SKIP_MIGRATIONS=1 — backup, migrações e manutenção pulados nesta subida."
        return 0
    fi
    if ! command -v alembic >/dev/null 2>&1; then
        err "'alembic' não encontrado no PATH."
        motivo_da_falha="nas migrações (alembic ausente)"
        return 1
    fi

    local erros atual_bruto cabecas_bruto atual cabecas
    erros="$(mktemp)"
    if ! atual_bruto="$(alembic current 2>"$erros")"; then
        cat "$erros" >&2; rm -f "$erros"
        err "não consegui consultar a revisão do banco (alembic current falhou)."
        err "  confira CRM_DATABASE_URL e se o banco está no ar; nada foi aplicado."
        motivo_da_falha="ao consultar a revisão do banco"
        return 1
    fi
    if ! cabecas_bruto="$(alembic heads 2>"$erros")"; then
        cat "$erros" >&2; rm -f "$erros"
        err "alembic heads falhou."
        motivo_da_falha="ao ler as migrações do código"
        return 1
    fi
    rm -f "$erros"
    atual="$(printf '%s\n' "$atual_bruto" | revisoes | paste -sd+ -)"
    cabecas="$(printf '%s\n' "$cabecas_bruto" | revisoes | paste -sd+ -)"

    log "revisão no código (head): ${cabecas:-<desconhecida>}"
    log "revisão no banco (atual): ${atual:-<nenhuma registrada>}"
    if [ -n "$cabecas" ] && [ "$atual" = "$cabecas" ]; then
        log "esquema em dia: nada a migrar."
        esquema_em_dia=1
        return 0
    fi

    if ! verdade "${RUN_MIGRATIONS}"; then
        warn "há migração pendente e RUN_MIGRATIONS=false: nada aplicado."
        return 0
    fi

    if ! fazer_backup_antes "$atual" "$cabecas"; then
        if verdade "${STRICT_UPDATER}"; then
            err "o backup antes da migração falhou: a migração NÃO foi aplicada e a API não sobe."
            err "  corrija a causa (espaço ou permissão em /app/backups, banco) ou, sabendo do risco, RUN_BACKUP=false."
            motivo_da_falha="no backup antes da migração"
            return 1
        fi
        warn "o backup falhou, mas STRICT_UPDATER=false — aplicando a migração SEM backup."
    fi

    log "há migração pendente — aplicando (alembic upgrade head)..."
    if ! alembic upgrade head; then
        err "falha ao aplicar as migrações (alembic upgrade head)."
        motivo_da_falha="nas migrações"
        return 1
    fi
    log "OK — banco atualizado para a revisão: $(alembic current 2>/dev/null | revisoes | paste -sd+ -)"
    esquema_em_dia=1
    houve_mudanca=1
    return 0
}

# -----------------------------------------------------------------------------
# 4) MANUTENÇÃO — tarefas de dados versionadas, rodadas UMA vez (scripts/manutencao.py).
#    Cada tarefa roda na sua transação, junto com o registro em manutencao_aplicada;
#    falha não registra, e ela roda de novo no próximo Redeploy.
#
#    >>> Para automatizar uma correção de dados: acrescente uma Tarefa em
#        crm/manutencao/registro.py (o passo a passo está lá). Aqui não muda nada. <<<
# -----------------------------------------------------------------------------
rodar_manutencao() {
    if ! verdade "${RUN_MAINTENANCE}"; then
        log "RUN_MAINTENANCE=false (ou SKIP_MIGRATIONS=1) — pulando manutenção."
        return 0
    fi
    if [ "${esquema_em_dia}" -ne 1 ]; then
        warn "esquema fora do head — manutenção adiada para a próxima subida."
        return 0
    fi
    if ! relatar "manutenção" python scripts/manutencao.py; then
        motivo_da_falha="na manutenção de dados"
        return 1
    fi
    case "$ultima_saida" in
        *"aplicada(s) agora"*) houve_mudanca=1 ;;
    esac
    return 0
}

# -----------------------------------------------------------------------------
# 5) CONFERÊNCIAS — olham o estado e RELATAM. Nenhuma altera dado; falha aqui
#    nunca bloqueia a subida. Formato: "Descrição|comando".
# -----------------------------------------------------------------------------
rodar_conferencias() {
    if ! verdade "${RUN_CHECKS}"; then
        log "RUN_CHECKS=false — pulando conferências."
        return 0
    fi

    local conferencias=(
        # Esquema = head, conta do admin, contagens principais e espaço em /app/backups.
        "estado|python scripts/conferir_estado.py"
    )

    local item desc cmd partes
    for item in "${conferencias[@]}"; do
        desc="${item%%|*}"
        cmd="${item#*|}"
        read -r -a partes <<< "$cmd"
        if [ "${#partes[@]}" -gt 1 ] && [ ! -f "${partes[1]}" ]; then
            continue
        fi
        if ! relatar "conferência" "${partes[@]}"; then
            warn "conferência '${desc}' não pôde ser feita (não bloqueia a subida)."
        fi
    done
    return 0
}

# -----------------------------------------------------------------------------
# Execução
# -----------------------------------------------------------------------------
log "iniciando verificação de atualizações..."

if ! conferir_ambiente; then
    err "variável obrigatória ausente ou inválida (acima): a API não sobe."
    err "  configure em Coolify › crmcs › Environment Variables e faça o Redeploy."
    exit 1
fi

if ! aplicar_migracoes; then
    if verdade "${STRICT_UPDATER}"; then
        err "abortando a subida (STRICT_UPDATER=true) por falha ${motivo_da_falha}."
        exit 1
    fi
    warn "seguindo apesar da falha ${motivo_da_falha} (STRICT_UPDATER=false)."
fi

if ! rodar_manutencao; then
    if verdade "${STRICT_UPDATER}"; then
        err "abortando a subida (STRICT_UPDATER=true) por falha ${motivo_da_falha}."
        exit 1
    fi
    warn "seguindo apesar da falha ${motivo_da_falha} (STRICT_UPDATER=false)."
fi

rodar_conferencias

if [ "${houve_mudanca}" -eq 1 ]; then
    log "atualização concluída — havia mudanças a aplicar."
else
    log "nada a atualizar — ambiente já estava em dia."
fi
exit 0
