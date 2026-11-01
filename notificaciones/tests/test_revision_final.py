"""Regresiones de la revisión final de la Fase 3 (notificaciones)."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from notificaciones.models import Notificacion
from notificaciones.services import generar_notificaciones

from .test_generar import _decision


@pytest.fixture
def perfil(client_con_cv, usuario):
    return usuario.perfil


def test_lo_decidido_despues_de_notificar_se_notifica_en_la_siguiente_corrida(perfil):
    generar_notificaciones()  # n8n notifica antes de que el batch decida
    _decision(perfil, 1)       # el batch decide después
    generar_notificaciones(hoy=timezone.localdate() + timedelta(days=1))  # al día siguiente
    assert Notificacion.objects.filter(perfil=perfil, vacante_id="v1").count() == 1


def test_el_maximo_individual_es_por_dia(perfil):
    perfil.notif_modo, perfil.notif_max = "individual", 3
    perfil.save()
    for i in range(4):
        _decision(perfil, i)
    generar_notificaciones()
    for i in range(4, 8):
        _decision(perfil, i)
    generar_notificaciones()
    assert len(mail.outbox) == 3


def test_el_correo_va_a_la_cuenta_no_al_del_cv(perfil, usuario):
    perfil.contacto = "tercero@otro.com"
    perfil.save()
    _decision(perfil, 1)
    generar_notificaciones()
    assert mail.outbox[0].to == [usuario.email]


def test_un_titulo_con_salto_de_linea_no_tumba_la_corrida(perfil):
    d = _decision(perfil, 1)
    d.vacante.titulo = "Cargo\nBcc: todos@x.com"
    d.vacante.save()
    perfil.notif_modo = "individual"
    perfil.save()
    generar_notificaciones()
    assert len(mail.outbox) == 1 and "\n" not in mail.outbox[0].subject


def test_los_correos_que_fallaron_se_reintentan(perfil, monkeypatch):
    import notificaciones.services as servicios

    _decision(perfil, 1)
    monkeypatch.setattr(servicios, "send_mail", lambda *a, **k: (_ for _ in ()).throw(OSError("SMTP caído")))
    generar_notificaciones()
    monkeypatch.undo()
    generar_notificaciones()
    assert len(mail.outbox) == 1 and Notificacion.objects.get().enviada
