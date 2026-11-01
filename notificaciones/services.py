from cuentas.models import Perfil

from .models import Notificacion


def bandeja(perfil: Perfil | None) -> list[Notificacion]:
    """Las notificaciones del candidato; abrir la bandeja marca como leídas las que no lo estaban."""
    if perfil is None:
        return []
    notificaciones = list(Notificacion.objects.filter(perfil=perfil).select_related("vacante"))
    sin_leer = [n.id for n in notificaciones if not n.leida]
    if sin_leer:
        Notificacion.objects.filter(id__in=sin_leer).update(leida=True)
    return notificaciones
