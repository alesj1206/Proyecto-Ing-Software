import pytest

from spike.fase0.calidad import UMBRAL_CALIDAD, cargar_calidad, evaluar_embeddings, evaluar_reranker
from spike.fase0.comun import MODELOS_EMBEDDING, MODELOS_RERANKER, usa_prefijo_e5


def test_yaml_cubre_casos_obligatorios():
    casos = cargar_calidad()
    assert len(casos) == 40
    assert all({"requisito", "positivo", "negativo", "tipo"} <= c.keys() for c in casos)
    assert any("nodejs" in c["positivo"].lower().replace(".", "") for c in casos)
    tipos = {c["tipo"] for c in casos}
    assert {"variante", "sinonimo", "implicita", "negativo_dificil", "acentos"} <= tipos
    industrias_no_tech = {c["industria"] for c in casos} - {"tecnología"}
    assert len(industrias_no_tech) >= 4


def test_umbral_definido():
    assert UMBRAL_CALIDAD == 0.85


@pytest.mark.lento
@pytest.mark.parametrize("modelo", MODELOS_EMBEDDING)
def test_embeddings_miden_los_40(modelo):
    r = evaluar_embeddings(modelo, con_prefijo=usa_prefijo_e5(modelo))
    assert r["total"] == 40 and 0.0 <= r["exactitud"] <= 1.0


@pytest.mark.lento
@pytest.mark.parametrize("modelo", [m for m in MODELOS_EMBEDDING if usa_prefijo_e5(m)])
def test_e5_sin_prefijo_tambien_se_mide(modelo):
    assert evaluar_embeddings(modelo, con_prefijo=False)["total"] == 40


@pytest.mark.lento
@pytest.mark.parametrize("modelo", MODELOS_RERANKER)
def test_reranker_mide_los_40(modelo):
    r = evaluar_reranker(modelo)
    assert r["total"] == 40 and 0.0 <= r["exactitud"] <= 1.0


def test_cuda_ausente_falla_explicito():
    import onnxruntime

    from spike.fase0.comun import _providers

    if "CUDAExecutionProvider" in onnxruntime.get_available_providers():
        pytest.skip("este entorno sí tiene CUDA")
    with pytest.raises(RuntimeError, match="CUDAExecutionProvider"):
        _providers("cuda")
