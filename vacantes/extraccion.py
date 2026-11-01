"""Extracción de requisitos y restricciones del texto completo de una vacante, con vocabulario abierto.

Reglas, en orden:
1. El texto se parte en párrafos y líneas. Un encabezado es una línea corta que termina en ":" o que empieza
   con una palabra de encabezado conocida.
2. El resumen de Magneto ("Requisitos para aplicar a la vacante:" + años, nivel, salario y ciudad) no da
   requisitos: alimenta las restricciones.
3. Si hay secciones de requisitos, cada viñeta, línea u oración larga de ellas es una unidad. Si no las hay,
   se usan las oraciones de todo el texto que tengan palabras de requisito.
4. El filtro de ruido descarta salarios, beneficios y la presentación de la empresa.
5. Las palabras guía ("deseable", "plus", "valorable", ...) marcan `deseable`; también un encabezado que las
   tenga. Las etiquetas de Magneto se agregan como `deseable` (son señales, no obligatorios; spec §13.2).
"""

import re
import unicodedata
from dataclasses import dataclass

RESUMEN_MAGNETO = "requisitos para aplicar a la vacante"
MAX_LINEAS_RESUMEN = 4  # años y nivel, salario, ciudad (y a veces "Apto para personas con discapacidad")
PALABRAS_ENCABEZADO_REQUISITOS = (
    "requisito", "requerimiento", "perfil", "que buscamos", "lo que buscamos", "buscamos", "que busca",
    "lo que necesitas", "que necesitas", "necesitamos", "conocimiento", "formacion", "estudios", "experiencia",
    "competencia", "habilidades", "nivel de educacion", "debes contar", "indispensable", "deseable", "valoramos",
    "seria un plus",
)
PALABRAS_ENCABEZADO_OTRAS = (
    "funcion", "responsabilidad", "ofrecemos", "que ofrece", "beneficio", "condiciones", "horario", "salario",
    "actividades", "sobre nosotros", "quienes somos", "acerca de", "que haras", "tus retos", "tu reto", "proposito",
    "mision", "objetivo", "palabras clave", "lugar de trabajo", "tipo de contrato", "jornada", "aprenderas",
    "encontraras", "proceso de seleccion", "tu rol", "sectores laborales", "enamorara",
)
ENCABEZADOS_EXACTOS_OTROS = {"cargo"}
PALABRAS_DESEABLE = ("deseable", "plus", "valorable", "ideal", "preferible", "preferiblemente", "opcional",
                     "se valora", "valoramos", "no indispensable")
PALABRAS_INICIO_DESEABLE = 4  # "Deseable conocimiento…", "Experiencia deseable en…", "Valoramos: …"
PALABRAS_REQUISITO = ("experiencia", "conocimiento", "manejo", "titulo", "formacion", "dominio", "certificacion",
                      "certificado", "tecnico", "tecnologo", "profesional en", "bachiller", "estudiante",
                      "indispensable", "se requiere", "habilidad", "nivel de ingles",
                      "licencia de conduccion", "curso", "graduado", "valoramos", "deseable")
REQUISITO_EN_LINEA = re.compile(
    r"^(?:competencias|formacion(?: academica)?|experiencia|conocimientos?|requisitos?|estudios|idiomas?|"
    r"nivel de (?:educacion|ingles)|habilidades)\b[^:]{0,25}:\s*\S")
RUIDO = re.compile(
    r"\$\s?\d|salario|prestaciones|importante empresa|empresa (?:lider|líder)|te apasiona|unete|únete|ofrecemos|"
    r"beneficio|postulate|postúlate|postularte|aplica ya|tipo de contrato|contrato a término|^horarios?\b|"
    r"horario\s*:|jornada|somos una|nuestra empresa|te invitamos|te invita|auxilio de|bonificaci|lugar de trabajo|"
    r"modalidad\s*:|ubicaci[oó]n\s*:|^ciudad\s*:|cupos|fecha de publicaci|buen ambiente|crecimiento profesional|"
    r"palabras clave|pagos? quincenal|parte de (?:este|nuestro) equipo|listo para|contratación inmediata|"
    r"vinculaci[oó]n inmediata|remuneraci",
    re.IGNORECASE,
)
VINETA = re.compile(r"^\s*(?:[-*•▪●◦‣·–✓✔➢►o]\s+|\d+[.)]\s*|[-*•▪●◦‣·–✓✔➢►])\s*")
VINETA_EN_LINEA = re.compile(r"\s+[•▪●]\s+")
ENCABEZADO_AL_FINAL = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿][^.:]{2,40}:\s*$)")
# Un encabezado corto sin dos puntos solo puede tener estas palabras ("Perfil requerido", "Condiciones laborales").
VOCABULARIO_ENCABEZADO = set("""
requisitos requisito requerimientos perfil requerido buscamos busca compania necesitas necesitamos conocimientos
formacion academica estudios experiencia competencias habilidades deseadas deseables deseable tecnicas interpersonales
nivel educacion funciones principales especificas responsabilidades ofrecemos ofrece beneficios bienestar condiciones
laborales horario salario objetivo cargo proposito mision descripcion oferta palabras clave sobre nosotros tipo
contrato lugar trabajo jornada proceso seleccion aprenderas encontraras haras reto retos rol cuales seran sera tus tu
que lo del de la el y en para otras con contar debes
""".split())
MAX_PALABRAS_PREGUNTA = 8
MAX_LARGO_UNIDAD = 220
MAX_PALABRAS_ENCABEZADO = 5
MIN_REQUISITOS_LEGIBLES = 2


@dataclass(frozen=True)
class RequisitoExtraido:
    texto: str
    tipo: str  # "obligatorio" | "deseable"
    origen: str  # "texto" | "etiqueta"


@dataclass(frozen=True)
class Restricciones:
    anios_minimos: int | None = None
    salario_min: int | None = None
    salario_max: int | None = None
    modalidad: str | None = None
    ubicacion: str | None = None
    nivel_formacion: str | None = None


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos ni puntuación, con espacios simples."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^\w\s]", " ", sin_acentos.lower()).split())


def _lineas(texto: str) -> list[str]:
    """Líneas limpias; separa viñetas metidas en la misma línea y encabezados pegados al final de una oración."""
    lineas = []
    for cruda in texto.replace("\xa0", " ").split("\n"):
        for parte in VINETA_EN_LINEA.split(cruda):
            for trozo in ENCABEZADO_AL_FINAL.split(parte):
                trozo = re.sub(r"\s+", " ", trozo).strip()
                if trozo:
                    lineas.append(trozo)
    return lineas


def _minusculas(texto: str) -> str:
    """Minúsculas sin acentos, conservando la puntuación (para reglas que dependen de los dos puntos)."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn").strip()


def _tipo_encabezado(linea: str) -> str | None:
    """"requisitos", "deseables", "resumen", "etiquetas", "otra" o None si la línea es contenido."""
    limpio = VINETA.sub("", linea).strip()
    normal = normalizar(limpio)
    if not normal:
        return None
    if normal.startswith(RESUMEN_MAGNETO):
        return "resumen"
    if limpio == "Habilidades":  # bloque final de etiquetas de Magneto
        return "etiquetas"
    if normal in ENCABEZADOS_EXACTOS_OTROS and limpio.endswith(":"):
        return "otra"
    termina_en_dos_puntos = limpio.endswith(":") and len(limpio) <= 70
    palabras = normal.split()
    con_palabra_clave = any(p in normal for p in PALABRAS_ENCABEZADO_REQUISITOS + PALABRAS_ENCABEZADO_OTRAS)
    corto_sin_cierre = (len(palabras) <= MAX_PALABRAS_ENCABEZADO and not limpio.endswith((".", ","))
                        and con_palabra_clave and all(p in VOCABULARIO_ENCABEZADO for p in palabras))
    pregunta = (limpio.endswith("?") or "¿" in limpio[:3]) and len(palabras) <= MAX_PALABRAS_PREGUNTA \
        and con_palabra_clave
    if REQUISITO_EN_LINEA.match(_minusculas(limpio)):
        return None
    if not (termina_en_dos_puntos or corto_sin_cierre or pregunta):
        return None
    if any(p in normal for p in PALABRAS_ENCABEZADO_OTRAS):
        return "otra"
    if any(p in normal for p in PALABRAS_ENCABEZADO_REQUISITOS):
        return "deseables" if any(p in normal for p in PALABRAS_DESEABLE) else "requisitos"
    return "otra"


def _clasificar(texto: str) -> tuple[list[tuple[str | None, str]], list[str]]:
    """Cada línea de contenido con su sección (None si va antes de cualquier encabezado), y el resumen de Magneto."""
    lineas: list[tuple[str | None, str]] = []
    resumen: list[str] = []
    seccion: str | None = None
    restantes_resumen = 0
    for linea in _lineas(texto):
        if restantes_resumen:
            resumen.append(linea)
            restantes_resumen -= 1
            if re.match(r"^\$|^salario a convenir", linea, re.IGNORECASE):
                restantes_resumen = min(restantes_resumen, 1)  # después del salario solo queda la ciudad
            continue
        tipo = _tipo_encabezado(linea)
        if tipo == "resumen":
            restantes_resumen, seccion = MAX_LINEAS_RESUMEN, None
        elif tipo:
            seccion = tipo
        else:
            lineas.append((seccion, linea))
    return lineas, resumen


def _oraciones(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.;!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])", texto)
    return [p.strip() for p in partes if p.strip()]


def _unidades(linea: str) -> list[str]:
    texto = VINETA.sub("", linea).strip()
    if len(texto) <= MAX_LARGO_UNIDAD:
        return [texto]
    return _oraciones(texto)


def _es_ruido(texto: str) -> bool:
    return len(texto) < 3 or bool(RUIDO.search(texto))


def _tipo(texto: str, seccion: str | None) -> str:
    """Deseable si la sección lo es, si la palabra guía va al principio o si aparece sola entre paréntesis."""
    normal = normalizar(texto)
    inicio = " ".join(normal.split()[:PALABRAS_INICIO_DESEABLE])
    entre_parentesis = re.search(r"\((?:deseable|opcional|plus)\)", texto, re.IGNORECASE)
    if seccion == "deseables" or entre_parentesis or any(re.search(rf"\b{p}", inicio) for p in PALABRAS_DESEABLE):
        return "deseable"
    return "obligatorio"


def _candidatos(texto: str) -> list[tuple[str | None, str]]:
    lineas, _ = _clasificar(texto)
    en_secciones = [(s, u) for s, linea in lineas if s in ("requisitos", "deseables") for u in _unidades(linea)]
    sueltas = [(None, VINETA.sub("", linea).strip()) for s, linea in lineas
               if s is None and REQUISITO_EN_LINEA.match(_minusculas(VINETA.sub("", linea)))]
    if en_secciones:
        return sueltas + en_secciones
    # Sin sección de requisitos: oraciones con palabras de requisito, solo del texto que no está bajo un
    # encabezado de funciones, condiciones o similares.
    return sueltas + [(None, oracion) for s, linea in lineas if s is None
                      for oracion in _oraciones(VINETA.sub("", linea))
                      if any(p in normalizar(oracion) for p in PALABRAS_REQUISITO)]


def extraer_requisitos(texto: str, etiquetas: list[str]) -> list[RequisitoExtraido]:
    requisitos: list[RequisitoExtraido] = []
    vistos: set[str] = set()
    for seccion, unidad in _candidatos(texto):
        unidad = unidad.strip(" .;")
        clave = normalizar(unidad)
        if _es_ruido(unidad) or not clave or clave in vistos:
            continue
        vistos.add(clave)
        requisitos.append(RequisitoExtraido(unidad, _tipo(unidad, seccion), "texto"))

    texto_unidades = " ".join(vistos)
    for etiqueta in etiquetas:
        clave = normalizar(etiqueta)
        if clave and clave not in vistos and clave not in texto_unidades:
            vistos.add(clave)
            requisitos.append(RequisitoExtraido(etiqueta.strip(), "deseable", "etiqueta"))
    return requisitos


def requisitos_insuficientes(requisitos: list[RequisitoExtraido]) -> bool:
    """Menos de 2 requisitos legibles del texto: la base de SIN_DATOS en la Fase 2."""
    return sum(r.origen == "texto" for r in requisitos) < MIN_REQUISITOS_LEGIBLES


# --- restricciones ---------------------------------------------------------------------------------

_ANIOS = (
    re.compile(r"(\d+)\s*(?:[-–a]\s*\d+\s*)?años?\s+de\s+experiencia", re.IGNORECASE),
    re.compile(r"experiencia[^.\n\d]{0,30}?(?:m[ií]nim[ao]\s+)?(?:de\s+)?(\d+)\s*(?:[-–a]\s*\d+\s*)?años?", re.IGNORECASE),
    re.compile(r"m[ií]nimo\s+(\d+)\s*(?:[-–a]\s*\d+\s*)?años?", re.IGNORECASE),
)
_MESES = re.compile(r"\d+\s+meses\s+de\s+experiencia", re.IGNORECASE)  # menos de un año cuenta como 0
_SIN_EXPERIENCIA = re.compile(r"\bsin experiencia\b", re.IGNORECASE)
_RANGO_SALARIO = re.compile(r"\$\s*([\d.]{5,})\s*a\s*\$\s*([\d.]{5,})")
_SALARIO = re.compile(r"\$\s*([\d.]{5,})")
_A_CONVENIR = re.compile(r"^salario a convenir", re.IGNORECASE)
_INCLUSION = re.compile(r"^apto para personas", re.IGNORECASE)


def _entero(cifra: str) -> int:
    return int(cifra.replace(".", ""))


def _anios(texto: str) -> int | None:
    if _SIN_EXPERIENCIA.search(texto) or _MESES.search(texto):
        return 0
    for patron in _ANIOS:
        if m := patron.search(texto):
            return int(m.group(1))
    return None


def _salario(texto: str) -> tuple[int | None, int | None]:
    """El primer monto de una línea que no hable de auxilios ni bonificaciones."""
    for linea in texto.split("\n"):
        if re.search(r"auxilio|bonificaci|comisi", linea, re.IGNORECASE):
            continue
        if m := _RANGO_SALARIO.search(linea):
            return _entero(m.group(1)), _entero(m.group(2))
        if m := _SALARIO.search(linea):
            return _entero(m.group(1)), _entero(m.group(1))
    return None, None


_FRASES_MODALIDAD = (  # solo frases sobre la forma de trabajo: "nube híbrida" no es una modalidad
    (re.compile(r"modalidad (?:de trabajo )?(presencial|remot[oa]|hibrid[oa])"), None),
    (re.compile(r"(?:esquema|trabajo|modelo) hibrido|hibrido \d|\d+ dias? (?:en casa|remoto)"), "Híbrido"),
    (re.compile(r"100 remoto|trabajo remoto|teletrabajo|trabajo en casa|home office|trabajo desde casa"), "Remoto"),
    (re.compile(r"100 presencial|trabajo presencial"), "Presencial"),
)


def _modalidad(texto: str) -> str | None:
    normal = normalizar(texto)
    for patron, modalidad in _FRASES_MODALIDAD:
        if m := patron.search(normal):
            return modalidad or {"p": "Presencial", "r": "Remoto", "h": "Híbrido"}[m.group(1)[0]]
    return None


@dataclass
class _Resumen:
    """El bloque fijo de Magneto: [inclusión], años y nivel (o solo nivel), salario y ciudad."""

    experiencia: str | None = None
    nivel: str | None = None
    salario: str | None = None
    ubicacion: str | None = None

    @classmethod
    def leer(cls, lineas: list[str]) -> "_Resumen":
        resumen = cls()
        for linea in lineas:
            if _INCLUSION.match(linea):
                continue
            if resumen.salario is None and (linea.startswith("$") or _A_CONVENIR.match(linea)):
                resumen.salario = linea
            elif resumen.salario is not None:
                resumen.ubicacion = resumen.ubicacion or linea
            elif "experiencia" in linea.lower():
                resumen.experiencia = linea
                resumen.nivel = linea.split(",", 1)[1].strip() if "," in linea else None
            else:
                resumen.nivel = linea
        return resumen


def extraer_restricciones(texto: str) -> Restricciones:
    """Con el resumen de Magneto, años, salario, nivel y ciudad salen solo de él; sin resumen, del texto."""
    _, lineas_resumen = _clasificar(texto)
    if lineas_resumen:
        resumen = _Resumen.leer(lineas_resumen)
        salario_min, salario_max = _salario(resumen.salario or "")
        anios = _anios(resumen.experiencia) if resumen.experiencia else None
        nivel, ubicacion = resumen.nivel or None, resumen.ubicacion
    else:  # sin resumen: los años salen de los requisitos, no de "somos una empresa con 20 años de experiencia"
        salario_min, salario_max = _salario(texto)
        requisitos = "\n".join(u for _, u in _candidatos(texto))
        anios, nivel, ubicacion = _anios(requisitos), None, None
    return Restricciones(anios_minimos=anios, salario_min=salario_min, salario_max=salario_max,
                         modalidad=_modalidad(texto), ubicacion=ubicacion, nivel_formacion=nivel)
