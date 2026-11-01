import pytest
from django.urls import reverse

from cuentas.models import EvidenciaPerfil
from matching.models import Decision, SugerenciaCV
from matching.taller import generar_sugerencias, responder, taller, texto_adaptado


def _req(texto, estado, evidencia=None, tipo="obligatorio"):
    return {"texto": texto, "tipo": tipo, "origen": "texto", "estado": estado, "similitud": 0.45, "evidencia": evidencia}


COBERTURA = [_req("SQL", "cubierto", "Usé SQL en reportes"), _req("Excel", "cubierto", "Reportes en Excel"),
             _req("Power BI", "parcial", "Hice tableros en Excel."), _req("Docker", "faltante")]


@pytest.fixture
def decision(client_con_cv, usuario, vacante_v1):
    perfil = usuario.perfil
    perfil.evidencias.all().delete()
    for i, t in enumerate(["Usé SQL en reportes", "Reportes en Excel", "Hice tableros en Excel."]):
        EvidenciaPerfil.objects.create(perfil=perfil, texto=t, seccion="experiencia", posicion=i)
    return Decision.objects.create(perfil=perfil, vacante=vacante_v1, accion="AJUSTAR_CV", solidez="media",
                                   motivo_solidez="ok", motivos=["Haz explícito «Power BI»"], similitud=0.8,
                                   cobertura_pct=63, version_politica="t", cobertura=COBERTURA, restricciones=[])


def test_sugerencia_por_requisito_parcial_con_su_evidencia(decision):
    [s] = [s for s in generar_sugerencias(decision, ["Hice tableros en Excel."]) if s.tipo == "requisito"]
    assert (s.requisito, s.evidencia, s.propuesta) == ("Power BI", "Hice tableros en Excel.",
                                                       "Hice tableros en Excel (Power BI).")


def test_sin_evidencia_no_hay_sugerencia(decision):
    assert not any(s.requisito == "Docker" for s in generar_sugerencias(decision, ["Hice tableros en Excel."]))


def test_evidencia_que_ya_no_esta_en_el_cv_no_se_sugiere(decision):
    assert not [s for s in generar_sugerencias(decision, ["Otra cosa"]) if s.tipo == "requisito"]


def test_resumen_solo_con_requisitos_cubiertos(decision):
    [r] = [s for s in generar_sugerencias(decision, ["Usé SQL en reportes", "Reportes en Excel"]) if s.tipo == "resumen"]
    assert r.propuesta == "Resumen sugerido: experiencia en SQL y Excel." and "Docker" not in r.propuesta


def test_aceptar_y_rechazar_y_texto_para_copiar(decision, usuario, vacante_v1):
    sugerencias = taller(usuario.perfil, vacante_v1)
    req = next(s for s in sugerencias if s.tipo == "requisito")
    resumen = next(s for s in sugerencias if s.tipo == "resumen")
    responder(req, acepta=True)
    responder(resumen, acepta=False)
    assert texto_adaptado(usuario.perfil, vacante_v1) == "Hice tableros en Excel (Power BI)."
    assert len(taller(usuario.perfil, vacante_v1)) == 2  # sincronizar no duplica ni borra las respondidas


def test_no_se_puede_responder_la_sugerencia_de_otro(client, decision, usuario, vacante_v1, django_user_model):
    s = taller(usuario.perfil, vacante_v1)[0]
    otro = django_user_model.objects.create_user(email="otro@ejemplo.com", password="Lienzo-Tardio-73")
    client.force_login(otro)
    r = client.post(reverse("taller_responder", args=["v1", s.id]), {"acepta": "1"})
    assert r.status_code == 404 and SugerenciaCV.objects.get(id=s.id).estado == "pendiente"


def test_la_pagina_avisa_que_el_cv_debe_ser_verdadero(client_con_cv, decision):
    html = client_con_cv.get(reverse("taller", args=["v1"])).content.decode()
    assert "Solo acepta lo que sea verdad" in html and "tu evidencia: «Hice tableros en Excel.»" in html


def test_responder_desde_la_pagina(client_con_cv, decision, usuario, vacante_v1):
    s = next(s for s in taller(usuario.perfil, vacante_v1) if s.tipo == "requisito")
    client_con_cv.post(reverse("taller_responder", args=["v1", s.id]), {"acepta": "1"})
    assert "Hice tableros en Excel (Power BI)." in client_con_cv.get(reverse("taller", args=["v1"])).content.decode()


def test_el_detalle_ofrece_el_taller_solo_en_ajustar_cv(client_con_cv, decision):
    url = reverse("taller", args=["v1"])
    assert url in client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode()
    Decision.objects.filter(id=decision.id).update(accion="POSTULAR")
    assert url not in client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode()


def test_sin_decision_el_taller_es_404(client_con_cv, vacante_v1):
    assert client_con_cv.get(reverse("taller", args=["v1"])).status_code == 404


# --- revisión final de la Fase 3 -----------------------------------------------------------------------

def test_el_resumen_no_cita_cubiertos_cuya_evidencia_ya_no_esta(decision, usuario, vacante_v1):
    sugerencias = generar_sugerencias(decision, ["Hice tableros en Excel."])  # el CV ya no tiene SQL ni Excel
    assert not [s for s in sugerencias if s.tipo == "resumen"]


def test_el_texto_para_copiar_no_lleva_evidencia_que_ya_no_esta(decision, usuario, vacante_v1):
    s = next(s for s in taller(usuario.perfil, vacante_v1) if s.tipo == "requisito")
    responder(s, acepta=True)
    usuario.perfil.evidencias.filter(texto="Hice tableros en Excel.").delete()
    assert texto_adaptado(usuario.perfil, vacante_v1) == ""
