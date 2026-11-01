"""Taller de CV en versión texto (spec §13.3, propuesta C). Cada sugerencia reformula una evidencia que el CV YA tiene
para nombrar un requisito que quedó parcial: nunca inventa experiencia, y sin evidencia no hay sugerencia (eso va al
plan de aprendizaje). El candidato acepta o rechaza cada una; las aceptadas forman un texto para copiar."""

from cuentas.models import Perfil
from vacantes.models import Vacante

from .models import Decision, SugerenciaCV

MAX_EN_RESUMEN = 3


def _enumerar(textos: list[str]) -> str:
    return textos[0] if len(textos) == 1 else f"{', '.join(textos[:-1])} y {textos[-1]}"


def generar_sugerencias(decision: Decision, evidencias_actuales: list[str]) -> list[SugerenciaCV]:
    """Las sugerencias que corresponden hoy (sin guardar). Solo usa evidencias que el CV actual todavía tiene."""
    actuales = set(evidencias_actuales)
    sugerencias = []
    for r in decision.cobertura:
        if r["estado"] == "parcial" and r["tipo"] == "obligatorio" and r["evidencia"] in actuales:
            sugerencias.append(SugerenciaCV(
                perfil=decision.perfil, vacante=decision.vacante, tipo=SugerenciaCV.Tipo.REQUISITO,
                requisito=r["texto"], evidencia=r["evidencia"],
                propuesta=f"{r['evidencia'].rstrip('. ')} ({r['texto']})."))
    cubiertos = [r["texto"] for r in decision.cobertura if r["estado"] == "cubierto" and r["tipo"] == "obligatorio"]
    if len(cubiertos) >= 2:
        sugerencias.append(SugerenciaCV(
            perfil=decision.perfil, vacante=decision.vacante, tipo=SugerenciaCV.Tipo.RESUMEN, requisito="",
            propuesta=f"Resumen sugerido: experiencia en {_enumerar(cubiertos[:MAX_EN_RESUMEN])}."))
    return sugerencias


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
    return list(SugerenciaCV.objects.filter(perfil=perfil, vacante=vacante))


def responder(sugerencia: SugerenciaCV, acepta: bool) -> None:
    sugerencia.estado = SugerenciaCV.Estado.ACEPTADA if acepta else SugerenciaCV.Estado.RECHAZADA
    sugerencia.save(update_fields=["estado"])


def texto_adaptado(perfil: Perfil, vacante: Vacante) -> str:
    aceptadas = SugerenciaCV.objects.filter(perfil=perfil, vacante=vacante, estado=SugerenciaCV.Estado.ACEPTADA)
    return "\n".join(s.propuesta for s in aceptadas)
