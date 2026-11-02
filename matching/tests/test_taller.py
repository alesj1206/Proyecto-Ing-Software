import pytest
from django.urls import reverse

from cuentas.models import EvidenciaPerfil
from matching.models import Decision, SugerenciaCV
from matching.taller import generar_sugerencias, responder, taller, texto_adaptado


def _req(texto, estado, evidencia=None, tipo="obligatorio"):
    return {"texto": texto, "tipo": tipo, "origen": "texto", "estado": estado, "similitud": 0.45, "evidencia": evidencia}


COBERTURA = [_req("SQL", "cubierto", "Usé SQL en reportes"), _req("Excel", "cubierto", "Reportes en Excel"),
             _req("Power BI", "parcial", "Hice tableros en Excel."), _req("Docker", "faltante", tipo="deseable")]


@pytest.fixture
def decision(client_con_cv, usuario, vacante_v1):
    perfil = usuario.perfil
    perfil.evidencias.all().delete()
    for i, t in enumerate(["Usé SQL en reportes", "Reportes en Excel", "Hice tableros en Excel."]):
        EvidenciaPerfil.objects.create(perfil=perfil, texto=t, seccion="experiencia", posicion=i)
    return Decision.objects.create(perfil=perfil, vacante=vacante_v1, accion="AJUSTAR_CV", solidez="media",
                                   motivo_solidez="ok", motivos=["Haz explícito «Power BI»"], similitud=0.8,
                                   cobertura_pct=63, version_politica="t", cobertura=COBERTURA, restricciones=[])


def test_la_sugerencia_es_una_pregunta_con_la_evidencia_como_pista(decision):
    [s] = generar_sugerencias(decision, ["Hice tableros en Excel."])
    assert (s.requisito, s.evidencia) == ("Power BI", "Hice tableros en Excel.")
    assert s.propuesta == "¿Has trabajado con «Power BI»? Si es así, cuéntalo con tus palabras."


def test_un_deseable_faltante_no_se_pregunta(decision):
    assert not any(s.requisito == "Docker" for s in generar_sugerencias(decision, ["Hice tableros en Excel."]))


def test_un_obligatorio_faltante_se_pregunta_sin_pista(decision):
    """Con mpnet y τ_alto = τ_bajo no hay parciales: el Taller pregunta por lo que falta, que a veces es algo que la
    persona hizo y no escribió (decisión del usuario, 2026-11-02)."""
    decision.cobertura = [_req("SQL", "cubierto", "Usé SQL en reportes"), _req("Tableau", "faltante")]
    [s] = generar_sugerencias(decision, ["Usé SQL en reportes"])
    assert (s.requisito, s.evidencia) == ("Tableau", "")
    assert s.propuesta == "¿Has trabajado con «Tableau»? Si es así, cuéntalo con tus palabras."


def test_formacion_y_anios_faltantes_no_se_preguntan(decision):
    decision.cobertura = [_req("Profesional en contaduría", "formacion"), _req("2 años de experiencia", "experiencia"),
                          _req("Trabajo en equipo", "blando")]
    assert generar_sugerencias(decision, []) == []


def test_evidencia_que_ya_no_esta_en_el_cv_no_se_sugiere(decision):
    assert not [s for s in generar_sugerencias(decision, ["Otra cosa"]) if s.tipo == "requisito"]


def test_no_genera_texto_de_resumen(decision):
    assert not [s for s in generar_sugerencias(decision, ["Usé SQL en reportes", "Reportes en Excel"])
                if s.tipo == "resumen"]


def test_el_texto_para_copiar_son_las_palabras_del_candidato(decision, usuario, vacante_v1):
    [s] = taller(usuario.perfil, vacante_v1)
    responder(s, acepta=True, respuesta="  Construí tableros en Power BI para el área de ventas. ")
    assert texto_adaptado(usuario.perfil, vacante_v1) == "Construí tableros en Power BI para el área de ventas."
    assert len(taller(usuario.perfil, vacante_v1)) == 1  # sincronizar no duplica ni borra las respondidas


def test_aceptar_sin_escribir_nada_no_cuenta(decision, usuario, vacante_v1):
    [s] = taller(usuario.perfil, vacante_v1)
    with pytest.raises(ValueError):
        responder(s, acepta=True, respuesta="   ")
    assert SugerenciaCV.objects.get(id=s.id).estado == "pendiente"


def test_no_se_puede_responder_la_sugerencia_de_otro(client, decision, usuario, vacante_v1, django_user_model):
    s = taller(usuario.perfil, vacante_v1)[0]
    otro = django_user_model.objects.create_user(email="otro@ejemplo.com", password="Lienzo-Tardio-73")
    client.force_login(otro)
    r = client.post(reverse("taller_responder", args=["v1", s.id]), {"acepta": "1"})
    assert r.status_code == 404 and SugerenciaCV.objects.get(id=s.id).estado == "pendiente"


def test_la_pagina_avisa_que_el_cv_debe_ser_verdadero(client_con_cv, decision):
    html = client_con_cv.get(reverse("taller", args=["v1"])).content.decode()
    assert "Escribe solo lo que sea verdad" in html and "Pista: en tu hoja de vida dice «Hice tableros en Excel.»" in html


def test_responder_desde_la_pagina(client_con_cv, decision, usuario, vacante_v1):
    [s] = taller(usuario.perfil, vacante_v1)
    client_con_cv.post(reverse("taller_responder", args=["v1", s.id]), {"acepta": "1", "respuesta": "Usé Power BI a diario"})
    assert "Usé Power BI a diario" in client_con_cv.get(reverse("taller", args=["v1"])).content.decode()


def test_aceptar_sin_texto_desde_la_pagina_avisa(client_con_cv, decision, usuario, vacante_v1):
    [s] = taller(usuario.perfil, vacante_v1)
    r = client_con_cv.post(reverse("taller_responder", args=["v1", s.id]), {"acepta": "1", "respuesta": ""}, follow=True)
    assert "Escribe con tus palabras" in r.content.decode() and SugerenciaCV.objects.get(id=s.id).estado == "pendiente"


def test_el_detalle_ofrece_el_taller_si_hay_algo_que_preguntar(client_con_cv, decision):
    url = reverse("taller", args=["v1"])
    for accion in ("AJUSTAR_CV", "POSTULAR", "CERRAR_BRECHA"):
        Decision.objects.filter(id=decision.id).update(accion=accion)
        assert url in client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode(), accion
    Decision.objects.filter(id=decision.id).update(accion="DESCARTAR")
    assert url not in client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode()
    Decision.objects.filter(id=decision.id).update(accion="POSTULAR", cobertura=COBERTURA[:2])  # todo cubierto
    assert url not in client_con_cv.get(reverse("vacante_detalle", args=["v1"])).content.decode()


def test_la_pregunta_por_un_faltante_no_muestra_pista(client_con_cv, decision):
    Decision.objects.filter(id=decision.id).update(cobertura=[_req("Tableau", "faltante")])
    html = client_con_cv.get(reverse("taller", args=["v1"])).content.decode()
    assert "Esta vacante pide: Tableau" in html and "Pista:" not in html


def test_sin_decision_el_taller_es_404(client_con_cv, vacante_v1):
    assert client_con_cv.get(reverse("taller", args=["v1"])).status_code == 404


# --- revisión final de la Fase 3 -----------------------------------------------------------------------

def test_el_texto_para_copiar_no_lleva_evidencia_que_ya_no_esta(decision, usuario, vacante_v1):
    [s] = taller(usuario.perfil, vacante_v1)
    responder(s, acepta=True, respuesta="Usé Power BI")
    usuario.perfil.evidencias.filter(texto="Hice tableros en Excel.").delete()
    assert texto_adaptado(usuario.perfil, vacante_v1) == ""


def test_taller_get_concurrente_no_da_500(decision, usuario, vacante_v1):
    """Otro GET simultáneo ya creó la sugerencia: este no debe chocar con la restricción única."""
    evidencias = list(usuario.perfil.evidencias.values_list("texto", flat=True))
    for s in generar_sugerencias(decision, evidencias):
        s.save()
    assert len(taller(usuario.perfil, vacante_v1)) == SugerenciaCV.objects.count() > 0
