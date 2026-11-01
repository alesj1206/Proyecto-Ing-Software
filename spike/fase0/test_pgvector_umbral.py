import numpy as np
import pytest
from pgvector.psycopg import register_vector

from spike.fase0.bench_pgvector import buscar_por_umbral, cargar_docs, crear_indice, crear_tablas
from spike.fase0.comun import conectar

D = 32


@pytest.fixture(scope="module")
def conn_y_consulta():
    rnd = np.random.default_rng(0)
    consulta = rnd.normal(size=D).astype(np.float32)
    consulta /= np.linalg.norm(consulta)
    cerca = consulta + rnd.normal(scale=0.05, size=(1_500, D)).astype(np.float32)  # sim ~0.96
    lejos = rnd.normal(size=(18_500, D)).astype(np.float32)
    vectores = np.vstack([cerca, lejos])
    vectores /= np.linalg.norm(vectores, axis=1, keepdims=True)
    with conectar() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(c)
        crear_tablas(c, D, prefijo="test_")
        cargar_docs(c, vectores, prefijo="test_")
        crear_indice(c, prefijo="test_")
        yield c, consulta
        c.execute("DROP TABLE IF EXISTS test_docs, test_requisitos")


def test_umbral_devuelve_mas_que_ef_search(conn_y_consulta):
    conn, consulta = conn_y_consulta
    filas = buscar_por_umbral(conn, consulta.tolist(), tau=0.9, tabla="test_docs")
    assert len(filas) >= 1400  # ef_search por defecto es 40
    assert all(s >= 0.9 for _, s in filas)
    sims = [s for _, s in filas]
    assert sims == sorted(sims, reverse=True)


def test_tope_de_seguridad(conn_y_consulta):
    conn, consulta = conn_y_consulta
    assert len(buscar_por_umbral(conn, consulta.tolist(), tau=0.0, tope=500, tabla="test_docs")) == 500


def test_tamano_tabla_es_serializable(conn_y_consulta):
    import json

    from spike.fase0.bench_pgvector import _mb

    conn, _ = conn_y_consulta
    json.dumps({"mb": _mb(conn, "test_docs")})
