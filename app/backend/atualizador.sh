#!/usr/bin/env bash
# ATUALIZADOR do banco da API (crmcs): roda a cada subida do container, antes da API. Idempotente.
#
#   SKIP_MIGRATIONS=1      pula tudo (manutenção, restauração de backup à mão).
#   RUN_MIGRATIONS=true    (padrão) aplica as migrações pendentes; false só informa.
#   STRICT_UPDATER=true    (padrão) se o alembic falhar, a API NÃO sobe: subir com esquema
#                          desalinhado gravaria dado de cliente em tabela errada. false só avisa.
#
# Compara `alembic current` com `alembic heads` e só roda `alembic upgrade head` quando diferem;
# no redeploy sem migração nova, diz "nada a fazer".
#
# Seed: NÃO há seed aqui de propósito. As linhas iniciais (perfis, metas, parâmetros) vêm das próprias
# migrações, e a conta de CRM_ADMIN_EMAIL é criada pela API ao subir (lifespan, semear_administrador),
# só se ainda não existir. Repetir aqui seria duas fontes para a mesma regra.
#
# Não imprime a URL do banco: a mensagem de erro do alembic vai como está, e ela não traz a senha.
set -euo pipefail

cd /app || exit 1

log() { printf '[ATUALIZADOR] %s\n' "$*"; }
verdade() { case "${1,,}" in 1|true|sim|yes|on) return 0 ;; *) return 1 ;; esac; }

if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then
    log "SKIP_MIGRATIONS=1: migrações puladas."
    exit 0
fi

falhou() {
    if verdade "${STRICT_UPDATER:-true}"; then
        log "ERRO: $1 STRICT_UPDATER=true: a API não sobe."
        exit 1
    fi
    log "AVISO: $1 STRICT_UPDATER=false: a API sobe mesmo assim."
    exit 0
}

# As revisões, uma por linha, ordenadas: a primeira palavra de cada linha que parece revisão.
revisoes() { awk '$1 ~ /^[0-9A-Za-z_]+$/ {print $1}' | sort -u; }

log "conferindo a versão do esquema..."
if ! atual_bruto="$(alembic current 2>/tmp/atualizador.err)"; then
    cat /tmp/atualizador.err >&2
    falhou "alembic current falhou."
fi
if ! cabecas_bruto="$(alembic heads 2>/tmp/atualizador.err)"; then
    cat /tmp/atualizador.err >&2
    falhou "alembic heads falhou."
fi
rm -f /tmp/atualizador.err
atual="$(printf '%s\n' "$atual_bruto" | revisoes)"
cabecas="$(printf '%s\n' "$cabecas_bruto" | revisoes)"

log "banco em: ${atual:-<vazio>} | código em: ${cabecas}"
if [ "$atual" = "$cabecas" ]; then
    log "esquema em dia: nada a fazer."
    exit 0
fi

if ! verdade "${RUN_MIGRATIONS:-true}"; then
    log "AVISO: há migração pendente e RUN_MIGRATIONS=false: nada aplicado."
    exit 0
fi

log "aplicando migrações (alembic upgrade head)..."
if ! alembic upgrade head; then
    falhou "alembic upgrade head falhou."
fi
log "migrações aplicadas: banco em $(alembic current 2>/dev/null | revisoes | tr '\n' ' ')"
