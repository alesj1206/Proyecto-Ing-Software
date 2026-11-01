"""Páginas del decisor. En la Fase 1 renderizan con el catálogo y sin decisiones: los templates de v2 muestran su
estado vacío. La Fase 2 llena top_matches, el historial y el match del detalle."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from cuentas.selectors import perfil_con_cv
from postulaciones.models import Postulacion
from vacantes.models import Vacante

from . import selectors


@login_required
def dashboard_view(request):
    modalidad_activa = request.GET.get("modalidad", "")
    return render(request, "matching/dashboard.html", {
        "perfil": perfil_con_cv(request.user),
        "top_matches": [],
        "vacantes": selectors.catalogo(modalidad_activa),
        "total_vacantes": selectors.total_vacantes(),
        "modalidades": Vacante.Modalidad.choices,
        "modalidad_activa": modalidad_activa,
    })


@login_required
def historial_view(request):
    perfil = perfil_con_cv(request.user)
    if not perfil:
        return render(request, "matching/historial.html", {"perfil": None})
    return render(request, "matching/historial.html", {
        "perfil": perfil, "fechas_disponibles": [], "fecha_sel": None, "fecha_anterior": None, "ranking": [],
    })


def detalle_view(request, vacante_id):
    vacante = get_object_or_404(Vacante.objects.prefetch_related("requisito_set"), id=vacante_id)
    perfil = perfil_con_cv(request.user) if request.user.is_authenticated else None
    postulacion = Postulacion.objects.filter(perfil=perfil, vacante=vacante).first() if perfil else None
    return render(request, "matching/detalle.html", {
        "vacante": vacante, "match": None, "criterios": [], "postulacion": postulacion, "modificador": None,
    })
