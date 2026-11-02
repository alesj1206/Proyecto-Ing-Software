import json, sys
from collections import Counter
from types import SimpleNamespace as N
sys.path.insert(0, sys.argv[1])
import simular
from simular import informe
from lexico import nombra_alguna, herramientas, _norm, EQUIVALENTES
from matching.cobertura import Cobertura, RequisitoEvaluado

def cobertura_lexica(par, puntaje, alto, bajo):
    base = ORIGINAL(par, puntaje, alto, bajo)
    cv = " ".join(par["evidencias"])
    nuevos = []
    for r in base.requisitos:
        estado, evid = r.estado, r.evidencia
        if r.cuenta and estado in ("cubierto", "parcial"):
            hay = nombra_alguna(r.texto, cv)
            if hay is False:
                estado, evid = "faltante", None
            elif hay and estado == "cubierto":
                exactas = [h for h in herramientas(r.texto) if f" {h} " in " " + _norm(cv) + " "]
                if not exactas and "power bi" not in _norm(cv):
                    estado = "parcial"  # lo nombra distinto: hacerlo explícito
        nuevos.append(RequisitoEvaluado(r.texto, r.tipo, r.origen, estado, r.similitud, evid))
    return Cobertura(nuevos)

original = ORIGINAL = simular.cobertura
pares = []
for f in sys.argv[2:]:
    pares += [p for p in json.load(open(f, encoding="utf-8")) if p["mitad"] != "excluida"]
grupos = {m: [p for p in pares if p["mitad"] == m] for m in ("ajuste", "prueba_1", "prueba", "prueba_2")}
for nombre, gate in (("coseno", False), ("coseno + compuerta léxica", True)):
    simular.cobertura = cobertura_lexica if gate else original
    for fus in (False, True):
        r = {m: informe(g, fusionar=fus)[0] for m, g in grupos.items()}
        t, d, c = informe(pares, fusionar=fus)
        print(f"{nombre:28} fusion={fus!s:5} todas {t:.0%} | " + " ".join(f"{m} {v:.0%}" for m, v in r.items()) + f" | máx {max(d.values())/len(pares):.0%}")
simular.cobertura = original
