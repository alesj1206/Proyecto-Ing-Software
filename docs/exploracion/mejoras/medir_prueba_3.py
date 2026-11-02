"""Medición única de las 4 variantes preregistradas en PREREGISTRO_prueba_3.md. Uso: medir_prueba_3.py scripts p3.json"""
import json, sys
from collections import Counter
import numpy as np
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, ".")
from simular import informe
from spike.fase0.comun import cargar_embedding

pares = json.load(open(sys.argv[2], encoding="utf-8"))
modelo = cargar_embedding("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "cpu")
textos = sorted({t for p in pares for t in [r["texto"] for r in p["requisitos"]] + p["evidencias"]})
m = np.asarray(list(modelo.embed(textos)), dtype=np.float32); m /= np.linalg.norm(m, axis=1, keepdims=True)
vec = dict(zip(textos, m))
mpnet = []
for p in pares:
    q = dict(p)
    if p["requisitos"] and p["evidencias"]:
        q["cos"] = (np.array([vec[r["texto"]] for r in p["requisitos"]]) @ np.array([vec[e] for e in p["evidencias"]]).T).tolist()
    mpnet.append(q)
VARIANTES = [("V1 actual (MiniLM, .45/.35)", pares, {}), ("V2 fusión (MiniLM)", pares, {"fusionar": True}),
             ("V3 mpnet (.475/.425)", mpnet, {"alto": 0.475, "bajo": 0.425}),
             ("V4 mpnet + fusión (.425/.425)", mpnet, {"alto": 0.425, "bajo": 0.425, "fusionar": True})]
for nombre, datos, kw in VARIANTES:
    t, dist, conf = informe(datos, **kw)
    d_ok = conf[("DESCARTAR", "DESCARTAR")]; d_esp = sum(v for (e, _), v in conf.items() if e == "DESCARTAR")
    print(f"{nombre:32} {t:.0%} ({round(t*len(datos))}/{len(datos)}) | máx acción {max(dist.values())/len(datos):.0%} | "
          f"DESCARTAR {d_ok}/{d_esp} (precisión {d_ok}/{dist['DESCARTAR']}) | {dict(dist)}")
print("clase mayoritaria:", f"{max(Counter(p['esperada'] for p in pares).values())/len(pares):.0%}")
