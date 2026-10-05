#!/usr/bin/env bash
# Entrada do container da API (crmcs).
#
#   1. diretórios de runtime: nenhum. A API não grava em disco (matrizes, backups e arquivos gerados
#      vivem no banco ou na memória); o único lugar gravável que ela usa é o /tmp, para upload grande;
#   2. espera o PostgreSQL responder (pg_isready, até ESPERA_BANCO_SEGUNDOS, padrão 60);
#   3. roda o atualizador (migrações; SKIP_MIGRATIONS=1 pula);
#   4. exec do comando (CMD): a API vira o PID 1 e recebe o SIGTERM do docker direto.
#
# Nada aqui imprime a URL do banco nem a senha.
set -euo pipefail

cd /app || exit 1

log() { printf '[entrypoint] %s\n' "$*"; }

# ---------------------------------------------------------------- 1. runtime
if [ ! -w /tmp ]; then
    log "ERRO: /tmp não é gravável; upload grande (backup, matriz de proposta) falharia."
    exit 1
fi

# ---------------------------------------------------------------- 2. PostgreSQL
# Host, porta e usuário saem de CRM_DATABASE_URL (postgres://, postgresql:// ou
# postgresql+psycopg://usuario:senha@host:porta/banco?opcoes); sem ela, de CRM_DB_*.
host="" porta="" usuario=""
if [ -n "${CRM_DATABASE_URL:-}" ]; then
    resto="${CRM_DATABASE_URL#*://}"          # tira o esquema
    resto="${resto%%[/?]*}"                   # fica usuario:senha@host:porta
    if [[ "$resto" == *@* ]]; then
        credenciais="${resto%@*}"             # até o ÚLTIMO @ (senha pode ter @ codificado ou não)
        endereco="${resto##*@}"
        usuario="${credenciais%%:*}"
    else
        endereco="$resto"
    fi
    if [[ "$endereco" == \[*\]* ]]; then        # IPv6: [::1]:5432
        host="${endereco%%]*}"; host="${host#[}"
        depois="${endereco#*]}"; porta="${depois#:}"
    elif [[ "$endereco" == *:* ]]; then
        host="${endereco%%:*}"; porta="${endereco##*:}"
    else
        host="$endereco"
    fi
else
    host="${CRM_DB_HOST:-}"; porta="${CRM_DB_PORT:-}"; usuario="${CRM_DB_USER:-}"
fi
porta="${porta:-5432}"

if [ -z "$host" ]; then
    log "ERRO: falta CRM_DATABASE_URL (ou CRM_DB_HOST). Nada foi iniciado."
    exit 1
fi

espera="${ESPERA_BANCO_SEGUNDOS:-60}"
log "aguardando PostgreSQL em ${host}:${porta} (até ${espera}s)..."
inicio=$SECONDS
args=(-h "$host" -p "$porta" -t 3)
[ -n "$usuario" ] && args+=(-U "$usuario")
until pg_isready "${args[@]}" >/dev/null 2>&1; do
    if (( SECONDS - inicio >= espera )); then
        log "ERRO: o PostgreSQL em ${host}:${porta} não respondeu em ${espera}s. Nada foi iniciado."
        exit 1
    fi
    sleep 2
done
log "PostgreSQL pronto em $(( SECONDS - inicio ))s."

# ---------------------------------------------------------------- 3. migrações
/app/atualizador.sh

# ---------------------------------------------------------------- 4. a API
log "iniciando: $*"
exec "$@"
