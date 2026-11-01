import re
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail, signing
from django.urls import reverse

from conftest import CLAVE_DE_PRUEBA
from cuentas.models import Usuario
from cuentas.services import crear_usuario_con_autorizacion
from cuentas.verificacion import EnlaceInvalido, EnlaceUsado, EnlaceVencido, generar_token, verificar

DATOS = {"paso": "datos", "email": "nueva@ejemplo.com", "email_confirmacion": "nueva@ejemplo.com",
         "autoriza_datos": "on", "acepta_terminos": "on"}


def _registrar(client):
    client.post(reverse("registro"), DATOS)
    return client.post(reverse("registro"), {"paso": "clave", "password1": CLAVE_DE_PRUEBA,
                                             "password2": CLAVE_DE_PRUEBA})


def _enlace() -> str:
    return re.search(r"https?://\S+/cuentas/verificar/\S+", mail.outbox[-1].body).group(0)


def test_registro_deja_la_cuenta_inactiva_y_envia_el_enlace(client, db):
    r = _registrar(client)
    u = Usuario.objects.get(email="nueva@ejemplo.com")
    assert not u.is_active and "_auth_user_id" not in client.session
    assert "Te enviamos un enlace a nueva@ejemplo.com" in r.content.decode() and len(mail.outbox) == 1


def test_el_enlace_activa_y_permite_entrar(client, db):
    _registrar(client)
    r = client.get(_enlace())
    assert r.status_code == 302 and Usuario.objects.get(email="nueva@ejemplo.com").is_active
    client.post(reverse("login"), {"paso": "correo", "email": "nueva@ejemplo.com"})
    assert client.post(reverse("login"), {"paso": "clave", "password": CLAVE_DE_PRUEBA}).status_code == 302


def test_sin_verificar_el_login_pide_confirmar(client, db):
    _registrar(client)
    client.post(reverse("login"), {"paso": "correo", "email": "nueva@ejemplo.com"})
    html = client.post(reverse("login"), {"paso": "clave", "password": CLAVE_DE_PRUEBA}).content.decode()
    assert "Confirma tu correo para entrar" in html and "_auth_user_id" not in client.session


def test_enlace_alterado(db):
    u = crear_usuario_con_autorizacion("a@ejemplo.com", CLAVE_DE_PRUEBA, activo=False)
    with pytest.raises(EnlaceInvalido):
        verificar(generar_token(u)[:-3] + "xyz")


def test_enlace_vencido(db):
    u = crear_usuario_con_autorizacion("a@ejemplo.com", CLAVE_DE_PRUEBA, activo=False)
    token = generar_token(u)
    with mock.patch("django.core.signing.time.time", return_value=__import__("time").time() + 4 * 86400):
        with pytest.raises(EnlaceVencido):
            verificar(token)


def test_enlace_reusado(db):
    u = crear_usuario_con_autorizacion("a@ejemplo.com", CLAVE_DE_PRUEBA, activo=False)
    token = generar_token(u)
    verificar(token)
    with pytest.raises(EnlaceUsado):
        verificar(token)


def test_la_pagina_de_enlace_invalido_permite_pedir_otro(client, db):
    html = client.get(reverse("verificar", args=["no-sirve"])).content.decode()
    assert "Este enlace no es válido" in html and reverse("reenviar_verificacion") in html


def test_reenviar_no_revela_si_el_correo_existe(client, db):
    crear_usuario_con_autorizacion("a@ejemplo.com", CLAVE_DE_PRUEBA, activo=False)
    sin_csrf = lambda html: re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", html)  # cambia en cada respuesta
    existe = client.post(reverse("reenviar_verificacion"), {"email": "a@ejemplo.com"}).content.decode()
    no_existe = client.post(reverse("reenviar_verificacion"), {"email": "nadie@ejemplo.com"}).content.decode()
    assert sin_csrf(existe) == sin_csrf(no_existe) and len(mail.outbox) == 1


def test_el_enlace_de_otro_usuario_no_activa_la_mia(db):
    a = crear_usuario_con_autorizacion("a@ejemplo.com", CLAVE_DE_PRUEBA, activo=False)
    b = crear_usuario_con_autorizacion("b@ejemplo.com", CLAVE_DE_PRUEBA, activo=False)
    verificar(generar_token(a))
    b.refresh_from_db()
    assert not b.is_active
    falso = signing.dumps({"u": b.pk, "e": "a@ejemplo.com"}, salt="otra-sal")
    with pytest.raises(EnlaceInvalido):
        verificar(falso)


def test_cuentas_sociales_no_necesitan_verificacion(db):
    assert crear_usuario_con_autorizacion("social@ejemplo.com", None).is_active
