"""Recuperar la contraseña con las vistas de restablecimiento de Django (auditoría, hallazgo 12)."""

import re

from django.core import mail
from django.urls import reverse

NUEVA = "Faro-Lejano-48"


def test_recuperar_la_contrasena_de_punta_a_punta(client, usuario):
    client.post(reverse("clave_olvidada"), {"email": "ANA@ejemplo.com"})
    ruta = re.search(r"https?://[^/]+(/clave/nueva/\S+)", mail.outbox[0].body).group(1)
    formulario = client.get(ruta, follow=True).request["PATH_INFO"]
    assert client.post(formulario, {"new_password1": NUEVA, "new_password2": NUEVA}).status_code == 302
    usuario.refresh_from_db()
    assert usuario.check_password(NUEVA)
    client.post(reverse("login"), {"paso": "correo", "email": "ana@ejemplo.com"})
    assert client.post(reverse("login"), {"paso": "clave", "password": NUEVA}).status_code == 302


def test_recuperar_no_revela_si_el_correo_existe(client, db):
    r = client.post(reverse("clave_olvidada"), {"email": "nadie@ejemplo.com"})
    assert (r.status_code, r.url) == (302, reverse("clave_enviado")) and not mail.outbox


def test_el_login_enlaza_a_recuperar_la_contrasena(client, db):
    html = client.post(reverse("login"), {"paso": "correo", "email": "ana@ejemplo.com"}).content.decode()
    assert reverse("clave_olvidada") in html
