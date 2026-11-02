"""Estructura del set de evaluación (spec §10): mitades sin fuga, prueba balanceada y referencias válidas."""

import json
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from matching.evaluacion.capturar import exportar, sin_contactos
from vacantes.fuentes import VacanteCruda

DATOS = Path(__file__).resolve().parents[1] / "evaluacion"
PARES = yaml.safe_load((DATOS / "pares.yaml").read_text(encoding="utf-8"))["pares"]


def _mitad(nombre):
    return [p for p in PARES if p["mitad"] == nombre]


def test_sin_contactos_quita_correos_y_telefonos():
    limpio = sin_contactos("Envía tu hoja a rh@empresa.co o al 300 123 4567. Whatsapp +57 (604) 444-5566")
    assert "@" not in limpio and "300" not in limpio and "444" not in limpio and limpio.startswith("Envía tu hoja a")


def test_exportar_omite_las_ya_conocidas_y_limpia_contactos():
    def cruda(i):
        return VacanteCruda(id=f"mag-{i}", titulo="Analista", empresa="X", ubicacion="Cali", modalidad="",
                            texto_completo="Requisitos: SQL. Escribe a a@b.co", etiquetas=("SQL",),
                            url=f"https://www.magneto365.com/co/empleos/x-{i}", fecha_publicacion=date(2026, 11, 1),
                            salario_min=2000000, salario_max=2500000)
    fuente = type("F", (), {"obtener": lambda self: [cruda(1), cruda(2)]})()
    [registro] = exportar(fuente, excluir_ids={"mag-1"})
    assert registro["id"] == "mag-2" and "@" not in registro["descripcion"]
    assert registro["salario"] == {"min": 2000000, "max": 2500000} and registro["fechaPublicacion"] == "2026-11-01"


def test_las_mitades_no_comparten_vacantes():
    ajuste, prueba_1, prueba = ({p["vacante"] for p in _mitad(m)} for m in ("ajuste", "prueba_1", "prueba"))
    assert prueba & (ajuste | prueba_1) == set() and prueba_1 & ajuste == set()


def test_la_prueba_esta_balanceada():
    prueba = _mitad("prueba")
    conteo = Counter(p["accion_esperada"] for p in prueba)
    assert 22 <= len(prueba) <= 30
    assert all(conteo[a] >= 4 for a in ("POSTULAR", "AJUSTAR_CV", "CERRAR_BRECHA", "DESCARTAR")) and conteo["SIN_DATOS"] >= 3
    assert conteo["DESCARTAR"] / len(prueba) <= 0.35


def test_todo_par_apunta_a_datos_existentes():
    cvs = yaml.safe_load((DATOS / "cvs.yaml").read_text(encoding="utf-8"))
    vacantes = {v["id"] for v in json.loads((DATOS / "vacantes.json").read_text(encoding="utf-8"))}
    assert all(p["cv"] in cvs and p["vacante"] in vacantes for p in PARES)
    assert len({(p["cv"], p["vacante"]) for p in PARES}) == len(PARES)


def test_la_prueba_no_tiene_clones_de_lo_ya_visto():
    """Magneto republica el mismo aviso por ciudad con otro id: hay que comparar el texto, no solo el id."""
    from difflib import SequenceMatcher
    textos = {v["id"]: " ".join(v["descripcion"].lower().split())[:1500]
              for v in json.loads((DATOS / "vacantes.json").read_text(encoding="utf-8"))}
    anteriores = {"prueba": ("ajuste", "prueba_1"), "prueba_2": ("ajuste", "prueba_1", "prueba", "excluida"),
                  "prueba_3": ("ajuste", "prueba_1", "prueba", "excluida", "prueba_2")}
    clones = []
    for mitad, previas in anteriores.items():
        vistas = {p["vacante"] for p in PARES if p["mitad"] in previas}
        for nueva in {p["vacante"] for p in _mitad(mitad)}:
            for vista in vistas:
                comparador = SequenceMatcher(None, textos[nueva], textos[vista])
                if comparador.quick_ratio() > 0.9 and comparador.ratio() > 0.9:
                    clones.append((nueva, vista))
    assert clones == []


def test_la_prueba_2_esta_balanceada():
    prueba = _mitad("prueba_2")
    conteo = Counter(p["accion_esperada"] for p in prueba)
    assert 22 <= len(prueba) <= 30 and all(conteo[a] >= 4 for a in ("POSTULAR", "AJUSTAR_CV", "CERRAR_BRECHA", "DESCARTAR"))
    assert conteo["SIN_DATOS"] >= 3 and conteo["DESCARTAR"] / len(prueba) <= 0.35


def test_la_prueba_3_esta_balanceada():
    """Preregistrada (docs/exploracion/mejoras/PREREGISTRO_prueba_3.md); SIN_DATOS quedó en 2 por falta de vacantes
    escuetas, y se reporta como desvío."""
    prueba = _mitad("prueba_3")
    conteo = Counter(p["accion_esperada"] for p in prueba)
    assert 22 <= len(prueba) <= 30 and all(conteo[a] >= 4 for a in ("POSTULAR", "AJUSTAR_CV", "CERRAR_BRECHA", "DESCARTAR"))
    assert conteo["SIN_DATOS"] >= 2 and conteo["DESCARTAR"] / len(prueba) <= 0.35
