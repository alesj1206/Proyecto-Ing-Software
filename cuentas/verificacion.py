"""Verificación del correo al registrarse: la cuenta queda inactiva hasta abrir un enlace firmado (3 días). Evita que
alguien registre un correo ajeno (pendiente de la revisión de la Fase 1). Las cuentas sociales ya llegan verificadas."""

from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

from .models import Usuario

SAL = "scoutly.verificacion"
VIGENCIA = timedelta(days=3)


class EnlaceInvalido(Exception):
    pass


class EnlaceVencido(Exception):
    pass


class EnlaceUsado(Exception):
    pass


def generar_token(usuario: Usuario) -> str:
    return signing.dumps({"u": usuario.pk, "e": usuario.email}, salt=SAL)


def enviar_verificacion(usuario: Usuario, request) -> None:
    enlace = request.build_absolute_uri(reverse("verificar", args=[generar_token(usuario)]))
    send_mail("Confirma tu correo en Scoutly",
              f"Hola. Abre este enlace para activar tu cuenta de Scoutly (vence en 3 días):\n\n{enlace}\n\n"
              "Si no creaste una cuenta, ignora este correo.",
              settings.DEFAULT_FROM_EMAIL, [usuario.email])


def verificar(token: str) -> Usuario:
    try:
        datos = signing.loads(token, salt=SAL, max_age=VIGENCIA)
    except signing.SignatureExpired as error:
        raise EnlaceVencido from error
    except signing.BadSignature as error:
        raise EnlaceInvalido from error
    usuario = Usuario.objects.filter(pk=datos.get("u"), email=datos.get("e")).first()
    if usuario is None:
        raise EnlaceInvalido
    if usuario.is_active:
        raise EnlaceUsado
    usuario.is_active = True
    usuario.save(update_fields=["is_active"])
    return usuario
