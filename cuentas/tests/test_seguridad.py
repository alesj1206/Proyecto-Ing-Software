"""Regresiones de la revisión final de la Fase 1 (toma de cuentas, fuerza bruta, enumeración, PDFs, minimización)."""

import pytest
from allauth.account.models import EmailAddress
from allauth.core import context
from allauth.socialaccount.models import SocialAccount
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse

from conftest import CLAVE_DE_PRUEBA
from cuentas.adaptadores import AdaptadorCuenta
from cuentas.forms import ClaveLoginForm, RegistroSocialForm
from cuentas.services import crear_usuario_con_autorizacion

from .test_sociales import _sociallogin, con_google, sin_proveedores  # noqa: F401 (fixtures)

BLOQUEADAS = ["/cuentas/email/", "/cuentas/password/change/", "/cuentas/password/set/", "/cuentas/password/reset/",
              "/cuentas/3rdparty/", "/cuentas/reauthenticate/", "/cuentas/inactive/", "/cuentas/logout/"]


@pytest.fixture(autouse=True)
def cache_limpia():
    cache.clear()


# --- toma de cuentas con login social --------------------------------------------------------------

def test_el_correo_del_alta_social_no_se_puede_cambiar(db, con_google):
    request = RequestFactory().get("/")
    with context.request_context(request):
        sl = _sociallogin("atacante@gmail.com", True, request=request)
        form = RegistroSocialForm(sociallogin=sl, data={"email": "victima@ejemplo.com", "autoriza_datos": "on",
                                                        "acepta_terminos": "on"})
        assert not form.is_valid() and "email" in form.errors


def test_un_correo_verificado_no_entra_a_una_cuenta_existente(usuario, con_google):
    # Nuestro registro no verifica correos: si se enlazara por correo, quien registró primero el correo ajeno
    # compartiría la cuenta con su dueño real.
    request = RequestFactory().get("/")
    with context.request_context(request):
        sl = _sociallogin("ana@ejemplo.com", verificado=True, request=request)
        sl.lookup()
    assert not sl.is_existing


@pytest.mark.parametrize("ruta", BLOQUEADAS)
def test_paginas_de_allauth_que_no_usamos_estan_bloqueadas(client, usuario, ruta):
    client.force_login(usuario)
    r = client.get(ruta)
    assert r.status_code in (302, 404) and r.status_code != 200


def test_no_se_redirige_a_otros_dominios_tras_el_login(rf):
    request = rf.get("/", HTTP_HOST="mi-tunel.trycloudflare.com")
    with context.request_context(request):
        adaptador = AdaptadorCuenta(request)
        assert not adaptador.is_safe_url("https://atacante.trycloudflare.com/robar")
        assert adaptador.is_safe_url("/dashboard")


# --- fuerza bruta y enumeración ----------------------------------------------------------------------

def _intento(client, email, clave):
    client.post(reverse("login"), {"paso": "correo", "email": email})
    return client.post(reverse("login"), {"paso": "clave", "password": clave})


def test_login_bloquea_tras_5_intentos_fallidos(client, usuario):
    for _ in range(5):
        _intento(client, "ana@ejemplo.com", "mala")
    r = _intento(client, "ana@ejemplo.com", CLAVE_DE_PRUEBA)
    assert "Demasiados intentos" in r.content.decode() and "_auth_user_id" not in client.session


def test_cuenta_solo_social_responde_igual_que_una_inexistente(client, db):
    crear_usuario_con_autorizacion("social@ejemplo.com", None)
    social = _intento(client, "social@ejemplo.com", "x").content.decode()
    assert ClaveLoginForm.ERROR_GENERICO in social and "no tiene contraseña" not in social


# --- borrado completo ---------------------------------------------------------------------------------

def test_eliminar_borra_tambien_postulaciones_notificaciones_y_cuentas_sociales(client_con_cv, usuario, vacante_v1):
    from notificaciones.models import Notificacion
    from postulaciones.models import Postulacion

    client_con_cv.post(reverse("postularme", args=["v1"]))
    Notificacion.objects.create(perfil=usuario.perfil, vacante=vacante_v1, score_pct=80, mensaje="x", fecha="2026-11-01")
    SocialAccount.objects.create(user=usuario, provider="google", uid="1")
    EmailAddress.objects.create(user=usuario, email=usuario.email, verified=True, primary=True)
    client_con_cv.post(reverse("eliminar_cuenta"), {"confirmo": "on"})
    assert (Postulacion.objects.count(), Notificacion.objects.count(), SocialAccount.objects.count(),
            EmailAddress.objects.count()) == (0, 0, 0, 0)
