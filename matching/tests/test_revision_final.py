"""Regresiones de la revisión final de la Fase 2 (cada test reproduce un hallazgo antes del arreglo)."""

from datetime import timedelta
from types import SimpleNamespace as N

import numpy as np
import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from matching.cobertura import Cobertura, RequisitoEvaluado, es_blando
from matching.models import Decision, FotoDiaria, SolicitudDecision
from matching.politica import POLITICA, Accion, ContextoDecision, Politica, decidir
from matching.restricciones import RestriccionUbicacion
from matching.services import NUEVA, decidir_para_perfil, solicitar_decision
from matching.vectores import embeber_vacantes
from vacantes.models import Vacante
from vacantes.services import ingerir
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

from .test_decidir import M, TODAS, VACANTES, _perfil, catalogo  # noqa: F401 (fixture)


# 1. vacante modificada después de embeberse -------------------------------------------------------------

def test_vacante_cambiada_sin_reembeber_no_entra_al_decisor(usuario, catalogo):
    perfil = _perfil(usuario)
    ingerir(FuenteEnMemoria([cruda("vpost", VACANTES["vpost"] + "\n- Docker Kubernetes\n- Python Django")]))
    decidir_para_perfil(perfil, M, politica=TODAS)
    assert not Decision.objects.filter(perfil=perfil, vacante_id="vpost").exists()


# 2. ubicación de relleno -----------------------------------------------------------------------------

@pytest.mark.parametrize("ubicacion", ["", "Colombia"])
def test_vacante_sin_ubicacion_es_sin_datos(ubicacion):
    r = RestriccionUbicacion().evaluar(N(exp_ubicacion="Bogotá"),
                                       N(modalidad="Presencial", modalidad_inferida=False, ubicacion=ubicacion), POLITICA)
    assert r.estado == "sin_datos"


def test_la_ingesta_no_inventa_colombia(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel", ubicacion="")]))
    assert Vacante.objects.get(id="v1").ubicacion == ""


# 3. solicitud hecha mientras se decide ----------------------------------------------------------------

def test_una_solicitud_durante_la_decision_no_se_pierde(usuario, catalogo, monkeypatch):
    import matching.services as servicios

    perfil = _perfil(usuario)
    solicitar_decision(perfil)
    original = servicios.preseleccionar

    def y_el_usuario_cambia_algo(*a, **k):
        resultado = original(*a, **k)
        SolicitudDecision.objects.filter(perfil=perfil).update(creada_en=timezone.now() + timedelta(seconds=1))
        return resultado

    monkeypatch.setattr(servicios, "preseleccionar", y_el_usuario_cambia_algo)
    decidir_para_perfil(perfil, M, politica=TODAS)
    assert SolicitudDecision.objects.filter(perfil=perfil).exists()


def test_solicitar_de_nuevo_refresca_la_fecha(usuario):
    perfil = _perfil(usuario)
    solicitar_decision(perfil)
    antes = SolicitudDecision.objects.get(perfil=perfil).creada_en
    solicitar_decision(perfil)
    assert SolicitudDecision.objects.get(perfil=perfil).creada_en > antes


# 4. falsas competencias blandas ---------------------------------------------------------------------

@pytest.mark.parametrize("texto", ["Conocimientos en aprendizaje automático", "Experiencia en medicina estética",
                                   "Manejo de títulos valores", "Liderazgo técnico de equipos de desarrollo"])
def test_requisitos_tecnicos_que_parecen_blandos(texto):
    assert not es_blando(texto)


# 5. cero obligatorios comparables -----------------------------------------------------------------

def test_sin_obligatorios_comparables_es_sin_datos():
    reqs = [RequisitoEvaluado("Técnico en logística", "obligatorio", "texto", "formacion", 0.5, None),
            RequisitoEvaluado("Trabajo en equipo", "obligatorio", "texto", "blando", 0.2, None),
            RequisitoEvaluado("Disponibilidad", "obligatorio", "texto", "blando", 0.2, None)]
    ctx = ContextoDecision(Cobertura(reqs), [], [N(origen="texto")] * 3, POLITICA)
    assert decidir(ctx).accion == Accion.SIN_DATOS


# 6 y 7. dashboard ------------------------------------------------------------------------------------

def test_ocultas_por_modalidad_se_guarda_en_la_foto(usuario, catalogo):
    Vacante.objects.filter(id="vpost").update(modalidad="Presencial", modalidad_inferida=False)
    perfil = _perfil(usuario, exp_modalidad="Remoto")
    decidir_para_perfil(perfil, M, politica=TODAS)
    assert FotoDiaria.objects.get(perfil=perfil).ocultas_por_modalidad >= 1


def test_el_dashboard_no_repite_la_busqueda_vectorial(client, usuario, catalogo, monkeypatch):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, M, politica=TODAS)
    monkeypatch.setattr("matching.preseleccion.preseleccionar", lambda *a, **k: pytest.fail("búsqueda en la web"))
    client.force_login(usuario)
    assert client.get(reverse("dashboard")).status_code == 200


def test_el_dashboard_limita_cada_grupo(client, usuario, db):
    from matching.selectors import MAX_POR_GRUPO

    ingerir(FuenteEnMemoria([cruda(f"v{i:02d}", VACANTES["vdesc"]) for i in range(MAX_POR_GRUPO + 5)]))
    embeber_vacantes(M)
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, M, politica=TODAS)
    client.force_login(usuario)
    html = client.get(reverse("dashboard")).content.decode()
    assert f"y 5 más" in html


def test_sin_plan_pero_con_decisiones_no_dice_que_no_hay_relevantes(client, usuario, catalogo):
    perfil = _perfil(usuario, evidencia=["Reportes de ventas en Excel"])
    decidir_para_perfil(perfil, M, politica=TODAS)
    Decision.objects.filter(perfil=perfil, accion__in=["POSTULAR", "AJUSTAR_CV"]).delete()
    client.force_login(usuario)
    html = client.get(reverse("dashboard")).content.decode()
    assert "No encontramos vacantes relevantes" not in html and "Hoy no hay vacantes para postular ya" in html


# 8. accion_anterior ----------------------------------------------------------------------------------

def test_accion_anterior_distingue_nueva_de_sin_cambios(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, M, politica=TODAS)
    primera = Decision.objects.get(perfil=perfil, vacante_id="vpost")
    assert primera.accion_anterior == NUEVA and primera.cambio_en is not None
    decidir_para_perfil(perfil, M, politica=TODAS)
    segunda = Decision.objects.get(perfil=perfil, vacante_id="vpost")
    assert segunda.accion_anterior == "POSTULAR" and segunda.cambio_en == primera.cambio_en


# seguridad M1. un perfil que falla no tumba el batch ----------------------------------------------------

def test_un_perfil_que_falla_no_tumba_el_batch(usuario, django_user_model, catalogo, monkeypatch):
    import matching.management.commands.decidir as comando

    malo = _perfil(usuario)
    otro = django_user_model.objects.create_user(email="otro@ejemplo.com", password="Lienzo-Tardio-73")
    bueno = _perfil(otro)
    solicitar_decision(malo), solicitar_decision(bueno)
    original = comando.decidir_para_perfil

    def falla_con_malo(perfil, *a, **k):
        if perfil.pk == malo.pk:
            raise ValueError("CV raro")
        return original(perfil, *a, **k)

    monkeypatch.setattr(comando, "decidir_para_perfil", falla_con_malo)
    call_command("decidir", "--pendientes")
    assert Decision.objects.filter(perfil=bueno).exists()
    assert SolicitudDecision.objects.get(perfil=malo).intentos == 1


# 9. evaluación ---------------------------------------------------------------------------------------

def test_el_informe_trae_la_linea_base_de_la_clase_mayoritaria(db):
    from matching.evaluacion.evaluar import Informe

    informe = Informe(total=4, confusion={("DESCARTAR", "DESCARTAR"): 3, ("POSTULAR", "DESCARTAR"): 1})
    assert informe.exactitud_mayoritaria == 0.75
