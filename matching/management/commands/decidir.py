import logging
import signal
import subprocess
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cuentas.models import Perfil
from matching.ia import obtener_modelos, obtener_reordenador
from matching.models import SolicitudDecision
from matching.orden import OrdenConReranker, OrdenSimilitudCobertura
from matching.services import decidir_para_perfil
from matching.vectores import embeber_vacantes

PAUSA_ESCUCHA_S = 5
PAUSA_SUPERVISION_S = 1
TANDA_NOTIFICACIONES = 20  # perfiles decididos entre una generación de notificaciones y la siguiente
MAX_PROCESOS = 6  # en este PC (31 GB), 3 ya rinden lo mismo que 6 (docs/exploracion/2026-11-02-eficiencia.md)
MAX_INTENTOS = 3  # tras 3 fallos el perfil sale de la cola (queda en el log) para no bloquear a nadie
log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Calcula las decisiones (carga los modelos una sola vez). Embebe antes las vacantes nuevas o modificadas."

    def add_arguments(self, parser):
        modo = parser.add_mutually_exclusive_group(required=True)
        modo.add_argument("--todos", action="store_true", help="todos los perfiles con hoja de vida")
        modo.add_argument("--pendientes", action="store_true", help="solo los perfiles en cola")
        modo.add_argument("--escuchar", action="store_true", help="atender la cola cada 5 s hasta Ctrl+C")
        parser.add_argument("--procesos", type=int, default=1,
                            help="con --escuchar: cuántos procesos atienden la cola en paralelo (cada uno carga los "
                                 "modelos, ~2 GB de RAM)")

    def handle(self, *args, todos, pendientes, escuchar, procesos=1, **options):
        if not 1 <= procesos <= MAX_PROCESOS:  # cada proceso carga ~2 GB de modelos: sin tope se agota la memoria
            raise CommandError(f"--procesos debe estar entre 1 y un máximo de {MAX_PROCESOS}.")
        if procesos > 1:
            if not escuchar:
                raise CommandError("--procesos solo sirve con --escuchar.")
            return self._lanzar(procesos)
        self.modelos, self.escuchando = obtener_modelos(), escuchar
        reordenador = obtener_reordenador()
        self.ordenador = OrdenConReranker(reordenador) if reordenador else OrdenSimilitudCobertura()
        if todos:
            self._decidir(Perfil.objects.exclude(cv_nombre_archivo=""))
        elif pendientes:
            self._atender_cola()
        else:
            self.stdout.write("Escuchando la cola de decisiones (Ctrl+C para salir)…")
            try:
                while True:
                    try:
                        self._atender_cola()
                    except Exception:  # un error de base de datos pasajero no debe apagar al que escucha
                        log.exception("Falló una vuelta de la cola de decisiones")
                    time.sleep(PAUSA_ESCUCHA_S)
            except KeyboardInterrupt:
                self.stdout.write("Listo.")

    def _lanzar(self, procesos: int):
        """N procesos `decidir --escuchar` independientes: se reparten la cola sin pisarse (ver `_atender_cola`). Se
        lanzan con la ruta de manage.py, así que no dependen del directorio de trabajo."""
        orden = [sys.executable, str(settings.BASE_DIR / "manage.py"), "decidir", "--escuchar"]
        hijos = [subprocess.Popen(orden, cwd=settings.BASE_DIR) for _ in range(procesos)]
        terminando = []

        def terminar(*_):  # un SIGTERM al padre (systemd, kill) no deja hijos huérfanos
            terminando.append(True)
            for hijo in hijos:
                hijo.terminate()

        signal.signal(signal.SIGTERM, terminar)
        self.stdout.write(f"{procesos} procesos escuchando la cola (Ctrl+C para salir)…")
        vivos, fallidos = list(hijos), []
        try:
            while vivos:
                for hijo in list(vivos):
                    codigo = hijo.poll()
                    if codigo is None:
                        continue
                    vivos.remove(hijo)
                    if codigo and not terminando:  # se avisa enseguida: los demás siguen atendiendo la cola
                        fallidos.append(codigo)
                        log.error("Un proceso de la cola terminó con código %s; quedan %s", codigo, len(vivos))
                if vivos:
                    time.sleep(PAUSA_SUPERVISION_S)
        except KeyboardInterrupt:  # Ctrl+C llega a todo el grupo; se espera a que cada hijo termine
            for hijo in hijos:
                hijo.wait()
            self.stdout.write("Listo.")
            return
        if fallidos:
            raise CommandError(f"Procesos de la cola que terminaron con error: {fallidos}")

    def _atender_cola(self):
        """Toma los perfiles de la cola de a uno, con `SELECT … FOR UPDATE SKIP LOCKED`: otro proceso que escucha no ve
        los que este ya tomó, y si este muere, Postgres suelta el candado y el perfil vuelve a la cola."""
        embebidas = embeber_vacantes(self.modelos, esperar=False)  # si otro proceso embebe, no se espera
        if embebidas:
            self.stdout.write(f"vacantes embebidas: {embebidas}")
        vistos, decididos = [], 0
        while True:
            with transaction.atomic():
                # of=("self",): solo la fila de la cola; sin eso se bloquea también el perfil y la web del candidato
                # (expectativas, borrar la cuenta) espera a que termine la decisión.
                solicitud = (SolicitudDecision.objects.select_for_update(skip_locked=True, of=("self",))
                             .select_related("perfil").exclude(perfil_id__in=vistos).order_by("creada_en").first())
                if solicitud is None:
                    break
                vistos.append(solicitud.perfil_id)  # uno que falla no se reintenta en esta misma vuelta
                decididos += self._decidir_uno(solicitud.perfil)
            if decididos >= TANDA_NOTIFICACIONES:  # fuera de la transacción: una cola larga no retrasa los correos
                self._notificar(decididos)
                decididos = 0
        self._notificar(decididos)

    def _decidir(self, perfiles):
        perfiles = list(perfiles)
        if not perfiles:
            return
        embebidas = embeber_vacantes(self.modelos)
        if embebidas:
            self.stdout.write(f"vacantes embebidas: {embebidas}")
        self._notificar(sum(self._decidir_uno(perfil) for perfil in perfiles))

    def _decidir_uno(self, perfil) -> bool:
        try:
            with transaction.atomic():  # si falla, se deshace solo lo de este perfil
                r = decidir_para_perfil(perfil, self.modelos, self.ordenador)
        except Exception:  # un perfil que falla no detiene a los demás (revisión de seguridad, Fase 2)
            log.exception("No se pudo decidir para el perfil %s", perfil.pk)
            self._contar_fallo(perfil)
            return False
        self.stdout.write(f"perfil {perfil.pk}: {r.relevantes} relevantes {r.por_accion} en {r.segundos:.2f} s")
        return True

    def _notificar(self, decididos: int):
        """n8n no espera al batch: las notificaciones salen en cuanto hay decisiones nuevas. Si otro proceso está
        notificando, no se espera: queda pendiente y se reintenta en la vuelta siguiente (--escuchar, cada 5 s)."""
        self.notificar_pendiente = getattr(self, "notificar_pendiente", False) or decididos > 0
        if not self.notificar_pendiente:
            return
        from notificaciones.services import generar_notificaciones

        r = generar_notificaciones(esperar=not self.escuchando)  # las corridas únicas sí esperan
        if r is None:
            self.stdout.write("notificaciones: otro proceso está notificando; se reintenta en la próxima vuelta")
            return
        self.notificar_pendiente = False
        self.stdout.write(f"notificaciones: {r.creadas} nuevas, {r.correos} correos")

    def _contar_fallo(self, perfil):
        solicitud = SolicitudDecision.objects.filter(perfil=perfil).first()
        if solicitud is None:
            return
        solicitud.intentos += 1
        if solicitud.intentos >= MAX_INTENTOS:
            solicitud.delete()
        else:
            solicitud.save(update_fields=["intentos"])
