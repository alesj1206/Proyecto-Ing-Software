"""Junta los JSON de resultados/ y escribe REPORTE.md con veredicto por umbral.
Uso: python -m spike.fase0.reporte
"""

import json
from pathlib import Path

from spike.fase0.calidad import UMBRAL_CALIDAD
from spike.fase0.comun import E5_PERSONALIZADOS, MODELOS_EMBEDDING, MODELOS_RERANKER, RESULTADOS

N_VACANTES, REQ_POR_VACANTE, DELTA_DIARIO = 120_000, 9, 3_000
PARES_DECISION, PARES_PAGINA = 40, 20
LIMITES = {  # spec §6
    "carga_inicial_cpu_h": 8,
    "carga_inicial_gpu_h": 2,
    "delta_diario_min": 15,
    "decision_candidato_s": 5,
    "pagina_s": 1.5,
}
DIMENSION = {**E5_PERSONALIZADOS, "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
             "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768, "minishlab/potion-multilingual-128M": 256}
REPORTE = Path(__file__).resolve().parent / "REPORTE.md"


def _segundos_embeber(n_vacantes: int, unidades_por_s: float, docs_por_s: float | None) -> float:
    """Con docs_por_s se embebe la descripción completa; sin él, el vector de la vacante es el
    promedio de sus requisitos más el título (una unidad corta más por vacante)."""
    if docs_por_s is None:
        return n_vacantes * (REQ_POR_VACANTE + 1) / unidades_por_s
    return n_vacantes * REQ_POR_VACANTE / unidades_por_s + n_vacantes / docs_por_s


def _horas_carga(unidades_por_s: float, docs_por_s: float | None, segundos_indice: float) -> float:
    return (_segundos_embeber(N_VACANTES, unidades_por_s, docs_por_s) + segundos_indice) / 3600


def _fila(umbral: str, medido: float, limite: float, cumple: bool | None = None) -> dict:
    return {"umbral": umbral, "limite": limite, "medido": medido, "cumple": medido <= limite if cumple is None else cumple}


def veredictos(r: dict) -> list[dict]:
    filas = [
        _fila("carga_inicial_cpu_h", _horas_carga(r["unidades_por_s"], r.get("docs_por_s"), r["segundos_indice_hnsw"]), LIMITES["carga_inicial_cpu_h"]),
        _fila("delta_diario_min", _segundos_embeber(DELTA_DIARIO, r["unidades_por_s"], r.get("docs_por_s")) / 60, LIMITES["delta_diario_min"]),
        _fila(
            "decision_candidato_s",
            (r["ms_busqueda_p95"] + r["ms_cobertura"] + r.get("ms_fetch_requisitos_3000", 0)) / 1000 + PARES_DECISION / r["pares_por_s"],
            LIMITES["decision_candidato_s"],
        ),
        _fila("pagina_s", PARES_PAGINA / r["pares_por_s"], LIMITES["pagina_s"]),
        _fila("calidad", r["exactitud"], UMBRAL_CALIDAD, cumple=r["exactitud"] >= UMBRAL_CALIDAD),
    ]
    if "gpu_unidades_por_s" in r:
        horas = _horas_carga(r["gpu_unidades_por_s"], r.get("gpu_docs_por_s"), r["segundos_indice_hnsw"])
        filas.append(_fila("carga_inicial_gpu_h", horas, LIMITES["carga_inicial_gpu_h"]))
    return filas


def elegir(candidatos: list[dict]) -> dict | None:
    """El de mayor calidad entre los que cumplen todo. Si difieren en ≤ 2 puntos, desempata en orden:
    más rápido al embeber, mayor recall, mejor reranker, reranker más rápido."""
    validos = [c for c in candidatos if c["cumple_todo"]]
    if not validos:
        return None
    mejor = max(c["exactitud"] for c in validos)
    empatados = [c for c in validos if mejor - c["exactitud"] <= 0.02]
    return max(empatados, key=lambda c: (c["unidades_por_s"], c.get("recall", 0), c.get("calidad_rer", 0), c.get("pares_por_s", 0)))


def _leer(nombre: str) -> dict | None:
    ruta = RESULTADOS / f"{nombre}.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def _slug(m: str) -> str:
    return m.replace("/", "__")


def _calidad_emb(modelo: str) -> tuple[float, bool]:
    variantes = [(_leer(f"calidad_emb_{_slug(modelo)}{suf}"), suf == "_prefijo") for suf in ("", "_prefijo")]
    medidas = [(v["exactitud"], prefijo) for v, prefijo in variantes if v]
    return max(medidas) if medidas else (0.0, False)


ARQUITECTURAS = {
    "hnsw": "pgvector HNSW + requisitos fila por fila",
    "exacta": "búsqueda exacta numpy f32 en memoria + requisitos en bytea por vacante",
}


def _retrieval(arquitectura: str, dim_bench: int) -> dict | None:
    if arquitectura == "hnsw":
        pg = _leer(f"pgvector_{dim_bench}")
        return pg and {"segundos_indice_hnsw": pg["segundos_indice_hnsw"], "ms_busqueda_p95": pg["ms_busqueda_p95"],
                       "ms_fetch_requisitos_3000": pg["ms_fetch_requisitos_3000"], "recall": pg["k3000"]["recall_promedio"]}
    alt = _leer(f"alternativas_{dim_bench}")
    return alt and {"segundos_indice_hnsw": alt["segundos_carga_bytea"], "ms_busqueda_p95": alt["ms_busqueda_exacta_f32_p50"],
                    "ms_fetch_requisitos_3000": alt["ms_fetch_bytea_3000_p50"], "recall": 1.0}


def combinaciones() -> list[dict]:
    cobertura = _leer("cobertura") or {}
    filas = []
    for emb in MODELOS_EMBEDDING:
        rend = _leer(f"rend_embedding_{_slug(emb)}_cpu")
        gpu = _leer(f"rend_embedding_{_slug(emb)}_cuda")
        dim_bench = 768 if DIMENSION[emb] > 384 else 384  # 256 se mide con la tabla de 384 (conservador)
        exactitud_emb, con_prefijo = _calidad_emb(emb)
        if not rend or "error" in rend:
            continue
        for arq in ARQUITECTURAS:
            ret = _retrieval(arq, dim_bench)
            if not ret:
                continue
            for rer in MODELOS_RERANKER:
                cal_rr = _leer(f"calidad_rer_{_slug(rer)}")
                for modo in ("cpu", "cuda"):
                    rr = _leer(f"rend_reranker_{_slug(rer)}_{modo}")
                    if not (rr and cal_rr) or "error" in rr:
                        continue
                    r = {
                        "unidades_por_s": rend["unidades_por_s"],  # vector de vacante = promedio de requisitos + título
                        **{k: v for k, v in ret.items() if k != "recall"},
                        "ms_cobertura": cobertura.get(f"ms_cobertura_{dim_bench}", 0), "pares_por_s": rr["pares_por_s"],
                        "exactitud": min(exactitud_emb, cal_rr["exactitud"]),
                    }
                    if gpu and "error" not in gpu:
                        r |= {"gpu_unidades_por_s": gpu["unidades_por_s"]}
                    vs = veredictos(r)
                    filas.append({
                        "nombre": f"{emb.split('/')[1]} + {rer.split('/')[1]} [{arq}, reranker {modo}]",
                        "embedding": emb, "reranker": rer, "arquitectura": arq, "modo_reranker": modo, "dim": DIMENSION[emb],
                        "prefijo_e5": con_prefijo, "calidad_emb": exactitud_emb, "calidad_rer": cal_rr["exactitud"],
                        "recall": ret["recall"], "veredictos": vs, "pares_por_s": rr["pares_por_s"],
                        "exactitud": r["exactitud"], "unidades_por_s": r["unidades_por_s"],
                        "cumple_todo": all(v["cumple"] for v in vs),
                    })
    return filas


def veredicto_global(filas: list[dict]) -> tuple[str, dict | None]:
    cpu = elegir([f for f in filas if f["modo_reranker"] == "cpu"])
    if cpu:
        return "VIABLE EN CPU", cpu
    gpu = elegir(filas)
    return ("VIABLE SOLO CON GPU PARA EL RERANKER", gpu) if gpu else ("VOLVER AL DISEÑO", None)


def _md(filas: list[dict], estado: str, elegido: dict | None) -> str:
    umbrales = ["carga_inicial_cpu_h", "carga_inicial_gpu_h", "delta_diario_min", "decision_candidato_s", "pagina_s", "calidad"]
    lineas = [
        "# Fase 0 — Reporte de viabilidad (generado por `python -m spike.fase0.reporte`)", "",
        f"**Veredicto global: {estado}**", "",
        (f"Elegido: `{elegido['embedding']}` + `{elegido['reranker']}` · arquitectura **{elegido['arquitectura']}** "
         f"({ARQUITECTURAS[elegido['arquitectura']]}) · reranker en **{elegido['modo_reranker']}**") if elegido
        else "Ninguna combinación cumple todos los umbrales.", "",
        "Límites (spec §6): " + ", ".join(f"{k} ≤ {v}" for k, v in LIMITES.items()) + f", calidad ≥ {UMBRAL_CALIDAD}.", "",
        "Arquitecturas: " + "; ".join(f"**{k}** = {v}" for k, v in ARQUITECTURAS.items()) + ".", "",
        "Solo se listan las combinaciones que cumplen todos los umbrales; el resto queda en el JSON de resultados.", "",
        "| Combinación | dim | cal. emb | cal. rer | recall | pares/s | " + " | ".join(umbrales) + " |",
        "|---|---|---|---|---|---|" + "---|" * len(umbrales),
    ]
    for f in sorted([f for f in filas if f["cumple_todo"]], key=lambda f: (-f["exactitud"], -f["pares_por_s"])):
        v = {x["umbral"]: x for x in f["veredictos"]}
        celdas = [f"{v[u]['medido']:.2f}" if u in v else "—" for u in umbrales]
        lineas.append(f"| {f['nombre']} | {f['dim']} | {f['calidad_emb']:.2f} | {f['calidad_rer']:.2f} | {f['recall']:.2f} | "
                      f"{f['pares_por_s']:.1f} | " + " | ".join(celdas) + " |")
    lineas += ["", "## Por qué falla cada combinación descartada (primer umbral incumplido)", ""]
    motivos = {}
    for f in filas:
        if not f["cumple_todo"]:
            primero = next(x for x in f["veredictos"] if not x["cumple"])
            motivos.setdefault(primero["umbral"], []).append(f"{f['nombre']} ({primero['medido']:.2f} > {primero['limite']})"
                                                              if primero["umbral"] != "calidad" else f"{f['nombre']} ({primero['medido']:.2f})")
    for umbral, nombres in motivos.items():
        lineas.append(f"- **{umbral}** ({len(nombres)}): " + "; ".join(sorted(set(nombres))[:6]) + (" …" if len(nombres) > 6 else ""))
    return "\n".join(lineas) + "\n"


def main() -> None:
    filas = combinaciones()
    estado, elegido = veredicto_global(filas)
    REPORTE.write_text(_md(filas, estado, elegido), encoding="utf-8")
    print(REPORTE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
