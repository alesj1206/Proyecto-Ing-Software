"""Páginas del decisor: solo leen las decisiones ya calculadas por el batch (`manage.py decidir`)."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cuentas.selectors import perfil_con_cv
from postulaciones.models import Postulacion
from vacantes.models import Vacante

from . import selectors, taller as taller_cv
from .explicaciones import explicar
from .ia import obtener_redactor
from .models import Decision, SugerenciaCV
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
            "mercado": selectors.mercado(perfil),
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


@login_required
def taller_view(request, vacante_id):
    perfil = perfil_con_cv(request.user)
    vacante = get_object_or_404(Vacante, id=vacante_id)
    if perfil is None or not Decision.objects.filter(perfil=perfil, vacante=vacante).exists():
        raise Http404("No hay una decisión para esta vacante")
    return render(request, "matching/taller.html", {
        "vacante": vacante, "sugerencias": taller_cv.taller(perfil, vacante),
        "texto": taller_cv.texto_adaptado(perfil, vacante)})


@login_required
@require_POST
def taller_responder_view(request, vacante_id, sugerencia_id):
    sugerencia = get_object_or_404(SugerenciaCV, id=sugerencia_id, vacante_id=vacante_id,
                                   perfil=perfil_con_cv(request.user))
    taller_cv.responder(sugerencia, acepta=request.POST.get("acepta") == "1")
    return redirect("taller", vacante_id=vacante_id)


@login_required
def explicacion_view(request, vacante_id):
    """Fragmento HTML que el detalle carga a pedido ("Explícamelo"); así la página nunca espera a Groq."""
    decision = get_object_or_404(Decision, perfil=perfil_con_cv(request.user), vacante_id=vacante_id)
    return render(request, "matching/_explicacion.html", {"texto": explicar(decision, obtener_redactor())})
