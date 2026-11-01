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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, required=True)
    dim = ap.parse_args().dim
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
        ids = rnd.choice(N_VACANTES, RELEVANTES, replace=False).tolist()
        consulta = "SELECT vacante, m FROM req_blob WHERE vacante = ANY(%s)"
        c.cursor(binary=True).execute(consulta, (ids,)).fetchall()  # calentamiento
        tiempos = []
        for _ in range(10):
            t = time.perf_counter()
            filas = c.cursor(binary=True).execute(consulta, (ids,)).fetchall()
            np.vstack([bytes_como_requisitos(m, dim) for _, m in filas]).astype(np.float32)
            tiempos.append((time.perf_counter() - t) * 1000)
        mb = float(c.execute("SELECT pg_total_relation_size('req_blob') / 1048576.0").fetchone()[0])
        c.execute("DROP TABLE req_blob")

    docs = rnd.normal(size=(N_VACANTES, dim)).astype(np.float32)
    docs /= np.linalg.norm(docs, axis=1, keepdims=True)
    q = docs[0]
    tau = float(np.sort(docs @ q)[-RELEVANTES])
    busqueda_exacta(docs, q, tau)
    t_exacta = []
    for _ in range(20):
        t = time.perf_counter()
        busqueda_exacta(docs, q, tau)
        t_exacta.append((time.perf_counter() - t) * 1000)

    resultado = {
        "dim": dim,
        "segundos_carga_bytea": s_carga,
        "mb_req_blob": mb,
        "ms_fetch_bytea_3000_p50": float(np.median(tiempos)),
        "ms_busqueda_exacta_f32_p50": float(np.median(t_exacta)),
        "mb_matriz_docs_f32": docs.nbytes / 1048576,
    }
    (RESULTADOS / f"alternativas_{dim}.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado))


if __name__ == "__main__":
    main()
