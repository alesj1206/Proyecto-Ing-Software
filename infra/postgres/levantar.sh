#!/usr/bin/env bash
# Levanta (o crea) el contenedor de Postgres 17 + pgvector. Idempotente.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Falta infra/postgres/.env (copia .env.ejemplo)"; exit 1; }
set -a; source .env; set +a

if podman container exists scoutly-postgres; then
  podman start scoutly-postgres >/dev/null
else
  # --shm-size: la construcción paralela de HNSW usa /dev/shm; los 64 MB por defecto no alcanzan.
  podman run -d --name scoutly-postgres --env-file .env --shm-size=3g \
    -p "127.0.0.1:${POSTGRES_PORT}:5432" -v scoutly_pgdata:/var/lib/postgresql/data \
    docker.io/pgvector/pgvector:pg17 \
    -c shared_buffers=4GB -c maintenance_work_mem=2GB -c max_parallel_maintenance_workers=6 \
    -c jit=off >/dev/null
fi

for _ in $(seq 1 30); do
  if podman exec scoutly-postgres pg_isready -U "$POSTGRES_USER" -q; then
    # Base de la app v3 (la del spike, $POSTGRES_DB, queda aparte). Idempotente.
    BD_APP="${DJANGO_DB_NAME:-scoutly_v3}"
    existe=$(podman exec scoutly-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
      "SELECT 1 FROM pg_database WHERE datname = '${BD_APP}'")
    [ "$existe" = "1" ] || podman exec scoutly-postgres createdb -U "$POSTGRES_USER" "$BD_APP"
    echo "scoutly-postgres listo en :${POSTGRES_PORT} (base de la app: ${BD_APP})"
    exit 0
  fi
  sleep 1
done
echo "Postgres no respondió en 30 s"; exit 1
