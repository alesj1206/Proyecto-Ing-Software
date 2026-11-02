"""Notificaciones de vacantes nuevas para postular (spec §5.7).

Una decisión se notifica si hoy es POSTULAR, antes no lo era (o recién es relevante: `accion_anterior`) y no se ha
notificado desde su último cambio (`cambio_en`), dentro de una ventana de 36 h. No depende de que n8n llame en el
momento justo: lo que el batch decida después de una corrida se notifica en la siguiente (revisión final, Fase 3).
La campana muestra todas; el correo va a la cuenta (verificada) según la preferencia y con un máximo por día, y los
correos que fallan se reintentan."""

import logging
import smtplib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection
from django.db.models import Exists, OuterRef
from django.utils import timezone

from cuentas.models import Perfil
from matching.models import Decision
from matching.politica import Accion

from .models import Notificacion

VENTANA = timedelta(hours=36)  # un día más margen: cubre lo que el batch decidió después de la corrida anterior
MAX_ASUNTO = 150
log = logging.getLogger(__name__)


@dataclass
class ResumenNotificaciones:
    creadas: int = 0
    correos: int = 0


def _limpio(texto: str) -> str:
    """Una sola línea: un título scrapeado con saltos de línea no puede romper (ni inyectar) encabezados."""
    return " ".join(texto.split())[:MAX_ASUNTO]


def enviar_correo(perfil: Perfil, asunto: str, cuerpo: str) -> bool:
    """Al correo de la cuenta (verificado o dado por la red social), nunca al que aparece en el CV."""
    try:
        return send_mail(_limpio(asunto), cuerpo, settings.DEFAULT_FROM_EMAIL, [perfil.usuario.email]) > 0
    except (smtplib.SMTPException, OSError, ValueError):  # ValueError: encabezado inválido; se reintenta luego
        log.exception("No se pudo enviar el correo al perfil %s", perfil.pk)
        return False


def _por_notificar(ahora):
    ya_notificada = Notificacion.objects.filter(perfil=OuterRef("perfil"), vacante=OuterRef("vacante"),
                                                creada_en__gte=OuterRef("cambio_en"))
    return (Decision.objects.filter(accion=Accion.POSTULAR, cambio_en__gte=ahora - VENTANA)
            .exclude(accion_anterior=Accion.POSTULAR).exclude(Exists(ya_notificada))
            .select_related("vacante", "perfil__usuario"))


def _crear(decision: Decision, hoy: date) -> bool:
    v = decision.vacante
    _, creada = Notificacion.objects.update_or_create(
        perfil=decision.perfil, vacante=v, fecha=hoy,
        defaults={"score_pct": decision.cobertura_pct, "enviada": False, "leida": False,
                  "mensaje": _limpio(f"Nueva vacante para postular: {v.titulo} en {v.empresa}")})
    return creada


def _enviar_pendientes(perfil: Perfil, hoy: date, ahora) -> int:
    """Envía según la preferencia; devuelve cuántos correos salieron. El máximo individual es por día."""
    if perfil.notif_modo == Perfil.ModoNotificacion.DESACTIVADO:
        return 0
    pendientes = list(Notificacion.objects.filter(perfil=perfil, enviada=False, creada_en__gte=ahora - VENTANA)
                      .order_by("creada_en"))
    if not pendientes:
        return 0
    enviados_hoy = Notificacion.objects.filter(perfil=perfil, enviada=True, fecha=hoy)
    if perfil.notif_modo == Perfil.ModoNotificacion.INDIVIDUAL:
        restantes = max(perfil.notif_max - enviados_hoy.count(), 0)
        enviadas = [n for n in pendientes[:restantes] if enviar_correo(perfil, n.mensaje, n.mensaje)]
        correos = len(enviadas)
    else:  # resumen: un solo correo al día
        if enviados_hoy.exists():
            return 0
        cuerpo = "Tienes vacantes nuevas para postular en Scoutly:\n\n" + "\n".join(f"- {n.mensaje}" for n in pendientes)
        enviadas = pendientes if enviar_correo(perfil, f"{len(pendientes)} vacantes nuevas para postular", cuerpo) else []
        correos = 1 if enviadas else 0
    Notificacion.objects.filter(id__in=[n.id for n in enviadas]).update(enviada=True, fecha=hoy)
    return correos


CANDADO_NOTIFICACIONES = 731_002  # candado de aviso de Postgres


def generar_notificaciones(hoy: date | None = None) -> ResumenNotificaciones:
    """De a un proceso a la vez (los `decidir --escuchar` en paralelo y la API de n8n): dos corridas simultáneas verían
    las mismas pendientes y enviarían el mismo correo dos veces. La segunda espera y luego no encuentra nada nuevo."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [CANDADO_NOTIFICACIONES])
        try:
            return _generar(hoy)
        finally:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [CANDADO_NOTIFICACIONES])


def _generar(hoy: date | None) -> ResumenNotificaciones:
    ahora, hoy = timezone.now(), hoy or timezone.localdate()
    resumen = ResumenNotificaciones()
    perfiles = {}
    for decision in _por_notificar(ahora):
        resumen.creadas += _crear(decision, hoy)
        perfiles[decision.perfil_id] = decision.perfil
    for perfil in Perfil.objects.filter(notificaciones__enviada=False,
                                        notificaciones__creada_en__gte=ahora - VENTANA).distinct():
        perfiles[perfil.pk] = perfil
    for perfil in perfiles.values():
        resumen.correos += _enviar_pendientes(perfil, hoy, ahora)
    return resumen


def bandeja(perfil: Perfil | None) -> list[Notificacion]:
    """Las notificaciones del candidato; abrir la bandeja marca como leídas las que no lo estaban."""
    if perfil is None:
        return []
    notificaciones = list(Notificacion.objects.filter(perfil=perfil).select_related("vacante"))
    sin_leer = [n.id for n in notificaciones if not n.leida]
    if sin_leer:
        Notificacion.objects.filter(id__in=sin_leer).update(leida=True)
    return notificaciones
