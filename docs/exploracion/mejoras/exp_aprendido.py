"""¿Le gana un clasificador aprendido a las reglas? Regresión logística multinomial (numpy) sobre las señales que ya
calcula el decisor, con validación cruzada por set (entrena con 3 sets, evalúa en el que no vio).
Uso: exp_aprendido.py carpeta_de_scripts vistos.json p2.json"""
import json, sys
import numpy as np
sys.path.insert(0, sys.argv[1])
from simular import cobertura, coseno, predecir
from vacantes.extraccion import requisitos_insuficientes
from types import SimpleNamespace as N

ACCIONES = ["POSTULAR", "AJUSTAR_CV", "CERRAR_BRECHA", "DESCARTAR", "SIN_DATOS"]


def senales(p):
    c = cobertura(p, coseno, 0.45, 0.35)
    contables = [r for r in c.requisitos if r.cuenta]
    sims = [r.similitud for r in contables] or [0.0]
    violadas = sum(x["estado"] == "no_cumple" for x in p["restricciones"])
    parciales_restr = sum(x["estado"] == "parcial" for x in p["restricciones"])
    ilegible = requisitos_insuficientes([N(origen=r["origen"]) for r in p["requisitos"]])
    return [p["similitud"], len(contables), c.obligatorios_cubiertos, len(c._contables("parcial")),
            len(c.faltantes_obligatorios), c.porcentaje / 100, min(sims), float(np.mean(sims)), violadas,
            parciales_restr, float(ilegible), float(not contables)]


def entrenar(X, y, k, l2=1.0, pasos=3000, tasa=0.1):
    W = np.zeros((X.shape[1], k)); b = np.zeros(k)
    Y = np.eye(k)[y]
    for _ in range(pasos):
        z = X @ W + b; z -= z.max(axis=1, keepdims=True)
        P = np.exp(z); P /= P.sum(axis=1, keepdims=True)
        G = (P - Y) / len(X)
        W -= tasa * (X.T @ G + l2 * W / len(X)); b -= tasa * G.sum(axis=0)
    return W, b


def evaluar(pares, fusionar):
    acciones = [a for a in ACCIONES if not (fusionar and a == "AJUSTAR_CV")]
    etiqueta = lambda a: "POSTULAR" if fusionar and a == "AJUSTAR_CV" else a
    X = np.array([senales(p) for p in pares]); y = np.array([acciones.index(etiqueta(p["esperada"])) for p in pares])
    sets = [p["mitad"] for p in pares]
    print(f"\n{'fusión' if fusionar else '5 acciones'}:  set (n) | reglas | aprendido")
    tot_r = tot_a = 0
    for s in ("ajuste", "prueba_1", "prueba", "prueba_2"):
        test = np.array([m == s for m in sets]); train = ~test
        mu, sd = X[train].mean(0), X[train].std(0) + 1e-9
        W, b = entrenar((X[train] - mu) / sd, y[train], len(acciones))
        pred = ((X[test] - mu) / sd @ W + b).argmax(1)
        reglas = np.array([acciones.index(etiqueta(predecir(p, fusionar=fusionar))) for p, t in zip(pares, test) if t])
        a_r, a_a = (reglas == y[test]).mean(), (pred == y[test]).mean()
        tot_r += (reglas == y[test]).sum(); tot_a += (pred == y[test]).sum()
        print(f"  {s:9} ({test.sum():2}) | {a_r:5.0%} | {a_a:5.0%}")
    print(f"  {'total':9} ({len(pares)}) | {tot_r/len(pares):5.0%} | {tot_a/len(pares):5.0%}")


pares = [p for f in sys.argv[2:] for p in json.load(open(f, encoding="utf-8")) if p["mitad"] != "excluida"]
evaluar(pares, fusionar=False)
evaluar(pares, fusionar=True)
