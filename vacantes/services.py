"""Ingesta incremental: solo se reescriben las vacantes nuevas o cuyo contenido cambió (hash)."""

import hashlib
import logging
import threading
import uuid
from datetime import timedelta
from dataclasses import dataclass

from django.db import connection, models, transaction
from django.utils import timezone

from .extraccion import extraer_requisitos, extraer_restricciones, requisitos_insuficientes
from .fuentes import FuenteVacantes, VacanteCruda
from .models import EstadoIngesta, Requisito, Vacante

log = logging.getLogger(__name__)
# Va dentro del hash: al cambiar las reglas de extracción o lo que se embebe, la próxima ingesta reprocesa todo.
VERSION_EXTRACCION = "2026-11-04.3"
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
        VERSION_EXTRACCION, cruda.titulo, cruda.empresa, cruda.ubicacion, cruda.modalidad, cruda.texto_completo, "|".join(cruda.etiquetas),
        cruda.url, cruda.fecha_publicacion, cruda.salario_min, cruda.salario_max, cruda.urgente,
        "|".join(cruda.prefiltro)))
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
            "ubicacion": cruda.ubicacion or restricciones.ubicacion or "",  # vacío = la vacante no lo dice
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
            "modalidad_inferida": not (cruda.modalidad or restricciones.modalidad),
            "prefiltro": list(cruda.prefiltro),
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


INGESTA_COLGADA = timedelta(minutes=30)  # una ingesta que murió sin soltar el candado se puede retomar


def lanzar_hilo(funcion) -> None:
    def en_su_propia_conexion():
        try:
            funcion()
        finally:
            connection.close()  # el hilo abrió su propia conexión a la base

    threading.Thread(target=en_su_propia_conexion, daemon=True).start()


def _tomar_candado() -> str | None:
    """Atómico: solo una petición puede pasar de libre (o colgada) a en curso. Devuelve el id de la corrida."""
    EstadoIngesta.objects.get_or_create(id=1)
    corrida = uuid.uuid4().hex
    libre = EstadoIngesta.objects.filter(id=1).filter(
        models.Q(en_curso=False) | models.Q(iniciada_en__lt=timezone.now() - INGESTA_COLGADA))
    return corrida if libre.update(en_curso=True, iniciada_en=timezone.now(), corrida=corrida) == 1 else None


def _encolar_decisiones() -> None:
    from cuentas.models import Perfil
    from matching.services import solicitar_decision  # vacantes no depende de matching al importar

    for perfil in Perfil.objects.exclude(cv_nombre_archivo=""):
        solicitar_decision(perfil)


def ingerir_en_segundo_plano(fuente: FuenteVacantes) -> bool:
    """Lanza la ingesta en un hilo (la pide n8n). Devuelve False si ya había una en curso."""
    corrida = _tomar_candado()
    if corrida is None:
        return False

    def trabajar():
        resumen = ""
        try:
            resumen = str(ingerir(fuente))
            _encolar_decisiones()  # n8n no espera: el batch decide en cuanto termina la ingesta
        except Exception:  # se registra; el candado se suelta igual
            log.exception("La ingesta en segundo plano falló")
            resumen = "falló (ver el log)"
        finally:
            # Solo el dueño suelta el candado: un hilo viejo que termina tarde no libera el de otra corrida.
            EstadoIngesta.objects.filter(id=1, corrida=corrida).update(en_curso=False, ultimo_resumen=resumen[:255])

    lanzar_hilo(trabajar)
    return True
