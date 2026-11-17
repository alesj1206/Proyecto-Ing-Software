"""Regresiones de la revisión final de la Fase 3: la cuenta no existe hasta abrir el enlace."""

import re

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from conftest import CLAVE_DE_PRUEBA
from cuentas.models import Usuario


@pytest.fixture(autouse=True)
def cache_limpia():
    cache.clear()


def _registrar(client, email="victima@ejemplo.com", clave=CLAVE_DE_PRUEBA):
    client.post(reverse("registro"), {"paso": "datos", "email": email, "email_confirmacion": email,
                                      "autoriza_datos": "on", "acepta_terminos": "on"})
    return client.post(reverse("registro"), {"paso": "clave", "password1": clave, "password2": clave})


def _enlace(indice=-1) -> str:
    return re.search(r"https?://\S+/cuentas/verificar/\S+", mail.outbox[indice].body).group(0)


def test_registrar_no_crea_la_cuenta_hasta_abrir_el_enlace(client, db):
    _registrar(client)
    assert not Usuario.objects.exists()
    client.get(_enlace())
    u = Usuario.objects.get(email="victima@ejemplo.com")
    assert u.is_active and u.check_password(CLAVE_DE_PRUEBA) and u.autorizacion_set.exists()


def test_nadie_se_queda_con_un_correo_ajeno(client, db):
    _registrar(client, clave="Clave-Del-Atacante-91")
    enlace_del_atacante = _enlace()
    _registrar(client, clave=CLAVE_DE_PRUEBA)  # la dueña se registra: no ve "ya existe" y reemplaza lo pendiente
    client.get(_enlace())
    u = Usuario.objects.get(email="victima@ejemplo.com")
    assert u.check_password(CLAVE_DE_PRUEBA) and not u.check_password("Clave-Del-Atacante-91")
    assert "no es válido" in client.get(enlace_del_atacante).content.decode() or \
        client.get(enlace_del_atacante).status_code == 302


def test_reenviar_tiene_limite(client, db):
    _registrar(client)
    for _ in range(5):
        client.post(reverse("reenviar_verificacion"), {"email": "victima@ejemplo.com"})
    assert len(mail.outbox) == 2  # el del registro y un solo reenvío dentro de la ventana


def test_verificar_no_reactiva_una_cuenta_desactivada(client, usuario):
    usuario.is_active = False
    usuario.save()
    client.post(reverse("reenviar_verificacion"), {"email": usuario.email})
    assert len(mail.outbox) == 0


def test_registrarse_en_bucle_no_manda_correos_sin_limite(client, db, monkeypatch):
    monkeypatch.setattr("cuentas.views_auth.MAX_REGISTROS_IP", 2)
    respuestas = [_registrar(client, email=f"victima{i}@ejemplo.com") for i in range(4)]
    assert len(mail.outbox) == 2 and "Demasiados registros" in respuestas[-1].content.decode()
