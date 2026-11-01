from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from pypdf import PdfWriter

from .cv_parser import MAX_PAGINAS_CV, extraer_datos_cv
from .forms import MAX_BYTES_CV, CVUploadForm


def pdf_en_blanco(paginas=1):
    escritor = PdfWriter()
    for _ in range(paginas):
        escritor.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


def subir(contenido, nombre="cv.pdf", tipo="application/pdf"):
    return CVUploadForm(files={"cv": SimpleUploadedFile(nombre, contenido, content_type=tipo)})


class SubidaCVTests(SimpleTestCase):
    def test_acepta_un_pdf_real(self):
        self.assertTrue(subir(pdf_en_blanco()).is_valid())

    def test_rechaza_un_archivo_que_no_es_pdf_aunque_se_llame_pdf(self):
        form = subir(b"MZ\x90\x00 esto es un ejecutable")
        self.assertFalse(form.is_valid())
        self.assertIn("cv", form.errors)

    def test_rechaza_archivos_de_mas_de_5_mb(self):
        self.assertEqual(MAX_BYTES_CV, 5 * 1024 * 1024)
        form = subir(b"%PDF-1.7\n" + b"0" * MAX_BYTES_CV)
        self.assertFalse(form.is_valid())
        self.assertIn("5 MB", form.errors["cv"][0])


class LecturaCVTests(SimpleTestCase):
    def test_solo_lee_las_primeras_paginas(self):
        self.assertEqual(MAX_PAGINAS_CV, 10)
        archivo = SimpleUploadedFile("cv.pdf", pdf_en_blanco(25), content_type="application/pdf")
        leidas = []
        original = __import__("pypdf").PageObject.extract_text

        def contar(pagina, *a, **k):
            leidas.append(pagina)
            return original(pagina, *a, **k)

        with mock.patch("pypdf.PageObject.extract_text", contar):
            extraer_datos_cv(archivo)
        self.assertEqual(len(leidas), MAX_PAGINAS_CV)

    def test_un_pdf_corrupto_no_tumba_la_lectura(self):
        archivo = SimpleUploadedFile("ana_python.pdf", b"%PDF-1.7 basura", content_type="application/pdf")
        datos = extraer_datos_cv(archivo)
        self.assertIsNotNone(datos)

    def test_un_error_de_programacion_no_se_oculta(self):
        archivo = SimpleUploadedFile("cv.pdf", pdf_en_blanco(), content_type="application/pdf")
        with mock.patch("vacantes.cv_parser.PdfReader", side_effect=TypeError("bug")):
            with self.assertRaises(TypeError):
                extraer_datos_cv(archivo)
