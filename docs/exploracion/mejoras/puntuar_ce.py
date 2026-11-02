"""Puntajes del cross-encoder bge-reranker-v2-m3 (GPU) para cada requisito × evidencia de los pares volcados."""
import json, sys, time
from pathlib import Path
from fastembed.rerank.cross_encoder import TextCrossEncoder
entrada, salida = sys.argv[1], sys.argv[2]
modelo = TextCrossEncoder("BAAI/bge-reranker-v2-m3", cache_dir=str(Path.home() / ".cache" / "scoutly-modelos"),
                          providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
pares = json.load(open(entrada, encoding="utf-8"))
inicio, n = time.time(), 0
for p in pares:
    p["ce"] = []
    for r in p["requisitos"]:
        if r["base"] == "comparable" and p["evidencias"]:
            p["ce"].append([float(x) for x in modelo.rerank(r["texto"], p["evidencias"])]); n += len(p["evidencias"])
        else:
            p["ce"].append([0.0] * len(p["evidencias"]))
Path(salida).write_text(json.dumps(pares, ensure_ascii=False), encoding="utf-8")
print(f"{n} pares requisito×evidencia en {time.time()-inicio:.0f} s")
