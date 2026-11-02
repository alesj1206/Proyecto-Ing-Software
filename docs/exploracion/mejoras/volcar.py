"""Vuelca, por cada par etiquetado, lo necesario para re-decidir sin modelos: requisitos, evidencias, similitudes
coseno requisito×evidencia, restricciones y similitud del par. Uso: volcar.py salida.json mitad [mitad...]"""
import json, os, sys
sys.path.insert(0, os.getcwd()); os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scoutly.settings")
import django; django.setup()
from pathlib import Path
import numpy as np, yaml
from django.db import transaction
import matching.evaluacion.evaluar as ev
from matching.cobertura import es_formacion, es_solo_anios, es_blando
from matching.ia import obtener_embedder
from matching.politica import POLITICA
from matching.restricciones import RESTRICCIONES
from matching.vectores import de_bytes
from vacantes.fuentes.fixture import FuenteFixture
from vacantes.models import Vacante
D = Path("matching/evaluacion")
salida, mitades = sys.argv[1], sys.argv[2:]
cvs = yaml.safe_load((D / "cvs.yaml").read_text(encoding="utf-8"))
datos = []
with transaction.atomic():
    esc = ev.preparar(cvs, FuenteFixture(D / "vacantes.json"), obtener_embedder())
    for mitad in mitades:
        for par in ev.cargar_pares(D / "pares.yaml", mitad):
            perfil = esc.perfiles[par.cv]
            vac = Vacante.objects.prefetch_related("requisito_set").get(id=par.vacante)
            sim = float(np.dot(np.asarray(perfil.vector, np.float32), np.asarray(vac.vector, np.float32)))
            evid = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))
            reqs = sorted(vac.requisito_set.all(), key=lambda r: r.posicion)
            mr, me = de_bytes(vac.matriz_requisitos, len(reqs)), de_bytes(perfil.matriz_evidencia, len(evid))
            cos = (mr @ me.T).tolist() if len(reqs) and len(evid) else [[0.0] * len(evid) for _ in reqs]
            base = ["formacion" if es_formacion(r.texto) else "experiencia" if es_solo_anios(r.texto)
                    else "blando" if es_blando(r.texto) else "comparable" for r in reqs]
            restr = [{"criterio": x.criterio, "estado": x.estado, "motivo": x.motivo}
                     for r in RESTRICCIONES if (x := r.evaluar(perfil, vac, POLITICA)) is not None]
            datos.append({"mitad": mitad, "cv": par.cv, "vacante": par.vacante, "esperada": par.accion_esperada,
                          "similitud": sim, "titulo": vac.titulo,
                          "requisitos": [{"texto": r.texto, "tipo": r.tipo, "origen": r.origen, "base": b}
                                         for r, b in zip(reqs, base)],
                          "evidencias": evid, "cos": cos, "restricciones": restr})
    transaction.set_rollback(True)
Path(salida).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
print(len(datos), "pares volcados")
