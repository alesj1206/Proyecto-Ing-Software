import importlib

import pytest
from django.urls import reverse

from notificaciones.models import Notificacion
from postulaciones.models import Postulacion


@pytest.mark.parametrize("ruta,args", [("dashboard", []), ("historial", []), ("tablero", []),
                                        ("notificaciones", []), ("vacante_detalle", ["v1"])])
def test_cada_pagina_renderiza_con_sesion_y_cv(client_con_cv, vacante_v1, ruta, args):
    assert client_con_cv.get(reverse(ruta, args=args)).status_code == 200


@pytest.mark.parametrize("ruta", ["dashboard", "historial", "tablero", "notificaciones"])
def test_las_paginas_privadas_piden_sesion(client, db, ruta):
    assert client.get(reverse(ruta)).status_code == 302


def test_el_detalle_es_publico_y_muestra_los_requisitos(client, vacante_v1):
    html = client.get(reverse("vacante_detalle", args=["v1"])).content.decode()
    assert "Analista de Datos Junior" in html and "SQL" in html


def test_el_dashboard_lista_el_catalogo_y_filtra_por_modalidad(client_con_cv, vacante_v1):
    assert "Analista de Datos Junior" in client_con_cv.get(reverse("dashboard")).content.decode()
    assert "Analista de Datos Junior" not in client_con_cv.get(reverse("dashboard") + "?modalidad=Remoto").content.decode()


def test_postular_crea_postulacion_y_aparece_en_tablero(client_con_cv, vacante_v1):
    client_con_cv.post(reverse("postularme", args=["v1"]))
    client_con_cv.post(reverse("postularme", args=["v1"]))  # idempotente
    assert Postulacion.objects.count() == 1
    assert vacante_v1.titulo in client_con_cv.get(reverse("tablero")).content.decode()


def test_mover_tarjeta_del_tablero(client_con_cv, vacante_v1):
    client_con_cv.post(reverse("postularme", args=["v1"]))
    p = Postulacion.objects.get()
    client_con_cv.post(reverse("cambiar_estado_postulacion", args=[p.id]), {"estado": "entrevista"})
    p.refresh_from_db()
    assert p.estado == "entrevista"


def test_no_se_puede_mover_la_tarjeta_de_otro(client, client_con_cv, vacante_v1, django_user_model):
    client_con_cv.post(reverse("postularme", args=["v1"]))
    p = Postulacion.objects.get()
    otro = django_user_model.objects.create_user(email="otro@ejemplo.com", password="Lienzo-Tardio-73")
    client_con_cv.force_login(otro)
    assert client_con_cv.post(reverse("cambiar_estado_postulacion", args=[p.id]), {"estado": "entrevista"}).status_code == 404


def test_abrir_notificaciones_las_marca_leidas_y_baja_la_campana(client_con_cv, vacante_v1, usuario):
    Notificacion.objects.create(perfil=usuario.perfil, vacante=vacante_v1, score_pct=80, mensaje="Nueva", fecha="2026-11-01")
    assert 'campana-contador">1<' in client_con_cv.get(reverse("perfil")).content.decode()
    client_con_cv.get(reverse("notificaciones"))
    assert not Notificacion.objects.filter(leida=False).exists()


def test_ya_no_quedan_rutas_pendientes():
    assert not hasattr(importlib.import_module("scoutly.views"), "pendiente")
