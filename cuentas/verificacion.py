"""Verificación del correo al registrarse (revisión final de la Fase 3). El registro deja un RegistroPendiente con un
token aleatorio (solo se guarda su hash) y la cuenta se crea al abrir el enlace, dentro de 3 días. Así:
- nadie se apropia de un correo ajeno: el enlace llega al dueño del correo, y si el dueño se registra, reemplaza lo
  pendiente con su propia contraseña;
- no hay cuentas inactivas que reactivar;
- los reenvíos tienen límite."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .legal import VERSION_POLITICA, VERSION_TERMINOS
from .models import RegistroPendiente, Usuario, normalizar_correo
from .services import crear_usuario_con_autorizacion

VIGENCIA = timedelta(days=3)
ESPERA_REENVIO_S = 300  # un reenvío cada 5 minutos por correo


class EnlaceInvalido(Exception):
    pass


class EnlaceVencido(Exception):
    pass


class EnlaceUsado(Exception):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _enviar(pendiente: RegistroPendiente, request) -> None:
    token = secrets.token_urlsafe(32)
    pendiente.token_hash = _hash(token)
    pendiente.save()
    enlace = request.build_absolute_uri(reverse("verificar", args=[token]))
    send_mail("Confirma tu correo en Scoutly",
              f"Hola. Abre este enlace para crear tu cuenta de Scoutly (vence en 3 días):\n\n{enlace}\n\n"
              "Si no te registraste, ignora este correo: no se creará ninguna cuenta.",
              settings.DEFAULT_FROM_EMAIL, [pendiente.email],
              html_message=render_to_string("cuentas/correo_verificacion.html",
                                            {"url_accion": enlace, "texto_boton": "Confirmar mi correo"}))


def registrar_pendiente(email: str, password: str, request) -> None:
    """Crea o REEMPLAZA el registro pendiente de ese correo y envía el enlace."""
    email = normalizar_correo(email)
    pendiente = RegistroPendiente.objects.filter(email=email).first() or RegistroPendiente(email=email)
    pendiente.password = make_password(password)
    pendiente.version_politica, pendiente.version_terminos = VERSION_POLITICA, VERSION_TERMINOS
    _enviar(pendiente, request)


def reenviar(email: str, request) -> None:
    """Reenvía el enlace si hay un registro pendiente, como mucho uno cada 5 minutos. No revela nada."""
    email = normalizar_correo(email)
    if not cache.add(f"reenvio-verificacion:{email}", 1, ESPERA_REENVIO_S):
        return
    if pendiente := RegistroPendiente.objects.filter(email=email).first():
        _enviar(pendiente, request)


@transaction.atomic
def verificar(token: str) -> Usuario:
    pendiente = RegistroPendiente.objects.select_for_update().filter(token_hash=_hash(token)).first()
    if pendiente is None:
        raise EnlaceInvalido
    if pendiente.creado_en < timezone.now() - VIGENCIA:
        pendiente.delete()
        raise EnlaceVencido
    if Usuario.objects.filter(email=pendiente.email).exists():
        pendiente.delete()
        raise EnlaceUsado
    usuario = crear_usuario_con_autorizacion(pendiente.email, None)
    usuario.password = pendiente.password  # el hash que eligió quien se registró
    usuario.save(update_fields=["password"])
    pendiente.delete()
    return usuario
