"""Notificaciones de vacantes nuevas para postular (spec §5.7). Una vacante es "nueva" si hoy es POSTULAR y antes no lo
era o no estaba entre las relevantes (`accion_anterior`), y cambió hoy (`cambio_en`). La campana muestra todas; el
correo respeta la preferencia del candidato. Volver a correr el mismo día no duplica nada."""

import logging
import smtplib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from cuentas.models import Perfil
from matching.models import Decision
from matching.politica import Accion

from .models import Notificacion

log = logging.getLogger(__name__)


@dataclass
class ResumenNotificaciones:
    creadas: int = 0
    correos: int = 0


def enviar_correo(perfil: Perfil, asunto: str, cuerpo: str) -> bool:
    if not perfil.puede_notificar():
        return False
    try:
        return send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [perfil.contacto]) > 0
    except (smtplib.SMTPException, OSError):  # un SMTP caído no debe tumbar la generación; queda en el log
        log.exception("No se pudo enviar el correo al perfil %s", perfil.pk)
        return False


def _nuevas_de_hoy(hoy: date):
    return (Decision.objects.filter(accion=Accion.POSTULAR, cambio_en__date=hoy)
            .exclude(accion_anterior=Accion.POSTULAR).select_related("vacante", "perfil"))


def _crear(perfil: Perfil, decision: Decision, hoy: date) -> Notificacion | None:
    """La notificación de hoy para esa vacante, o None si ya existía (idempotente)."""
    v = decision.vacante
    notificacion, creada = Notificacion.objects.get_or_create(
        perfil=perfil, vacante=v, fecha=hoy,
        defaults={"score_pct": decision.cobertura_pct,
                  "mensaje": f"Nueva vacante para postular: {v.titulo} en {v.empresa}"})
    return notificacion if creada else None


def _correos(perfil: Perfil, nuevas: list[Notificacion]) -> list[Notificacion]:
    """Envía según la preferencia y devuelve las notificaciones que salieron por correo."""
    if perfil.notif_modo == Perfil.ModoNotificacion.DESACTIVADO or not nuevas:
        return []
    if perfil.notif_modo == Perfil.ModoNotificacion.INDIVIDUAL:
        enviadas = [n for n in nuevas[: perfil.notif_max] if enviar_correo(perfil, n.mensaje, n.mensaje)]
        return enviadas
    cuerpo = "Hoy tienes vacantes nuevas para postular en Scoutly:\n\n" + "\n".join(f"- {n.mensaje}" for n in nuevas)
    return nuevas if enviar_correo(perfil, f"{len(nuevas)} vacantes nuevas para postular", cuerpo) else []


def generar_notificaciones(hoy: date | None = None) -> ResumenNotificaciones:
    hoy = hoy or timezone.localdate()
    resumen = ResumenNotificaciones()
    por_perfil = defaultdict(list)
    for decision in _nuevas_de_hoy(hoy):
        if notificacion := _crear(decision.perfil, decision, hoy):
            por_perfil[decision.perfil].append(notificacion)
    for perfil, nuevas in por_perfil.items():
        resumen.creadas += len(nuevas)
        enviadas = _correos(perfil, nuevas)
        if enviadas:
            Notificacion.objects.filter(id__in=[n.id for n in enviadas]).update(enviada=True)
            resumen.correos += 1 if perfil.notif_modo == Perfil.ModoNotificacion.RESUMEN else len(enviadas)
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
