from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from cuentas.selectors import perfil_con_cv

from . import services


@login_required
def notificaciones_view(request):
    perfil = perfil_con_cv(request.user)
    return render(request, "notificaciones/notificaciones.html",
                  {"notificaciones": services.bandeja(perfil), "perfil": perfil})
