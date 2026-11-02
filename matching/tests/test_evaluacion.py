import re
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from matching.evaluacion.evaluar import Par, cargar_pares, evaluar, linea_base, preparar
from matching.ia.fakes import EmbedderFalso
from matching.politica import POLITICA, Politica
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

DATOS = Path("matching/evaluacion")
CVS = {"ana": {"nombre": "Ana Ficticia", "experiencia": ["Reportes de ventas en Excel", "Atención de clientes en tienda"],
               "habilidades": "Excel, servicio al cliente", "expectativas": {}}}


def test_evaluar_calcula_exactitud_y_linea_base(db):
    fuente = FuenteEnMemoria([
        cruda("ok", "Requisitos:\n- Reportes de ventas en Excel\n- Atención de clientes en tienda"),
        cruda("lejos", "Requisitos:\n- Docker Kubernetes\n- Python Django\n- Linux redes")])
    escenario = preparar(CVS, fuente, EmbedderFalso())
    pares = [Par("ana", "ok", "POSTULAR", "cubre todo", "ajuste"), Par("ana", "lejos", "DESCARTAR", "otra área", "ajuste")]
    informe = evaluar(escenario, pares, Politica(tau_relevancia=0.0))
    assert informe.total == 2 and informe.exactitud == 1.0
    assert informe.distribucion == {"POSTULAR": 1, "DESCARTAR": 1}
    assert 0.0 <= informe.exactitud_linea_base <= 1.0


def test_con_fusion_una_etiqueta_ajustar_cv_se_compara_como_postular(db):
    """Con la fusión, Ajustar CV y Postular son una sola acción: así se preregistró y midió prueba_3."""
    escenario = preparar(CVS, FuenteEnMemoria([cruda("ok", "Requisitos:\n- Reportes de ventas en Excel\n- Atención de "
                                                            "clientes en tienda")]), EmbedderFalso())
    pares = [Par("ana", "ok", "AJUSTAR_CV", "lo tiene a medias", "ajuste")]
    con_fusion = evaluar(escenario, pares, Politica(tau_relevancia=0.0, fusionar_ajustar=True))
    sin_fusion = evaluar(escenario, pares, Politica(tau_relevancia=0.0, fusionar_ajustar=False))
    assert con_fusion.exactitud == 1.0 and con_fusion.confusion == {("POSTULAR", "POSTULAR"): 1}
    assert sin_fusion.exactitud == 0.0


def test_linea_base_por_similitud_pura():
    politica = Politica(tau_relevancia=0.40)  # independiente de los valores calibrados
    assert linea_base(0.55, politica) == "POSTULAR"
    assert linea_base(0.45, politica) == "CERRAR_BRECHA"
    assert linea_base(0.20, politica) == "DESCARTAR"


def test_la_mitad_de_prueba_no_se_usa_sin_confirmar(db):
    with pytest.raises(CommandError, match="Fase 4"):
        call_command("evaluar_decisor", "--mitad", "prueba")


def test_el_set_cubre_las_cinco_acciones_en_ajuste():
    pares = cargar_pares(DATOS / "pares.yaml", "ajuste")
    assert 20 <= len(pares) and {p.accion_esperada for p in pares} == {
        "POSTULAR", "AJUSTAR_CV", "CERRAR_BRECHA", "DESCARTAR", "SIN_DATOS"}
    assert len(cargar_pares(DATOS / "pares.yaml", "prueba")) >= 15


def test_ningun_cv_del_set_tiene_datos_de_personas_reales():
    cvs = yaml.safe_load((DATOS / "cvs.yaml").read_text(encoding="utf-8"))
    assert 10 <= len(cvs) <= 12
    for clave, cv in cvs.items():
        correo = cv.get("contacto")
        assert correo is None or correo.endswith("@correo-ficticio.co"), clave
        sin_expectativas = {k: v for k, v in cv.items() if k != "expectativas"}  # los salarios sí tienen 7 dígitos
        assert not re.search(r"\b\d{7,}\b", yaml.safe_dump(sin_expectativas)), clave


def _informe(filas):
    from collections import Counter
    from matching.evaluacion.evaluar import Informe
    informe = Informe(total=len(filas), aciertos=sum(e == p for e, p in filas))
    informe.confusion = Counter(filas)
    informe.distribucion = Counter(p for _, p in filas)
    return informe


def test_exactitud_por_accion():
    informe = _informe([("POSTULAR", "POSTULAR"), ("POSTULAR", "DESCARTAR"), ("DESCARTAR", "DESCARTAR")])
    assert informe.exactitud_por_accion() == {"POSTULAR": 0.5, "DESCARTAR": 1.0}


def test_tabla_confusion_markdown():
    tabla = _informe([("DESCARTAR", "POSTULAR"), ("DESCARTAR", "POSTULAR"), ("POSTULAR", "POSTULAR")]).tabla_confusion()
    filas = {f.split("|")[1].strip(): f for f in tabla.splitlines()[2:]}
    assert set(filas) == {"DESCARTAR", "POSTULAR"}
    encabezado = [c.strip() for c in tabla.splitlines()[0].split("|")]
    columna = encabezado.index("POSTULAR")
    assert filas["DESCARTAR"].split("|")[columna].strip() == "2"


def test_informe_markdown_lleva_todo_lo_que_se_reporta():
    from matching.evaluacion.evaluar import informe_markdown
    texto = informe_markdown(_informe([("POSTULAR", "POSTULAR"), ("DESCARTAR", "POSTULAR")]), "prueba", POLITICA)
    for esperado in ("prueba", POLITICA.version, "exactitud", "línea base", "clase mayoritaria", "| POSTULAR |", "50%"):
        assert esperado in texto
