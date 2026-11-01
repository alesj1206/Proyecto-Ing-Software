"""Calidad en español: ¿el modelo pone la evidencia correcta por encima de la trampa?"""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from spike.fase0.comun import RESULTADOS, cargar_embedding, cargar_reranker

UMBRAL_CALIDAD = 0.85
DATOS = Path(__file__).resolve().parent / "datos" / "calidad.yaml"


def cargar_calidad() -> list[dict]:
    return yaml.safe_load(DATOS.read_text(encoding="utf-8"))


def _slug(modelo: str) -> str:
    return modelo.replace("/", "__")


def _resumen(modelo: str, casos: list[dict], aciertos: list[bool], **extra) -> dict:
    total_tipo = Counter(c["tipo"] for c in casos)
    ok_tipo = Counter(c["tipo"] for c, ok in zip(casos, aciertos) if ok)
    return {
        "modelo": modelo,
        **extra,
        "aciertos": sum(aciertos),
        "total": len(casos),
        "exactitud": sum(aciertos) / len(casos),
        "por_tipo": {t: f"{ok_tipo[t]}/{n}" for t, n in total_tipo.items()},
        "fallos": [c["requisito"] for c, ok in zip(casos, aciertos) if not ok],
    }


def _guardar(nombre: str, resultado: dict) -> dict:
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / f"{nombre}.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


def evaluar_embeddings(modelo: str, con_prefijo: bool) -> dict:
    casos = cargar_calidad()
    q, p = ("query: ", "passage: ") if con_prefijo else ("", "")
    textos = [q + c["requisito"] for c in casos] + [p + c["positivo"] for c in casos] + [p + c["negativo"] for c in casos]
    vectores = np.array(list(cargar_embedding(modelo).embed(textos)))
    vectores /= np.linalg.norm(vectores, axis=1, keepdims=True)
    req, pos, neg = np.split(vectores, 3)
    aciertos = ((req * pos).sum(1) > (req * neg).sum(1)).tolist()
    resultado = _resumen(modelo, casos, aciertos, tipo="embedding", con_prefijo=con_prefijo)
    return _guardar(f"calidad_emb_{_slug(modelo)}{'_prefijo' if con_prefijo else ''}", resultado)


def evaluar_reranker(modelo: str) -> dict:
    casos = cargar_calidad()
    rr = cargar_reranker(modelo)
    aciertos = []
    for c in casos:
        s_pos, s_neg = rr.rerank(c["requisito"], [c["positivo"], c["negativo"]])
        aciertos.append(s_pos > s_neg)
    return _guardar(f"calidad_rer_{_slug(modelo)}", _resumen(modelo, casos, aciertos, tipo="reranker"))
