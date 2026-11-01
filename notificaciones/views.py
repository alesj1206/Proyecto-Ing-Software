from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from cuentas.selectors import perfil_con_cv

from .models import Notificacion


@login_required
def notificaciones_view(request):
    """Abrir la bandeja marca como leídas las notificaciones que no lo estaban."""
    perfil = perfil_con_cv(request.user)
    notificaciones = list(Notificacion.objects.filter(perfil=perfil).select_related("vacante")) if perfil else []
    sin_leer = [n.id for n in notificaciones if not n.leida]
    if sin_leer:
        Notificacion.objects.filter(id__in=sin_leer).update(leida=True)
    return render(request, "notificaciones/notificaciones.html", {"notificaciones": notificaciones, "perfil": perfil})
