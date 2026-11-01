import numpy as np

from spike.fase0.bench_alternativas import busqueda_exacta, bytes_como_requisitos, requisitos_como_bytes


def test_ida_y_vuelta_bytes():
    m = np.arange(18, dtype=np.float32).reshape(9, 2)
    np.testing.assert_array_equal(bytes_como_requisitos(requisitos_como_bytes(m), 2), m.astype(np.float16))


def test_busqueda_exacta_umbral_orden_y_tope():
    docs = np.array([[1, 0], [0.6, 0.8], [0, 1], [0.8, 0.6]], dtype=np.float32)
    q = np.array([1, 0], dtype=np.float32)
    assert busqueda_exacta(docs, q, 0.5).tolist() == [0, 3, 1]
    assert busqueda_exacta(docs, q, 0.5, tope=2).tolist() == [0, 3]
