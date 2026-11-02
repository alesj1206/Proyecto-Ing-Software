"""Re-decide pares volcados con otra forma de medir la cobertura, sin modelos."""
import json, os, sys
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace as N
sys.path.insert(0, os.getcwd()); os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scoutly.settings")
import django; django.setup()
from matching.cobertura import Cobertura, RequisitoEvaluado
from matching.politica import POLITICA, ContextoDecision, decidir
from matching.restricciones import ResultadoRestriccion

NO_RELEVANTE = "DESCARTAR"


def cobertura(par, puntaje, alto, bajo):
    """puntaje(par, i) -> (valor, j) del requisito i contra la mejor evidencia j."""
    evaluados = []
    for i, r in enumerate(par["requisitos"]):
        valor, j = puntaje(par, i) if par["evidencias"] else (0.0, 0)
        if r["base"] != "comparable":
            estado = r["base"]
        else:
            estado = "cubierto" if valor >= alto else "parcial" if valor >= bajo else "faltante"
        evid = par["evidencias"][j] if estado in ("cubierto", "parcial") else None
        evaluados.append(RequisitoEvaluado(r["texto"], r["tipo"], r["origen"], estado, valor, evid))
    return Cobertura(evaluados)


def coseno(par, i):
    fila = par["cos"][i]
    j = max(range(len(fila)), key=fila.__getitem__)
    return fila[j], j


def predecir(par, puntaje=coseno, alto=None, bajo=None, relevancia=None, politica=POLITICA, fusionar=False):
    alto = politica.tau_alto if alto is None else alto
    bajo = politica.tau_bajo if bajo is None else bajo
    relevancia = politica.tau_relevancia if relevancia is None else relevancia
    if par["similitud"] < relevancia:
        accion = NO_RELEVANTE
    else:
        c = cobertura(par, puntaje, alto, bajo)
        restr = [ResultadoRestriccion(x["criterio"], x["estado"], x["motivo"]) for x in par["restricciones"]]
        reqs = [N(origen=r["origen"]) for r in par["requisitos"]]
        accion = str(decidir(ContextoDecision(c, restr, reqs, politica)).accion)
    if fusionar and accion == "AJUSTAR_CV":
        accion = "POSTULAR"
    return accion


def informe(pares, fusionar=False, **kw):
    aciertos, dist, conf = 0, Counter(), Counter()
    for p in pares:
        pred = predecir(p, fusionar=fusionar, **kw)
        esp = "POSTULAR" if fusionar and p["esperada"] == "AJUSTAR_CV" else p["esperada"]
        aciertos += pred == esp; dist[pred] += 1; conf[(esp, pred)] += 1
    return aciertos / len(pares), dist, conf


if __name__ == "__main__":
    pares = json.load(open(sys.argv[1], encoding="utf-8"))
    for mitad in ("ajuste", "prueba_1", "prueba", "excluida"):
        sub = [p for p in pares if p["mitad"] == mitad]
        if sub:
            print(mitad, len(sub), f"{informe(sub)[0]:.0%}")
