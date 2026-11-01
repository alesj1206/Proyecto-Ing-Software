import pytest
from django.urls import reverse

from cuentas.forms import RegistroClaveForm
from cuentas.models import Usuario
from cuentas.services import crear_usuario_con_autorizacion, guardar_perfil_desde_cv
from conftest import CLAVE_DE_PRUEBA

from .cvs import pdf_cv

DATOS_REGISTRO = {"paso": "datos", "email": "n@e.com", "email_confirmacion": "n@e.com",
                  "autoriza_datos": "on", "acepta_terminos": "on"}


def _login(client, email, password):
    client.post(reverse("login"), {"paso": "correo", "email": email})
    return client.post(reverse("login"), {"paso": "clave", "password": password})


# --- login en dos pasos ----------------------------------------------------------------------------

def test_login_paso1_siempre_pide_contrasena(client, db):
    r = client.post(reverse("login"), {"paso": "correo", "email": "nadie@ejemplo.com"})
    assert 'name="password"' in r.content.decode()


def test_login_correcto_con_mayusculas_y_espacios(client, usuario):
    r = _login(client, " Ana@Ejemplo.com ", CLAVE_DE_PRUEBA)
    assert r.status_code == 302 and "_auth_user_id" in client.session


def test_login_sin_cv_va_a_onboarding_y_con_cv_al_dashboard(client, usuario):
    assert _login(client, "ana@ejemplo.com", CLAVE_DE_PRUEBA).url == reverse("onboarding")
    client.logout()
    guardar_perfil_desde_cv(usuario, pdf_cv())
    assert _login(client, "ana@ejemplo.com", CLAVE_DE_PRUEBA).url == reverse("dashboard")


def test_login_incorrecto_mensaje_generico(client, usuario):
    r = _login(client, "ana@ejemplo.com", "otra")
    assert "Correo electrónico o contraseña incorrectos" in r.content.decode()
    assert "_auth_user_id" not in client.session


def test_login_paso2_sin_paso1_vuelve_al_inicio(client, usuario):
    r = client.post(reverse("login"), {"paso": "clave", "password": CLAVE_DE_PRUEBA})
    assert r.status_code == 302 and r.url == reverse("login")


def test_login_de_cuenta_social_sin_contrasena(client, db):
    crear_usuario_con_autorizacion("social@ejemplo.com", None)
    r = _login(client, "social@ejemplo.com", "cualquiera")
    assert "Ingresa con el botón de tu red social" in r.content.decode()


def test_login_no_muestra_estadisticas_inventadas(client, db):
    assert "Precisión del match" not in client.get(reverse("login")).content.decode()


def test_con_sesion_login_redirige(client, usuario):
    client.force_login(usuario)
    assert client.get(reverse("login")).status_code == 302


# --- registro en dos pasos -------------------------------------------------------------------------

def test_registro_exige_las_dos_casillas(client, db):
    datos = {**DATOS_REGISTRO}
    del datos["acepta_terminos"]
    r = client.post(reverse("registro"), datos)
    assert "registro_paso1" not in client.session and r.status_code == 200


def test_registro_correos_distintos(client, db):
    r = client.post(reverse("registro"), {**DATOS_REGISTRO, "email_confirmacion": "m@e.com"})
    assert "Los correos no coinciden" in r.content.decode()


def test_registro_paso2_sin_paso1_vuelve_al_inicio(client, db):
    r = client.post(reverse("registro"), {"paso": "clave", "password1": CLAVE_DE_PRUEBA,
                                          "password2": CLAVE_DE_PRUEBA})
    assert r.status_code == 302 and r.url == reverse("registro")
    assert not Usuario.objects.exists()


def test_registro_completo_crea_usuario_autorizado_y_va_a_onboarding(client, db):
    client.post(reverse("registro"), DATOS_REGISTRO)
    r = client.post(reverse("registro"), {"paso": "clave", "password1": CLAVE_DE_PRUEBA,
                                          "password2": CLAVE_DE_PRUEBA})
    assert r.url == reverse("onboarding")
    assert Usuario.objects.get(email="n@e.com").autorizacion_set.exists()
    assert "registro_paso1" not in client.session


def test_registro_con_correo_existente(client, usuario):
    r = client.post(reverse("registro"), {**DATOS_REGISTRO, "email": "ana@ejemplo.com",
                                          "email_confirmacion": "ana@ejemplo.com"})
    assert "Ya existe una cuenta con ese correo" in r.content.decode()


def test_registro_contrasenas_distintas(client, db):
    client.post(reverse("registro"), DATOS_REGISTRO)
    r = client.post(reverse("registro"), {"paso": "clave", "password1": CLAVE_DE_PRUEBA, "password2": "otra"})
    assert "Las contraseñas no coinciden" in r.content.decode() and not Usuario.objects.exists()


def test_los_errores_de_django_salen_en_espanol(client, db):
    client.post(reverse("registro"), DATOS_REGISTRO)
    r = client.post(reverse("registro"), {"paso": "clave", "password1": "corta", "password2": "corta"})
    assert "contraseña" in r.content.decode().lower() and "This password" not in r.content.decode()


def test_logout_por_post(client, usuario):
    client.force_login(usuario)
    assert client.get(reverse("logout")).status_code == 405
    assert client.post(reverse("logout")).url == reverse("login")


# --- robustez de la contraseña (de v2, commit bcc2550) ---------------------------------------------

def _clave(password, email="ana@example.com"):
    return RegistroClaveForm(email=email, data={"password1": password, "password2": password})


@pytest.mark.parametrize("mala", ["Xk9#pq2", "password123", "83920174619"])
def test_rechaza_contrasenas_debiles(mala, db):
    assert not _clave(mala).is_valid()


def test_rechaza_contrasenas_parecidas_al_correo(db):
    assert not _clave("anaexample", email="anaexample@example.com").is_valid()


def test_acepta_una_contrasena_robusta(db):
    form = _clave("Lienzo-Tardio-73")
    assert form.is_valid(), form.errors
