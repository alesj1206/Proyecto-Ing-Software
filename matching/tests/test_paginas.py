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


# --- Fase 2: pantallas del decisor ------------------------------------------------------------------

import difflib
import subprocess
from datetime import timedelta

from django.utils import timezone

from matching.models import Decision, FotoDiaria
from matching.services import solicitar_decision

LINEAS_V2_QUE_CAMBIAN = {  # cambios acordados (ledger Task 8 y 9); todo lo demás de v2 se conserva
    '{% block title %}Matches de hoy | Scoutly{% endblock %}',
    '<p class="label-eyebrow">Matches de hoy</p>',
    '<h2 style="font-size:1.25rem;color:var(--navy);">Matches de hoy</h2>',
    '<p style="margin-top:1rem;color:var(--muted-foreground);">Todavía no hay vacantes que coincidan con tus habilidades registradas.</p>',
    '<span class="criterio-peso">peso {{ c.peso_pct }}%</span>',
    '5 criterios, cada uno con su propio peso. Toca "¿Por qué?" para el detalle.',
}


def _decidir(perfil, vacante, accion="POSTULAR", **extra):
    datos = dict(perfil=perfil, vacante=vacante, accion=accion, solidez="alta", motivo_solidez="Datos completos",
                 motivos=["Cubres 1/2 obligatorios"], similitud=0.8, cobertura_pct=75, orden=0.6, version_politica="t",
                 cobertura=[{"texto": "SQL", "tipo": "obligatorio", "origen": "texto", "estado": "cubierto",
                             "similitud": 0.7, "evidencia": "Usé SQL en reportes"},
                            {"texto": "Power BI", "tipo": "obligatorio", "origen": "texto", "estado": "parcial",
                             "similitud": 0.45, "evidencia": "Hice tableros en Excel"},
                            {"texto": "Docker", "tipo": "obligatorio", "origen": "texto", "estado": "faltante",
                             "similitud": 0.1, "evidencia": None}],
                 restricciones=[{"criterio": "salario", "estado": "sin_datos", "motivo": "La vacante no dice el salario"}])
    datos.update(extra)
    return Decision.objects.create(**datos)


def test_dashboard_muestra_plan_de_hoy_con_insignia_y_solidez(client_con_cv, usuario, vacante_v1):
    _decidir(usuario.perfil, vacante_v1)
    html = client_con_cv.get(reverse("dashboard")).content.decode()
    assert "Tu plan de hoy" in html and "Postular · solidez alta" in html and "Cubres 1/2 obligatorios" in html


def test_dashboard_agrupa_por_accion(client_con_cv, usuario, vacante_v1):
    _decidir(usuario.perfil, vacante_v1, accion="CERRAR_BRECHA")
    html = client_con_cv.get(reverse("dashboard")).content.decode()
    assert "Tus vacantes por acción" in html and "Cerrar brecha (1)" in html


def test_dashboard_muestra_plan_de_aprendizaje(client_con_cv, usuario, vacante_v1):
    _decidir(usuario.perfil, vacante_v1, accion="CERRAR_BRECHA")
    assert "Docker aparece en 1 de tus vacantes relevantes" in client_con_cv.get(reverse("dashboard")).content.decode()


def test_dashboard_pendiente_muestra_aviso_de_analisis(client_con_cv, usuario, vacante_v1):
    solicitar_decision(usuario.perfil)
    assert "Estamos analizando tu hoja de vida" in client_con_cv.get(reverse("dashboard")).content.decode()


def test_dashboard_sin_relevantes_explica_por_que(client_con_cv, usuario, vacante_v1):
    from matching.models import SolicitudDecision

    SolicitudDecision.objects.all().delete()
    html = client_con_cv.get(reverse("dashboard")).content.decode()
    assert "No encontramos vacantes relevantes para tu perfil todavía" in html


def test_detalle_muestra_requisitos_con_evidencia(client_con_cv, usuario, vacante_v1):
    _decidir(usuario.perfil, vacante_v1, accion="AJUSTAR_CV", con_nota="")
    html = client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode()
    assert "Ajustar CV · solidez alta" in html and "tu evidencia: «Hice tableros en Excel»" in html
    assert "Usé SQL en reportes" in html and "peso" not in html


def test_detalle_habilita_postularme_con_decision(client_con_cv, usuario, vacante_v1):
    _decidir(usuario.perfil, vacante_v1)
    html = client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode()
    assert 'action="/vacantes/v1/postularme"' in html


def test_historial_muestra_el_ranking_de_la_foto(client_con_cv, usuario, vacante_v1):
    FotoDiaria.objects.create(perfil=usuario.perfil, fecha=timezone.localdate(), conteos={"POSTULAR": 1},
                              top={"POSTULAR": [{"vacante_id": "v1", "cobertura_pct": 75, "orden": 0.6}]})
    html = client_con_cv.get(reverse("historial")).content.decode()
    assert "Analista de Datos Junior" in html and "75%" in html


@pytest.mark.parametrize("plantilla", ["dashboard", "detalle", "historial"])
def test_los_templates_solo_agregan_lineas_a_v2(plantilla):
    v2 = subprocess.run(["git", "show", f"pre-sprint3-rebuild:vacantes/templates/vacantes/{plantilla}.html"],
                        capture_output=True, text=True, check=True).stdout.splitlines()
    v3 = open(f"matching/templates/matching/{plantilla}.html", encoding="utf-8").read().splitlines()
    borradas = {l[1:].strip() for l in difflib.unified_diff(v2, v3, lineterm="", n=0)
                if l.startswith("-") and not l.startswith("---")}
    assert borradas <= LINEAS_V2_QUE_CAMBIAN, borradas - LINEAS_V2_QUE_CAMBIAN
