"""Evaluación ciega con reclutadores (spec §13.3): los paquetes no delatan qué es cada opción y la clave es reproducible."""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from matching.evaluacion.ciega import asignar, preparar as preparar_ciega, tabular
from matching.evaluacion.evaluar import preparar
from matching.ia.fakes import EmbedderFalso
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

PROHIBIDAS = ("decisor", "similitud", "adaptado", "plan de hoy", "postular", "ajustar", "cerrar_brecha", "descartar",
              "sin_datos", "original")
CVS = {"ana": {"nombre": "Ana Ficticia", "experiencia": ["Reportes de ventas en Excel", "Atención de clientes en tienda"],
               "habilidades": "Excel, servicio al cliente", "expectativas": {}}}


def test_paquete_no_revela_el_origen(db):
    fuente = FuenteEnMemoria([cruda(f"v{i}", "Requisitos:\n- Reportes de ventas en Excel\n- Atención de clientes")
                              for i in range(4)])
    escenario = preparar(CVS, fuente, EmbedderFalso())
    paquetes, clave = preparar_ciega(escenario, CVS, ["ana"], EmbedderFalso(), semilla=1)
    texto = paquetes[0].markdown().lower()
    assert "lista a" in texto and "lista b" in texto
    assert not [p for p in PROHIBIDAS if p in texto]
    assert clave["1"]["cv"] == "ana"


def test_la_asignacion_ab_es_aleatoria_pero_reproducible():
    claves = [f"cv{i}" for i in range(6)]
    assert asignar(claves, 5) == asignar(claves, 5)
    assert {c["listas"]["A"] for c in asignar(claves, 5).values()} == {"decisor", "similitud"}


def test_tabular_cuenta_preferencias():
    clave = {"1": {"cv": "x", "listas": {"A": "decisor", "B": "similitud"}, "cvs": {"1": "adaptado", "2": "original"}}}
    filas = [{"reclutador": "r1", "paquete": "1", "pregunta": "lista", "eleccion": "A"},
             {"reclutador": "r2", "paquete": "1", "pregunta": "lista", "eleccion": "B"},
             {"reclutador": "r1", "paquete": "1", "pregunta": "cv", "eleccion": "1"}]
    resultado = tabular(filas, clave)
    assert resultado["lista"]["decisor"] == 0.5 and resultado["lista"]["por_reclutador"] == {"r1": 1.0, "r2": 0.0}
    assert resultado["cv"]["adaptado"] == 1.0 and resultado["cv"]["n"] == 1


def test_csv_mal_formado_da_error_claro(tmp_path):
    respuestas, clave = tmp_path / "r.csv", tmp_path / "clave.json"
    respuestas.write_text("reclutador,paquete,eleccion\nr1,1,A\n", encoding="utf-8")
    clave.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(CommandError, match="pregunta"):
        call_command("evaluacion_ciega", "tabular", respuestas=respuestas, clave=clave)
