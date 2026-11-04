"""El correo invita a entrar a Scoutly: cuenta cuántas vacantes hay, muestra pocas y lleva a la página (no las lista)."""

from django.core import mail

from cuentas.models import Perfil
from notificaciones.services import generar_notificaciones
from notificaciones.tests.test_generar import _decision, perfil  # noqa: F401 (fixture)
from vacantes.models import Vacante

SITIO = "https://scoutly.ejemplo.co"


def _html(correo) -> str:
    return next(contenido for contenido, tipo in correo.alternatives if tipo == "text/html")


def _enviar(perfil, n, settings):
    settings.SCOUTLY_URL_SITIO = SITIO
    for i in range(n):
        _decision(perfil, i)
    generar_notificaciones()
    return mail.outbox[-1]


def test_el_resumen_no_lista_todas_las_vacantes(perfil, settings):
    correo = _enviar(perfil, 8, settings)
    html = _html(correo)
    assert sum(f"Cargo {i}<" in html for i in range(8)) == 3
    assert sum(f"Cargo {i}" in correo.body for i in range(8)) == 3
    assert "8 vacantes nuevas" in correo.subject and ">8<" in html


def test_el_resumen_lleva_a_la_pagina_con_un_enlace_absoluto(perfil, settings):
    correo = _enviar(perfil, 2, settings)
    assert f'href="{SITIO}/notificaciones"' in _html(correo) and f"{SITIO}/notificaciones" in correo.body


def test_el_correo_dice_como_cambiar_los_avisos(perfil, settings):
    correo = _enviar(perfil, 1, settings)
    assert f'href="{SITIO}/expectativas"' in _html(correo) and f"{SITIO}/expectativas" in correo.body


def test_una_sola_vacante_se_nombra_en_singular(perfil, settings):
    correo = _enviar(perfil, 1, settings)
    assert "1 vacante nueva" in correo.subject and "1 vacantes" not in correo.subject + correo.body + _html(correo)


def test_el_asunto_usa_el_primer_nombre(perfil, settings):
    perfil.nombre = "Laura Gómez Ríos"
    perfil.save()
    assert _enviar(perfil, 2, settings).subject.startswith("Laura, ")


def test_sin_nombre_el_correo_sigue_saliendo(perfil, settings):
    perfil.nombre = None
    perfil.save()
    correo = _enviar(perfil, 2, settings)
    assert correo.subject.startswith("2 vacantes") and "None" not in correo.body + _html(correo)


def test_un_titulo_scrapeado_no_inyecta_html(perfil, settings):
    settings.SCOUTLY_URL_SITIO = SITIO
    _decision(perfil, 1)
    Vacante.objects.filter(id="v1").update(titulo='<img src=x onerror="alert(1)">')
    generar_notificaciones()
    assert "<img" not in _html(mail.outbox[-1])


def test_el_aviso_individual_lleva_al_detalle_de_la_vacante(perfil, settings):
    perfil.notif_modo = Perfil.ModoNotificacion.INDIVIDUAL
    perfil.save()
    correo = _enviar(perfil, 1, settings)
    assert f'href="{SITIO}/vacantes/v0"' in _html(correo) and f"{SITIO}/vacantes/v0" in correo.body
    assert "Cargo 0" in correo.subject


def test_una_url_con_barra_final_no_duplica_la_barra(perfil, settings):
    settings.SCOUTLY_URL_SITIO = SITIO
    correo = _enviar(perfil, 1, settings)
    settings.SCOUTLY_URL_SITIO = SITIO + "/"
    _decision(perfil, 9)
    Perfil.objects.filter(pk=perfil.pk).update(notif_modo=Perfil.ModoNotificacion.INDIVIDUAL)
    generar_notificaciones()
    assert correo and f"{SITIO}//" not in _html(mail.outbox[-1])
