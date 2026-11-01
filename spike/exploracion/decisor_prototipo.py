"""Prototipo DESECHABLE del decisor sobre las 18 vacantes reales de Magneto del fixture y 3 perfiles
ficticios. Objetivo: ver qué le diría de verdad a un candidato, no código para la app.
Uso (venv GPU): python -m spike.exploracion.decisor_prototipo
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from spike.fase0.comun import cargar_embedding, cargar_reranker

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "vacantes" / "fixtures" / "vacantes_magneto.json"
SALIDA = RAIZ / "docs" / "exploracion" / "prototipo-decisor-resultados.md"
EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANKER = "BAAI/bge-reranker-v2-m3"

PISTAS_REQUISITO = re.compile(
    r"\b(experiencia|conocimient|manejo|dominio|formaci[oó]n|profesional|t[eé]cnic|tecn[oó]log|años|"
    r"herramientas|deseable|requiere|requisitos|habilidad|certificaci|ingl[eé]s|estudiante|carreras? afines)", re.I)
PISTAS_DESEABLE = re.compile(r"\b(deseable|plus|valorable|ideal|preferible)", re.I)
MODALIDAD_OPUESTA = {("Remoto", "Presencial"), ("Presencial", "Remoto")}


@dataclass
class Perfil:
    nombre: str
    evidencias: list[str]
    anios: int
    modalidad: str
    ciudades: list[str]
    salario_min: int


@dataclass
class Resultado:
    vacante: dict
    accion: str
    solidez: str
    motivos: list[str]
    similitud: float = 0.0
    cobertura: float = 0.0
    relevancia: float | None = None
    cubiertos: list[tuple[str, str, float]] = field(default_factory=list)
    parciales: list[tuple[str, str, float]] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)


PERFILES = [
    Perfil("Analista de datos junior (Medellín)", [
        "Construí tableros en Power BI para el área comercial de una cadena de tiendas",
        "Consultas SQL sobre la base de ventas para reportes mensuales",
        "Limpieza y cruce de datos en Excel con tablas dinámicas y BUSCARV",
        "Automatización de reportes con macros de Excel",
        "Curso de Python para análisis de datos con pandas",
        "Tecnólogo en sistemas, 1 año y medio de experiencia",
        "Presenté indicadores semanales a la gerencia",
    ], anios=1, modalidad="Híbrido", ciudades=["medellín", "sabaneta", "itagui", "envigado"], salario_min=2_500_000),
    Perfil("QA tester semi-senior (Bogotá)", [
        "Diseño y ejecución de casos de prueba funcionales y de regresión",
        "Automatización de pruebas con Selenium y Python",
        "Pruebas de APIs con Postman y documentación de resultados",
        "Reporte y seguimiento de bugs en Jira bajo Scrum",
        "Pruebas de rendimiento básicas con JMeter",
        "3 años de experiencia en el sector financiero",
        "Ingeniero de sistemas",
    ], anios=3, modalidad="Presencial", ciudades=["bogotá"], salario_min=3_000_000),
    Perfil("Diseñadora UX/UI junior (Medellín)", [
        "Prototipos y wireframes en Figma para una app de domicilios",
        "Entrevistas con usuarios y mapas de experiencia (journey maps)",
        "Piezas gráficas en Illustrator y Photoshop",
        "Diseño de interfaces móviles siguiendo un sistema de diseño",
        "Estudiante de último semestre de diseño de interacción",
    ], anios=0, modalidad="Presencial", ciudades=["medellín", "itagui", "envigado"], salario_min=1_500_000),
]

# v2: calibrados con el set de 40 casos (MiniLM: τ=0,50 → 65% positivos / 2% negativos; τ=0,40 → 85% / 10%).
TAU_ALTO, TAU_BAJO = 0.50, 0.40
TAU_RELEVANCIA = 0.40  # similitud perfil↔vacante mínima para que la vacante entre al decisor (spec §5.7)
RUIDO = re.compile(r"(\$\s?\d|importante empresa|somos una|te apasiona|únete|nos encontramos|compañía (global|canadiense)|"
                   r"ubicaci[oó]n:|jornada|horario|vacantes:|salario|apto para personas)", re.I)
FORMACION = re.compile(r"^(formaci[oó]n|profesional (en|o)|t[eé]cnico|tecn[oó]logo|ingenier[oa]|estudiante|carreras)", re.I)


def extraer_requisitos(v: dict) -> list[tuple[str, bool]]:
    """(texto, obligatorio). Oraciones y viñetas con pistas de requisito + etiquetas que trae Magneto."""
    trozos = re.split(r"(?<=[.;:!?])\s+|\s[-–•·]\s|\n", v["descripcion"])
    unidades = []
    for t in trozos:
        t = t.strip(" -–•·.")
        # v2: sin ruido (salario, presentación de la empresa) y sin formación, que es un dato estructurado:
        # compararla por similitud llevó a sugerirle a un tecnólogo "haz explícito que eres profesional".
        if (3 <= len(t.split()) <= 30 and PISTAS_REQUISITO.search(t) and "Palabras clave" not in t
                and not RUIDO.search(t) and not FORMACION.search(t)):
            unidades.append((t, not PISTAS_DESEABLE.search(t)))
    unidades += [(r, True) for r in v["requisitos"] if r.lower() not in " ".join(u for u, _ in unidades).lower()]
    return unidades


def restricciones(p: Perfil, v: dict) -> list[str]:
    violadas = []
    if (v["modalidad"], p.modalidad) in MODALIDAD_OPUESTA:
        violadas.append(f"modalidad {v['modalidad']} y buscas {p.modalidad}")
    if v["modalidad"] != "Remoto" and not any(c in v["ubicacion"].lower() for c in p.ciudades):
        violadas.append(f"está en {v['ubicacion']}, fuera de tus ciudades")
    sal = (v.get("salario") or {}).get("max")
    if sal and sal < p.salario_min:
        violadas.append(f"ofrece {sal:,.0f} y tu mínimo es {p.salario_min:,.0f}".replace(",", "."))
    exp = v.get("experienciaMinima")
    if exp and p.anios < 0.5 * exp:
        violadas.append(f"pide {exp} años y tienes {p.anios}")
    return violadas


def decidir(p: Perfil, v: dict, reqs, sims_req, evidencias, sim_doc) -> Resultado:
    r = Resultado(vacante=v, accion="", solidez="", motivos=[], similitud=sim_doc)
    for (texto, oblig), fila in zip(reqs, sims_req):
        j = int(fila.argmax())
        if fila[j] >= TAU_ALTO:
            r.cubiertos.append((texto, evidencias[j], float(fila[j])))
        elif fila[j] >= TAU_BAJO:
            r.parciales.append((texto, evidencias[j], float(fila[j])))
        elif oblig:
            r.faltantes.append(texto)
    total = len(r.cubiertos) + len(r.parciales) + len(r.faltantes)
    r.cobertura = (len(r.cubiertos) + 0.5 * len(r.parciales)) / total if total else 0.0
    violadas = restricciones(p, v)
    if total == 0:  # v2: sin requisitos legibles NO es POSTULAR (en v1 salía "cubres 0 de 0")
        r.accion, r.solidez, r.motivos = "SIN_DATOS", "baja", ["la vacante no trae requisitos legibles: revísala tú"]
        return r
    if violadas:
        r.accion, r.motivos = "DESCARTAR", violadas
    elif len(r.faltantes) >= 3:
        r.accion, r.motivos = "DESCARTAR", [f"te faltan {len(r.faltantes)} requisitos obligatorios"]
    elif r.faltantes:
        r.accion, r.motivos = "CERRAR_BRECHA", [f"te falta: {f}" for f in r.faltantes]
    elif r.parciales:
        r.accion, r.motivos = "AJUSTAR_CV", [f"hazlo explícito: «{t}» (tu evidencia: «{e}»)" for t, e, _ in r.parciales]
    else:
        r.accion, r.motivos = "POSTULAR", [f"cubres {len(r.cubiertos)} de {total} requisitos"]
    sin_datos = sum(x is None for x in ((v.get("salario") or {}).get("max"), v.get("experienciaMinima")))
    pocos = total <= 1
    r.solidez = "baja" if pocos or sin_datos == 2 else ("media" if sin_datos == 1 else "alta")
    if pocos:
        r.motivos.append("la vacante trae muy pocos requisitos legibles")
    return r


def main() -> None:
    vacantes = json.loads(FIXTURE.read_text(encoding="utf-8"))
    emb = cargar_embedding(EMBEDDING, "cuda")
    rer = cargar_reranker(RERANKER, "cuda")
    hoy = max(date.fromisoformat(v["fechaPublicacion"]) for v in vacantes)  # "hoy" = la vacante más reciente del fixture

    def vec(textos):
        m = np.array(list(emb.embed(textos)), dtype=np.float32)
        return m / np.linalg.norm(m, axis=1, keepdims=True)

    salida = ["# Prototipo del decisor sobre vacantes reales de Magneto", "",
              f"18 vacantes reales (fixture de v2, texto recortado a 500 caracteres) × 3 perfiles ficticios. "
              f"Embeddings `{EMBEDDING}`, reranker `{RERANKER}` (GPU). **v2**: τ_alto={TAU_ALTO}, τ_bajo={TAU_BAJO} "
              f"(calibrados), τ_relevancia={TAU_RELEVANCIA}, sin ruido ni formación en los requisitos, SIN_DATOS en vez de POSTULAR "
              f"cuando no hay requisitos. \"Hoy\" = {hoy} (fecha más reciente del fixture).", ""]
    todas_sims = []
    for p in PERFILES:
        ev = vec(p.evidencias)
        perfil_vec = ev.mean(0)
        perfil_vec /= np.linalg.norm(perfil_vec)
        resultados = []
        for v in vacantes:
            reqs = extraer_requisitos(v)
            if reqs:
                rq = vec([t for t, _ in reqs])
                sims = rq @ ev.T
                todas_sims.extend(sims.max(1).tolist())
                doc = vec([v["titulo"]])[0] + rq.mean(0)
            else:
                sims, doc = np.zeros((0, len(p.evidencias))), vec([v["titulo"]])[0]
            doc /= np.linalg.norm(doc)
            resultados.append(decidir(p, v, reqs, sims, p.evidencias, float(doc @ perfil_vec)))
        candidatos = [r for r in resultados if r.accion in ("POSTULAR", "AJUSTAR_CV")]
        if candidatos:
            resumen_perfil = "; ".join(p.evidencias)
            resumenes = [f"{r.vacante['titulo']}. " + "; ".join(t for t, *_ in r.cubiertos + r.parciales) for r in candidatos]
            for r, s in zip(candidatos, rer.rerank(resumen_perfil, resumenes)):
                r.relevancia = float(s)
        relevantes = [r for r in resultados if r.similitud >= TAU_RELEVANCIA]
        irrelevantes = len(resultados) - len(relevantes)
        sims_doc = sorted((round(r.similitud, 2) for r in resultados), reverse=True)
        resultados = relevantes
        orden = {"POSTULAR": 0, "AJUSTAR_CV": 1, "CERRAR_BRECHA": 2, "SIN_DATOS": 3, "DESCARTAR": 4}
        resultados.sort(key=lambda r: (orden[r.accion], -(r.relevancia or r.similitud)))

        plan, empresas = [], set()
        for r in resultados:
            if r.accion in ("POSTULAR", "AJUSTAR_CV") and r.vacante["empresa"] not in empresas and len(plan) < 3:
                plan.append(r)
                empresas.add(r.vacante["empresa"])

        brechas = Counter(f.lower()[:60] for r in resultados if r.accion in ("CERRAR_BRECHA",) for f in r.faltantes)
        conteo = Counter(r.accion for r in resultados)
        salida += [f"## {p.nombre}", "",
                   f"Similitud perfil↔vacante (las 18): {sims_doc}. Fuera por relevancia (< {TAU_RELEVANCIA}): {irrelevantes}.", "",
                   "Distribución de las relevantes: " + ", ".join(f"{a} {conteo.get(a, 0)}" for a in orden), "",
                   "**Plan de hoy** (máx. 3, una por empresa): " + ("; ".join(
                       f"{r.vacante['titulo']} — {r.vacante['empresa']} ({r.accion}, solidez {r.solidez}, "
                       f"{(hoy - date.fromisoformat(r.vacante['fechaPublicacion'])).days} días publicada)" for r in plan) or "ninguna"), "",
                   "| Acción | Vacante | Empresa | Cobertura | Solidez | Motivo principal |", "|---|---|---|---|---|---|"]
        for r in resultados:
            salida.append(f"| {r.accion} | {r.vacante['titulo'][:55]} | {r.vacante['empresa'][:25]} | {r.cobertura:.0%} | "
                          f"{r.solidez} | {(r.motivos[0] if r.motivos else '')[:140]} |")
        ajustes = [r for r in resultados if r.accion == "AJUSTAR_CV"][:2]
        for r in ajustes:
            salida += ["", f"**Sugerencias de CV para «{r.vacante['titulo']}»:**"] + [f"- {m}" for m in r.motivos[:3]]
        if brechas:
            salida += ["", "**Brechas más repetidas (plan de aprendizaje):** " + "; ".join(f"{b} ({n})" for b, n in brechas.most_common(4))]
        salida.append("")

    s = np.array(todas_sims)
    salida += ["## Distribución de similitud máxima requisito→evidencia (para calibrar τ)", "",
               f"n={len(s)}, p10={np.percentile(s, 10):.2f}, p25={np.percentile(s, 25):.2f}, p50={np.percentile(s, 50):.2f}, "
               f"p75={np.percentile(s, 75):.2f}, p90={np.percentile(s, 90):.2f}", ""]
    SALIDA.write_text("\n".join(salida), encoding="utf-8")
    print("\n".join(salida))


if __name__ == "__main__":
    main()
