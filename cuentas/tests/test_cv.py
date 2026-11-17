from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from cuentas.cv.lector import MAX_PAGINAS_CV, extraer_texto
from cuentas.cv.minimizacion import minimizar
from cuentas.cv.secciones import analizar_cv
from cuentas.forms import MAX_BYTES_CV, CVUploadForm
from cuentas.services import guardar_perfil_desde_cv

from .cvs import pdf_cv, pdf_sin_texto, texto_cv


# --- vocabulario abierto -------------------------------------------------------------------------

def test_habilidades_abiertas_fuera_de_cualquier_lista():
    cv = analizar_cv(texto_cv(habilidades="Kubernetes, Power BI, Figma, Contabilidad NIIF"))
    assert {"Kubernetes", "Power BI", "Figma", "Contabilidad NIIF"} <= set(cv.habilidades)


def test_sin_habilidades_no_se_inventan():
    assert analizar_cv(texto_cv(habilidades=None)).habilidades == []


def test_unidades_de_experiencia_por_vineta():
    cv = analizar_cv(texto_cv(experiencia=["Lideré la migración a la nube.", "Automaticé reportes en SQL."]))
    assert [u.texto for u in cv.unidades if u.seccion == "experiencia"] == [
        "Lideré la migración a la nube.", "Automaticé reportes en SQL."]


def test_encabezados_en_minuscula_tambien_cuentan():
    cv = analizar_cv("Pedro Ruiz\nExperiencia laboral:\n- Vendí seguros puerta a puerta.\nHabilidades\nNegociación")
    assert [u.texto for u in cv.unidades if u.seccion == "experiencia"] == ["Vendí seguros puerta a puerta."]
    assert cv.habilidades == ["Negociación"]


def test_vineta_partida_en_dos_lineas_es_una_unidad():
    cv = analizar_cv("Pedro Ruiz\nEXPERIENCIA\n- Coordiné la logística de 3 bodegas\ny 40 conductores.\n- Reduje costos.")
    assert [u.texto for u in cv.unidades if u.seccion == "experiencia"] == [
        "Coordiné la logística de 3 bodegas y 40 conductores.", "Reduje costos."]


# --- minimización ----------------------------------------------------------------------------------

def test_minimizar_quita_datos_personales():
    t = minimizar("Ana Pérez, ana@x.com, +57 300 123 4567, CC 1.020.304.050, Calle 10 # 43-12")
    for dato in ("ana@x.com", "300 123 4567", "1.020.304.050", "Calle 10"):
        assert dato not in t


def test_minimizar_no_borra_rangos_de_fechas_ni_cifras():
    assert minimizar("Analista (2019-2021), manejé 1.500 clientes") == "Analista (2019-2021), manejé 1.500 clientes"


def test_la_evidencia_guardada_esta_minimizada(usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv(experiencia=["Soporte a clientes, escribir a ana@x.com"]))
    assert "ana@x.com" not in " ".join(perfil.evidencias.values_list("texto", flat=True))


# --- casos borde -----------------------------------------------------------------------------------

def test_cv_escaneado_sin_texto(usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_sin_texto("ana_perez_cv.pdf"))
    assert "contacto" in perfil.campos_pendientes and perfil.evidencias.count() == 0
    assert perfil.nombre == "Ana Perez" and perfil.habilidades == []


def test_cargar_cv_otra_vez_reemplaza_la_evidencia(usuario):
    guardar_perfil_desde_cv(usuario, pdf_cv(experiencia=["A.", "B."]))
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv(experiencia=["C."]))
    assert list(perfil.evidencias.filter(seccion="experiencia").values_list("texto", flat=True)) == ["C."]


# --- páginas ---------------------------------------------------------------------------------------

def test_onboarding_carga_el_cv_y_sigue_con_las_expectativas(client, usuario):
    client.force_login(usuario)
    r = client.post(reverse("onboarding"), {"cv": pdf_cv()})
    assert r.status_code == 302 and r.url == reverse("expectativas")
    assert "Power BI" in client.get(reverse("perfil")).content.decode()


def test_onboarding_y_perfil_requieren_sesion(client, db):
    for ruta in ("onboarding", "perfil"):
        assert client.get(reverse(ruta)).status_code == 302


# --- seguridad de la subida (traídos de v2, commit bcc2550) ----------------------------------------

def _subir(contenido, nombre="cv.pdf", tipo="application/pdf"):
    return CVUploadForm(files={"cv": SimpleUploadedFile(nombre, contenido, content_type=tipo)})


def test_acepta_un_pdf_real():
    assert _subir(pdf_cv().read()).is_valid()


def test_rechaza_un_archivo_que_no_es_pdf_aunque_se_llame_pdf():
    form = _subir(b"MZ\x90\x00 esto es un ejecutable")
    assert not form.is_valid() and "cv" in form.errors


def test_rechaza_archivos_de_mas_de_5_mb():
    assert MAX_BYTES_CV == 5 * 1024 * 1024
    form = _subir(b"%PDF-1.7\n" + b"0" * MAX_BYTES_CV)
    assert not form.is_valid() and "5 MB" in form.errors["cv"][0]


def test_solo_lee_las_primeras_paginas():
    from io import BytesIO

    from pypdf import PageObject, PdfWriter

    assert MAX_PAGINAS_CV == 10
    escritor = PdfWriter()
    for _ in range(25):
        escritor.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    escritor.write(buffer)
    leidas = []
    original = PageObject.extract_text

    def contar(pagina, *a, **k):
        leidas.append(pagina)
        return original(pagina, *a, **k)

    with mock.patch("pypdf.PageObject.extract_text", contar):
        extraer_texto(SimpleUploadedFile("cv.pdf", buffer.getvalue(), content_type="application/pdf"))
    assert len(leidas) == MAX_PAGINAS_CV


def test_un_pdf_corrupto_no_tumba_la_lectura():
    assert extraer_texto(SimpleUploadedFile("cv.pdf", b"%PDF-1.7 basura", content_type="application/pdf")) == ""


def test_un_error_de_programacion_no_se_oculta():
    with mock.patch("cuentas.cv.lector.PdfReader", side_effect=TypeError("bug")):
        with pytest.raises(TypeError):
            extraer_texto(pdf_cv())


# --- regresiones de la revisión final ------------------------------------------------------------

def test_cv_con_primera_linea_larga_no_falla(usuario):
    encabezado = "Laura Gómez | Analista | laura@x.co | 300 123 4567 | Medellín | linkedin.com/in/laura " * 3
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv(nombre=encabezado[:180]))
    assert perfil.nombre is None and "nombre" in perfil.campos_pendientes


@pytest.mark.parametrize("texto,dato", [("Calle 10 Sur # 43-12 apto 301", "43-12"), ("Cel: 300.123.4567", "4567"),
                                        ("Edad: 25 años", "25"), ("Estado civil: soltera", "soltera"),
                                        ("Género: femenino", "femenino")])
def test_minimizar_cubre_mas_formatos(texto, dato):
    assert dato not in minimizar(texto)


@pytest.mark.parametrize("texto", ["Soporte TI 2018 - 2020", "Analista del documento 2020-2021"])
def test_minimizar_no_borra_fechas_de_experiencia(texto):
    assert minimizar(texto) == texto


def test_la_evidencia_no_lleva_el_nombre_de_la_persona(usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv(nombre="Laura Gómez Ríos",
                                                     experiencia=["Laura Gómez lideró el equipo de soporte."]))
    assert "Laura" not in " ".join(perfil.evidencias.values_list("texto", flat=True))


def test_un_pdf_que_rompe_el_parser_no_da_error_500():
    with mock.patch("cuentas.cv.lector.PdfReader", side_effect=ValueError("xref roto")):
        assert extraer_texto(pdf_cv()) == ""


# --- auditoría: CVs con mayúsculas y cargo junto al nombre -----------------------------------------

def test_un_cargo_en_mayusculas_no_cierra_la_experiencia():
    cv = analizar_cv("Pedro Ruiz\nEXPERIENCIA\nANALISTA DE DATOS - BANCOLOMBIA\n- Construí tableros en Power BI.\n"
                     "REFERENCIAS\n- Ana, jefe directa.\nHABILIDADES\nSQL, PYTHON")
    experiencia = [u.texto for u in cv.unidades if u.seccion == "experiencia"]
    assert "Construí tableros en Power BI." in experiencia and not any("jefe" in t for t in experiencia)
    assert cv.habilidades == ["SQL", "PYTHON"]


def test_un_nombre_en_mayusculas_se_detecta():
    assert analizar_cv("LAURA GÓMEZ RÍOS\nEXPERIENCIA\n- Vendí seguros.").nombre == "LAURA GÓMEZ RÍOS"


def test_el_cargo_junto_al_nombre_no_se_tacha_de_la_evidencia(usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv(nombre="Laura Gómez Analista de Datos",
                                                     experiencia=["Analista de datos en Comercial Andina."]))
    assert perfil.nombre is None
    assert "Analista de datos en Comercial Andina." in perfil.evidencias.values_list("texto", flat=True)


def test_minimizar_no_tacha_una_palabra_suelta_del_nombre():
    assert minimizar("Trabajé en Cruz Verde con Ana Cruz", "Ana Cruz") == "Trabajé en Cruz Verde con [dato personal]"
