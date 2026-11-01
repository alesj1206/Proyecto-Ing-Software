"""Costo de la cobertura por candidato: ~3.000 vacantes relevantes × 9 requisitos
contra 30 unidades de evidencia del CV. Uso: python -m spike.fase0.bench_cobertura
"""

import json
import time

import numpy as np

from spike.fase0.comun import RESULTADOS

VACANTES, REQUISITOS, EVIDENCIAS, REPETICIONES = 3_000, 9, 30, 20


def cobertura(req: np.ndarray, evid: np.ndarray) -> np.ndarray:
    """Similitud máxima de cada requisito (fila de `req`) contra toda la evidencia. Vectores normalizados."""
    return (req @ evid.T).max(axis=1)


def medir(dim: int) -> float:
    rnd = np.random.default_rng(dim)
    req = rnd.normal(size=(VACANTES * REQUISITOS, dim)).astype(np.float32)
    evid = rnd.normal(size=(EVIDENCIAS, dim)).astype(np.float32)
    req /= np.linalg.norm(req, axis=1, keepdims=True)
    evid /= np.linalg.norm(evid, axis=1, keepdims=True)
    tiempos = []
    for _ in range(REPETICIONES):
        t = time.perf_counter()
        cobertura(req, evid)
        tiempos.append((time.perf_counter() - t) * 1000)
    return float(np.median(tiempos))


def main() -> None:
    resultado = {f"ms_cobertura_{d}": medir(d) for d in (384, 768)}
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "cobertura.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado))


if __name__ == "__main__":
    main()
