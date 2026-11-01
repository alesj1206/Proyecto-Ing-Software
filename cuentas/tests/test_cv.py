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

def test_onboarding_carga_el_cv_y_va_al_perfil(client, usuario):
    client.force_login(usuario)
    r = client.post(reverse("onboarding"), {"cv": pdf_cv()})
    assert r.status_code == 302 and r.url == reverse("perfil")
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
