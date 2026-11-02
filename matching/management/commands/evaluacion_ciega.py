import csv
import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from matching.evaluacion.ciega import COLUMNAS, preparar as preparar_ciega, tabular
from matching.evaluacion.evaluar import preparar
from matching.ia import obtener_embedder
from vacantes.fuentes.fixture import FuenteFixture

DATOS = Path(__file__).resolve().parents[2] / "evaluacion"
CLAVE = Path.home() / ".scoutly" / "clave_evaluacion_ciega.json"  # fuera del repo: nadie la ve antes de tabular
CVS_POR_DEFECTO = ["datos_junior", "auxiliar_contable", "auxiliar_enfermeria", "operario_produccion",
                   "habilidad_nombrada_distinto", "asesora_comercial"]


class Command(BaseCommand):
    help = "Evaluación ciega con reclutadores: `preparar` arma los paquetes y la clave; `tabular` cuenta las respuestas."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["preparar", "tabular"])
        parser.add_argument("--salida", type=Path, default=Path("docs/fase4/evaluacion_ciega/paquetes"))
        parser.add_argument("--clave", type=Path, default=CLAVE)
        parser.add_argument("--respuestas", type=Path)
        parser.add_argument("--semilla", type=int, default=2026)
        parser.add_argument("--cvs", nargs="+", default=CVS_POR_DEFECTO)

    def handle(self, *args, accion, **opciones):
        getattr(self, f"_{accion}")(**opciones)

    def _preparar(self, salida, clave, semilla, cvs, **_):
        datos = yaml.safe_load((DATOS / "cvs.yaml").read_text(encoding="utf-8"))
        embedder = obtener_embedder()
        with transaction.atomic():  # como la evaluación: no deja datos en la base
            escenario = preparar({c: datos[c] for c in cvs}, FuenteFixture(DATOS / "vacantes.json"), embedder)
            paquetes, sorteo = preparar_ciega(escenario, datos, cvs, embedder, semilla)
            transaction.set_rollback(True)
        salida.mkdir(parents=True, exist_ok=True)
        for paquete in paquetes:
            (salida / f"paquete_{paquete.numero}.md").write_text(paquete.markdown(), encoding="utf-8")
        clave.parent.mkdir(parents=True, exist_ok=True)
        clave.write_text(json.dumps(sorteo, indent=1), encoding="utf-8")
        self.stdout.write(f"{len(paquetes)} paquetes en {salida}; clave en {clave} (no la compartas antes de tabular)")

    def _tabular(self, respuestas, clave, **_):
        if not respuestas:
            raise CommandError("Indica el CSV con --respuestas.")
        with respuestas.open(encoding="utf-8") as archivo:
            lector = csv.DictReader(archivo)
            faltan = [c for c in COLUMNAS if c not in (lector.fieldnames or [])]
            if faltan:
                raise CommandError(f"Al CSV le faltan columnas: {', '.join(faltan)} (se esperan {', '.join(COLUMNAS)})")
            filas = list(lector)
        resultado = tabular(filas, json.loads(clave.read_text(encoding="utf-8")))
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, indent=1))
