from pathlib import Path

import numpy as np
import pytest

from matching.ia import obtener_embedder, obtener_reordenador
from matching.ia.fakes import EmbedderFalso, ReordenadorFalso


def test_el_falso_normaliza_y_es_determinista():
    a, b = EmbedderFalso().embeber(["Manejo de Excel avanzado", "manejo de excel AVANZADO"])
    assert np.allclose(np.linalg.norm(a), 1) and np.allclose(a, b)


def test_el_falso_separa_textos_sin_palabras_en_comun():
    a, b = EmbedderFalso().embeber(["Excel avanzado", "enfermería UCI"])
    assert float(a @ b) < 0.2


def test_el_falso_acerca_textos_con_palabras_en_comun():
    a, b = EmbedderFalso().embeber(["Manejo de Excel avanzado", "Excel avanzado para reportes"])
    assert float(a @ b) > 0.5


def test_embeber_lista_vacia():
    assert EmbedderFalso(dimension=64).embeber([]).shape == (0, 64)


def test_el_reordenador_falso_premia_palabras_compartidas():
    p = ReordenadorFalso().puntuar("analista de datos sql", ["analista sql", "enfermera"])
    assert p[0] > p[1]


def test_la_fabrica_respeta_la_configuracion(settings):
    settings.SCOUTLY_EMBEDDER, settings.SCOUTLY_RERANKER = "falso", ""
    assert isinstance(obtener_embedder(), EmbedderFalso) and obtener_reordenador() is None
    settings.SCOUTLY_RERANKER = "falso"
    assert isinstance(obtener_reordenador(), ReordenadorFalso)


def test_ninguna_vista_importa_fastembed():
    for app in ("cuentas", "vacantes", "matching", "postulaciones", "notificaciones"):
        for vista in Path(app).glob("views*.py"):
            assert "fastembed" not in vista.read_text(encoding="utf-8")


@pytest.mark.lento
def test_minilm_real_separa_requisito_de_ruido():
    from matching.ia.fastembed import EmbedderFastembed

    e = EmbedderFastembed()
    req, evid, ruido = e.embeber(["Manejo de Excel avanzado", "Construí tablas dinámicas en Excel", "Enfermería en UCI"])
    assert req @ evid > 0.5 > req @ ruido and e.dimension == 384
