import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from matching.services import solicitar_decision

from . import oauth_magneto
from .forms import CVUploadForm, ExpectativasForm
from .models import ConexionMagneto, Perfil
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


def _b1_activo():
    if not settings.SCOUTLY_MAGNETO_MCP:  # apagado hasta revisar los términos de uso de Magneto
        raise Http404("La conexión con Magneto no está activa")


@login_required
def conectar_magneto_view(request):
    _b1_activo()
    verificador, desafio = oauth_magneto.generar_pkce()
    estado = secrets.token_urlsafe(24)
    request.session["magneto_oauth"] = {"estado": estado, "verificador": verificador}
    return redirect(oauth_magneto.url_autorizacion(estado, desafio, request.build_absolute_uri(
        reverse("callback_magneto"))))


@login_required
def callback_magneto_view(request):
    _b1_activo()
    pendiente = request.session.pop("magneto_oauth", None)
    if not pendiente or request.GET.get("state") != pendiente["estado"] or "code" not in request.GET:
        messages.error(request, "No pudimos conectar tu cuenta de Magneto. Vuelve a intentarlo.")
        return redirect("perfil")
    token, expira = oauth_magneto.intercambiar_codigo(request.GET["code"], pendiente["verificador"],
                                                      request.build_absolute_uri(reverse("callback_magneto")))
    oauth_magneto.guardar_token(request.user, token, expira)
    messages.success(request, "Conectamos tu cuenta de Magneto (solo lectura).")
    return redirect("perfil")


@login_required
def desconectar_magneto_view(request):
    _b1_activo()
    if request.method == "POST":
        ConexionMagneto.objects.filter(usuario=request.user).delete()
        messages.success(request, "Desconectamos tu cuenta de Magneto y borramos su token.")
    return redirect("perfil")
