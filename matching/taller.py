"""Taller de CV como preguntas guiadas (exploración, docs/exploracion/2026-11-02-mejoras-decisor.md).

Por cada requisito obligatorio que el CV no dice con claridad (parcial con una evidencia parecida, o faltante), el
Taller PREGUNTA si la persona lo ha hecho y le pide contarlo con sus palabras; la evidencia, si la hay, es solo una
pista. Con mpnet y τ_alto = τ_bajo (política 2026-11-05.1) no hay parciales, así que pregunta por los faltantes: a veces
son cosas que la persona hizo y no escribió. No se propone texto: con MiniLM solo
4 de 29 reescrituras automáticas eran sensatas y ningún puntaje las separaba, y proponer texto es justo el riesgo de
inflar el CV que la spec prohíbe (§13.3). Lo que se copia es únicamente lo que el candidato escribió."""

from cuentas.models import Perfil
from vacantes.models import Vacante

from .models import Decision, SugerenciaCV

MAX_RESPUESTA = 500


def pregunta(requisito: str) -> str:
    return f"¿Has trabajado con «{requisito}»? Si es así, cuéntalo con tus palabras."


def se_pregunta(requisito: dict, evidencias_actuales: set[str]) -> bool:
    """Obligatorio y medido por similitud (no formación, años ni blandas): faltante, o parcial con una evidencia que el
    CV todavía tiene."""
    if requisito["tipo"] != "obligatorio":
        return False
    return requisito["estado"] == "faltante" or (requisito["estado"] == "parcial"
                                                 and requisito["evidencia"] in evidencias_actuales)


def generar_sugerencias(decision: Decision, evidencias_actuales: list[str]) -> list[SugerenciaCV]:
    """Las preguntas que corresponden hoy (sin guardar)."""
    actuales = set(evidencias_actuales)
    return [SugerenciaCV(perfil=decision.perfil, vacante=decision.vacante, tipo=SugerenciaCV.Tipo.REQUISITO,
                         requisito=r["texto"], evidencia=r["evidencia"] or "", propuesta=pregunta(r["texto"]))
            for r in decision.cobertura if se_pregunta(r, actuales)]


def taller(perfil: Perfil, vacante: Vacante) -> list[SugerenciaCV]:
    """Sincroniza las sugerencias con la decisión vigente: conserva las ya respondidas y quita las pendientes que dejaron
    de aplicar (por ejemplo, porque el CV cambió)."""
    decision = Decision.objects.filter(perfil=perfil, vacante=vacante).first()
    if decision is None:
        return []
    evidencias = list(perfil.evidencias.values_list("texto", flat=True))
    vigentes = generar_sugerencias(decision, evidencias)
    claves = set()
    for s in vigentes:
        claves.add((s.tipo, s.requisito))
        guardada, creada = SugerenciaCV.objects.get_or_create(
            perfil=perfil, vacante=vacante, tipo=s.tipo, requisito=s.requisito,
            defaults={"evidencia": s.evidencia, "propuesta": s.propuesta})
        if not creada and guardada.estado == SugerenciaCV.Estado.PENDIENTE and guardada.propuesta != s.propuesta:
            guardada.evidencia, guardada.propuesta = s.evidencia, s.propuesta
            guardada.save(update_fields=["evidencia", "propuesta"])
    for vieja in SugerenciaCV.objects.filter(perfil=perfil, vacante=vacante, estado=SugerenciaCV.Estado.PENDIENTE):
        if (vieja.tipo, vieja.requisito) not in claves:
            vieja.delete()
    propuestas_vigentes = {s.propuesta for s in vigentes}
    sugerencias = list(SugerenciaCV.objects.filter(perfil=perfil, vacante=vacante))
    for s in sugerencias:  # una respondida cuya evidencia ya no está en el CV se marca (se guarda como historial)
        s.vigente = s.propuesta in propuestas_vigentes
    return sugerencias


def responder(sugerencia: SugerenciaCV, acepta: bool, respuesta: str = "") -> None:
    """Aceptar exige que la persona escriba algo: lo que se copia sale de ella, nunca del sistema."""
    texto = " ".join(respuesta.split())[:MAX_RESPUESTA]
    if acepta and not texto:
        raise ValueError("Escribe con tus palabras qué hiciste, o marca que no lo has hecho.")
    sugerencia.estado = SugerenciaCV.Estado.ACEPTADA if acepta else SugerenciaCV.Estado.RECHAZADA
    sugerencia.respuesta = texto if acepta else ""
    sugerencia.save(update_fields=["estado", "respuesta"])


def texto_adaptado(perfil: Perfil, vacante: Vacante) -> str:
    """Las aceptadas que siguen respaldadas por el CV actual: nunca se copia algo cuya evidencia ya no está."""
    decision = Decision.objects.filter(perfil=perfil, vacante=vacante).first()
    if decision is None:
        return ""
    vigentes = {s.propuesta for s in generar_sugerencias(decision, list(perfil.evidencias.values_list("texto",
                                                                                                    flat=True)))}
    aceptadas = SugerenciaCV.objects.filter(perfil=perfil, vacante=vacante, estado=SugerenciaCV.Estado.ACEPTADA)
    return "\n".join(s.respuesta for s in aceptadas if s.propuesta in vigentes)
