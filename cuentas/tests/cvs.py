"""CVs ficticios para los tests (ninguna persona real). Se generan con fpdf2."""

from django.core.files.uploadedfile import SimpleUploadedFile
from fpdf import FPDF

EXPERIENCIA_POR_DEFECTO = ["Analista de datos en Comercial Andina (2021-2024).", "Automaticé reportes en SQL."]


def texto_cv(nombre="Laura Gómez Ríos", contacto="laura.gomez@correo-ficticio.co",
             experiencia=None, educacion=("Ingeniería Industrial, Universidad EAFIT",),
             habilidades="SQL, Excel avanzado, Power BI"):
    lineas = [nombre]
    if contacto:
        lineas.append(contacto)
    lineas += ["", "EXPERIENCIA"] + [f"- {e}" for e in (experiencia or EXPERIENCIA_POR_DEFECTO)]
    if educacion:
        lineas += ["", "EDUCACIÓN"] + [f"- {e}" for e in educacion]
    if habilidades:
        lineas += ["", "HABILIDADES", habilidades]
    return "\n".join(lineas)


def _pdf(lineas, nombre_archivo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for linea in lineas:
        pdf.cell(0, 7, linea, new_x="LMARGIN", new_y="NEXT")
    return SimpleUploadedFile(nombre_archivo, bytes(pdf.output()), content_type="application/pdf")


def pdf_cv(nombre_archivo="cv.pdf", **kwargs):
    return _pdf(texto_cv(**kwargs).split("\n"), nombre_archivo)


def pdf_sin_texto(nombre_archivo="cv.pdf"):
    """Como un escaneo: páginas sin capa de texto."""
    return _pdf([], nombre_archivo)
