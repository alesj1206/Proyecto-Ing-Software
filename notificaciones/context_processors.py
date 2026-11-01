from .models import Notificacion


def notificaciones_sin_leer(request):
    """Contador de la campana del menú (templates/base.html), disponible en todas las páginas."""
    if not request.user.is_authenticated:
        return {}
    return {"notificaciones_sin_leer": Notificacion.objects.filter(perfil__usuario=request.user, leida=False).count()}
