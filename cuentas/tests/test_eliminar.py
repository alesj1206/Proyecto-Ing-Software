from django.urls import reverse

from cuentas.models import Autorizacion, EvidenciaPerfil, Perfil, Usuario
from cuentas.services import guardar_perfil_desde_cv

from .cvs import pdf_cv


def test_eliminar_borra_todo_en_cascada(client, usuario):
    guardar_perfil_desde_cv(usuario, pdf_cv())
    client.force_login(usuario)
    r = client.post(reverse("eliminar_cuenta"), {"confirmo": "on"})
    assert r.status_code == 302 and r.url == reverse("login")
    assert (Usuario.objects.count(), Perfil.objects.count(), EvidenciaPerfil.objects.count(),
            Autorizacion.objects.count()) == (0, 0, 0, 0)
    assert "_auth_user_id" not in client.session
    assert "Eliminamos tu cuenta" in client.get(r.url).content.decode()


def test_eliminar_exige_confirmacion(client, usuario):
    client.force_login(usuario)
    r = client.post(reverse("eliminar_cuenta"), {})
    assert r.status_code == 200 and Usuario.objects.filter(pk=usuario.pk).exists()


def test_eliminar_requiere_sesion(client, db):
    r = client.get(reverse("eliminar_cuenta"))
    assert r.status_code == 302 and r.url.startswith(reverse("login"))


def test_el_perfil_ofrece_eliminar_la_cuenta(client, usuario):
    guardar_perfil_desde_cv(usuario, pdf_cv())
    client.force_login(usuario)
    assert reverse("eliminar_cuenta") in client.get(reverse("perfil")).content.decode()
