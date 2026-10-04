from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .cv_parser import extraer_datos_cv
from .forms import CVUploadForm, ExpectativasForm
from .matching import compute_match, compute_matches_de_hoy
from .models import Perfil, Vacante

TOP_MATCHES = 3


def _guardar_perfil_desde_cv(usuario, archivo):
    datos = extraer_datos_cv(archivo)
    Perfil.objects.update_or_create(
        usuario=usuario,
        defaults={**datos, "cv_nombre_archivo": archivo.name},
    )


def _perfil_con_cv(usuario):
    """Perfil solo si tiene una hoja de vida cargada. expectativas_view crea
    un Perfil vacío (cv_nombre_archivo="") la primera vez que alguien visita
    /expectativas sin haber pasado por onboarding — ese registro no cuenta
    como "ya tiene CV" para el resto de la app (dashboard, detalle)."""
    perfil = Perfil.objects.filter(usuario=usuario).first()
    if perfil and not perfil.cv_nombre_archivo:
        return None
    return perfil


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

    perfil = _perfil_con_cv(request.user)
    return render(request, "vacantes/perfil.html", {"perfil": perfil, "form": form})


@login_required
def expectativas_view(request):
    perfil, _ = Perfil.objects.get_or_create(
        usuario=request.user, defaults={"cv_nombre_archivo": ""}
    )

    if request.method == "POST":
        form = ExpectativasForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            return redirect("expectativas")
    else:
        form = ExpectativasForm(instance=perfil)

    return render(request, "vacantes/expectativas.html", {"form": form, "perfil": perfil})


@login_required
def dashboard_view(request):
    perfil = _perfil_con_cv(request.user)
    todas_vacantes = list(Vacante.objects.all())

    matches = compute_matches_de_hoy(perfil, todas_vacantes) if perfil else []
    top_matches = [
        {"vacante": m.vacante, "score_pct": round(m.score * 100), "coincidencias": m.coincidencias}
        for m in matches[:TOP_MATCHES]
    ]

    modalidad_activa = request.GET.get("modalidad", "")
    vacantes = (
        [v for v in todas_vacantes if v.modalidad == modalidad_activa]
        if modalidad_activa
        else todas_vacantes
    )

    return render(
        request,
        "vacantes/dashboard.html",
        {
            "perfil": perfil,
            "top_matches": top_matches,
            "vacantes": vacantes,
            # Total de la plataforma, no del filtro activo — el filtro ya se
            # ve reflejado en cuántas filas trae la lista de abajo.
            "total_vacantes": len(todas_vacantes),
            "modalidades": Vacante.Modalidad.choices,
            "modalidad_activa": modalidad_activa,
        },
    )


def detalle_view(request, vacante_id):
    vacante = get_object_or_404(Vacante, id=vacante_id)

    match = None
    if request.user.is_authenticated:
        perfil = _perfil_con_cv(request.user)
        if perfil:
            score, coincidencias = compute_match(perfil, vacante)
            faltantes = [r for r in vacante.requisitos if r not in coincidencias]
            match = {
                "score": round(score * 100),
                "coincidencias": coincidencias,
                "faltantes": faltantes,
            }

    return render(request, "vacantes/detalle.html", {"vacante": vacante, "match": match})
