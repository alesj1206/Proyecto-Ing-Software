"""Candados de aviso de Postgres (advisory locks) para coordinar procesos del batch y la API, en un solo lugar.

Dentro de una transacción se usa el candado de transacción, que Postgres suelta solo con el commit o el rollback. Fuera
de una, el de sesión, que se suelta al salir y también si la conexión se cierra. Así un error a mitad de camino nunca
deja el candado tomado (revisión independiente, hallazgo 3)."""

from contextlib import contextmanager

from django.db import connection

EMBEBIDO = 731_001  # un solo proceso embebe vacantes a la vez
NOTIFICACIONES = 731_002  # un solo proceso genera notificaciones a la vez


@contextmanager
def candado_de_aviso(clave: int, esperar: bool = True):
    """Da True si se tomó el candado. Con `esperar=False` no espera: da False si otro proceso lo tiene."""
    de_transaccion = connection.in_atomic_block
    funcion = ("pg_advisory_xact_lock" if esperar else "pg_try_advisory_xact_lock") if de_transaccion else \
        ("pg_advisory_lock" if esperar else "pg_try_advisory_lock")
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {funcion}(%s)", [clave])
        tomado = True if esperar else bool(cursor.fetchone()[0])
    try:
        yield tomado
    finally:
        if tomado and not de_transaccion:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [clave])
