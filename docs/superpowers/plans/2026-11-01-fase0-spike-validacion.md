# Fase 0 — Spike de validación: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demostrar con mediciones reales en esta máquina si el stack del decisor (Postgres+pgvector, fastembed con embeddings y reranker) cumple los umbrales de viabilidad del diseño, y elegir los modelos.

**Architecture:** Un directorio `spike/fase0/` autocontenido con scripts de medición, cada uno escribe un JSON en `spike/fase0/resultados/`. Un script final junta esos JSON en `spike/fase0/REPORTE.md` con veredicto por umbral. Postgres corre en Podman (imagen oficial de pgvector). Nada de esto es la app: es evidencia para decidir y para el informe.

**Tech Stack:** Python 3.14 (`.venv` del repo), fastembed 0.9.x (ONNX, sin torch), numpy 2.x, psycopg 3 + pgvector 0.5 (cliente), Postgres 17 + pgvector ≥ 0.8 (servidor, Podman), pytest.

**Spec:** `docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md` (secciones 3, 6, 8 y 9).

## Global Constraints

- Gratis, open source y local. No se usa torch.
- Python 3.14 del `.venv` del repo. Instalar siempre con `.venv/bin/python -m pip` (el script `.venv/bin/pip` tiene un shebang roto de cuando se movió la carpeta).
- Umbrales de viabilidad (copiados del spec §6), proyectados a 120k vacantes en esta máquina:
  - carga inicial de 120k vacantes (~9 unidades + 1 doc cada una, ≈ 1,2M embeddings): **≤ 8 h CPU**, **≤ 2 h GPU**;
  - delta diario de 3.000 vacantes nuevas: **≤ 15 min**;
  - decisión por candidato (≈ 3.000 relevantes + reranking de las primeras páginas, ~40 pares): **≤ 5 s CPU**;
  - página siguiente ordenada bajo demanda (~20 pares): **≤ 1,5 s**.
- Embeddings: multilingües, buen rendimiento en español, soportados por fastembed, dimensión ≤ 768, licencia apta para uso académico. Candidatos: `intfloat/multilingual-e5-small`, `intfloat/multilingual-e5-base`, `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Reranker: cross-encoder multilingüe soportado por `fastembed.rerank.cross_encoder.TextCrossEncoder`. Candidatos: `jinaai/jina-reranker-v2-base-multilingual` (CC-BY-NC, se documenta) y el `BAAI/bge-reranker-*` que fastembed soporte.
- Si ningún candidato cumple: se prueba la variante más pequeña. Si ni esa cumple, **se detiene la fase y se vuelve al diseño**.
- La caché de modelos de fastembed vive en `~/.cache/scoutly-modelos` (variable `FASTEMBED_CACHE_PATH`), nunca en `/tmp`, para no volver a descargar.

## Review Focus

1. **Prefijos de e5**: los modelos e5 esperan `query: ` / `passage: `. Sin ellos la calidad cae en silencio. El test de calidad de la Tarea 3 corre e5 con y sin prefijo y el reporte muestra ambos.
2. **Textos largos**: las descripciones completas de Magneto superan el límite de 512 tokens del modelo y se truncan. La Tarea 4 mide el rendimiento con la distribución real de longitudes (unidades cortas y documentos largos), no solo con frases cortas.
3. **Acentos y variantes**: "Gestión de nómina" frente a "gestion de nomina", "Node.js" frente a "NodeJS". El set de calidad de la Tarea 3 incluye estos pares.
4. **`hnsw.iterative_scan` es por sesión**: si no se activa con `SET` en la misma conexión, la búsqueda por umbral devuelve como máximo `ef_search` filas y parece que "no hay más vacantes". La Tarea 5 tiene un test que pide más filas que `ef_search` y exige recibirlas.
5. **Primera ejecución sin caché**: la descarga del modelo no debe contaminar la medición. Cada benchmark hace un calentamiento (carga + 1 lote) que no se cronometra.

---

### Task 1: Postgres 17 + pgvector en Podman

**Files:**
- Create: `infra/postgres/levantar.sh`
- Create: `infra/postgres/.env.ejemplo`
- Create: `spike/fase0/test_postgres.py`
- Modify: `.gitignore` (agregar `infra/postgres/.env`, `spike/fase0/resultados/*.json`)

**Interfaces:**
- Produces: contenedor `scoutly-postgres` (imagen `docker.io/pgvector/pgvector:pg17`, volumen `scoutly_pgdata`, puerto `5433` del host → `5432`), base `scoutly`, usuario `scoutly`. Variables en `infra/postgres/.env`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT=5433`. Función `spike/fase0/comun.py::conectar() -> psycopg.Connection` (lee ese `.env`) que usan las tareas 5 y 6.

- [ ] **Step 1: Write the failing test** `spike/fase0/test_postgres.py`

```python
def test_pgvector_disponible_y_reciente():
    with conectar() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
    assert tuple(map(int, version.split("."))) >= (0, 8, 0)

def test_halfvec_soportado():
    with conectar() as c:
        assert c.execute("SELECT '[1,2,3]'::halfvec(3)").fetchone()[0] is not None
```

- [ ] **Step 2:** `.venv/bin/python -m pytest spike/fase0/test_postgres.py -v`. Expected: FAIL (no existe `comun.conectar` ni el contenedor).
- [ ] **Step 3:** Escribir `levantar.sh`, que es idempotente: si el contenedor existe lo arranca y si no, lo crea con `podman run -d --name scoutly-postgres --env-file infra/postgres/.env -p 5433:5432 -v scoutly_pgdata:/var/lib/postgresql/data docker.io/pgvector/pgvector:pg17`. Después espera a `pg_isready`. Copiar `.env.ejemplo` → `.env` con una contraseña local. Instalar `psycopg[binary] pgvector pytest numpy` en el `.venv`. Implementar `comun.conectar()`.
- [ ] **Step 4:** `bash infra/postgres/levantar.sh && .venv/bin/python -m pytest spike/fase0/test_postgres.py -v`. Expected: 2 passed.
- [ ] **Step 5: Commit** — `git add infra/postgres spike/fase0/comun.py spike/fase0/test_postgres.py .gitignore && git commit -m "chore(fase0): postgres 17 + pgvector en podman"`

### Task 2: Generador de textos realistas

**Files:**
- Create: `spike/fase0/textos.py`
- Create: `spike/fase0/test_textos.py`

**Interfaces:**
- Consumes: `vacantes/fixtures/vacantes_magneto.json` (campos `titulo`, `descripcion`, `requisitos`).
- Produces: `unidades_requisito(n: int, semilla: int = 0) -> list[str]` (frases cortas de 5 a 25 palabras), `documentos_vacante(n: int, semilla: int = 0) -> list[str]` (300 a 2.500 caracteres) y `unidades_evidencia(n: int, semilla: int = 0) -> list[str]`. Son determinísticas por semilla. Se arman por combinación de plantillas en español (cargos, herramientas y verbos de varias industrias: tecnología, contabilidad, comercial, salud, logística, diseño) más los títulos y descripciones reales del fixture.

- [ ] **Step 1: Write the failing test**

```python
def test_deterministico_y_tamanos():
    assert unidades_requisito(50, 1) == unidades_requisito(50, 1)
    docs = documentos_vacante(200, 2)
    assert len(docs) == 200 and all(300 <= len(d) <= 2500 for d in docs)
    assert all(5 <= len(u.split()) <= 25 for u in unidades_requisito(200, 3))

def test_variedad():
    assert len(set(unidades_requisito(1000, 4))) >= 900
```

- [ ] **Step 2:** Correr `.venv/bin/python -m pytest spike/fase0/test_textos.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar las tres funciones en `textos.py` (`random.Random(semilla)`, sin dependencias nuevas).
- [ ] **Step 4:** Correr el test. Expected: 2 passed.
- [ ] **Step 5: Commit** — `git commit -m "chore(fase0): generador de textos realistas para benchmarks"`

### Task 3: Set de calidad en español y evaluación de modelos

**Files:**
- Create: `spike/fase0/datos/calidad.yaml`
- Create: `spike/fase0/calidad.py`
- Create: `spike/fase0/test_calidad.py`

**Interfaces:**
- Consumes: `fastembed.TextEmbedding`, `fastembed.rerank.cross_encoder.TextCrossEncoder`.
- Produces: `evaluar_embeddings(modelo: str, con_prefijo: bool) -> dict` y `evaluar_reranker(modelo: str) -> dict`. Cada uno devuelve `{"modelo", "aciertos", "total", "exactitud"}` y escribe `resultados/calidad_<modelo>.json`. Constante `UMBRAL_CALIDAD = 0.85` (umbral elegido por este plan: el spec pide "buen rendimiento en español" sin dar un número).

`calidad.yaml` tiene **40 tripletas** `{requisito, positivo, negativo}`. Un acierto es `sim(requisito, positivo) > sim(requisito, negativo)`. Deben incluir, como mínimo:
- variantes de escritura: "Node.js" / "NodeJS", "Excel avanzado" / "manejo avanzado de hojas de cálculo";
- sinónimos de dominio: "atención al cliente" / "servicio al cliente"; "NIIF" / "normas internacionales de información financiera";
- experiencia implícita: requisito "liderazgo de equipos", positivo "coordiné un equipo de 6 analistas";
- negativos difíciles: "Java" con positivo "Spring Boot" y negativo "JavaScript en el frontend"; "enfermería" con negativo "veterinaria";
- textos sin acentos frente a textos con acentos;
- al menos 4 industrias que no sean de tecnología.

- [ ] **Step 1: Write the failing test** (marcado `@pytest.mark.lento`, porque descarga modelos)

```python
@pytest.mark.parametrize("modelo", MODELOS_EMBEDDING)
def test_embeddings_superan_umbral(modelo):
    r = evaluar_embeddings(modelo, con_prefijo=modelo.startswith("intfloat/"))
    assert r["total"] == 40
    assert "exactitud" in r   # el veredicto lo emite el reporte; aquí solo se exige que mida

def test_yaml_cubre_casos_obligatorios():
    casos = cargar_calidad()
    assert len(casos) == 40
    assert any("nodejs" in c["positivo"].lower().replace(".", "") for c in casos)
```

- [ ] **Step 2:** Correr `.venv/bin/python -m pytest spike/fase0/test_calidad.py -v -m "not lento"`. Expected: FAIL.
- [ ] **Step 3:** Escribir el YAML (agregar `pyyaml` al `.venv`) e implementar `calidad.py`. Usa similitud coseno sobre vectores normalizados. Los modelos e5 se evalúan dos veces: con `query: `/`passage: ` y sin prefijo. El reranker puntúa `(requisito, positivo)` frente a `(requisito, negativo)`. Exportar `FASTEMBED_CACHE_PATH=~/.cache/scoutly-modelos`.
- [ ] **Step 4:** Correr `.venv/bin/python -m pytest spike/fase0/test_calidad.py -v` (incluye los lentos). Expected: todos pasan, y existe un JSON por modelo en `resultados/`.
- [ ] **Step 5: Commit** — `git commit -m "chore(fase0): set de calidad en español y evaluación de modelos"`

### Task 4: Benchmark de rendimiento de embeddings y reranker (CPU)

**Files:**
- Create: `spike/fase0/bench_modelos.py`

**Interfaces:**
- Consumes: `textos.*` (Tarea 2).
- Produces: CLI `python -m spike.fase0.bench_modelos --tipo {embedding,reranker} --modelo <id> --proveedor {cpu,cuda} --n <int>`, que escribe `resultados/rend_<tipo>_<modelo>_<proveedor>.json` con: `unidades_por_s`, `docs_por_s` (solo embedding), `pares_por_s` (solo reranker), `n`, `segundos`, `proveedor`, `hilos`.

- [ ] **Step 1:** Implementar el benchmark con un calentamiento no cronometrado (carga + 1 lote). Para `embedding` mide por separado 5.000 unidades cortas y 1.000 documentos largos (Review Focus 2). Para `reranker` usa 400 pares (requisito, documento). `--proveedor cuda` pasa `providers=["CUDAExecutionProvider"]`. Si no está disponible, escribe `{"proveedor": "cuda", "error": "<mensaje>"}` y sale con código 0, sin fallar.
- [ ] **Step 2:** Correrlo para los 3 embeddings y los rerankers candidatos en CPU:
  `for m in ...; do .venv/bin/python -m spike.fase0.bench_modelos --tipo embedding --modelo $m --proveedor cpu --n 5000; done` (y lo mismo con `--tipo reranker`).
  Expected: un JSON por combinación, sin campo `error`.
- [ ] **Step 3: Commit** — `git commit -m "chore(fase0): benchmark de rendimiento de modelos en CPU"`

### Task 5: Benchmark de pgvector a escala 120k + búsqueda por umbral

**Files:**
- Create: `spike/fase0/bench_pgvector.py`
- Create: `spike/fase0/test_pgvector_umbral.py`

**Interfaces:**
- Consumes: `comun.conectar()` (Tarea 1).
- Produces: `buscar_por_umbral(conn, vector: list[float], tau: float, tope: int = 5000) -> list[tuple[int, float]]`. Activa `SET hnsw.iterative_scan = relaxed_order` en la conexión y devuelve `(id, similitud)` con similitud ≥ `tau`, ordenadas de mayor a menor. Escribe `resultados/pgvector.json` con: `segundos_insercion_120k`, `segundos_indice_hnsw`, `mb_tabla_docs`, `mb_tabla_requisitos`, `ms_busqueda_p50`, `ms_busqueda_p95`, `filas_promedio_por_busqueda`.

Esquema del spike (no es el de la app): `docs(id bigint, v halfvec(D))` con 120.000 filas e índice `hnsw (v halfvec_cosine_ops)`, y `requisitos(id bigint, vacante bigint, v halfvec(D))` con 1.080.000 filas, sin índice ANN. D es la dimensión del modelo elegido (384 o 768: se miden las dos). Los vectores son aleatorios normalizados con clusters (k-means sintético de 200 centros), para que existan vecindarios densos como en la realidad. El contenido no afecta el tiempo de HNSW.

- [ ] **Step 1: Write the failing test** (en una tabla pequeña de 20.000 filas)

```python
def test_umbral_devuelve_mas_que_ef_search():
    # 1.500 vectores casi idénticos al de consulta; ef_search por defecto es 40
    filas = buscar_por_umbral(conn, consulta, tau=0.9)
    assert len(filas) >= 1400
    assert all(s >= 0.9 for _, s in filas)
    assert [s for _, s in filas] == sorted((s for _, s in filas), reverse=True)

def test_tope_de_seguridad():
    assert len(buscar_por_umbral(conn, consulta, tau=0.0, tope=500)) == 500
```

- [ ] **Step 2:** Correr `.venv/bin/python -m pytest spike/fase0/test_pgvector_umbral.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar `buscar_por_umbral` y el benchmark. La carga usa `COPY ... FORMAT BINARY` con el adaptador de pgvector. Las 200 consultas se toman de vectores cerca de los centros, para producir entre 500 y 3.000 resultados.
- [ ] **Step 4:** Correr el test (expected: 2 passed) y luego `.venv/bin/python -m spike.fase0.bench_pgvector --dim 384` y `--dim 768`. Expected: existe `resultados/pgvector_384.json` y `resultados/pgvector_768.json`.
- [ ] **Step 5: Commit** — `git commit -m "chore(fase0): benchmark de pgvector 120k y búsqueda por umbral iterativa"`

### Task 6: Costo de la cobertura y decisión por candidato

**Files:**
- Create: `spike/fase0/bench_cobertura.py`

**Interfaces:**
- Produces: `cobertura(req: np.ndarray, evid: np.ndarray, rangos: list[slice]) -> np.ndarray`. `req` es `(R, D)` con todos los requisitos de las vacantes relevantes, `evid` es `(E, D)` y el resultado es `(R,)` con la similitud máxima de cada requisito. Escribe `resultados/cobertura.json` con `ms_cobertura` para 3.000 vacantes × 9 requisitos × 30 evidencias, en D = 384 y D = 768.

- [ ] **Step 1:** Implementar `cobertura` como `(req @ evid.T).max(axis=1)` en float32. Medir la mediana de 20 repeticiones.
- [ ] **Step 2:** Correr `.venv/bin/python -m spike.fase0.bench_cobertura`. Expected: JSON escrito.
- [ ] **Step 3: Commit** — `git commit -m "chore(fase0): costo de cobertura por candidato"`

### Task 7 (opcional): GPU

**Files:**
- Create: `spike/fase0/GPU.md` (pasos que funcionaron o motivo por el que no)

- [ ] **Step 1:** En un venv aparte (`spike/fase0/.venv-gpu`, ignorado por git), instalar `fastembed-gpu` (trae `onnxruntime-gpu`; no puede convivir con `onnxruntime` en el mismo venv). Verificar que `onnxruntime.get_available_providers()` incluya `CUDAExecutionProvider`.
- [ ] **Step 2:** Si está disponible, repetir la Tarea 4 con `--proveedor cuda` solo para los modelos que pasaron calidad. Si no, documentar el error en `GPU.md` y seguir: **la GPU no es requisito**, y el umbral CPU de 8 h es el que decide.
- [ ] **Step 3: Commit** — `git commit -m "chore(fase0): medición en GPU"`

### Task 8: Reporte con veredicto y elección de modelos

**Files:**
- Create: `spike/fase0/reporte.py`
- Create: `spike/fase0/test_reporte.py`
- Create (generado): `spike/fase0/REPORTE.md`
- Modify: `docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md` §8 (modelos elegidos y números medidos)

**Interfaces:**
- Consumes: todos los JSON de `resultados/`.
- Produces: `veredictos(resultados: dict) -> list[dict]`. Cada elemento es `{"umbral", "limite", "medido", "cumple": bool}` para los 5 umbrales de la sección Global Constraints, más la calidad (≥ `UMBRAL_CALIDAD`). Proyecciones:
  - `carga_inicial_h = (120_000*9 / unidades_por_s + 120_000 / docs_por_s) / 3600 + segundos_indice_hnsw/3600`
  - `delta_min = (3_000*9 / unidades_por_s + 3_000 / docs_por_s) / 60`
  - `decision_s = ms_busqueda_p95/1000 + ms_cobertura/1000 + 40 / pares_por_s`
  - `pagina_s = 20 / pares_por_s`
- Regla de elección: entre los modelos que cumplen **todos** los umbrales de CPU y la calidad, el de **mayor exactitud de calidad**. En empate (diferencia ≤ 2 puntos), el más rápido.

- [ ] **Step 1: Write the failing test**

```python
def test_veredicto_con_valores_conocidos():
    r = {"unidades_por_s": 100, "docs_por_s": 20, "segundos_indice_hnsw": 600,
         "ms_busqueda_p95": 80, "ms_cobertura": 150, "pares_por_s": 30, "exactitud": 0.9}
    v = {x["umbral"]: x for x in veredictos(r)}
    assert v["carga_inicial_cpu_h"]["medido"] == pytest.approx(4.83, abs=0.01)
    assert v["carga_inicial_cpu_h"]["cumple"] is True
    assert v["decision_candidato_s"]["medido"] == pytest.approx(1.563, abs=0.01)
    assert v["pagina_s"]["cumple"] is True   # 20/30 = 0,67 s ≤ 1,5

def test_no_cumple_si_lento():
    r = {"unidades_por_s": 20, "docs_por_s": 2, "segundos_indice_hnsw": 600,
         "ms_busqueda_p95": 80, "ms_cobertura": 150, "pares_por_s": 5, "exactitud": 0.9}
    v = {x["umbral"]: x for x in veredictos(r)}
    assert v["carga_inicial_cpu_h"]["cumple"] is False
    assert v["pagina_s"]["cumple"] is False
```

- [ ] **Step 2:** Correr `.venv/bin/python -m pytest spike/fase0/test_reporte.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar `veredictos` y la generación de `REPORTE.md`, que lleva una tabla por combinación (embedding × reranker × D), los modelos elegidos, la licencia de cada uno y el veredicto global: **VIABLE** o **VOLVER AL DISEÑO**.
- [ ] **Step 4:** Correr el test (expected: 2 passed) y luego `.venv/bin/python -m spike.fase0.reporte`. Expected: existe `REPORTE.md` con veredicto global.
- [ ] **Step 5:** Actualizar §8 del spec con los modelos elegidos y los números medidos.
- [ ] **Step 6: Commit** — `git add spike/fase0/reporte.py spike/fase0/test_reporte.py spike/fase0/REPORTE.md docs/superpowers/specs && git commit -m "docs(fase0): reporte de viabilidad y modelos elegidos"`

**Puerta de salida de la Fase 0:** si el veredicto global es VIABLE, se planean las Fases 1 a 4 con los modelos elegidos. Si es VOLVER AL DISEÑO, se detiene y se le presentan los números al usuario.
