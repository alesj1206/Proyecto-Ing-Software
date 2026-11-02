import json
import platform
import statistics
from pathlib import Path

import numpy as np
import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from cuentas.models import Usuario
from matching.benchmark.medir import Medicion, cronometro, informe_markdown
from matching.benchmark.sintetico import FuenteSintetica
from matching.evaluacion.evaluar import preparar
from matching.ia import obtener_modelos
from matching.puertos import ModelosEmbebido
from matching.politica import POLITICA
from matching.preseleccion import TOPE_TECNICO
from matching.services import decidir_para_perfil
from matching.vectores import embeber_vacantes
from vacantes.models import Vacante
from vacantes.services import ingerir

DATOS = Path(__file__).resolve().parents[2] / "evaluacion"
VACANTES_120K = 120_000
DELTA_DIARIO = 3_000


def _base_conectada() -> str:
    """El nombre de la base a la que de verdad está conectado, no el configurado (un servicio de pg o un alias podrían
    diferir)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        return cursor.fetchone()[0]


def _cpu() -> str:
    try:
        for linea in Path("/proc/cpuinfo").read_text().splitlines():
            if linea.startswith("model name"):
                return linea.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


class EmbedderConMemoria:
    """Para la carga masiva: los textos sintéticos se repiten, así que se embebe cada texto distinto una vez. Mide la
    escritura en la base, no el modelo (el costo del modelo se mide sin memoria sobre la muestra)."""

    def __init__(self, embedder):
        self.embedder, self.memoria = embedder, {}
        self.modelo, self.dimension = embedder.modelo, embedder.dimension

    def embeber(self, textos: list[str]) -> np.ndarray:
        nuevos = [t for t in dict.fromkeys(textos) if t not in self.memoria]
        if nuevos:
            self.memoria.update(zip(nuevos, self.embedder.embeber(nuevos)))
        return np.vstack([self.memoria[t] for t in textos])


class FuenteVacia:
    nombre = "vacia"

    def obtener(self):
        return []


class Command(BaseCommand):
    help = "Benchmark de escala (§6): N vacantes sintéticas, ingesta, embebido y decisión por candidato. Solo en *_bench."

    def add_arguments(self, parser):
        parser.add_argument("--vacantes", type=int, default=VACANTES_120K)
        parser.add_argument("--muestra", type=int, default=DELTA_DIARIO, help="se embebe de verdad (= delta diario)")
        parser.add_argument("--candidatos", type=int, default=11, help="CVs ficticios del set de evaluación")
        parser.add_argument("--salida", type=Path)
        parser.add_argument("--confirmar", action="store_true", help="borra TODAS las vacantes de la base *_bench")

    def handle(self, *args, vacantes, muestra, candidatos, salida=None, confirmar=False, **options):
        base = _base_conectada()
        if not base.endswith("_bench"):
            raise CommandError(f"El benchmark borra y llena la base: solo corre en una base *_bench (esta es {base}).")
        if not confirmar:
            raise CommandError(f"Esto borra TODAS las vacantes de {base}. Repite con --confirmar.")
        plantillas = json.loads((DATOS / "vacantes.json").read_text(encoding="utf-8"))
        modelos, mediciones = obtener_modelos(), []
        Vacante.objects.all().delete()
        Usuario.objects.filter(email__startswith="eval-").delete()

        with cronometro() as t:  # 1. muestra real: extracción + embebido de verdad (sin memoria)
            ingerir(FuenteSintetica(plantillas, muestra, semilla=1))
            embeber_vacantes(modelos)
        por_vacante = t["s"] / muestra
        mediciones += [Medicion("delta_diario_min", DELTA_DIARIO, por_vacante * DELTA_DIARIO,
                                "medido" if muestra == DELTA_DIARIO else "proyectado", f"muestra de {muestra}"),
                       Medicion("carga_inicial_cpu_h", VACANTES_120K, por_vacante * VACANTES_120K, "proyectado",
                                f"lineal desde la muestra de {muestra}")]
        self.stdout.write(f"muestra: {muestra} vacantes en {t['s']:.0f} s")

        resto = max(vacantes - muestra, 0)
        with cronometro() as t:  # 2. carga masiva hasta N, reutilizando embeddings de textos repetidos
            ingerir(FuenteSintetica(plantillas, resto, semilla=1, desde=muestra))
            embeber_vacantes(ModelosEmbebido(EmbedderConMemoria(modelos.busqueda), EmbedderConMemoria(modelos.cobertura)))
        mediciones.append(Medicion("carga_masiva_min", resto, t["s"], "medido",
                                   "embeddings reutilizados: mide extracción y escritura"))
        self.stdout.write(f"carga masiva: {resto} vacantes en {t['s']:.0f} s; total {Vacante.objects.count()}")

        cvs = yaml.safe_load((DATOS / "cvs.yaml").read_text(encoding="utf-8"))
        cvs = dict(list(cvs.items())[:candidatos])
        perfiles = preparar(cvs, FuenteVacia(), modelos).perfiles
        tiempos, relevantes, topes = [], [], 0
        for clave, perfil in perfiles.items():  # 3. decisión completa por candidato
            resumen = decidir_para_perfil(perfil, modelos)
            tiempos.append(resumen.segundos)
            relevantes.append(resumen.relevantes)
            topes += resumen.relevantes >= TOPE_TECNICO
            self.stdout.write(f"  {clave}: {resumen.relevantes} relevantes en {resumen.segundos:.2f} s")
        nota = f"relevantes por candidato: mediana {statistics.median(relevantes):.0f}, máx {max(relevantes)}; " \
               f"tope técnico ({TOPE_TECNICO}) alcanzado por {topes}"
        mediciones += [Medicion("decision_candidato_p50_s", len(tiempos), statistics.median(tiempos), "medido", nota),
                       Medicion("decision_candidato_s", len(tiempos), max(tiempos), "medido", "el peor candidato")]

        contexto = {"fecha": timezone.now().strftime("%Y-%m-%d %H:%M"), "vacantes en la base": Vacante.objects.count(),
                    "CPU": _cpu(), "embeddings": f"búsqueda|cobertura = {modelos.firma}",
                    "política": f"{POLITICA.version} (τ_relevancia {POLITICA.tau_relevancia})",
                    "reranker": "apagado (el umbral de 1,5 s por página no aplica, §13.1)"}
        informe = informe_markdown(mediciones, contexto)
        self.stdout.write(informe)
        if salida:
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_text(informe, encoding="utf-8")
