"""Varios procesos `decidir --escuchar` en paralelo: se reparten la cola sin pisarse (SKIP LOCKED), uno solo embebe
a la vez y las notificaciones no se generan dos veces al mismo tiempo (candados de aviso de Postgres)."""

import threading

import pytest
from django.core.management import call_command
from django.db import connection, transaction

from matching.models import Decision, SolicitudDecision
from matching.services import solicitar_decision

from .test_decidir import _perfil, catalogo  # noqa: F401  (fixture)


def _en_otra_conexion(trabajo, listo: threading.Event, soltar: threading.Event):
    """Corre `trabajo` en un hilo con su propia conexión y transacción, y la mantiene abierta hasta `soltar`."""
    def hilo():
        try:
            with transaction.atomic():
                trabajo()
                listo.set()
                soltar.wait(10)
        finally:
            connection.close()
    t = threading.Thread(target=hilo)
    t.start()
    assert listo.wait(10)
    return t


@pytest.mark.django_db(transaction=True)
def test_un_perfil_tomado_por_otro_proceso_no_se_decide_dos_veces(usuario, django_user_model, catalogo):  # noqa: F811
    tomado = _perfil(usuario)
    otro = django_user_model.objects.create_user(email="otro@ejemplo.com", password="Lienzo-Tardio-73")
    libre = _perfil(otro)
    solicitar_decision(tomado), solicitar_decision(libre)
    listo, soltar = threading.Event(), threading.Event()
    hilo = _en_otra_conexion(lambda: list(SolicitudDecision.objects.select_for_update().filter(perfil=tomado)),
                             listo, soltar)
    try:
        call_command("decidir", "--pendientes")
    finally:
        soltar.set()
        hilo.join()
    assert Decision.objects.filter(perfil=libre).exists()
    assert not Decision.objects.filter(perfil=tomado).exists()
    assert SolicitudDecision.objects.filter(perfil=tomado).exists()  # sigue en cola para el otro proceso


@pytest.mark.django_db(transaction=True)
def test_las_notificaciones_esperan_a_que_termine_el_otro_proceso(db):
    from notificaciones.services import CANDADO_NOTIFICACIONES, generar_notificaciones

    listo, soltar = threading.Event(), threading.Event()

    def tomar():
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", [CANDADO_NOTIFICACIONES])

    hilo = _en_otra_conexion(tomar, listo, soltar)
    termino = threading.Event()

    def generar():
        try:
            generar_notificaciones()
            termino.set()
        finally:
            connection.close()

    segundo = threading.Thread(target=generar)
    segundo.start()
    assert not termino.wait(0.5)  # espera el candado
    soltar.set()
    hilo.join()
    segundo.join(10)
    assert termino.is_set()


@pytest.mark.django_db(transaction=True)
def test_si_otro_proceso_embebe_este_no_repite_el_trabajo(db):
    from vacantes.services import ingerir
    from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

    from matching.ia.fakes import EmbedderFalso
    from matching.vectores import CANDADO_EMBEBIDO, embeber_vacantes_si_libre

    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    listo, soltar = threading.Event(), threading.Event()

    def tomar():
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", [CANDADO_EMBEBIDO])

    hilo = _en_otra_conexion(tomar, listo, soltar)
    try:
        assert embeber_vacantes_si_libre(EmbedderFalso()) is None  # el otro está embebiendo
    finally:
        soltar.set()
        hilo.join()
    assert embeber_vacantes_si_libre(EmbedderFalso()) == 1


def test_procesos_lanza_n_escuchas(db, monkeypatch):
    import matching.management.commands.decidir as comando

    lanzados = []

    class Proceso:
        def __init__(self, args, **_):
            lanzados.append(args)

        def wait(self):
            return 0

    monkeypatch.setattr(comando.subprocess, "Popen", Proceso)
    call_command("decidir", "--escuchar", "--procesos", "3")
    assert len(lanzados) == 3 and all(a[-2:] == ["decidir", "--escuchar"] for a in lanzados)


def test_procesos_solo_con_escuchar(db):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="--escuchar"):
        call_command("decidir", "--pendientes", "--procesos", "2")
