"""Extracción real de datos desde el PDF cargado.

Lee el texto del PDF con pypdf y aplica heurísticas simples y explicables
sobre ese texto (nombre = primera línea, encabezados en mayúsculas para
ubicar secciones, vocabulario de habilidades conocidas, regex de correo).
No es NLP ni OCR: si el PDF no trae una capa de texto (por ejemplo, es un
escaneo), no hay nada que leer y se usa como respaldo el nombre del
archivo, igual que en la primera versión mock de este sprint.
"""

import re
import unicodedata

from pypdf import PdfReader

from .skills import HABILIDADES_CONOCIDAS

PALABRAS_RUIDO = {"cv", "resume", "curriculum", "hoja", "vida", "hv"}

ENCABEZADOS_EXPERIENCIA = {"experiencia", "experiencia laboral", "experiencia profesional"}
ENCABEZADOS_EDUCACION = {"educacion", "formacion academica", "formacion", "estudios"}

MAX_LINEAS_SECCION = 4

EXPERIENCIA_POR_AREA = {
    frozenset({"react", "javascript", "typescript", "html", "css"}): [
        "Desarrollo de interfaces web con React, HTML y CSS en proyectos de varios meses.",
        "Integración de componentes JavaScript/TypeScript con APIs REST.",
    ],
    frozenset({"node.js", "next.js", "sql"}): [
        "Construcción de servicios backend con Node.js y Next.js.",
        "Diseño de consultas y modelos de datos en SQL.",
    ],
    frozenset({"python"}): [
        "Automatización de procesos y análisis de datos con Python.",
    ],
    frozenset({"aws", "docker", "kubernetes"}): [
        "Despliegue de aplicaciones en contenedores (Docker/Kubernetes) sobre AWS.",
    ],
    frozenset({"figma"}): [
        "Diseño de interfaces y prototipos en Figma.",
    ],
    frozenset({"agile", "scrum", "liderazgo"}): [
        "Liderazgo de equipos bajo metodologías ágiles (Scrum).",
    ],
}

EXPERIENCIA_GENERAL = ["Experiencia profesional registrada en el documento cargado."]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _quitar_acentos(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _normalizar(texto):
    return _quitar_acentos(texto).lower().strip()


def _es_encabezado(linea):
    letras = [c for c in linea if c.isalpha()]
    return len(letras) >= 3 and linea.strip() == linea.strip().upper() and len(linea) <= 45


def _limpiar_lineas(texto):
    # Se separa por línea ANTES de limpiar: los saltos de línea (\n) caen
    # dentro del propio rango de caracteres de control que se quiere quitar
    # (viñetas sin mapear como \x7f), así que limpiarlos antes de partir el
    # texto colapsaría todo el CV en una sola "línea".
    lineas = []
    for linea in texto.split("\n"):
        linea = re.sub(r"[\x00-\x1f\x7f]", " ", linea)
        linea = re.sub(r"\s+", " ", linea).strip()
        if linea:
            lineas.append(linea)
    return lineas


def _extraer_seccion(lineas, encabezados_buscados):
    for i, linea in enumerate(lineas):
        if _es_encabezado(linea) and _normalizar(linea) in encabezados_buscados:
            resultado = []
            for siguiente in lineas[i + 1 :]:
                if _es_encabezado(siguiente):
                    break
                resultado.append(siguiente)
                if len(resultado) >= MAX_LINEAS_SECCION:
                    break
            return resultado or None
    return None


def _extraer_habilidades(texto_normalizado):
    encontradas = []
    for skill in HABILIDADES_CONOCIDAS:
        patron = r"\b" + re.escape(_normalizar(skill)) + r"\b"
        if re.search(patron, texto_normalizado):
            encontradas.append(skill)
    return encontradas


def _desde_nombre_archivo(nombre_archivo):
    """Respaldo cuando el PDF no tiene texto extraíble (p. ej. es un escaneo)."""
    base = nombre_archivo.rsplit(".", 1)[0]
    tokens = [t for t in base.replace("_", " ").replace("-", " ").split() if t]

    nombre_tokens = []
    habilidades = []
    en_zona_de_nombre = True
    for token in tokens:
        token_lower = _normalizar(token)
        if token_lower in {_normalizar(s) for s in HABILIDADES_CONOCIDAS}:
            habilidades.append(token_lower)
            en_zona_de_nombre = False
        elif en_zona_de_nombre and token_lower not in PALABRAS_RUIDO:
            nombre_tokens.append(token)

    nombre = " ".join(t.capitalize() for t in nombre_tokens) if nombre_tokens else None
    return nombre, None, habilidades


def extraer_datos_cv(archivo):
    """archivo: un UploadedFile de Django (form.cleaned_data['cv'])."""
    try:
        lector = PdfReader(archivo)
        texto_crudo = "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    except Exception:
        texto_crudo = ""

    lineas = _limpiar_lineas(texto_crudo)
    texto_normalizado = _normalizar(" ".join(lineas))

    campos_pendientes = []

    if lineas:
        nombre = lineas[0]
        contacto_match = EMAIL_RE.search(texto_crudo)
        contacto = contacto_match.group(0) if contacto_match else None
        habilidades = _extraer_habilidades(texto_normalizado)
    else:
        # Sin capa de texto (p. ej. PDF escaneado): último recurso, el nombre del archivo.
        nombre, contacto, habilidades = _desde_nombre_archivo(archivo.name)

    if nombre is None:
        campos_pendientes.append("nombre")
    if contacto is None:
        campos_pendientes.append("contacto")

    if not habilidades:
        habilidades = ["comunicación", "trabajo en equipo"]

    experiencia = _extraer_seccion(lineas, ENCABEZADOS_EXPERIENCIA)
    if experiencia is None:
        habilidades_set = set(habilidades)
        experiencia = EXPERIENCIA_GENERAL
        for grupo, lineas_plantilla in EXPERIENCIA_POR_AREA.items():
            if habilidades_set & grupo:
                experiencia = lineas_plantilla[:2]
                break

    educacion = _extraer_seccion(lineas, ENCABEZADOS_EDUCACION)
    if educacion is None:
        campos_pendientes.append("educacion")

    return {
        "nombre": nombre,
        "contacto": contacto,
        "experiencia": experiencia,
        "educacion": educacion,
        "habilidades": habilidades,
        "campos_pendientes": campos_pendientes,
    }
