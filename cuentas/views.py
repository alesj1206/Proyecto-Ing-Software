from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from matching.services import solicitar_decision

from .forms import CVUploadForm, ExpectativasForm
from .models import Perfil
from .selectors import perfil_con_cv
from .services import eliminar_cuenta, guardar_perfil_desde_cv


def _cargar_cv(request):
    """Procesa el POST de la hoja de vida; devuelve (form, guardado)."""
    form = CVUploadForm(request.POST, request.FILES)
    if form.is_valid():
        solicitar_decision(guardar_perfil_desde_cv(request.user, form.cleaned_data["cv"]))
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


@login_required
def expectativas_view(request):
    perfil, _ = Perfil.objects.get_or_create(usuario=request.user)
    form = ExpectativasForm(request.POST or None, instance=perfil)
    if request.method == "POST" and form.is_valid():
        form.save()
        if perfil.tiene_cv():
            solicitar_decision(perfil)  # el batch recalcula sus decisiones (la web no carga modelos)
        return redirect("expectativas")
    return render(request, "cuentas/expectativas.html", {"form": form, "perfil": perfil})


@login_required
def eliminar_cuenta_view(request):
    error = None
    if request.method == "POST":
        if request.POST.get("confirmo"):
            usuario = request.user
            logout(request)
            eliminar_cuenta(usuario)
            messages.success(request, "Eliminamos tu cuenta y todos tus datos.")
            return redirect("login")
        error = "Marca la casilla para confirmar que quieres eliminar tu cuenta."
    return render(request, "cuentas/eliminar_cuenta.html", {"error": error})
