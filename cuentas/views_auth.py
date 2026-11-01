"""Login y registro en dos pasos, con la estructura del login de Magneto (correo primero)."""

from django.contrib.auth import login, logout
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import ClaveLoginForm, CorreoForm, RegistroClaveForm, RegistroDatosForm
from .legal import VERSION_POLITICA, VERSION_TERMINOS
from .selectors import perfil_con_cv
from .services import crear_usuario_con_autorizacion
from .sociales import proveedores_activos

SESION_LOGIN = "login_correo"
SESION_REGISTRO = "registro_paso1"
BACKEND_CORREO = "django.contrib.auth.backends.ModelBackend"


def _destino_tras_login(usuario):
    return "dashboard" if perfil_con_cv(usuario) else "onboarding"


def _render_login(request, *, correo_form=None, clave_form=None):
    return render(request, "cuentas/login.html", {
        "correo_form": correo_form or CorreoForm(),
        "clave_form": clave_form,
        "email": request.session.get(SESION_LOGIN),
        "proveedores": proveedores_activos(),
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method != "POST" or "cambiar" in request.GET:
        request.session.pop(SESION_LOGIN, None)
        return _render_login(request)

    if request.POST.get("paso") == "correo":
        correo_form = CorreoForm(request.POST)
        if not correo_form.is_valid():
            return _render_login(request, correo_form=correo_form)
        # Siempre se pasa a la contraseña, exista o no el correo: así no se revela qué cuentas existen.
        request.session[SESION_LOGIN] = correo_form.cleaned_data["email"]
        return _render_login(request, clave_form=ClaveLoginForm(email=correo_form.cleaned_data["email"]))

    email = request.session.get(SESION_LOGIN)
    if not email:
        return redirect("login")
    clave_form = ClaveLoginForm(request.POST, email=email, request=request)
    if not clave_form.is_valid():
        return _render_login(request, clave_form=clave_form)
    request.session.pop(SESION_LOGIN, None)
    login(request, clave_form.usuario)
    return redirect(_destino_tras_login(clave_form.usuario))


def _render_registro(request, *, datos_form=None, clave_form=None):
    return render(request, "cuentas/registro.html", {
        "datos_form": datos_form or RegistroDatosForm(),
        "clave_form": clave_form,
        "email": (request.session.get(SESION_REGISTRO) or {}).get("email"),
        "proveedores": proveedores_activos(),
    })


def _paso1_vigente(request) -> dict | None:
    """El paso 1 guardado en la sesión, si aceptó las versiones vigentes de la política y los términos."""
    paso1 = request.session.get(SESION_REGISTRO)
    if paso1 and (paso1.get("version_politica"), paso1.get("version_terminos")) == (VERSION_POLITICA,
                                                                                   VERSION_TERMINOS):
        return paso1
    return None


def registro_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method != "POST":
        request.session.pop(SESION_REGISTRO, None)
        return _render_registro(request)

    if request.POST.get("paso") == "datos":
        datos_form = RegistroDatosForm(request.POST)
        if not datos_form.is_valid():
            return _render_registro(request, datos_form=datos_form)
        email = datos_form.cleaned_data["email"]
        request.session[SESION_REGISTRO] = {"email": email, "version_politica": VERSION_POLITICA,
                                            "version_terminos": VERSION_TERMINOS}
        return _render_registro(request, clave_form=RegistroClaveForm(email=email))

    paso1 = _paso1_vigente(request)
    if paso1 is None:  # sesión vencida, URL escrita a mano o textos legales actualizados
        request.session.pop(SESION_REGISTRO, None)
        return redirect("registro")
    clave_form = RegistroClaveForm(request.POST, email=paso1["email"])
    if not clave_form.is_valid():
        return _render_registro(request, clave_form=clave_form)
    request.session.pop(SESION_REGISTRO, None)
    try:
        usuario = crear_usuario_con_autorizacion(paso1["email"], clave_form.cleaned_data["password1"])
    except IntegrityError:  # alguien registró el mismo correo entre el paso 1 y el 2
        datos_form = RegistroDatosForm(initial={"email": paso1["email"]})
        datos_form.errors["email"] = datos_form.error_class(["Ya existe una cuenta con ese correo. Inicia sesión."])
        return _render_registro(request, datos_form=datos_form)
    login(request, usuario, backend=BACKEND_CORREO)
    return redirect("onboarding")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")
