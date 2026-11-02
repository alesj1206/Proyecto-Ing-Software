import csv
import hashlib
import json
import os
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from matching.evaluacion.ciega import COLUMNAS, preparar as preparar_ciega, tabular
from matching.evaluacion.evaluar import preparar
from matching.ia import obtener_modelos
from vacantes.fuentes.fixture import FuenteFixture

DATOS = Path(__file__).resolve().parents[2] / "evaluacion"
CLAVE = Path.home() / ".scoutly" / "clave_evaluacion_ciega.json"  # fuera del repo: nadie la ve antes de tabular
HUELLA = Path(__file__).resolve().parents[3] / "docs" / "fase4" / "evaluacion_ciega" / "CLAVE_SHA256.txt"
CVS_POR_DEFECTO = ["datos_junior", "auxiliar_contable", "auxiliar_enfermeria", "operario_produccion",
                   "habilidad_nombrada_distinto", "asesora_comercial"]


def _sortear(cvs: list[str], semilla: int | None):
    datos = yaml.safe_load((DATOS / "cvs.yaml").read_text(encoding="utf-8"))
    modelos = obtener_modelos()
    with transaction.atomic():  # como la evaluación: no deja datos en la base
        escenario = preparar({c: datos[c] for c in cvs}, FuenteFixture(DATOS / "vacantes.json"), modelos)
        resultado = preparar_ciega(escenario, datos, cvs, modelos, semilla)
        transaction.set_rollback(True)
    return resultado


class Command(BaseCommand):
    help = "Evaluación ciega con reclutadores: `preparar` arma los paquetes y la clave; `tabular` cuenta las respuestas."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["preparar", "tabular"])
        parser.add_argument("--salida", type=Path, default=Path("docs/fase4/evaluacion_ciega/paquetes"))
        parser.add_argument("--clave", type=Path, default=CLAVE)
        parser.add_argument("--respuestas", type=Path)
        parser.add_argument("--semilla", type=int, default=None, help="solo para pruebas: sin ella el sorteo es secreto")
        parser.add_argument("--cvs", nargs="+", default=CVS_POR_DEFECTO)

    def handle(self, *args, accion, **opciones):
        getattr(self, f"_{accion}")(**opciones)

    def _preparar(self, salida, clave, semilla, cvs, **_):
        if Path(clave).resolve().is_relative_to(Path(settings.BASE_DIR).resolve()):
            raise CommandError("La clave debe quedar fuera del repositorio (nadie del equipo la ve antes de tabular).")
        paquetes, sorteo = _sortear(cvs, semilla)
        salida.mkdir(parents=True, exist_ok=True)
        for paquete in paquetes:
            (salida / f"paquete_{paquete.numero}.md").write_text(paquete.markdown(), encoding="utf-8")
        clave.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(clave.parent, 0o700)
        descriptor = os.open(clave, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(sorteo, archivo, indent=1)
        os.chmod(clave, 0o600)
        self.stdout.write(f"{len(paquetes)} paquetes en {salida}; clave en {clave} (no la compartas antes de tabular)")

    def _tabular(self, respuestas, clave, **_):
        if not respuestas:
            raise CommandError("Indica el CSV con --respuestas.")
        if not clave.exists():
            raise CommandError(f"No encuentro la clave en {clave}.")
        if HUELLA.exists():  # la huella se commiteó antes de enviar los paquetes: la clave no pudo cambiar después
            esperada = HUELLA.read_text(encoding="utf-8").split()[0]
            if hashlib.sha256(clave.read_bytes()).hexdigest() != esperada:
                raise CommandError(f"El SHA-256 de {clave} no coincide con {HUELLA.name}: la clave cambió.")
        with respuestas.open(encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            faltan = [c for c in COLUMNAS if c not in (lector.fieldnames or [])]
            if faltan:
                raise CommandError(f"Al CSV le faltan columnas: {', '.join(faltan)} (se esperan {', '.join(COLUMNAS)})")
            filas = list(lector)
        resultado = tabular(filas, json.loads(clave.read_text(encoding="utf-8")))
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, indent=1))
