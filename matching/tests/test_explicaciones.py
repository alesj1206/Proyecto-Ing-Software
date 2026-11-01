import json
from unittest import mock

import pytest
import requests
from django.urls import reverse

from matching.explicaciones import explicar, insumos_publicos
from matching.ia.fakes import RedactorFalso
from matching.ia.groq import RedactorGroq
from matching.models import Decision, ExplicacionDecision

EVIDENCIA = "Usé SQL en reportes de Comercial Andina"


@pytest.fixture
def decision(client_con_cv, usuario, vacante_v1):
    return Decision.objects.create(
        perfil=usuario.perfil, vacante=vacante_v1, accion="AJUSTAR_CV", solidez="media", motivo_solidez="ok",
        motivos=[f"Haz explícito «Power BI» (tu evidencia: «{EVIDENCIA}»)"], similitud=0.8, cobertura_pct=63,
        version_politica="t", restricciones=[{"criterio": "salario", "estado": "cumple", "motivo": "Ofrece hasta $ 3"}],
        cobertura=[{"texto": "Power BI", "tipo": "obligatorio", "origen": "texto", "estado": "parcial",
                    "similitud": 0.45, "evidencia": EVIDENCIA}])


def test_a_groq_nunca_va_la_evidencia_ni_el_nombre(decision, usuario):
    redactor = RedactorFalso()
    explicar(decision, redactor)
    enviado = json.dumps(redactor.recibido, ensure_ascii=False)
    assert EVIDENCIA not in enviado and "Comercial Andina" not in enviado
    assert usuario.email not in enviado and (usuario.perfil.nombre or "@@") not in enviado
    assert "Power BI" in enviado  # el requisito (público) sí va


def test_se_cachea_y_no_se_repite_la_llamada(decision):
    redactor = RedactorFalso()
    primero = explicar(decision, redactor)
    assert explicar(decision, redactor) == primero and redactor.llamadas == 1


def test_si_cambian_los_insumos_se_regenera(decision):
    redactor = RedactorFalso()
    explicar(decision, redactor)
    decision.cobertura_pct = 80
    decision.save()
    explicar(decision, redactor)
    assert redactor.llamadas == 2


def test_groq_caido_usa_el_respaldo_y_no_lo_cachea(decision):
    texto = explicar(decision, RedactorFalso(falla=True))
    assert "Haz explícito «Power BI»" in texto and not ExplicacionDecision.objects.exists()


def test_sin_redactor_usa_el_respaldo(decision):
    assert "Haz explícito" in explicar(decision, None)


def test_groq_lento_respeta_el_timeout(decision):
    with mock.patch("matching.ia.groq.requests.post", side_effect=requests.Timeout) as post:
        assert RedactorGroq("clave").redactar(insumos_publicos(decision)) is None
    assert post.call_args.kwargs["timeout"] == 8


def test_la_explicacion_requiere_sesion_y_decision_propia(client, decision, django_user_model):
    url = reverse("explicacion", args=["v1"])
    client.logout()  # el fixture `decision` dejó a este mismo cliente con sesión
    assert client.get(url).status_code == 302
    otro = django_user_model.objects.create_user(email="otro@ejemplo.com", password="Lienzo-Tardio-73")
    client.force_login(otro)
    assert client.get(url).status_code == 404


def test_el_detalle_ofrece_explicamelo(client_con_cv, decision):
    html = client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode()
    assert "Explícamelo" in html and reverse("explicacion", args=["v1"]) in html
