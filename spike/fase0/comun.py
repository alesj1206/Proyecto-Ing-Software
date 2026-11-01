from pathlib import Path

import psycopg

ENV_POSTGRES = Path(__file__).resolve().parents[2] / "infra" / "postgres" / ".env"
RESULTADOS = Path(__file__).resolve().parent / "resultados"


def _leer_env(ruta: Path) -> dict[str, str]:
    pares = (linea.split("=", 1) for linea in ruta.read_text().splitlines() if "=" in linea and not linea.startswith("#"))
    return {k.strip(): v.strip() for k, v in pares}


def conectar() -> psycopg.Connection:
    env = _leer_env(ENV_POSTGRES)
    return psycopg.connect(
        host="localhost",
        port=env["POSTGRES_PORT"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        dbname=env["POSTGRES_DB"],
        autocommit=True,
    )
