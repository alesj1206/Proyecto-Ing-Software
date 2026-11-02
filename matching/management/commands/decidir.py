import logging
import time

from django.core.management.base import BaseCommand

from cuentas.models import Perfil
from matching.ia import obtener_embedder, obtener_embedder_cobertura, obtener_reordenador
from matching.models import SolicitudDecision
from matching.orden import OrdenConReranker, OrdenSimilitudCobertura
from matching.services import decidir_para_perfil
from matching.vectores import embeber_vacantes

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

    def handle(self, *args, todos, pendientes, escuchar, **options):
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

    def _atender_cola(self):
        ids = SolicitudDecision.objects.values_list("perfil_id", flat=True)
        self._decidir(Perfil.objects.filter(id__in=list(ids)))

    def _decidir(self, perfiles):
        perfiles = list(perfiles)
        if not perfiles:
            return
        embebidas = embeber_vacantes(self.embedder, cobertura=self.cobertura)
        if embebidas:
            self.stdout.write(f"vacantes embebidas: {embebidas}")
        decididos = 0
        for perfil in perfiles:
            try:
                r = decidir_para_perfil(perfil, self.embedder, self.ordenador, cobertura=self.cobertura)
            except Exception:  # un perfil que falla no detiene a los demás (revisión de seguridad, Fase 2)
                log.exception("No se pudo decidir para el perfil %s", perfil.pk)
                self._contar_fallo(perfil)
                continue
            decididos += 1
            self.stdout.write(f"perfil {perfil.pk}: {r.relevantes} relevantes {r.por_accion} en {r.segundos:.2f} s")
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
