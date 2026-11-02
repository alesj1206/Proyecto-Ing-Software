import logging
import subprocess
import sys
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cuentas.models import Perfil
from matching.ia import obtener_embedder, obtener_embedder_cobertura, obtener_reordenador
from matching.models import SolicitudDecision
from matching.orden import OrdenConReranker, OrdenSimilitudCobertura
from matching.services import decidir_para_perfil
from matching.vectores import embeber_vacantes, embeber_vacantes_si_libre

PAUSA_ESCUCHA_S = 5
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
        if procesos < 1:
            raise CommandError("--procesos debe ser al menos 1.")
        if procesos > 1:
            if not escuchar:
                raise CommandError("--procesos solo sirve con --escuchar.")
            return self._lanzar(procesos)
        self.embedder, self.cobertura = obtener_embedder(), obtener_embedder_cobertura()
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
        """N procesos `decidir --escuchar` independientes: se reparten la cola sin pisarse (ver `_atender_cola`)."""
        hijos = [subprocess.Popen([sys.executable, "-m", "django", "decidir", "--escuchar"]) for _ in range(procesos)]
        self.stdout.write(f"{procesos} procesos escuchando la cola (Ctrl+C para salir)…")
        try:
            for hijo in hijos:
                hijo.wait()
        except KeyboardInterrupt:  # Ctrl+C llega a todo el grupo; se espera a que cada hijo termine
            for hijo in hijos:
                hijo.wait()
            self.stdout.write("Listo.")

    def _atender_cola(self):
        """Toma los perfiles de la cola de a uno, con `SELECT … FOR UPDATE SKIP LOCKED`: otro proceso que escucha no ve
        los que este ya tomó, y si este muere, Postgres suelta el candado y el perfil vuelve a la cola."""
        embebidas = embeber_vacantes_si_libre(self.embedder, cobertura=self.cobertura)
        if embebidas:
            self.stdout.write(f"vacantes embebidas: {embebidas}")
        vistos, decididos = [], 0
        while True:
            with transaction.atomic():
                solicitud = (SolicitudDecision.objects.select_for_update(skip_locked=True).select_related("perfil")
                             .exclude(perfil_id__in=vistos).order_by("creada_en").first())
                if solicitud is None:
                    break
                vistos.append(solicitud.perfil_id)  # uno que falla no se reintenta en esta misma vuelta
                decididos += self._decidir_uno(solicitud.perfil)
        self._notificar(decididos)

    def _decidir(self, perfiles):
        perfiles = list(perfiles)
        if not perfiles:
            return
        embebidas = embeber_vacantes(self.embedder, cobertura=self.cobertura)
        if embebidas:
            self.stdout.write(f"vacantes embebidas: {embebidas}")
        self._notificar(sum(self._decidir_uno(perfil) for perfil in perfiles))

    def _decidir_uno(self, perfil) -> bool:
        try:
            with transaction.atomic():  # si falla, se deshace solo lo de este perfil
                r = decidir_para_perfil(perfil, self.embedder, self.ordenador, cobertura=self.cobertura)
        except Exception:  # un perfil que falla no detiene a los demás (revisión de seguridad, Fase 2)
            log.exception("No se pudo decidir para el perfil %s", perfil.pk)
            self._contar_fallo(perfil)
            return False
        self.stdout.write(f"perfil {perfil.pk}: {r.relevantes} relevantes {r.por_accion} en {r.segundos:.2f} s")
        return True

    def _notificar(self, decididos: int):
        if decididos:  # n8n no espera al batch: las notificaciones salen en cuanto hay decisiones nuevas
            from notificaciones.services import generar_notificaciones

            r = generar_notificaciones()
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
