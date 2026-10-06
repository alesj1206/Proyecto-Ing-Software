"""HU-11 — paso "notificación" del workflow de n8n (ingesta → normalización
→ scoring → notificación, "Idea 4" del documento del reto). Vive separado
de scoring.py a propósito: lo llama un segundo nodo HTTP Request en n8n,
después del de scoring, para que el workflow tenga los dos pasos como
nodos distintos y auditables por separado — no un solo paso que hace todo
por dentro sin que se note desde n8n.

Detecta "nuevo" comparando el top-3 de hoy contra el top-3 de ayer por
candidato: una vacante que ya estaba en tu top de ayer no te vuelve a
notificar solo porque el batch corrió otra vez.

Único canal: correo (al que trae el CV). Se evaluó WhatsApp vía Twilio y
se descartó a propósito — exige que cada candidato haga un opt-in manual
("join <código>" por WhatsApp, restricción de Meta para cuentas de prueba
de Twilio) para que algo le llegue, mientras que un correo con SMTP real
configurado (ver settings.py) llega sin ningún paso extra de su lado.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils import timezone

from .models import MatchDiario, Notificacion, Perfil

logger = logging.getLogger(__name__)

TOP_N = 3  # mismo top que el dashboard muestra como "Matches de hoy"


def _top_vacante_ids(perfil, fecha):
    return set(
        MatchDiario.objects.filter(perfil=perfil, fecha=fecha)
        .order_by("-score")[:TOP_N]
        .values_list("vacante_id", flat=True)
    )


def enviar_email(perfil, asunto, cuerpo):
    if not perfil.contacto:
        return False
    try:
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [perfil.contacto], fail_silently=False)
        return True
    except Exception as exc:
        logger.warning("No se pudo enviar email a %s: %s", perfil.contacto, exc)
        return False


def _enviar_notificacion(perfil, vacante, mensaje):
    asunto = f"Scoutly: nuevo match con {vacante.empresa}"
    cuerpo = f"{mensaje}\n\nVelo en Scoutly: /vacantes/{vacante.id}"
    return enviar_email(perfil, asunto, cuerpo)


def generar_notificaciones_nuevos_matches(fecha=None):
    """Para cada perfil con CV: compara su top-3 de hoy contra el de ayer,
    y por cada vacante que entró de nueva crea (y trata de enviar) una
    Notificacion. Idempotente por día — correrlo dos veces el mismo día no
    duplica notificaciones (UniqueConstraint perfil+vacante+fecha)."""
    fecha = fecha or timezone.localdate()
    ayer = fecha - timedelta(days=1)

    creadas = 0
    enviadas = 0
    for perfil in Perfil.objects.all():
        if not perfil.tiene_cv():
            continue

        # Si el batch de ayer no corrió (n8n caído, o el candidato es
        # nuevo desde hoy mismo), MatchDiario no tiene NINGUNA fila para
        # ayer — eso no es "0 matches ayer", es "no sabemos qué había
        # ayer". Tratarlo como "0" notificaría de golpe los 3 del top de
        # hoy como si fueran nuevos, aunque el candidato ya los hubiera
        # visto días atrás. Mejor no notificar nada ese día que mentir.
        if not MatchDiario.objects.filter(perfil=perfil, fecha=ayer).exists():
            continue

        nuevas_ids = _top_vacante_ids(perfil, fecha) - _top_vacante_ids(perfil, ayer)
        if not nuevas_ids:
            continue

        matches_hoy = MatchDiario.objects.filter(
            perfil=perfil, fecha=fecha, vacante_id__in=nuevas_ids
        ).select_related("vacante")

        for match in matches_hoy:
            score_pct = round(match.score * 100)
            mensaje = f'Nuevo match: "{match.vacante.titulo}" en {match.vacante.empresa} — {score_pct}% de compatibilidad.'

            enviada = False
            if perfil.puede_notificar():
                enviada = _enviar_notificacion(perfil, match.vacante, mensaje)

            try:
                Notificacion.objects.create(
                    perfil=perfil,
                    vacante=match.vacante,
                    score_pct=score_pct,
                    mensaje=mensaje,
                    enviada=enviada,
                    fecha=fecha,
                )
            except IntegrityError:
                # Dos corridas pisándose para el mismo perfil+vacante+fecha
                # (p. ej. el curl manual de prueba del README justo cuando
                # el Schedule Trigger de n8n también dispara) — se trata
                # como "ya estaba creada" en vez de tumbar el resto del
                # batch con un 500.
                continue

            creadas += 1
            enviadas += int(enviada)

    return {"notificaciones_creadas": creadas, "notificaciones_enviadas": enviadas, "fecha": fecha}
