from spike.fase0.comun import conectar


def test_pgvector_disponible_y_reciente():
    with conectar() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
    assert tuple(map(int, version.split("."))) >= (0, 8, 0)


def test_halfvec_soportado():
    with conectar() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        assert c.execute("SELECT '[1,2,3]'::halfvec(3)").fetchone()[0] is not None
