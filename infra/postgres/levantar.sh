#!/usr/bin/env bash
# Levanta (o crea) el contenedor de Postgres 17 + pgvector. Idempotente.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Falta infra/postgres/.env (copia .env.ejemplo)"; exit 1; }
set -a; source .env; set +a

if podman container exists scoutly-postgres; then
  podman start scoutly-postgres >/dev/null
else
  podman run -d --name scoutly-postgres --env-file .env \
    -p "${POSTGRES_PORT}:5432" -v scoutly_pgdata:/var/lib/postgresql/data \
    docker.io/pgvector/pgvector:pg17 >/dev/null
fi

for _ in $(seq 1 30); do
  podman exec scoutly-postgres pg_isready -U "$POSTGRES_USER" -q && { echo "scoutly-postgres listo en :${POSTGRES_PORT}"; exit 0; }
  sleep 1
done
echo "Postgres no respondió en 30 s"; exit 1
