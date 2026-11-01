from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CVUploadForm
from .selectors import perfil_con_cv
from .services import guardar_perfil_desde_cv


def _cargar_cv(request):
    """Procesa el POST de la hoja de vida; devuelve (form, guardado)."""
    form = CVUploadForm(request.POST, request.FILES)
    if form.is_valid():
        guardar_perfil_desde_cv(request.user, form.cleaned_data["cv"])
        return form, True
    return form, False


@login_required
def onboarding_view(request):
    form = CVUploadForm()
    if request.method == "POST":
        form, guardado = _cargar_cv(request)
        if guardado:
            return redirect("perfil")
    return render(request, "cuentas/onboarding.html", {"form": form})


@login_required
def perfil_view(request):
    form = CVUploadForm()
    if request.method == "POST":
        form, guardado = _cargar_cv(request)
        if guardado:
            return redirect("perfil")
    return render(request, "cuentas/perfil.html", {"perfil": perfil_con_cv(request.user), "form": form})
