from django.db import transaction

from .legal import FINALIDAD, VERSION_POLITICA, VERSION_TERMINOS
from .models import Autorizacion, Usuario


def registrar_autorizacion(usuario: Usuario) -> Autorizacion:
    """Guarda la autorización con las versiones vigentes de la política y los términos."""
    return Autorizacion.objects.create(
        usuario=usuario,
        version_politica=VERSION_POLITICA,
        version_terminos=VERSION_TERMINOS,
        finalidad=FINALIDAD,
    )


@transaction.atomic
def crear_usuario_con_autorizacion(email: str, password: str | None) -> Usuario:
    """Nunca existe un usuario sin autorización: los dos se crean en la misma transacción."""
    usuario = Usuario.objects.create_user(email=email, password=password)
    registrar_autorizacion(usuario)
    return usuario
