"""Solidez de una decisión (spec §5.4, §13.2): alta, media o baja, siempre con su motivo y sin números a la vista.
No es una probabilidad: resume margen, completitud de datos y calidad de la extracción, y es monótona en ellos."""

from .politica import Accion, ContextoDecision, Veredicto

PUNTOS_INICIALES = 3
MAX_PENALIZACION_DATOS = 2
MARGEN_UMBRAL = 0.03


def _penalizaciones(contexto: ContextoDecision) -> list[tuple[int, str]]:
    penalizaciones = []
    sin_datos = [r.motivo for r in contexto.restricciones if r.estado == "sin_datos"]
    if sin_datos:
        penalizaciones.append((min(len(sin_datos), MAX_PENALIZACION_DATOS), sin_datos[0]))
    de_texto = sum(r.origen == "texto" for r in contexto.requisitos)
    if de_texto <= 3:
        penalizaciones.append((2, "La vacante trae pocos requisitos legibles"))
    if not contexto.cobertura.obligatorios_total:
        penalizaciones.append((2, "La vacante no pide requisitos que podamos comparar con tu hoja de vida"))
    p = contexto.politica
    if any(min(abs(r.similitud - p.tau_alto), abs(r.similitud - p.tau_bajo)) < MARGEN_UMBRAL
           for r in contexto.cobertura.requisitos if r.cuenta):
        penalizaciones.append((1, "Algún requisito quedó justo en el límite"))
    return penalizaciones


def calcular_solidez(contexto: ContextoDecision, veredicto: Veredicto) -> tuple[str, str]:
    if veredicto.accion == Accion.SIN_DATOS:
        return "baja", "La vacante no trae requisitos legibles"
    penalizaciones = _penalizaciones(contexto)
    puntos = PUNTOS_INICIALES - sum(p for p, _ in penalizaciones)
    nivel = "alta" if puntos >= 3 else "media" if puntos == 2 else "baja"
    motivo = max(penalizaciones)[1] if penalizaciones else "Datos completos y requisitos claros"
    return nivel, motivo
