from django.db import IntegrityError

from cuentas.models import Perfil
from vacantes.models import Vacante

from .models import Postulacion


def postular(perfil: Perfil, vacante: Vacante) -> bool:
    """Idempotente: devuelve True solo si la postulación es nueva (un doble clic no crea dos)."""
    try:
        _, creada = Postulacion.objects.get_or_create(perfil=perfil, vacante=vacante)
    except IntegrityError:  # dos peticiones a la vez: la segunda choca con la restricción única
        return False
    return creada


def cambiar_estado(postulacion: Postulacion, estado: str) -> bool:
    if estado not in Postulacion.Estado.values:
        return False
    postulacion.estado = estado
    postulacion.save(update_fields=["estado", "actualizado_en"])
    return True
