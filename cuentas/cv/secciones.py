"""Secciones y unidades de evidencia de una hoja de vida, con vocabulario abierto: las habilidades
son lo que la persona escribió, no lo que coincide con una lista."""

import re
import unicodedata
from dataclasses import dataclass, field

ENCABEZADOS = {
    "experiencia": {"experiencia", "experiencia laboral", "experiencia profesional", "trayectoria",
                    "historial laboral"},
    "educacion": {"educacion", "formacion academica", "formacion", "estudios", "educacion y formacion"},
    "habilidades": {"habilidades", "habilidades tecnicas", "competencias", "conocimientos", "skills",
                    "herramientas", "aptitudes"},
}
MAX_LINEAS_VISIBLES = 4  # lo que muestra /perfil por sección, igual que en v2
PALABRAS_RUIDO_ARCHIVO = {"cv", "resume", "curriculum", "hoja", "de", "vida", "hv"}
VINETA = re.compile(r"^\s*(?:[-*•▪●◦‣·–]|\d+[.)])\s+")
SEPARADOR_HABILIDADES = re.compile(r"[,;•|·▪●\n]|\s-\s")
CORREO = re.compile(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)
FIN_DE_ORACION = (".", "!", "?", ";", ":")


@dataclass(frozen=True)
class UnidadEvidencia:
    texto: str
    seccion: str


@dataclass
class CVAnalizado:
    nombre: str | None
    contacto: str | None
    experiencia: list[str] = field(default_factory=list)
    educacion: list[str] = field(default_factory=list)
    habilidades: list[str] = field(default_factory=list)
    unidades: list[UnidadEvidencia] = field(default_factory=list)
    campos_pendientes: list[str] = field(default_factory=list)


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin_acentos.lower().strip().rstrip(":").strip()


def _lineas(texto: str) -> list[str]:
    limpias = (re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", linea)).strip() for linea in texto.split("\n"))
    return [linea for linea in limpias if linea]


def _seccion_de(linea: str) -> str | None:
    """El nombre de la sección si la línea es un encabezado conocido; "otra" si parece un encabezado
    desconocido (corto y en mayúsculas); None si es contenido."""
    normal = _normalizar(linea)
    for seccion, encabezados in ENCABEZADOS.items():
        if normal in encabezados:
            return seccion
    letras = [c for c in linea if c.isalpha()]
    if len(letras) >= 3 and linea == linea.upper() and len(linea) <= 45 and not VINETA.match(linea):
        return "otra"
    return None


def _agrupar(lineas: list[str]) -> dict[str, list[str]]:
    secciones: dict[str, list[str]] = {}
    actual = None
    for linea in lineas:
        seccion = _seccion_de(linea)
        if seccion:
            actual = seccion
            secciones.setdefault(actual, [])
        elif actual:
            secciones[actual].append(linea)
    return secciones


def _unidades(lineas: list[str]) -> list[str]:
    """Una unidad por viñeta u oración; una viñeta partida en varias líneas sigue siendo una."""
    unidades: list[str] = []
    for linea in lineas:
        es_vineta = bool(VINETA.match(linea))
        texto = VINETA.sub("", linea).strip()
        if unidades and not es_vineta and not unidades[-1].endswith(FIN_DE_ORACION):
            unidades[-1] = f"{unidades[-1]} {texto}"
        else:
            unidades.append(texto)
    return [u for u in unidades if u]


def _habilidades(lineas: list[str]) -> list[str]:
    vistas, resultado = set(), []
    texto = "\n".join(VINETA.sub("", linea) for linea in lineas)
    for parte in SEPARADOR_HABILIDADES.split(texto):
        habilidad = parte.strip(" .")
        if habilidad and _normalizar(habilidad) not in vistas:
            vistas.add(_normalizar(habilidad))
            resultado.append(habilidad)
    return resultado


def _nombre_desde_archivo(nombre_archivo: str) -> str | None:
    base = nombre_archivo.rsplit(".", 1)[0]
    tokens = [t for t in re.split(r"[_\-\s]+", base) if t and _normalizar(t) not in PALABRAS_RUIDO_ARCHIVO]
    return " ".join(t.capitalize() for t in tokens) or None


def analizar_cv(texto: str, nombre_archivo: str = "") -> CVAnalizado:
    lineas = _lineas(texto)
    if not lineas:  # sin capa de texto (p. ej. un escaneo): solo queda el nombre del archivo
        cv = CVAnalizado(nombre=_nombre_desde_archivo(nombre_archivo), contacto=None)
    else:
        secciones = _agrupar(lineas)
        experiencia = _unidades(secciones.get("experiencia", []))
        educacion = _unidades(secciones.get("educacion", []))
        habilidades = _habilidades(secciones.get("habilidades", []))
        correo = CORREO.search(texto)
        cv = CVAnalizado(
            nombre=lineas[0] if _seccion_de(lineas[0]) is None else None,
            contacto=correo.group(0) if correo else None,
            experiencia=experiencia[:MAX_LINEAS_VISIBLES],
            educacion=educacion[:MAX_LINEAS_VISIBLES],
            habilidades=habilidades,
            unidades=[UnidadEvidencia(t, "experiencia") for t in experiencia]
            + [UnidadEvidencia(t, "educacion") for t in educacion]
            + [UnidadEvidencia(t, "habilidades") for t in habilidades],
        )
    pendientes = (("nombre", cv.nombre), ("contacto", cv.contacto), ("educacion", cv.educacion))
    cv.campos_pendientes = [campo for campo, valor in pendientes if not valor]
    return cv
