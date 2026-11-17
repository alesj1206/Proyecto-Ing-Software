"""Verificación del correo (Fase 3, rediseñada en la revisión final: la cuenta se crea al abrir el enlace)."""

import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from conftest import CLAVE_DE_PRUEBA
from cuentas.models import RegistroPendiente, Usuario
from cuentas.services import crear_usuario_con_autorizacion
from cuentas.verificacion import EnlaceInvalido, EnlaceUsado, EnlaceVencido, verificar

DATOS = {"paso": "datos", "email": "nueva@ejemplo.com", "email_confirmacion": "nueva@ejemplo.com",
         "autoriza_datos": "on", "acepta_terminos": "on"}


@pytest.fixture(autouse=True)
def cache_limpia():
    cache.clear()


def _registrar(client):
    client.post(reverse("registro"), DATOS)
    return client.post(reverse("registro"), {"paso": "clave", "password1": CLAVE_DE_PRUEBA,
                                             "password2": CLAVE_DE_PRUEBA})


def _token() -> str:
    return re.search(r"/cuentas/verificar/(\S+)", mail.outbox[-1].body).group(1)


def test_registro_envia_el_enlace_sin_crear_la_cuenta(client, db):
    r = _registrar(client)
    assert not Usuario.objects.exists() and "_auth_user_id" not in client.session
    assert "Te enviamos un enlace a nueva@ejemplo.com" in r.content.decode() and len(mail.outbox) == 1


def test_el_enlace_crea_la_cuenta_y_permite_entrar(client, db):
    _registrar(client)
    r = client.get(reverse("verificar", args=[_token()]))
    assert r.status_code == 302 and Usuario.objects.get(email="nueva@ejemplo.com").is_active
    client.post(reverse("login"), {"paso": "correo", "email": "nueva@ejemplo.com"})
    assert client.post(reverse("login"), {"paso": "clave", "password": CLAVE_DE_PRUEBA}).status_code == 302


def test_enlace_alterado(client, db):
    _registrar(client)
    with pytest.raises(EnlaceInvalido):
        verificar(_token()[:-3] + "xyz")


def test_enlace_vencido(client, db):
    _registrar(client)
    RegistroPendiente.objects.update(creado_en=timezone.now() - timedelta(days=4))
    with pytest.raises(EnlaceVencido):
        verificar(_token())


def test_enlace_reusado(client, db):
    _registrar(client)
    token = _token()
    verificar(token)
    with pytest.raises(EnlaceInvalido):  # el registro pendiente ya no existe
        verificar(token)


def test_si_la_cuenta_ya_existe_el_enlace_no_crea_otra(client, db):
    _registrar(client)
    token = _token()
    crear_usuario_con_autorizacion("nueva@ejemplo.com", None)  # p. ej. entró antes con su red social
    with pytest.raises(EnlaceUsado):
        verificar(token)


def test_la_pagina_de_enlace_invalido_permite_pedir_otro(client, db):
    html = client.get(reverse("verificar", args=["no-sirve"])).content.decode()
    assert "Este enlace no es válido" in html and reverse("reenviar_verificacion") in html


def test_reenviar_no_revela_si_el_correo_existe(client, db):
    _registrar(client)
    sin_csrf = lambda html: re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", html)  # cambia en cada respuesta
    pendiente = client.post(reverse("reenviar_verificacion"), {"email": "nueva@ejemplo.com"}).content.decode()
    no_existe = client.post(reverse("reenviar_verificacion"), {"email": "nadie@ejemplo.com"}).content.decode()
    assert sin_csrf(pendiente) == sin_csrf(no_existe) and len(mail.outbox) == 2


def test_cuentas_sociales_no_necesitan_verificacion(db):
    assert crear_usuario_con_autorizacion("social@ejemplo.com", None).is_active


def test_la_autorizacion_guarda_la_version_que_se_acepto(client, db):
    _registrar(client)
    RegistroPendiente.objects.update(version_politica="vieja-1", version_terminos="vieja-2")
    usuario = verificar(_token())
    assert list(usuario.autorizacion_set.values_list("version_politica", "version_terminos")) == [("vieja-1", "vieja-2")]
