"""Rendimiento de embeddings y reranker. Uso:
python -m spike.fase0.bench_modelos --tipo embedding --modelo <id> --proveedor cpu --n 5000
"""

import argparse
import json
import os
import time

from spike.fase0.comun import RESULTADOS, cargar_embedding, cargar_reranker, usa_prefijo_e5
from spike.fase0.textos import documentos_vacante, resumenes_vacante, unidades_evidencia, unidades_requisito

N_DOCS_LARGOS = 1_000
N_PARES = 400


def _cronometrar(fn) -> float:
    inicio = time.perf_counter()
    fn()
    return time.perf_counter() - inicio


def bench_embedding(modelo: str, proveedor: str, n: int) -> dict:
    m = cargar_embedding(modelo, proveedor)
    p = "passage: " if usa_prefijo_e5(modelo) else ""
    cortas = [p + t for t in unidades_requisito(n, 11)]
    largos = [p + t for t in documentos_vacante(N_DOCS_LARGOS, 12)]
    list(m.embed(cortas[:64]))  # calentamiento: carga del modelo y primer lote, sin cronometrar
    s_cortas = _cronometrar(lambda: list(m.embed(cortas, batch_size=64)))
    s_largos = _cronometrar(lambda: list(m.embed(largos, batch_size=16)))
    return {"unidades_por_s": n / s_cortas, "docs_por_s": N_DOCS_LARGOS / s_largos, "n": n, "segundos": s_cortas + s_largos}


def bench_reranker(modelo: str, proveedor: str) -> dict:
    rr = cargar_reranker(modelo, proveedor)
    evidencias = unidades_evidencia(N_PARES * 5, 13)
    consultas = ["; ".join(evidencias[i : i + 5]) for i in range(0, len(evidencias), 5)]  # perfil resumido
    docs = resumenes_vacante(N_PARES, 14)  # spec §5.2: el reranker compara resúmenes, no la descripción completa
    list(rr.rerank(consultas[0], docs[:8]))  # calentamiento
    # Forma real de uso: un perfil contra un lote de vacantes.
    lotes = [(consultas[i], docs[i : i + 40]) for i in range(0, N_PARES, 40)]
    segundos = _cronometrar(lambda: [list(rr.rerank(q, d, batch_size=40)) for q, d in lotes])
    return {"pares_por_s": N_PARES / segundos, "n": N_PARES, "segundos": segundos}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tipo", choices=["embedding", "reranker"], required=True)
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--proveedor", choices=["cpu", "cuda"], default="cpu")
    ap.add_argument("--n", type=int, default=5_000)
    a = ap.parse_args()

    base = {"tipo": a.tipo, "modelo": a.modelo, "proveedor": a.proveedor, "hilos": os.cpu_count()}
    try:
        medida = bench_embedding(a.modelo, a.proveedor, a.n) if a.tipo == "embedding" else bench_reranker(a.modelo, a.proveedor)
    except Exception as exc:  # p. ej. CUDA no disponible: se registra, no se aborta la fase
        medida = {"error": f"{type(exc).__name__}: {exc}"}

    RESULTADOS.mkdir(exist_ok=True)
    nombre = f"rend_{a.tipo}_{a.modelo.replace('/', '__')}_{a.proveedor}.json"
    (RESULTADOS / nombre).write_text(json.dumps(base | medida, indent=2), encoding="utf-8")
    print(json.dumps(base | medida))


if __name__ == "__main__":
    main()
