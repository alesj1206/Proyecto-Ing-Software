"""¿Un modelo de embeddings más fuerte mejora la cobertura? Re-embebe requisitos y evidencias de los pares volcados con
otro modelo y elige umbrales con validación cruzada por set (3 sets para elegir, el 4.º para medir).
Uso: exp_modelos.py carpeta_de_scripts vistos.json p2.json"""
import itertools, json, sys, time
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, ".")
from simular import informe

CACHE = str(Path.home() / ".cache" / "scoutly-modelos")
MODELOS = {"MiniLM-L12 (actual)": None,
           "multilingual-e5-small": ("intfloat/multilingual-e5-small", "query: "),
           "multilingual-e5-base": ("intfloat/multilingual-e5-base", "query: "),
           "mpnet-base-v2": ("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "")}
SETS = ("ajuste", "prueba_1", "prueba", "prueba_2")
pares = [p for f in sys.argv[2:] for p in json.load(open(f, encoding="utf-8")) if p["mitad"] != "excluida"]


def reembeber(nombre, prefijo):
    from spike.fase0.comun import cargar_embedding  # registra e5 desde el ONNX oficial (como en la Fase 0)
    modelo = cargar_embedding(nombre, "cpu")
    textos = sorted({t for p in pares for t in [r["texto"] for r in p["requisitos"]] + p["evidencias"]})
    m = np.asarray(list(modelo.embed([prefijo + t for t in textos])), dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    vec = dict(zip(textos, m))
    copia = []
    for p in pares:
        q = dict(p)
        R = np.array([vec[r["texto"]] for r in p["requisitos"]]) if p["requisitos"] else np.zeros((0, m.shape[1]))
        E = np.array([vec[e] for e in p["evidencias"]]) if p["evidencias"] else np.zeros((0, m.shape[1]))
        q["cos"] = (R @ E.T).tolist() if len(R) and len(E) else [[0.0] * len(p["evidencias"]) for _ in p["requisitos"]]
        copia.append(q)
    return copia


def validacion_cruzada(datos, fusionar):
    rejilla = [(a, b) for a, b in itertools.product(np.arange(0.30, 0.95, 0.025), np.arange(0.20, 0.90, 0.025)) if b < a]
    aciertos = 0
    for s in SETS:
        entrena = [p for p in datos if p["mitad"] != s]; prueba = [p for p in datos if p["mitad"] == s]
        a, b = max(rejilla, key=lambda ab: informe(entrena, fusionar=fusionar, alto=ab[0], bajo=ab[1])[0])
        aciertos += informe(prueba, fusionar=fusionar, alto=a, bajo=b)[0] * len(prueba)
    return aciertos / len(datos)


for etiqueta, spec in MODELOS.items():
    inicio = time.time()
    datos = pares if spec is None else reembeber(*spec)
    r5, rf = validacion_cruzada(datos, False), validacion_cruzada(datos, True)
    print(f"{etiqueta:24} 5 acciones {r5:.0%} | con fusión {rf:.0%} | {time.time()-inicio:.0f} s", flush=True)
