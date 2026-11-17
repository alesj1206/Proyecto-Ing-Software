import math
from types import SimpleNamespace as R

import numpy as np

from matching.cobertura import cubrir

DIM = 8
EVIDENCIAS = ["Construí reportes en Excel", "Atendí clientes en tienda"]
MATRIZ_EVID = np.eye(DIM, dtype=np.float32)[:2]  # e0 y e1


def _fila(similitud, con=0):
    """Similitud exacta con la evidencia `con`; el resto en una dirección que ninguna evidencia usa."""
    v = np.zeros(DIM, dtype=np.float32)
    v[con], v[7] = similitud, math.sqrt(1 - similitud ** 2)
    return v


def req(texto, tipo="obligatorio", origen="texto"):
    return R(texto=texto, tipo=tipo, origen=origen)


def _cubrir(reqs, filas, evid=EVIDENCIAS, matriz_evid=MATRIZ_EVID):
    return cubrir(reqs, np.vstack(filas), evid, matriz_evid, tau_alto=0.50, tau_bajo=0.40)


def test_umbrales_cubierto_parcial_faltante():
    c = _cubrir([req("a"), req("b"), req("c")], [_fila(0.55), _fila(0.45), _fila(0.30)])
    assert [r.estado for r in c.requisitos] == ["cubierto", "parcial", "faltante"]


def test_la_evidencia_es_la_mas_parecida():
    c = _cubrir([req("Atención al cliente")], [_fila(0.7, con=1)])
    assert c.requisitos[0].evidencia == "Atendí clientes en tienda"
    assert c.requisitos[0].similitud == np.float32(0.7).item() or abs(c.requisitos[0].similitud - 0.7) < 1e-3


def test_faltante_no_lleva_evidencia():
    assert _cubrir([req("a")], [_fila(0.1)]).requisitos[0].evidencia is None


def test_porcentaje_cuenta_parciales_como_medio():
    c = _cubrir([req("a"), req("b"), req("c"), req("d")], [_fila(0.6), _fila(0.6), _fila(0.45), _fila(0.1)])
    assert c.porcentaje == 63 and (c.obligatorios_cubiertos, c.obligatorios_total) == (2, 4)
    assert [r.texto for r in c.faltantes_obligatorios] == ["d"] and [r.texto for r in c.parciales_con_evidencia] == ["c"]


def test_deseables_no_cuentan_en_el_porcentaje():
    c = _cubrir([req("a"), req("Docker", "deseable", "etiqueta")], [_fila(0.6), _fila(0.1)])
    assert c.porcentaje == 100 and c.faltantes_obligatorios == []


def test_la_formacion_no_se_mide_por_similitud():
    c = _cubrir([req("Técnico en sistemas o afines"), req("a")], [_fila(0.9), _fila(0.6)])
    assert c.requisitos[0].estado == "formacion" and c.obligatorios_total == 1


def test_sin_evidencia_todo_es_faltante():
    c = _cubrir([req("a"), req("b")], [_fila(0.9), _fila(0.9)], evid=[], matriz_evid=np.zeros((0, DIM), np.float32))
    assert [r.estado for r in c.requisitos] == ["faltante", "faltante"] and c.porcentaje == 0


def test_sin_obligatorios_el_porcentaje_es_cero():
    assert _cubrir([req("x", "deseable")], [_fila(0.9)]).porcentaje == 0


# --- calibración (Task 10): los años de experiencia los evalúa la restricción, no la similitud --------

import pytest

from matching.cobertura import es_solo_anios


@pytest.mark.parametrize("texto", ["Experiencia: mínimo 1–2 años", "Mínimo 1 año de experiencia",
                                   "Experiencia mínima de 6 meses", "2 años de experiencia comprobable"])
def test_requisitos_que_solo_piden_anios(texto):
    assert es_solo_anios(texto)


@pytest.mark.parametrize("texto", ["Experiencia mínima de 1 año en el sector educativo",
                                   "Mínimo 2 años de experiencia en análisis de datos", "Manejo de Excel"])
def test_requisitos_con_contenido_no_son_solo_anios(texto):
    assert not es_solo_anios(texto)


def test_los_anios_no_cuentan_ni_generan_ajustes():
    c = _cubrir([req("Experiencia: mínimo 1–2 años"), req("a")], [_fila(0.45), _fila(0.6)])
    assert c.requisitos[0].estado == "experiencia" and c.obligatorios_total == 1 and c.parciales_con_evidencia == []


# --- calibración (Task 10): competencias blandas y condiciones no son brechas --------------------------

from matching.cobertura import es_blando


@pytest.mark.parametrize("texto", ["Trabajo en equipo", "Disponibilidad para laborar en horarios rotativos",
                                   "Aprendizaje rápido", "Ética y valores", "Compromiso con la organización",
                                   "Esquema de vacunación completo (3 dosis Hepatitis B)", "Adaptabilidad",
                                   "Demostrar atención al detalle organización orientación al logro"])
def test_competencias_blandas_y_condiciones(texto):
    assert es_blando(texto)


@pytest.mark.parametrize("texto", ["Atención al cliente en punto de venta", "Manejo de Excel", "Programación",
                                   "Facturación electrónica"])
def test_requisitos_tecnicos_no_son_blandos(texto):
    assert not es_blando(texto)


def test_una_habilidad_blanda_del_cv_no_cubre_un_requisito():
    """Caso real: «…decisiones de diseño con equipos funcionales, líderes té» quedaba cubierto por «Liderazgo» (0,4998)."""
    evid = ["Liderazgo", "Lideré un equipo de 5 analistas en SQL"]
    c = _cubrir([req("Decisiones de diseño con líderes"), req("SQL")], [_fila(0.9, con=0), _fila(0.9, con=1)], evid=evid)
    assert [r.estado for r in c.requisitos] == ["faltante", "cubierto"]


def test_lo_blando_no_cuenta_como_brecha():
    c = _cubrir([req("Trabajo en equipo"), req("a")], [_fila(0.1), _fila(0.6)])
    assert c.requisitos[0].estado == "blando" and c.faltantes_obligatorios == [] and c.obligatorios_total == 1
