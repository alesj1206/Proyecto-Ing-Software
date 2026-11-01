from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cuentas.selectors import perfil_con_cv
from vacantes.models import Vacante

from . import services
from .models import Postulacion


@login_required
@require_POST
def postular_view(request, vacante_id):
    vacante = get_object_or_404(Vacante, id=vacante_id)
    perfil = perfil_con_cv(request.user)
    if not perfil:
        messages.error(request, "Carga tu hoja de vida antes de postularte.")
    elif services.postular(perfil, vacante):
        messages.success(request, f'Postulación registrada para "{vacante.titulo}".')
    else:
        messages.info(request, "Ya te habías postulado a esta vacante.")
    return redirect("vacante_detalle", vacante_id=vacante_id)


@login_required
def tablero_view(request):
    perfil = perfil_con_cv(request.user)
    postulaciones = Postulacion.objects.filter(perfil=perfil).select_related("vacante") if perfil else []
    columnas = [{"estado": valor, "etiqueta": etiqueta, "postulaciones": []}
                for valor, etiqueta in Postulacion.Estado.choices]
    por_estado = {c["estado"]: c for c in columnas}
    for p in postulaciones:
        por_estado[p.estado]["postulaciones"].append(p)
    return render(request, "postulaciones/tablero.html",
                  {"columnas": columnas, "perfil": perfil, "estados": Postulacion.Estado.choices})


@login_required
@require_POST
def cambiar_estado_postulacion_view(request, postulacion_id):
    postulacion = get_object_or_404(Postulacion, id=postulacion_id, perfil=perfil_con_cv(request.user))
    if services.cambiar_estado(postulacion, request.POST.get("estado", "")):
        messages.success(request, f'"{postulacion.vacante.titulo}" movida a {postulacion.get_estado_display()}.')
    else:
        messages.error(request, "Estado inválido.")
    return redirect("tablero")
