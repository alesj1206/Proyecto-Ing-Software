from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .cv_parser import extraer_datos_cv
from .forms import CVUploadForm
from .matching import compute_match, compute_matches_de_hoy
from .models import Perfil, Vacante

TOP_MATCHES = 3


def _guardar_perfil_desde_cv(usuario, archivo):
    datos = extraer_datos_cv(archivo)
    Perfil.objects.update_or_create(
        usuario=usuario,
        defaults={**datos, "cv_nombre_archivo": archivo.name},
    )


@login_required
def onboarding_view(request):
    form = CVUploadForm()

    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            _guardar_perfil_desde_cv(request.user, form.cleaned_data["cv"])
            return redirect("perfil")

    return render(request, "vacantes/onboarding.html", {"form": form})


@login_required
def perfil_view(request):
    form = CVUploadForm()

    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            _guardar_perfil_desde_cv(request.user, form.cleaned_data["cv"])
            return redirect("perfil")

    perfil = Perfil.objects.filter(usuario=request.user).first()
    return render(request, "vacantes/perfil.html", {"perfil": perfil, "form": form})


@login_required
def dashboard_view(request):
    perfil = Perfil.objects.filter(usuario=request.user).first()
    vacantes = list(Vacante.objects.all())

    matches = compute_matches_de_hoy(perfil, vacantes) if perfil else []
    top_matches = [
        {"vacante": m.vacante, "score_pct": round(m.score * 100), "coincidencias": m.coincidencias}
        for m in matches[:TOP_MATCHES]
    ]

    return render(
        request,
        "vacantes/dashboard.html",
        {
            "perfil": perfil,
            "top_matches": top_matches,
            "vacantes": vacantes,
            "total_vacantes": len(vacantes),
        },
    )


def detalle_view(request, vacante_id):
    vacante = get_object_or_404(Vacante, id=vacante_id)

    match = None
    if request.user.is_authenticated:
        perfil = Perfil.objects.filter(usuario=request.user).first()
        if perfil:
            score, coincidencias = compute_match(perfil, vacante)
            faltantes = [r for r in vacante.requisitos if r not in coincidencias]
            match = {
                "score": round(score * 100),
                "coincidencias": coincidencias,
                "faltantes": faltantes,
            }

    return render(request, "vacantes/detalle.html", {"vacante": vacante, "match": match})
