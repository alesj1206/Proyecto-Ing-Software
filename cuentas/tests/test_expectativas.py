from django.urls import reverse

from cuentas.models import Perfil


def test_guarda_expectativas(client, usuario):
    client.force_login(usuario)
    r = client.post(reverse("expectativas"), {"exp_modalidad": "Remoto", "exp_salario_min": 3000000})
    assert r.status_code == 302 and r.url == reverse("expectativas")
    perfil = Perfil.objects.get(usuario=usuario)
    assert (perfil.exp_modalidad, perfil.exp_salario_min) == ("Remoto", 3000000)


def test_expectativas_sin_cv_crea_perfil_vacio(client, usuario):
    client.force_login(usuario)
    assert client.get(reverse("expectativas")).status_code == 200
    assert not Perfil.objects.get(usuario=usuario).tiene_cv()


def test_salario_negativo_no_se_guarda(client, usuario):
    client.force_login(usuario)
    r = client.post(reverse("expectativas"), {"exp_salario_min": -5})
    assert r.status_code == 200 and Perfil.objects.get(usuario=usuario).exp_salario_min is None
