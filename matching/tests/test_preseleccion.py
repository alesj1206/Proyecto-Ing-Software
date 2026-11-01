import logging
import math
from datetime import date

import numpy as np
import pytest

from cuentas.models import Perfil
from matching.preseleccion import preseleccionar
from vacantes.models import Vacante

DIM = 384


def _vector(similitud: float) -> list[float]:
    """Un vector unitario cuya similitud coseno con e0 es exactamente `similitud`."""
    v = np.zeros(DIM, dtype=np.float32)
    v[0], v[1] = similitud, math.sqrt(1 - similitud ** 2)
    return v.tolist()


def _vacante(id_, similitud, modalidad="Presencial", inferida=False, activa=True, con_vector=True):
    return Vacante.objects.create(id=id_, titulo=id_, empresa="ACME", ubicacion="Medellín", modalidad=modalidad,
                                  fecha_publicacion=date(2026, 10, 30), fuente="prueba", hash_contenido="x",
                                  modalidad_inferida=inferida, activa=activa,
                                  vector=_vector(similitud) if con_vector else None)


@pytest.fixture
def perfil(usuario):
    return Perfil.objects.create(usuario=usuario, cv_nombre_archivo="cv.pdf", vector=_vector(1.0))


def test_solo_entran_las_que_superan_tau(perfil):
    _vacante("a", 0.9), _vacante("b", 0.39), _vacante("c", 0.41)
    assert [i for i, _ in preseleccionar(perfil, tau=0.40).relevantes] == ["a", "c"]


def test_ordenadas_por_similitud_descendente(perfil):
    _vacante("a", 0.5), _vacante("b", 0.8), _vacante("c", 0.6)
    p = preseleccionar(perfil, tau=0.4)
    assert [i for i, _ in p.relevantes] == ["b", "c", "a"] and p.relevantes[0][1] == pytest.approx(0.8, abs=1e-2)


def test_excluye_modalidad_opuesta_y_las_cuenta(perfil):
    perfil.exp_modalidad = "Remoto"
    perfil.save()
    _vacante("presencial", 0.9, "Presencial"), _vacante("hibrida", 0.9, "Híbrido"), _vacante("remota", 0.9, "Remoto")
    p = preseleccionar(perfil, tau=0.4)
    assert {i for i, _ in p.relevantes} == {"hibrida", "remota"} and p.ocultas_por_modalidad == 1


def test_no_excluye_si_la_modalidad_de_la_vacante_es_inferida(perfil):
    perfil.exp_modalidad = "Remoto"
    perfil.save()
    _vacante("inferida", 0.9, "Presencial", inferida=True)
    assert [i for i, _ in preseleccionar(perfil, tau=0.4).relevantes] == ["inferida"]


def test_sin_modalidad_declarada_no_excluye_nada(perfil):
    _vacante("p", 0.9, "Presencial"), _vacante("r", 0.9, "Remoto")
    p = preseleccionar(perfil, tau=0.4)
    assert len(p.relevantes) == 2 and p.ocultas_por_modalidad == 0


def test_ignora_vacantes_sin_vector_o_inactivas(perfil):
    _vacante("sin", 0.9, con_vector=False), _vacante("inactiva", 0.9, activa=False), _vacante("ok", 0.9)
    assert [i for i, _ in preseleccionar(perfil, tau=0.4).relevantes] == ["ok"]


def test_perfil_sin_vector_no_tiene_relevantes(perfil):
    perfil.vector = None
    perfil.save()
    _vacante("a", 0.9)
    assert preseleccionar(perfil, tau=0.4).relevantes == []


def test_tope_tecnico_se_marca_y_se_registra(perfil, caplog):
    for i in range(3):
        _vacante(f"v{i}", 0.9 - i / 100)
    with caplog.at_level(logging.WARNING):
        p = preseleccionar(perfil, tau=0.4, tope=2)
    assert p.tope_alcanzado and len(p.relevantes) == 2 and "tope" in caplog.text
