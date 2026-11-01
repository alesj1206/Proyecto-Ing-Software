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
