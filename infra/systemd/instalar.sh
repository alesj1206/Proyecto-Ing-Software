#!/usr/bin/env bash
# Instala los servicios de usuario de Scoutly con la ruta real del repo y los deja activos. Idempotente.
# Para quitarlos: systemctl --user disable --now scoutly-web scoutly-batch scoutly-postgres
set -euo pipefail
ORIGEN="$(cd "$(dirname "$0")" && pwd)"
RUTA="$(cd "$ORIGEN/../.." && pwd)"
DESTINO="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$DESTINO"
for unidad in scoutly-postgres scoutly-batch scoutly-web; do
  sed "s|@RUTA@|$RUTA|g" "$ORIGEN/$unidad.service" > "$DESTINO/$unidad.service"
done
systemctl --user daemon-reload
systemctl --user enable --now scoutly-postgres scoutly-batch scoutly-web
echo "Listo. Ver el estado: systemctl --user status scoutly-batch; registros: journalctl --user -u scoutly-batch -f"
