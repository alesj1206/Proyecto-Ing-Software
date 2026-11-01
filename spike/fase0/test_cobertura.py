import numpy as np

from spike.fase0.bench_cobertura import cobertura


def test_cobertura_es_la_mejor_evidencia_por_requisito():
    req = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32)
    evid = np.array([[1.0, 0.0], [0.8, 0.6]], dtype=np.float32)
    np.testing.assert_allclose(cobertura(req, evid), [1.0, 0.6, 0.96], atol=1e-6)
