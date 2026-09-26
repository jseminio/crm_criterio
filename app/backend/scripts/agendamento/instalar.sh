#!/usr/bin/env bash
# Liga (ou desliga) o backup automático diário do CRM no macOS (launchd).
#
#   ./instalar.sh            instala e agenda para todo dia às 12:00
#   ./instalar.sh remover    desliga e remove o agendamento
#
# Se o Mac estiver dormindo ou desligado às 12:00, o launchd roda o backup assim
# que ele voltar. O PostgreSQL precisa estar no ar; se não estiver, o backup falha
# e o CRM avisa por notificação.
set -euo pipefail

ROTULO="com.criterio.crm.backup"
AQUI="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${CRM_PYTHON:-$HOME/.venvs/criterio-crm/bin/python}"
SCRIPT="$(cd "$AQUI/.." && pwd)/backup_agendado.py"
DESTINO="$HOME/Library/LaunchAgents/$ROTULO.plist"
ALVO="gui/$(id -u)"

if [ "${1:-}" = "remover" ]; then
  launchctl bootout "$ALVO/$ROTULO" 2>/dev/null || true
  rm -f "$DESTINO"
  echo "✓ Backup automático desligado. Os arquivos em ~/Backups-CRM foram mantidos."
  exit 0
fi

[ -x "$PYTHON" ] || { echo "✗ Python não encontrado em $PYTHON" >&2; exit 1; }
mkdir -p "$HOME/Backups-CRM" "$HOME/Library/LaunchAgents"
chmod 700 "$HOME/Backups-CRM"
sed -e "s|__PYTHON__|$PYTHON|" -e "s|__SCRIPT__|$SCRIPT|" -e "s|__HOME__|$HOME|g" \
  "$AQUI/$ROTULO.plist.modelo" > "$DESTINO"
plutil -lint "$DESTINO" >/dev/null
launchctl bootout "$ALVO/$ROTULO" 2>/dev/null || true
launchctl bootstrap "$ALVO" "$DESTINO"
echo "✓ Backup automático agendado para todo dia às 12:00."
echo "  Arquivos e log em ~/Backups-CRM (crm-auto-*.zip, backup.log)."
echo "  Rodar agora:  launchctl kickstart $ALVO/$ROTULO"
