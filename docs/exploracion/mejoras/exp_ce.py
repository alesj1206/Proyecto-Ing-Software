import json, math, sys, itertools
sys.path.insert(0, sys.argv[2]); from simular import informe
pares = [p for p in json.load(open(sys.argv[1], encoding="utf-8")) if p["mitad"] != "excluida"]
def ce(par, i):
    fila = par["ce"][i]; j = max(range(len(fila)), key=fila.__getitem__)
    return 1 / (1 + math.exp(-fila[j])), j
grupos = {m: [p for p in pares if p["mitad"] == m] for m in ("ajuste", "prueba_1", "prueba")}
def linea(nombre, **kw):
    r = {m: informe(g, **kw)[0] for m, g in grupos.items()}; tot, dist, _ = informe(pares, **kw)
    print(f"{nombre:38} ajuste {r['ajuste']:.0%} p1 {r['prueba_1']:.0%} p {r['prueba']:.0%} | todas {tot:.0%} | AJ {dist['AJUSTAR_CV']} SD {dist['SIN_DATOS']}")
    return tot
linea("coseno (actual .3)")
linea("coseno + fusionar P/A", fusionar=True)
mejores = []
for alto, bajo in itertools.product([0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], [0.02, 0.05, 0.1, 0.2, 0.3, 0.4]):
    if bajo >= alto: continue
    tot, dist, _ = informe(pares, puntaje=ce, alto=alto, bajo=bajo)
    mejores.append((tot, alto, bajo, dist["AJUSTAR_CV"]))
for tot, alto, bajo, aj in sorted(mejores, reverse=True)[:6]:
    linea(f"CE alto {alto} bajo {bajo}", puntaje=ce, alto=alto, bajo=bajo)
t, a, b, _ = max(mejores)
linea(f"CE mejor + fusionar", puntaje=ce, alto=a, bajo=b, fusionar=True)
