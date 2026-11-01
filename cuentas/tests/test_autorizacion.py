from unittest import mock

import pytest
from django.db import IntegrityError
from django.urls import reverse

from cuentas.legal import VERSION_POLITICA, VERSION_TERMINOS
from cuentas.models import Autorizacion, Usuario
from cuentas.services import crear_usuario_con_autorizacion


def test_crear_usuario_guarda_la_autorizacion_vigente(db):
    u = crear_usuario_con_autorizacion(" Ana@Ejemplo.com ", "Lienzo-Tardio-73")
    a = u.autorizacion_set.get()
    assert u.email == "ana@ejemplo.com"
    assert u.check_password("Lienzo-Tardio-73")
    assert (a.version_politica, a.version_terminos) == (VERSION_POLITICA, VERSION_TERMINOS)


def test_si_falla_la_autorizacion_no_queda_usuario(db, monkeypatch):
    monkeypatch.setattr(Autorizacion.objects, "create", mock.Mock(side_effect=IntegrityError))
    with pytest.raises(IntegrityError):
        crear_usuario_con_autorizacion("b@ejemplo.com", "Lienzo-Tardio-73")
    assert not Usuario.objects.filter(email="b@ejemplo.com").exists()


def test_usuario_social_sin_contrasena_usable(db):
    assert not crear_usuario_con_autorizacion("c@ejemplo.com", None).has_usable_password()


def test_el_correo_es_unico_sin_importar_mayusculas(db):
    crear_usuario_con_autorizacion("d@ejemplo.com", "Lienzo-Tardio-73")
    with pytest.raises(IntegrityError):
        crear_usuario_con_autorizacion("D@Ejemplo.com", "Lienzo-Tardio-73")


def test_paginas_legales_publicas(client, db):
    for ruta, version in (("privacidad", VERSION_POLITICA), ("terminos", VERSION_TERMINOS)):
        r = client.get(reverse(ruta))
        assert r.status_code == 200 and version in r.content.decode()


def test_la_politica_describe_lo_que_hace_el_codigo(client, db):
    """Revisión final: la política debe nombrar a quienes reciben datos, al responsable y cómo revocar."""
    texto = client.get(reverse("privacidad")).content.decode()
    for frase in ("Google, Microsoft, Facebook y LinkedIn", "Cloudflare", "Responsable del tratamiento",
                  "Eliminar mi cuenta", "nombre y tu correo"):
        assert frase in texto, frase


def test_la_politica_dice_que_groq_no_recibe_el_cv(client, db):
    texto = client.get(reverse("privacidad")).content.decode()
    assert "Groq" in texto and "nunca el CV" in texto
