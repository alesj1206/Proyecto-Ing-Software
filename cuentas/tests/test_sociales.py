import pytest
from allauth.account.models import EmailAddress
from allauth.core import context
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.test import RequestFactory
from django.urls import reverse

from conftest import CLAVE_DE_PRUEBA
from cuentas.forms import RegistroSocialForm
from cuentas.models import Usuario
from cuentas.sociales import proveedores_activos, settings_proveedores

PROVEEDORES = ("LINKEDIN", "FACEBOOK", "GOOGLE", "MICROSOFT")


@pytest.fixture
def sin_proveedores(monkeypatch):
    for p in PROVEEDORES:
        monkeypatch.delenv(f"SOCIAL_{p}_ID", raising=False)
        monkeypatch.delenv(f"SOCIAL_{p}_SECRET", raising=False)


def _configurar(monkeypatch, *proveedores):
    for p in proveedores:
        monkeypatch.setenv(f"SOCIAL_{p}_ID", f"id-{p}")
        monkeypatch.setenv(f"SOCIAL_{p}_SECRET", f"secreto-{p}")


@pytest.fixture
def con_google(sin_proveedores, monkeypatch, settings):
    _configurar(monkeypatch, "GOOGLE")
    settings.SOCIALACCOUNT_PROVIDERS = settings_proveedores()


def _sociallogin(email, verificado, request=None):
    cuenta = SocialAccount(provider="google", uid="uid-123")
    return SocialLogin(
        user=Usuario(email=email),
        account=cuenta,
        email_addresses=[EmailAddress(email=email, verified=verificado, primary=True)],
        provider=cuenta.get_provider(request) if request else None,
    )


# --- qué botones aparecen --------------------------------------------------------------------------

def test_sin_credenciales_no_hay_botones(client, db, sin_proveedores):
    assert proveedores_activos() == []
    assert "auth-social" not in client.get(reverse("login")).content.decode()


def test_solo_aparecen_los_configurados_en_orden_magneto(sin_proveedores, monkeypatch):
    _configurar(monkeypatch, "GOOGLE", "LINKEDIN")
    assert [p.id for p in proveedores_activos()] == ["linkedin", "google"]


def test_un_proveedor_sin_secret_no_cuenta(sin_proveedores, monkeypatch):
    monkeypatch.setenv("SOCIAL_FACEBOOK_ID", "f")
    assert "facebook" not in [p.id for p in proveedores_activos()]


def test_los_botones_inician_el_login_por_post(client, db, sin_proveedores, monkeypatch, settings):
    _configurar(monkeypatch, "GOOGLE")
    settings.SOCIALACCOUNT_PROVIDERS = settings_proveedores()
    html = client.get(reverse("registro")).content.decode()
    assert 'method="post" action="/cuentas/google/login/' in html and "Google" in html


def test_linkedin_va_por_openid_connect(sin_proveedores, monkeypatch):
    _configurar(monkeypatch, "LINKEDIN")
    [app] = settings_proveedores()["openid_connect"]["APPS"]
    assert app["provider_id"] == "linkedin"
    assert app["settings"]["server_url"] == "https://www.linkedin.com/oauth"


# --- alta con red social: siempre con autorización -------------------------------------------------

def test_registro_social_exige_las_casillas(db):
    form = RegistroSocialForm(sociallogin=_sociallogin("x@e.com", True), data={"email": "x@e.com"})
    assert not form.is_valid()
    assert {"autoriza_datos", "acepta_terminos"} <= set(form.errors)


def test_registro_social_guarda_la_autorizacion(db):
    sl = _sociallogin("x@e.com", True)
    form = RegistroSocialForm(sociallogin=sl, data={"email": "x@e.com", "autoriza_datos": "on",
                                                    "acepta_terminos": "on"})
    assert form.is_valid(), form.errors
    request = RequestFactory().post("/")
    request.session = {}
    with context.request_context(request):
        usuario = form.save(request)
    assert usuario.autorizacion_set.exists() and not usuario.has_usable_password()


def test_los_textos_de_allauth_no_dejan_pantallas_sin_estilo(client, db):
    assert client.get("/cuentas/login/").url == reverse("login")
    assert client.get("/cuentas/signup/").url == reverse("registro")


# --- enlace con cuentas existentes ------------------------------------------------------------------

def test_correo_no_verificado_no_toma_una_cuenta_existente(usuario, con_google):
    request = RequestFactory().get("/")
    with context.request_context(request):
        sl = _sociallogin("ana@ejemplo.com", verificado=False, request=request)
        sl.lookup()
    assert not sl.is_existing



def test_el_boton_de_google_lleva_a_google_con_nuestro_client_id(client, db, con_google):
    r = client.post("/cuentas/google/login/")
    assert r.status_code == 302
    assert r.url.startswith("https://accounts.google.com/") and "client_id=id-GOOGLE" in r.url
    assert "redirect_uri=http%3A%2F%2Ftestserver%2Fcuentas%2Fgoogle%2Flogin%2Fcallback%2F" in r.url
