from .models import Notificacion


def notificaciones_sin_leer(request):
    """Contador para la campanita del nav (templates/base.html) — tiene que
    estar disponible en todas las páginas, no solo en /notificaciones, así
    que va como context processor en vez de repetirse en cada vista."""
    if not request.user.is_authenticated:
        return {}
    return {
        "notificaciones_sin_leer": Notificacion.objects.filter(
            perfil__usuario=request.user, leida=False
        ).count()
    }
