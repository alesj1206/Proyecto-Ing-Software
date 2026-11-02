"""La web sirve sus estáticos sin DEBUG ni --insecure (whitenoise), como en producción."""

from django.test import Client


def test_el_css_se_sirve_sin_debug(settings):
    assert settings.DEBUG is False
    respuesta = Client().get("/static/css/scoutly.css")
    assert respuesta.status_code == 200 and b"".join(respuesta.streaming_content)
