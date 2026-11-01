"""Ingesta incremental: solo se reescriben las vacantes nuevas o cuyo contenido cambió (hash)."""

import hashlib
import logging
from dataclasses import dataclass

from django.db import transaction

from .extraccion import extraer_requisitos, extraer_restricciones, requisitos_insuficientes
from .fuentes import FuenteVacantes, VacanteCruda
from .models import Requisito, Vacante

log = logging.getLogger(__name__)
MODALIDAD_POR_DEFECTO = Vacante.Modalidad.PRESENCIAL  # como en v2, si ni la fuente ni el texto la dicen


@dataclass
class ResumenIngesta:
    creadas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    insuficientes: int = 0
    errores: int = 0

    def __str__(self) -> str:
        return (f"creadas: {self.creadas}, actualizadas: {self.actualizadas}, sin cambios: {self.sin_cambios}, "
                f"insuficientes: {self.insuficientes}, errores: {self.errores}")


def hash_contenido(cruda: VacanteCruda) -> str:
    """Todo lo que se guarda: una vacante republicada (fecha nueva) o marcada urgente también se actualiza."""
    contenido = "\n".join(str(v) for v in (
        cruda.titulo, cruda.empresa, cruda.ubicacion, cruda.modalidad, cruda.texto_completo, "|".join(cruda.etiquetas),
        cruda.url, cruda.fecha_publicacion, cruda.salario_min, cruda.salario_max, cruda.urgente))
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


@transaction.atomic
def _guardar(cruda: VacanteCruda, fuente: str, firma: str) -> bool:
    """Guarda la vacante y reemplaza sus requisitos en una sola transacción. Devuelve si son insuficientes."""
    restricciones = extraer_restricciones(cruda.texto_completo)
    requisitos = extraer_requisitos(cruda.texto_completo, list(cruda.etiquetas))
    salario_min = cruda.salario_min if cruda.salario_min is not None else restricciones.salario_min
    salario_max = cruda.salario_max if cruda.salario_max is not None else restricciones.salario_max
    vacante, _ = Vacante.objects.update_or_create(
        id=cruda.id,
        defaults={
            "titulo": cruda.titulo,
            "empresa": cruda.empresa,
            "ubicacion": cruda.ubicacion or restricciones.ubicacion or "Colombia",
            "modalidad": cruda.modalidad or restricciones.modalidad or MODALIDAD_POR_DEFECTO,
            "salario_min": salario_min,
            "salario_max": salario_max,
            "salario_moneda": "COP" if salario_min is not None else None,
            "salario_periodo": Vacante.Periodo.MENSUAL if salario_min is not None else None,
            "descripcion": cruda.texto_completo,
            "fecha_publicacion": cruda.fecha_publicacion,
            "experiencia_minima": restricciones.anios_minimos,
            "nivel_formacion": restricciones.nivel_formacion or "",
            "urgente": cruda.urgente,
            "texto_completo": cruda.texto_completo,
            "url": cruda.url,
            "fuente": fuente,
            "hash_contenido": firma,
            "activa": True,
            "etiquetas": list(cruda.etiquetas),
        },
    )
    vacante.requisito_set.all().delete()
    Requisito.objects.bulk_create(
        Requisito(vacante=vacante, texto=r.texto, tipo=r.tipo, origen=r.origen, posicion=i)
        for i, r in enumerate(requisitos)
    )
    return requisitos_insuficientes(requisitos)


def ingerir(fuente: FuenteVacantes) -> ResumenIngesta:
    resumen = ResumenIngesta()
    hashes = dict(Vacante.objects.values_list("id", "hash_contenido"))
    for cruda in fuente.obtener():
        firma = hash_contenido(cruda)
        if hashes.get(cruda.id) == firma:
            resumen.sin_cambios += 1
            continue
        try:
            insuficiente = _guardar(cruda, fuente.nombre, firma)
        except Exception:  # una vacante rota no debe tumbar la ingesta de las demás (se registra)
            log.exception("No se pudo ingerir la vacante %s", cruda.id)
            resumen.errores += 1
            continue
        if cruda.id in hashes:
            resumen.actualizadas += 1
        else:
            resumen.creadas += 1
        hashes[cruda.id] = firma
        resumen.insuficientes += insuficiente
    return resumen
