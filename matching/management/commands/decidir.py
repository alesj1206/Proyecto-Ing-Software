import time

from django.core.management.base import BaseCommand

from cuentas.models import Perfil
from matching.ia import obtener_embedder, obtener_reordenador
from matching.models import SolicitudDecision
from matching.orden import OrdenConReranker, OrdenSimilitudCobertura
from matching.services import decidir_para_perfil
from matching.vectores import embeber_vacantes

PAUSA_ESCUCHA_S = 5


class Command(BaseCommand):
    help = "Calcula las decisiones (carga los modelos una sola vez). Embebe antes las vacantes nuevas o modificadas."

    def add_arguments(self, parser):
        modo = parser.add_mutually_exclusive_group(required=True)
        modo.add_argument("--todos", action="store_true", help="todos los perfiles con hoja de vida")
        modo.add_argument("--pendientes", action="store_true", help="solo los perfiles en cola")
        modo.add_argument("--escuchar", action="store_true", help="atender la cola cada 5 s hasta Ctrl+C")

    def handle(self, *args, todos, pendientes, escuchar, **options):
        self.embedder = obtener_embedder()
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
                    self._atender_cola()
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
        embebidas = embeber_vacantes(self.embedder)
        if embebidas:
            self.stdout.write(f"vacantes embebidas: {embebidas}")
        for perfil in perfiles:
            r = decidir_para_perfil(perfil, self.embedder, self.ordenador)
            self.stdout.write(f"perfil {perfil.pk}: {r.relevantes} relevantes {r.por_accion} en {r.segundos:.2f} s")
