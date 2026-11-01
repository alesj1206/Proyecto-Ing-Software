from django.test import TestCase

from .forms import RegistroForm


def registro(password, email="ana@example.com"):
    return RegistroForm(data={"email": email, "password": password})


class ContrasenaTests(TestCase):
    def test_rechaza_menos_de_8_caracteres(self):
        self.assertFalse(registro("Xk9#pq2").is_valid())

    def test_rechaza_contrasenas_comunes(self):
        self.assertFalse(registro("password123").is_valid())

    def test_rechaza_contrasenas_solo_numericas(self):
        self.assertFalse(registro("83920174619").is_valid())

    def test_rechaza_contrasenas_parecidas_al_correo(self):
        self.assertFalse(registro("anaexample", email="anaexample@example.com").is_valid())

    def test_acepta_una_contrasena_robusta(self):
        form = registro("Lienzo-Tardio-73")
        self.assertTrue(form.is_valid(), form.errors)
