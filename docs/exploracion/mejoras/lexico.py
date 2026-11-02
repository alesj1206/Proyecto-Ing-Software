"""Compuerta léxica: un requisito que nombra herramientas concretas solo puede quedar cubierto si el CV nombra alguna."""
import re, unicodedata

def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^\w+#/.]", " ", t).split())

COMUNES = {"experiencia", "conocimiento", "manejo", "dominio", "profesional", "tecnico", "tecnologo", "minimo", "minima",
           "nivel", "capacidad", "habilidad", "formacion", "requisitos", "deseable", "manejo", "excelente", "contar",
           "colombia", "bogota", "medellin", "cali", "lunes", "viernes", "empresa", "importante", "ser", "tener", "buen",
           "buena", "alta", "alto", "sector", "area", "areas", "titulo", "estudiante", "persona", "personas", "curso",
           "cursos", "certificado", "licencia", "ingles", "español", "la", "el", "los", "las", "de", "en", "y", "o"}
# Equivalencias de uso común en hojas de vida en español (no del set de evaluación en particular).
EQUIVALENTES = {"excel": ["hojas de calculo", "hoja de calculo"], "power bi": ["tableros", "dashboards"],
                "sql": ["consultas", "bases de datos"]}

def herramientas(texto):
    """Nombres propios o siglas dentro del requisito (no la primera palabra): SQL, Power BI, Siigo, RETHUS, AWS."""
    palabras = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ][\w+#/.-]*", texto)
    encontradas = []
    for i, p in enumerate(palabras):
        if i == 0 or _norm(p) in COMUNES or len(p) < 2:
            continue
        if p.isupper() or (p[0].isupper() and not p[1:].islower()) or (p[0].isupper() and i > 0):
            encontradas.append(_norm(p))
    return encontradas

def nombra_alguna(texto_req, texto_cv):
    cv = " " + _norm(texto_cv) + " "
    hs = herramientas(texto_req)
    if not hs:
        return None  # el requisito no nombra herramientas: la compuerta no aplica
    for h in hs:
        if f" {h} " in cv or any(f" {e} " in cv for e in EQUIVALENTES.get(h, [])):
            return True
    # "Power BI" en dos palabras
    req = _norm(texto_req)
    for compuesta, equiv in EQUIVALENTES.items():
        if compuesta in req and (f" {compuesta} " in cv or any(f" {e} " in cv for e in equiv)):
            return True
    return False
