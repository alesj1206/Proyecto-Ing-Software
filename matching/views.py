"""Páginas del decisor: solo leen las decisiones ya calculadas por el batch (`manage.py decidir`)."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from cuentas.selectors import perfil_con_cv
from postulaciones.models import Postulacion
from vacantes.models import Vacante

from . import selectors
from .politica import Accion


@login_required
def dashboard_view(request):
    perfil = perfil_con_cv(request.user)
    modalidad_activa = request.GET.get("modalidad", "")
    contexto = {
        "perfil": perfil,
        "top_matches": selectors.plan_de_hoy(perfil) if perfil else [],
        "vacantes": selectors.catalogo(modalidad_activa),
        "total_vacantes": selectors.total_vacantes(),
        "modalidades": Vacante.Modalidad.choices,
        "modalidad_activa": modalidad_activa,
    }
    if perfil:
        grupos, conteos = selectors.decisiones_por_accion(perfil), selectors.conteo_por_accion(perfil)
        contexto |= {
            "pendiente": selectors.pendiente_de_decision(perfil),
            "por_accion": [(a, Accion(a).label, ds, conteos.get(a, 0), conteos.get(a, 0) - len(ds))
                           for a, ds in grupos.items() if ds],
            "aprendizaje": selectors.plan_de_aprendizaje(perfil),
            "ocultas_por_modalidad": selectors.ocultas_por_modalidad(perfil),
            "modalidad_oculta": selectors.MODALIDAD_OPUESTA.get(perfil.exp_modalidad, ""),
        }
    return render(request, "matching/dashboard.html", contexto)


@login_required
def historial_view(request):
    perfil = perfil_con_cv(request.user)
    if not perfil:
        return render(request, "matching/historial.html", {"perfil": None})
    try:
        fecha = date.fromisoformat(request.GET.get("fecha", ""))
    except ValueError:
        fecha = None
    return render(request, "matching/historial.html", selectors.historial(perfil, fecha))


def detalle_view(request, vacante_id):
    vacante = get_object_or_404(Vacante.objects.prefetch_related("requisito_set"), id=vacante_id)
    perfil = perfil_con_cv(request.user) if request.user.is_authenticated else None
    decision = selectors.detalle(perfil, vacante) if perfil else None
    contexto = {"vacante": vacante, "match": None, "criterios": [], "modificador": None, "decision": None,
                "postulacion": Postulacion.objects.filter(perfil=perfil, vacante=vacante).first() if perfil else None}
    return render(request, "matching/detalle.html", contexto | (decision or {}))
