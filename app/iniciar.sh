#!/usr/bin/env bash
# Sobe o Critério CRM: a API e a tela, cada uma no seu processo.
#
#     ./iniciar.sh
#
# Ctrl+C derruba as duas. Abra http://localhost:5173 no navegador.
#
# A API escuta só em 127.0.0.1 e NÃO tem login (o E1 foi adiado). Não exponha
# esta porta na rede.

set -euo pipefail

RAIZ="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${CRM_PYTHON:-$HOME/.venvs/criterio-crm/bin/python}"
PG_ISREADY="$(command -v pg_isready || echo /Library/PostgreSQL/18/bin/pg_isready)"

falhar() { echo "✗ $1" >&2; exit 1; }

# Falha visível antes de subir qualquer coisa: cada checagem diz o que fazer.
[ -x "$PYTHON" ] || falhar "Ambiente Python não encontrado em $PYTHON. Veja 'Como rodar' em README.md."
[ -d "$RAIZ/frontend/node_modules" ] || falhar "Faltam as dependências da tela. Rode: cd frontend && npm install"
"$PG_ISREADY" -q -h localhost -p 5432 || falhar "O PostgreSQL não está respondendo em localhost:5432. Inicie-o antes."
[ -f "$RAIZ/backend/.env" ] || falhar "Falta backend/.env. Rode: backend/scripts/definir_senha.py, ou copie .env.example."

for porta in 8000 5173; do
  if lsof -nP -iTCP:"$porta" -sTCP:LISTEN >/dev/null 2>&1; then
    falhar "A porta $porta já está em uso — provavelmente o CRM já está rodando. Abra http://localhost:5173."
  fi
done

PIDS=()
encerrar() {
  echo; echo "Encerrando…"
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap encerrar EXIT INT TERM

echo "Subindo a API em 127.0.0.1:8000…"
( cd "$RAIZ/backend" && PYTHONDONTWRITEBYTECODE=1 exec "$PYTHON" scripts/servir.py ) &
PIDS+=($!)

echo "Subindo a tela em localhost:5173…"
( cd "$RAIZ/frontend" && exec npm run dev ) &
PIDS+=($!)

# Espera a API responder de verdade, em vez de supor que subiu.
for _ in $(seq 1 30); do
  curl -s -m 2 -o /dev/null http://127.0.0.1:8000/api/listas && break
  sleep 1
done
curl -s -m 2 -o /dev/null http://127.0.0.1:8000/api/listas \
  || falhar "A API não respondeu em 30 segundos. Veja a mensagem de erro acima."

echo
echo "✓ Pronto. Abra:  http://localhost:5173"
echo "  Ctrl+C para encerrar."
wait
