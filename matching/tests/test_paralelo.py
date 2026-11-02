"""Varios procesos `decidir --escuchar` en paralelo: se reparten la cola sin pisarse (SKIP LOCKED), uno solo embebe
a la vez y las notificaciones no se generan dos veces al mismo tiempo (candados de aviso de Postgres)."""

import threading

import pytest
from django.core.management import call_command
from django.db import connection, transaction

from matching.models import Decision, SolicitudDecision
from matching.services import solicitar_decision

from .test_decidir import _perfil, catalogo  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def sin_procesos_reales(monkeypatch):
    """Ninguna prueba de este módulo puede lanzar procesos de verdad: cada uno carga ~2 GB de modelos, y una prueba de
    --procesos 50 sin el tope agotó la memoria del PC (2026-11-02)."""
    import matching.management.commands.decidir as comando

    def prohibido(*a, **k):
        raise AssertionError("una prueba intentó lanzar un proceso real")

    monkeypatch.setattr(comando.subprocess, "Popen", prohibido)


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
    from matching.candados import NOTIFICACIONES as CANDADO_NOTIFICACIONES
    from notificaciones.services import generar_notificaciones

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
    from matching.candados import EMBEBIDO
    from matching.puertos import ModelosEmbebido
    from matching.vectores import embeber_vacantes

    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    listo, soltar = threading.Event(), threading.Event()

    def tomar():
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", [EMBEBIDO])

    hilo = _en_otra_conexion(tomar, listo, soltar)
    try:
        assert embeber_vacantes(ModelosEmbebido(EmbedderFalso(), EmbedderFalso()), esperar=False) is None  # otro embebe
    finally:
        soltar.set()
        hilo.join()
    assert embeber_vacantes(ModelosEmbebido(EmbedderFalso(), EmbedderFalso()), esperar=False) == 1


def test_procesos_lanza_n_escuchas(db, monkeypatch):
    import matching.management.commands.decidir as comando

    lanzados = []

    class Proceso:
        def __init__(self, args, **_):
            lanzados.append(args)

        def poll(self):
            return 0

    monkeypatch.setattr(comando.subprocess, "Popen", Proceso)
    call_command("decidir", "--escuchar", "--procesos", "3")
    assert len(lanzados) == 3 and all(a[-2:] == ["decidir", "--escuchar"] for a in lanzados)


def test_procesos_solo_con_escuchar(db):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="--escuchar"):
        call_command("decidir", "--pendientes", "--procesos", "2")


# --- revisión independiente, hallazgos 3 y 8: candados que nunca quedan tomados --------------------------------------

def _libre_en_otra_conexion(clave) -> bool:
    resultado = []

    def hilo():
        try:
            with connection.cursor() as c:
                c.execute("SELECT pg_try_advisory_lock(%s)", [clave])
                resultado.append(c.fetchone()[0])
                c.execute("SELECT pg_advisory_unlock(%s)", [clave])
        finally:
            connection.close()
    t = threading.Thread(target=hilo)
    t.start()
    t.join(10)
    return resultado == [True]


@pytest.mark.django_db(transaction=True)
def test_un_error_con_el_candado_tomado_no_lo_deja_tomado(db):
    from matching.candados import candado_de_aviso

    with pytest.raises(ValueError):
        with candado_de_aviso(4242):
            raise ValueError("falla a mitad")
    assert _libre_en_otra_conexion(4242)
    with pytest.raises(ValueError):  # dentro de una transacción que se deshace, igual
        with transaction.atomic():
            with candado_de_aviso(4242):
                raise ValueError("falla a mitad")
    assert _libre_en_otra_conexion(4242)


@pytest.mark.django_db(transaction=True)
def test_el_batch_que_escucha_no_espera_las_notificaciones_y_reintenta(db, monkeypatch):
    from matching.candados import NOTIFICACIONES
    from matching.management.commands.decidir import Command

    llamadas = []
    monkeypatch.setattr("notificaciones.services._generar", lambda hoy: llamadas.append(hoy) or
                        __import__("notificaciones.services", fromlist=["x"]).ResumenNotificaciones())
    comando = Command()
    comando.escuchando = True
    listo, soltar = threading.Event(), threading.Event()

    def tomar():
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", [NOTIFICACIONES])

    hilo = _en_otra_conexion(tomar, listo, soltar)
    try:
        comando._notificar(decididos=1)  # no se queda esperando
        assert comando.notificar_pendiente and not llamadas
    finally:
        soltar.set()
        hilo.join()
    comando._notificar(decididos=0)  # la vuelta siguiente, sin decisiones nuevas, igual notifica
    assert not comando.notificar_pendiente and len(llamadas) == 1


@pytest.mark.django_db(transaction=True)
def test_embeber_desde_un_comando_espera_al_que_escucha(db):
    """--todos, embeber_vacantes y la evaluación también respetan el candado (antes solo los que escuchaban)."""
    from vacantes.services import ingerir
    from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

    from matching.candados import EMBEBIDO
    from matching.ia.fakes import EmbedderFalso
    from matching.puertos import ModelosEmbebido
    from matching.vectores import embeber_vacantes

    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    listo, soltar = threading.Event(), threading.Event()

    def tomar():
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", [EMBEBIDO])

    hilo = _en_otra_conexion(tomar, listo, soltar)
    termino = threading.Event()

    def embeber():
        try:
            embeber_vacantes(ModelosEmbebido(EmbedderFalso(), EmbedderFalso()))
            termino.set()
        finally:
            connection.close()
    segundo = threading.Thread(target=embeber)
    segundo.start()
    assert not termino.wait(0.5)
    soltar.set()
    hilo.join()
    segundo.join(10)
    assert termino.is_set()


# --- revisión independiente, hallazgo 4: la cola no bloquea la fila del perfil ----------------------------------------

@pytest.mark.django_db(transaction=True)
def test_mientras_se_decide_la_web_puede_escribir_el_perfil(usuario, catalogo, monkeypatch):  # noqa: F811
    """Guardar expectativas o borrar la cuenta no debe esperar a que el batch termine de decidir."""
    import matching.management.commands.decidir as comando
    from django.db import DatabaseError

    from cuentas.models import Perfil

    perfil = _perfil(usuario)
    solicitar_decision(perfil)
    resultado = []

    def decidir_y_mirar(p, *a, **k):
        def web():
            try:
                with transaction.atomic():
                    Perfil.objects.select_for_update(nowait=True).get(pk=p.pk)
                resultado.append("libre")
            except DatabaseError:
                resultado.append("bloqueado")
            finally:
                connection.close()
        t = threading.Thread(target=web)
        t.start()
        t.join(10)
        return original(p, *a, **k)

    original = comando.decidir_para_perfil
    monkeypatch.setattr(comando, "decidir_para_perfil", decidir_y_mirar)
    call_command("decidir", "--pendientes")
    assert resultado == ["libre"]


# --- revisión independiente, hallazgo 7: los procesos hijos -----------------------------------------------------------

class _Hijo:
    lanzados = []

    def __init__(self, args, cwd=None, **_):
        self.args, self.cwd, self.terminado, self.codigo = args, cwd, False, 0
        _Hijo.lanzados.append(self)

    def poll(self):
        return self.codigo

    def terminate(self):
        self.terminado = True


@pytest.fixture
def hijos(monkeypatch):
    import matching.management.commands.decidir as comando

    _Hijo.lanzados = []
    monkeypatch.setattr(comando.subprocess, "Popen", _Hijo)
    manejadores = {}
    monkeypatch.setattr(comando.signal, "signal", lambda sig, f: manejadores.__setitem__(sig, f))
    return manejadores


def test_los_hijos_se_lanzan_con_manage_py_desde_cualquier_directorio(db, hijos, settings):
    import sys

    call_command("decidir", "--escuchar", "--procesos", "2")
    assert all(h.args == [sys.executable, str(settings.BASE_DIR / "manage.py"), "decidir", "--escuchar"]
               and h.cwd == settings.BASE_DIR for h in _Hijo.lanzados)


def test_sigterm_al_padre_termina_a_los_hijos(db, hijos):
    import signal

    call_command("decidir", "--escuchar", "--procesos", "2")
    hijos[signal.SIGTERM](signal.SIGTERM, None)
    assert all(h.terminado for h in _Hijo.lanzados)


def test_un_hijo_que_muere_se_reporta(db, hijos, monkeypatch):
    from django.core.management.base import CommandError

    monkeypatch.setattr(_Hijo, "poll", lambda self: 1 if self is _Hijo.lanzados[0] else 0)
    with pytest.raises(CommandError, match="terminaron con error"):
        call_command("decidir", "--escuchar", "--procesos", "2")


def test_procesos_tiene_un_tope(db):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="máximo"):
        call_command("decidir", "--escuchar", "--procesos", "50")


# --- revisión independiente, hallazgo menor: una cola larga no retrasa las notificaciones ------------------------------

def test_una_cola_larga_notifica_por_tandas(db, django_user_model, catalogo, monkeypatch):  # noqa: F811
    import matching.management.commands.decidir as comando

    for i in range(3):
        solicitar_decision(_perfil(django_user_model.objects.create_user(email=f"u{i}@ejemplo.com",
                                                                         password="Lienzo-Tardio-73")))
    tandas = []
    monkeypatch.setattr(comando, "TANDA_NOTIFICACIONES", 2)
    monkeypatch.setattr("notificaciones.services.generar_notificaciones",
                        lambda **k: tandas.append(1) or type("R", (), {"creadas": 0, "correos": 0})())
    call_command("decidir", "--pendientes")
    assert len(tandas) == 2  # tras los 2 primeros perfiles, y al terminar la cola
