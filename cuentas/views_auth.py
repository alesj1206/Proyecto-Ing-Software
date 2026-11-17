"""Login y registro en dos pasos, con la estructura del login de Magneto (correo primero)."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import PasswordResetView
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import ClaveLoginForm, CorreoForm, RegistroClaveForm, RegistroDatosForm
from .legal import VERSION_POLITICA, VERSION_TERMINOS
from .models import Usuario
from .selectors import perfil_con_cv
from .sociales import proveedores_activos
from .verificacion import EnlaceInvalido, EnlaceUsado, EnlaceVencido, registrar_pendiente, reenviar, verificar

MAX_INTENTOS_LOGIN = 5
BLOQUEO_LOGIN_S = 15 * 60
MAX_REGISTROS_IP, VENTANA_REGISTROS_S = 20, 60 * 60  # correos de confirmación por IP y hora (una red compartida cabe)
SESION_LOGIN = "login_correo"
SESION_REGISTRO = "registro_paso1"
BACKEND_CORREO = "django.contrib.auth.backends.ModelBackend"


def _destino_tras_login(usuario):
    return "dashboard" if perfil_con_cv(usuario) else "onboarding"


def _ip(request) -> str:
    """Detrás de cloudflared la IP real llega en CF-Connecting-IP."""
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR", "")


def _clave_intentos(request, email: str) -> str:
    """Por correo y por IP."""
    return f"login-fallidos:{email}:{_ip(request)}"


def _demasiados_registros(request) -> bool:
    """Tope de correos de confirmación por IP: sin él, registrarse en bucle manda correos sin límite a un tercero. Es
    por IP y no por correo para que nadie pueda bloquear el registro del dueño de una dirección."""
    clave = f"registros:{_ip(request)}"
    cache.add(clave, 0, VENTANA_REGISTROS_S)
    try:
        return cache.incr(clave) > MAX_REGISTROS_IP
    except ValueError:  # la clave venció entre el add y el incr
        return False


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
    clave_intentos = _clave_intentos(request, email)
    bloqueado = cache.get(clave_intentos, 0) >= MAX_INTENTOS_LOGIN
    clave_form = ClaveLoginForm(request.POST, email=email, request=request, bloqueado=bloqueado)
    if not clave_form.is_valid():
        cache.set(clave_intentos, cache.get(clave_intentos, 0) + 1, BLOQUEO_LOGIN_S)
        return _render_login(request, clave_form=clave_form)
    cache.delete(clave_intentos)
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
    if _demasiados_registros(request):
        clave_form.add_error("password1", "Demasiados registros desde tu red. Inténtalo de nuevo en una hora.")
        return _render_registro(request, clave_form=clave_form)
    request.session.pop(SESION_REGISTRO, None)
    registrar_pendiente(paso1["email"], clave_form.cleaned_data["password1"], request)
    return render(request, "cuentas/registro.html", {"enviado": paso1["email"], "proveedores": []})


def verificar_view(request, token):
    try:
        verificar(token)
    except EnlaceUsado:
        messages.info(request, "Tu correo ya estaba confirmado: inicia sesión.")
        return redirect("login")
    except EnlaceVencido:
        return render(request, "cuentas/verificacion.html", {"problema": "Este enlace venció."})
    except EnlaceInvalido:
        return render(request, "cuentas/verificacion.html", {"problema": "Este enlace no es válido."})
    messages.success(request, "Tu correo quedó confirmado. Ya puedes iniciar sesión.")
    return redirect("login")


@require_POST
def reenviar_verificacion_view(request):
    """La misma respuesta exista o no la cuenta: no revela qué correos están registrados."""
    reenviar(request.POST.get("email", ""), request)
    return render(request, "cuentas/verificacion.html", {
        "aviso": "Si ese correo tiene un registro pendiente de confirmar, te enviamos un enlace nuevo "
                 "(como mucho uno cada 5 minutos)."})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


class ClaveOlvidadaView(PasswordResetView):
    """Restablecimiento de Django: solo escribe a cuentas activas con contraseña y responde igual exista o no el
    correo. Comparte el tope de correos por IP del registro."""

    template_name = "cuentas/clave.html"
    extra_context = {"paso": "olvidada"}
    email_template_name = "cuentas/correo_clave.txt"
    subject_template_name = "cuentas/correo_clave_asunto.txt"
    success_url = reverse_lazy("clave_enviado")

    def get_initial(self):  # viene del paso de contraseña del login: el correo ya está escrito
        return {"email": self.request.session.get(SESION_LOGIN, "")}

    def form_valid(self, form):
        if _demasiados_registros(self.request):
            return redirect(self.success_url)  # misma respuesta, sin correo
        return super().form_valid(form)
