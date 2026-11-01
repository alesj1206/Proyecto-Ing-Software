"""Alternativas a los dos cuellos de botella de bench_pgvector:
1) leer requisitos de 3.000 vacantes (2-4 s fila por fila) → un bytea por vacante;
2) recall de HNSW ~93% → búsqueda exacta en numpy float32 sobre la matriz en memoria.
Uso: python -m spike.fase0.bench_alternativas --dim 384
"""

import argparse
import json
import time

import numpy as np

from spike.fase0.comun import RESULTADOS, conectar

N_VACANTES, REQ, RELEVANTES = 120_000, 9, 3_000


def requisitos_como_bytes(matriz: np.ndarray) -> bytes:
    return matriz.astype(np.float16).tobytes()


def bytes_como_requisitos(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float16).reshape(-1, dim)


def busqueda_exacta(matriz: np.ndarray, q: np.ndarray, tau: float, tope: int = 5_000) -> np.ndarray:
    sims = matriz @ q
    idx = np.flatnonzero(sims >= tau)
    if len(idx) > tope:
        idx = idx[np.argpartition(-sims[idx], tope)[:tope]]
    return idx[np.argsort(-sims[idx])]


def busqueda_exacta_postgres(conn, vector: list[float], tau: float, tope: int = 5_000, tabla: str = "docs") -> list[tuple[int, float]]:
    """Búsqueda exacta dentro de Postgres (sin índice): recall total y una sola fuente de verdad.
    SET LOCAL dentro de la transacción para no dejar la sesión con el índice desactivado."""
    from pgvector import HalfVector

    q = HalfVector(np.asarray(vector, dtype=np.float32))
    with conn.transaction():
        conn.execute("SET LOCAL enable_indexscan = off")
        conn.execute("SET LOCAL max_parallel_workers_per_gather = 4")
        return conn.execute(
            f"SELECT id, 1 - (v <=> %s::halfvec) AS sim FROM {tabla} WHERE v <=> %s::halfvec <= %s ORDER BY v <=> %s::halfvec LIMIT %s",
            (q, q, 1 - tau, q, tope),
        ).fetchall()


def medir_exacta_postgres(dim: int, n_consultas: int = 30) -> dict:
    """Sobre la tabla docs que dejó bench_pgvector (con vectores agrupados como los reales)."""
    from pgvector.psycopg import register_vector

    with conectar() as c:
        register_vector(c)
        if c.execute("SELECT count(*) FROM docs").fetchone()[0] != N_VACANTES:
            raise RuntimeError("corre primero bench_pgvector con la misma dimensión")
        ids = np.random.default_rng(1).choice(N_VACANTES, n_consultas + 1, replace=False).tolist()
        consultas = [np.asarray(c.execute("SELECT v FROM docs WHERE id = %s", (i,)).fetchone()[0].to_numpy(), dtype=np.float32) for i in ids]
        busqueda_exacta_postgres(c, consultas[-1].tolist(), 0.5)  # calentamiento con otra consulta
        tiempos, filas = [], []
        for q in consultas[:-1]:
            t = time.perf_counter()
            res = busqueda_exacta_postgres(c, q.tolist(), 0.5)
            tiempos.append((time.perf_counter() - t) * 1000)
            filas.append(len(res))
    return {"ms_busqueda_exacta_pg_p95": float(np.percentile(tiempos, 95)), "filas_promedio": float(np.mean(filas))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, required=True)
    ap.add_argument("--solo-postgres", action="store_true")
    args = ap.parse_args()
    dim = args.dim
    if args.solo_postgres:
        ruta = RESULTADOS / f"alternativas_{dim}.json"
        datos = json.loads(ruta.read_text(encoding="utf-8")) | medir_exacta_postgres(dim)
        ruta.write_text(json.dumps(datos, indent=2), encoding="utf-8")
        print(json.dumps(datos))
        return
    rnd = np.random.default_rng(dim)

    reqs = rnd.normal(size=(N_VACANTES, REQ, dim)).astype(np.float16)
    with conectar() as c:
        c.execute("DROP TABLE IF EXISTS req_blob")
        c.execute("CREATE TABLE req_blob (vacante bigint PRIMARY KEY, m bytea)")
        t = time.perf_counter()
        with c.cursor().copy("COPY req_blob (vacante, m) FROM STDIN WITH (FORMAT BINARY)") as copy:
            copy.set_types(["int8", "bytea"])
            for i in range(N_VACANTES):
                copy.write_row((i, requisitos_como_bytes(reqs[i])))
        s_carga = time.perf_counter() - t
        c.execute("ANALYZE req_blob")
        consulta = "SELECT vacante, m FROM req_blob WHERE vacante = ANY(%s)"
        c.cursor(binary=True).execute(consulta, (rnd.choice(N_VACANTES, RELEVANTES, replace=False).tolist(),)).fetchall()  # calentamiento
        tiempos = []
        for _ in range(20):  # cada repetición con un conjunto distinto de vacantes
            ids = rnd.choice(N_VACANTES, RELEVANTES, replace=False).tolist()
            t = time.perf_counter()
            filas = c.cursor(binary=True).execute(consulta, (ids,)).fetchall()
            np.vstack([bytes_como_requisitos(m, dim) for _, m in filas]).astype(np.float32)
            tiempos.append((time.perf_counter() - t) * 1000)
        mb = float(c.execute("SELECT pg_total_relation_size('req_blob') / 1048576.0").fetchone()[0])
        c.execute("DROP TABLE req_blob")

    docs = rnd.normal(size=(N_VACANTES, dim)).astype(np.float32)
    docs /= np.linalg.norm(docs, axis=1, keepdims=True)
    busqueda_exacta(docs, docs[-1], 0.0)  # calentamiento
    t_exacta = []
    for q in docs[:100]:  # 100 consultas distintas, cada una con el umbral que deja ~3.000 relevantes
        tau = float(np.partition(docs @ q, -RELEVANTES)[-RELEVANTES])
        t = time.perf_counter()
        busqueda_exacta(docs, q, tau)
        t_exacta.append((time.perf_counter() - t) * 1000)

    resultado = {
        "dim": dim,
        "segundos_carga_bytea": s_carga,
        "mb_req_blob": mb,
        "ms_fetch_bytea_3000_p95": float(np.percentile(tiempos, 95)),
        "ms_busqueda_exacta_f32_p95": float(np.percentile(t_exacta, 95)),
        "mb_matriz_docs_f32": docs.nbytes / 1048576,
    }
    (RESULTADOS / f"alternativas_{dim}.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado))


if __name__ == "__main__":
    main()
