"""pgvector a escala 120k: carga, índice HNSW, búsqueda por umbral (con recall
contra búsqueda exacta) y lectura de requisitos. Uso:
python -m spike.fase0.bench_pgvector --dim 384
"""

import argparse
import json
import time

import numpy as np
from pgvector import HalfVector
from pgvector.psycopg import register_vector

from spike.fase0.comun import RESULTADOS, conectar

N_DOCS = 120_000
REQ_POR_VACANTE = 9
N_CENTROS = 200
N_CONSULTAS = 100
VACANTES_RELEVANTES = 3_000


def crear_tablas(conn, dim: int, prefijo: str = "") -> None:
    conn.execute(f"DROP TABLE IF EXISTS {prefijo}docs, {prefijo}requisitos")
    conn.execute(f"CREATE TABLE {prefijo}docs (id bigint PRIMARY KEY, v halfvec({dim}))")
    conn.execute(f"CREATE TABLE {prefijo}requisitos (id bigint, vacante bigint, v halfvec({dim}))")


def _copiar(conn, tabla: str, columnas: str, tipos: list[str], filas) -> None:
    with conn.cursor().copy(f"COPY {tabla} ({columnas}) FROM STDIN WITH (FORMAT BINARY)") as copy:
        copy.set_types(tipos)
        for fila in filas:
            copy.write_row(fila)


def cargar_docs(conn, vectores: np.ndarray, prefijo: str = "") -> None:
    _copiar(conn, f"{prefijo}docs", "id, v", ["int8", "halfvec"], ((i, HalfVector(v)) for i, v in enumerate(vectores)))


def cargar_requisitos(conn, vectores: np.ndarray, prefijo: str = "") -> None:
    filas = ((i, i // REQ_POR_VACANTE, HalfVector(v)) for i, v in enumerate(vectores))
    _copiar(conn, f"{prefijo}requisitos", "id, vacante, v", ["int8", "int8", "halfvec"], filas)
    conn.execute(f"CREATE INDEX ON {prefijo}requisitos (vacante)")


def crear_indice(conn, prefijo: str = "") -> None:
    conn.execute("SET maintenance_work_mem = '2GB'")
    conn.execute("SET max_parallel_maintenance_workers = 6")
    conn.execute(f"CREATE INDEX ON {prefijo}docs USING hnsw (v halfvec_cosine_ops) WITH (m = 16, ef_construction = 128)")
    conn.execute(f"ANALYZE {prefijo}docs")


def buscar_por_umbral(conn, vector: list[float], tau: float, tope: int = 5_000, tabla: str = "docs") -> list[tuple[int, float]]:
    """Todas las filas con similitud coseno >= tau, de mayor a menor, hasta `tope`.

    Dos pasadas: casi siempre bastan 500; solo si las 500 califican se repite con
    `tope`. El orden de relaxed_order es aproximado, por eso se re-ordena al final.
    """
    conn.execute("SET hnsw.iterative_scan = relaxed_order")
    conn.execute("SET hnsw.ef_search = 200")
    conn.execute("SET hnsw.max_scan_tuples = 50000")
    conn.execute("SET hnsw.scan_mem_multiplier = 2")
    q = HalfVector(np.asarray(vector, dtype=np.float32))
    distancia_max = 1 - tau
    for limite in sorted({min(500, tope), tope}):
        filas = conn.execute(
            f"WITH r AS MATERIALIZED (SELECT id, v <=> %s::halfvec AS d FROM {tabla} ORDER BY d LIMIT %s) SELECT id, d FROM r",
            (q, limite),
        ).fetchall()
        dentro = [(i, 1 - d) for i, d in filas if d <= distancia_max]
        if len(dentro) < limite:
            break
    return sorted(dentro, key=lambda f: f[1], reverse=True)[:tope]


def _normalizar(x: np.ndarray) -> np.ndarray:
    return (x / np.linalg.norm(x, axis=1, keepdims=True)).astype(np.float32)


def _vectores_agrupados(n: int, dim: int, centros: np.ndarray, rnd) -> np.ndarray:
    asignacion = rnd.integers(0, len(centros), n)
    # Ruido de norma ~0.8: similitud ~0.78 con su centro, como textos del mismo tipo de cargo.
    return _normalizar(centros[asignacion] + rnd.normal(scale=0.8 / np.sqrt(dim), size=(n, dim)))


def _mb(conn, tabla: str) -> float:
    return float(conn.execute("SELECT pg_total_relation_size(%s) / 1048576.0", (tabla,)).fetchone()[0])


def _seg(fn) -> float:
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, required=True)
    dim = ap.parse_args().dim
    rnd = np.random.default_rng(dim)
    # Componente común: todas las vacantes en español comparten vocabulario (sim ~0.3 entre grupos).
    comun = _normalizar(rnd.normal(size=(1, dim)))
    centros = _normalizar(0.65 * comun + _normalizar(rnd.normal(size=(N_CENTROS, dim))))
    docs = _vectores_agrupados(N_DOCS, dim, centros, rnd)
    reqs = _vectores_agrupados(N_DOCS * REQ_POR_VACANTE, dim, centros, rnd)
    consultas = _vectores_agrupados(N_CONSULTAS, dim, centros, rnd)

    with conectar() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.execute("CREATE EXTENSION IF NOT EXISTS pg_prewarm")
        register_vector(c)
        crear_tablas(c, dim)
        s_docs = _seg(lambda: cargar_docs(c, docs))
        s_reqs = _seg(lambda: cargar_requisitos(c, reqs))
        s_indice = _seg(lambda: crear_indice(c))
        c.execute("ANALYZE requisitos")
        c.execute("SELECT pg_prewarm('docs'), pg_prewarm('docs_v_idx'), pg_prewarm('requisitos')")

        exactas = docs.astype(np.float16)
        medidas = {}
        for objetivo in (30, VACANTES_RELEVANTES):
            ms, recalls, ms_exacta = [], [], []
            for q in consultas:
                t = time.perf_counter()
                sims = exactas @ q.astype(np.float16)
                ms_exacta.append((time.perf_counter() - t) * 1000)
                tau = float(np.sort(sims)[-objetivo])  # umbral que deja ~objetivo vacantes relevantes
                verdad = set(np.flatnonzero(sims >= tau).tolist())
                buscar_por_umbral(c, q.tolist(), tau)  # calentamiento de esta consulta
                t = time.perf_counter()
                filas = buscar_por_umbral(c, q.tolist(), tau)
                ms.append((time.perf_counter() - t) * 1000)
                recalls.append(len(verdad & {i for i, _ in filas}) / len(verdad))
            medidas[f"k{objetivo}"] = {
                "ms_busqueda_p50": float(np.percentile(ms, 50)),
                "ms_busqueda_p95": float(np.percentile(ms, 95)),
                "recall_promedio": float(np.mean(recalls)),
                "recall_min": float(np.min(recalls)),
                "ms_exacta_numpy_p95": float(np.percentile(ms_exacta, 95)),
            }

        ids = rnd.choice(N_DOCS, VACANTES_RELEVANTES, replace=False).tolist()
        c.execute("SELECT v FROM requisitos WHERE vacante = ANY(%s)", (ids,)).fetchall()  # calentamiento
        ms_fetch = _seg(lambda: c.execute("SELECT vacante, v FROM requisitos WHERE vacante = ANY(%s)", (ids,)).fetchall()) * 1000

        resultado = {
            "dim": dim,
            "segundos_insercion_120k": s_docs,
            "segundos_insercion_requisitos": s_reqs,
            "segundos_indice_hnsw": s_indice,
            "mb_tabla_docs": _mb(c, "docs"),
            "mb_tabla_requisitos": _mb(c, "requisitos"),
            "ms_fetch_requisitos_3000": ms_fetch,
            # El veredicto usa el peor caso: un perfil amplio con ~3.000 vacantes relevantes.
            "ms_busqueda_p95": medidas[f"k{VACANTES_RELEVANTES}"]["ms_busqueda_p95"],
            **medidas,
        }
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / f"pgvector_{dim}.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    main()
