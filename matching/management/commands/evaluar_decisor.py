from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from matching.evaluacion.evaluar import barrido as barrer_umbrales, cargar_pares, evaluar, informe_markdown, preparar
from matching.ia import obtener_embedder, obtener_embedder_cobertura
from matching.politica import POLITICA
from vacantes.fuentes.fixture import FuenteFixture

DATOS = Path(__file__).resolve().parents[2] / "evaluacion"


class Command(BaseCommand):
    help = "Evalúa el decisor contra el set etiquetado (en una transacción que se deshace al terminar)."

    def add_arguments(self, parser):
        parser.add_argument("--mitad", choices=["ajuste", "prueba_1", "prueba", "prueba_2", "prueba_3"], default="ajuste")  # prueba_1 ya se vio
        parser.add_argument("--barrido", action="store_true", help="probar la grilla de umbrales (solo ajuste)")
        parser.add_argument("--confirmo-prueba", action="store_true")
        parser.add_argument("--salida", type=Path, help="agrega el informe en Markdown al final de este archivo")

    def handle(self, *args, mitad, barrido: bool, confirmo_prueba, salida=None, **options):
        if mitad == "prueba" and not confirmo_prueba:
            raise CommandError("La mitad de prueba se reserva para la Fase 4 (usa --confirmo-prueba solo entonces).")
        if mitad == "prueba" and barrido:
            raise CommandError("El barrido de umbrales solo se hace sobre la mitad de ajuste.")
        cvs = yaml.safe_load((DATOS / "cvs.yaml").read_text(encoding="utf-8"))
        pares = cargar_pares(DATOS / "pares.yaml", mitad)
        with transaction.atomic():
            escenario = preparar(cvs, FuenteFixture(DATOS / "vacantes.json"), obtener_embedder(),
                                 obtener_embedder_cobertura())
            if barrido:
                for politica, informe in barrer_umbrales(escenario, pares, POLITICA)[:5]:
                    self.stdout.write(f"τ_alto={politica.tau_alto} τ_bajo={politica.tau_bajo} "
                                      f"τ_relevancia={politica.tau_relevancia}: exactitud {informe.exactitud:.0%}")
            informe = evaluar(escenario, pares, POLITICA)
            self._imprimir(informe)
            if salida:
                with salida.open("a", encoding="utf-8") as archivo:
                    archivo.write(informe_markdown(informe, mitad, POLITICA) + "\n")
            transaction.set_rollback(True)  # la evaluación no deja datos en la base

    def _imprimir(self, informe):
        self.stdout.write(f"pares: {informe.total}  exactitud: {informe.exactitud:.0%}  "
                          f"línea base: {informe.exactitud_linea_base:.0%}  "
                          f"clase mayoritaria: {informe.exactitud_mayoritaria:.0%}")
        self.stdout.write(f"distribución: {dict(informe.distribucion)}")
        for error in informe.errores:
            self.stdout.write(f"  ✗ {error}")
