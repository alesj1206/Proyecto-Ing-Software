from datetime import date, datetime, timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from matching.models import Decision
from notificaciones.models import Notificacion
from notificaciones.services import generar_notificaciones
from vacantes.models import Vacante

HOY = timezone.localdate()


def _vacante(i):
    return Vacante.objects.create(id=f"v{i}", titulo=f"Cargo {i}", empresa=f"Empresa {i}", ubicacion="Medellín",
                                  modalidad="Presencial", fecha_publicacion=HOY, fuente="t", hash_contenido="x")


def _decision(perfil, i, accion="POSTULAR", anterior="NUEVA", cuando=None):
    return Decision.objects.create(perfil=perfil, vacante=_vacante(i), accion=accion, accion_anterior=anterior,
                                   cambio_en=cuando or timezone.now(), solidez="alta", motivo_solidez="ok",
                                   motivos=[], similitud=0.8, cobertura_pct=80, version_politica="t")


@pytest.fixture
def perfil(client_con_cv, usuario):
    return usuario.perfil  # su CV ficticio trae un correo, así que puede_notificar


def test_solo_notifica_postular_nuevo_de_hoy(perfil):
    _decision(perfil, 1)
    _decision(perfil, 2, anterior="POSTULAR")
    _decision(perfil, 3, anterior="AJUSTAR_CV", cuando=timezone.now() - timedelta(days=3))  # fuera de la ventana
    _decision(perfil, 4, accion="AJUSTAR_CV")
    generar_notificaciones()
    assert list(Notificacion.objects.values_list("vacante_id", flat=True)) == ["v1"]
    assert Notificacion.objects.get().mensaje == "Nueva vacante para postular: Cargo 1 en Empresa 1"


def test_resumen_envia_un_solo_correo_con_todas(perfil):
    for i in range(3):
        _decision(perfil, i)
    r = generar_notificaciones()
    assert (r.creadas, r.correos, len(mail.outbox)) == (3, 1, 1)
    assert all(f"Cargo {i}" in mail.outbox[0].body for i in range(3))
    assert Notificacion.objects.filter(enviada=True).count() == 3


def test_individual_respeta_el_maximo_y_la_campana_las_tiene_todas(perfil):
    perfil.notif_modo, perfil.notif_max = "individual", 3
    perfil.save()
    for i in range(10):
        _decision(perfil, i)
    generar_notificaciones()
    assert len(mail.outbox) == 3 and Notificacion.objects.count() == 10
    assert Notificacion.objects.filter(enviada=True).count() == 3


def test_desactivado_no_envia_correo_pero_si_campana(perfil):
    perfil.notif_modo = "desactivado"
    perfil.save()
    _decision(perfil, 1)
    generar_notificaciones()
    assert len(mail.outbox) == 0 and Notificacion.objects.count() == 1


def test_correr_dos_veces_no_duplica(perfil):
    _decision(perfil, 1)
    generar_notificaciones()
    r = generar_notificaciones()
    assert (r.creadas, Notificacion.objects.count(), len(mail.outbox)) == (0, 1, 1)


def test_redecidir_el_mismo_dia_no_renotifica(perfil):
    d = _decision(perfil, 1)
    generar_notificaciones()
    Notificacion.objects.all().delete()  # aunque se borre la campana, la segunda corrida ya no es "nueva"
    Decision.objects.filter(id=d.id).update(accion_anterior="POSTULAR")  # lo que deja decidir_para_perfil
    generar_notificaciones()
    assert not Notificacion.objects.exists()


def test_la_preferencia_se_guarda_desde_expectativas(client_con_cv, usuario):
    client_con_cv.post(reverse("expectativas"), {"notif_modo": "individual", "notif_max": 2})
    usuario.perfil.refresh_from_db()
    assert (usuario.perfil.notif_modo, usuario.perfil.notif_max) == ("individual", 2)
