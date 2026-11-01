# Fase 2 (el decisor) de Scoutly v3: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que cada candidato reciba, para cada vacante relevante del catálogo, una acción con su solidez y sus razones,
calculada de forma local y gratuita. Eso se ve en el dashboard (Plan de hoy, acciones y plan de aprendizaje), en el
detalle (anillo de cobertura, insignia y requisitos con su evidencia) y en el historial. La calidad se mide contra una
línea base.

**Architecture:** las piezas viven en `matching`. **Puertos** (Protocols) para embeddings y reranker, con adaptadores de
fastembed y fakes determinísticos para los tests. **Preselección** exacta en Postgres. **Cobertura** con numpy.
**Restricciones** como Strategy. **Política** como Chain of Responsibility. Todo se expone por una **fachada**,
`decidir_para_perfil`. Solo el proceso batch (`manage.py decidir`) carga modelos; la web lee las `Decision` ya
calculadas y encola un perfil cuando cambian su CV o sus expectativas.

**Tech Stack:** lo de la Fase 1, más fastembed 0.9.1 (ONNX, sin torch), numpy, `pgvector.django.HalfVectorField` y
`paraphrase-multilingual-MiniLM-L12-v2` (384 d, en caché en `~/.cache/scoutly-modelos`). Opcionalmente,
`BAAI/bge-reranker-v2-m3` en GPU.

**Spec:** `docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md`. La §13 manda; acá aplican §5, §6, §7.3,
§7.5, §10 y §13.1–13.5.

## Global Constraints

- **Valores iniciales de la política (§13.1):** τ_alto = 0,50, τ_bajo = 0,40 y τ_relevancia = 0,40. Viven en **un solo
  objeto** versionado (`Politica`, con `version = "2026-11-02"`) y se ajustan **solo** con la mitad de ajuste del set de
  evaluación (Task 10).
- **Orden de la cadena (§13.2):** DESCARTAR por restricción → SIN_DATOS (< 2 requisitos de texto) → DESCARTAR (≥ 3
  obligatorios faltantes) → POSTULAR (con nota opcional) → AJUSTAR_CV → CERRAR_BRECHA.
- **"Solidez":** alta, media o baja, siempre con un motivo y **nunca con números a la vista** (§13.2).
- **La formación no se mide por similitud** (§13.2). Los requisitos de formación se tratan como dato estructurado y no
  generan AJUSTAR_CV.
- **Las etiquetas de Magneto (`origen="etiqueta"`) son deseables:** nunca bloquean (§13.2).
- **Búsqueda:** exacta en Postgres, sin índice HNSW. El conjunto decidido se define por **umbral, no por tope**; hay un
  tope técnico de 5.000 que se registra en el log si se alcanza (§5.7, §13.1).
- **Vectores:** el de la vacante es el promedio normalizado de (título + requisitos de texto); el del perfil, el
  promedio normalizado de su evidencia. La matriz de requisitos va como `bytea` float16, escrita en la **misma
  transacción** que los requisitos (§13.1, P3).
- **Reranker:** apagado por defecto (`SCOUTLY_RERANKER` vacío). Sin él, el orden es similitud × cobertura.
- **Solo el batch carga modelos.** Ninguna vista importa fastembed. Los tests no cargan modelos salvo los marcados
  `lento`.
- **Visual (§7.5):** los templates de v2 solo reciben **bloques agregados**, con el vocabulario CSS existente más clases
  nuevas `decision-*` al final de `scoutly.css`. El anillo muestra la cobertura (los parciales cuentan como medio) y al
  lado va la insignia "ACCIÓN · solidez" con "cubres X/Y obligatorios". Las 5 barras del detalle se mantienen.
- **Ningún texto del CV sale de la máquina.** Groq queda para la Fase 3 (ver la decisión D1 abajo).

## Decisiones del builder (reversibles; van al ledger como Ruling)

- **D1. Groq (§5.6) pasa a la Fase 3.** Las razones estructuradas cubren la explicación, y la política de privacidad
  ya dice "en una fase posterior".
- **D2. Decisiones a pedido.** Cuando un candidato carga el CV o cambia sus expectativas, la web crea una
  `SolicitudDecision`. `manage.py decidir --escuchar` las atiende con los modelos cargados una sola vez. Mientras
  tanto, el dashboard dice "Estamos analizando tu hoja de vida". Esto cumple §13.4 (la web no carga modelos) sin
  traer un broker de colas.
- **D3. Regla de experiencia (calibración inicial, §13.2).** Viola la restricción si el candidato tiene menos del 50%
  de los años pedidos **y** la vacante pide 2 años o más. Si pide 1 año o menos, el estado es `parcial` y no descarta,
  porque la regla anterior dejaba fuera a los juniors. Se recalibra en la Task 10.
- **D4. Modalidad desconocida.** `Vacante.modalidad_inferida = True` cuando la ingesta usó el valor por defecto
  (decisión de la Fase 1). Esa restricción da `sin_datos`, no `cumple`.
- **D5. El reranker solo reordena la primera página** (20) de POSTULAR y AJUSTAR_CV dentro del batch. No hay reranking
  al paginar: con P1-b, la página bajo demanda no depende de la GPU.

## Review Focus

1. **Un candidato sin expectativas declaradas** (sin salario, modalidad ni ubicación). Debe recibir decisiones (las
   restricciones dan `sin_datos` y bajan la solidez), nunca DESCARTAR por datos que no dio (Task 5).
2. **Un perfil cuyo vector no supera τ_relevancia con ninguna vacante.** El dashboard dice que no hay vacantes
   relevantes, con un mensaje claro, sin error ni ranking vacío confuso (Task 9).
3. **Volver a decidir después de que una vacante relevante dejó de serlo** (cambió el CV). La `Decision` vieja
   desaparece del dashboard y no queda como POSTULAR fantasma (Task 7).
4. **Una vacante ingerida en la Fase 1 sin vectores** (o modificada después de embeberse). No entra al decisor hasta
   tener vector; el batch la embebe primero (Task 2 y Task 7).
5. **Dos empresas con el mismo nombre escrito distinto** ("ACME S.A.S." y "Acme SAS") en el Plan de hoy. Cuentan como
   una sola empresa (normalización), así que sigue siendo una vacante por empresa (Task 8).

---

### Task 1: Puertos de IA, adaptadores de fastembed y fakes

**Files:**
- Create: `matching/puertos.py`, `matching/ia/__init__.py` (la fábrica), `matching/ia/fastembed.py`,
  `matching/ia/fakes.py`
- Test: `matching/tests/test_ia.py`

**Interfaces:**
- Produces: en `matching/puertos.py`:
  - `class Embedder(Protocol): dimension: int; def embeber(self, textos: list[str]) -> np.ndarray`, que devuelve un
    float32 de forma `(n, dimension)` con **filas normalizadas (L2 = 1)**; con `n = 0` devuelve `(0, dimension)`;
  - `class Reordenador(Protocol): def puntuar(self, consulta: str, documentos: list[str]) -> list[float]`.
- Produces: `EmbedderFastembed(modelo: str = MODELO_EMBEDDINGS, proveedor: str = "cpu")` y
  `ReordenadorFastembed(modelo: str = MODELO_RERANKER, proveedor: str = "cuda")`. Usan
  `cache_dir=~/.cache/scoutly-modelos`, igual que `spike/fase0/comun.py`. Constantes:
  `MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"`,
  `MODELO_RERANKER = "BAAI/bge-reranker-v2-m3"`.
- Produces: `EmbedderFalso(dimension=64)`. Es un hashing determinístico de palabras normalizadas (sin acentos, en
  minúsculas): textos con las mismas palabras dan vectores iguales, y textos sin palabras en común dan similitud ≈ 0.
  También `ReordenadorFalso`, que puntúa por proporción de palabras compartidas.
- Produces: `obtener_embedder() -> Embedder` y `obtener_reordenador() -> Reordenador | None`, que leen
  `settings.SCOUTLY_EMBEDDER` (`"fastembed"` por defecto; `"falso"` en tests vía `conftest.py`) y
  `settings.SCOUTLY_RERANKER` (`""` = apagado, `"bge"` = activado).

- [ ] **Step 1: Write the failing tests**

```python
def test_el_falso_normaliza_y_es_determinista():
    e = EmbedderFalso()
    a, b = e.embeber(["Manejo de Excel avanzado", "manejo de excel AVANZADO"])
    assert np.allclose(np.linalg.norm(a), 1) and np.allclose(a, b)

def test_el_falso_separa_textos_sin_palabras_en_comun():
    a, b = EmbedderFalso().embeber(["Excel avanzado", "enfermería UCI"])
    assert float(a @ b) < 0.2

def test_embeber_lista_vacia():
    assert EmbedderFalso().embeber([]).shape == (0, 64)

def test_la_fabrica_respeta_la_configuracion(settings):
    settings.SCOUTLY_EMBEDDER, settings.SCOUTLY_RERANKER = "falso", ""
    assert isinstance(obtener_embedder(), EmbedderFalso) and obtener_reordenador() is None

def test_ninguna_vista_importa_fastembed():
    for app in ("cuentas", "vacantes", "matching", "postulaciones", "notificaciones"):
        for vista in Path(app).glob("views*.py"):
            assert "fastembed" not in vista.read_text(encoding="utf-8")

@pytest.mark.lento
def test_minilm_real_separa_requisito_de_ruido():
    e = EmbedderFastembed()
    req, evid, ruido = e.embeber(["Manejo de Excel avanzado", "Construí tablas dinámicas en Excel", "Enfermería en UCI"])
    assert req @ evid > 0.5 > req @ ruido and e.dimension == 384
```

- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_ia.py -q -m "not lento"`. Expected: FAIL
  (ImportError).
- [ ] **Step 3:** Implementar. En `scoutly/settings.py` van `SCOUTLY_EMBEDDER` y `SCOUTLY_RERANKER` desde el entorno, y
  en `conftest.py`, un fixture `autouse` que pone `SCOUTLY_EMBEDDER="falso"`.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest matching -q -m "not lento"`, y una vez `-m lento -k minilm`.
  Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): puertos de IA con adaptadores de fastembed y fakes`

### Task 2: Vectores de vacantes y perfiles

**Files:**
- Modify: `vacantes/models.py` (`vector`, `matriz_requisitos`, `hash_embebido`, `modalidad_inferida`),
  `vacantes/services.py` (marca `modalidad_inferida`), `cuentas/models.py` (en `Perfil`: `vector`, `matriz_evidencia`,
  `hash_embebido`)
- Create: `matching/vectores.py`, `matching/management/commands/embeber_vacantes.py`
- Test: `matching/tests/test_vectores.py`

**Interfaces:**
- Consumes: `Embedder` (Task 1).
- Produces:
  - `Vacante.vector = HalfVectorField(dimensions=384, null=True)`; la dimensión sale de
    `settings.SCOUTLY_DIMENSION = 384`;
  - `Vacante.matriz_requisitos = BinaryField(null=True)` (float16, filas en el orden de `Requisito.posicion`);
  - `Vacante.hash_embebido = CharField(64, blank=True)`;
  - `Vacante.modalidad_inferida = BooleanField(default=False)`;
  - en `Perfil`: `vector`, `matriz_evidencia` y `hash_embebido`.
- Produces: en `matching/vectores.py`:
  - `a_bytes(m: np.ndarray) -> bytes` y `de_bytes(b: bytes, dim: int) -> np.ndarray`, con float16 y una matriz vacía
    para `b""`;
  - `embeber_vacantes(embedder: Embedder, lote: int = 256) -> int`, que embebe solo las vacantes con
    `hash_embebido != hash_contenido` y guarda en **una transacción por lote** `vector`, `matriz_requisitos` y
    `hash_embebido`. Los requisitos que entran son todos (texto y etiqueta), en orden de `posicion`;
  - `embeber_perfil(perfil: Perfil, embedder: Embedder) -> bool`, que solo actúa si el hash de los textos de la
    evidencia cambió y devuelve si actuó.
- Ruling D4: `ingerir` pone `modalidad_inferida=True` cuando usó `MODALIDAD_POR_DEFECTO`.

- [ ] **Step 1: Write the failing tests**: `test_bytes_ida_y_vuelta` (forma y valores con tolerancia de float16);
  `test_embeber_vacantes_solo_las_nuevas_o_cambiadas` (la primera corrida devuelve 2; la segunda, 0; después de
  re-ingerir una vacante con otro texto, 1); `test_la_matriz_sigue_el_orden_de_posicion`;
  `test_el_vector_de_la_vacante_es_el_promedio_normalizado` (comparado con el cálculo a mano con `EmbedderFalso`);
  `test_vacante_sin_requisitos_tiene_vector_solo_del_titulo`; `test_perfil_sin_evidencia_no_tiene_vector`;
  `test_embeber_perfil_no_repite_si_no_cambio`; `test_modalidad_por_defecto_queda_marcada_como_inferida`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_vectores.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar, con las migraciones y el comando `embeber_vacantes`, que usa `obtener_embedder()` e
  imprime cuántas embebió.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): vectores de vacantes y perfiles (bytea float16 + halfvec)`

### Task 3: Preselección exacta en Postgres

**Files:**
- Create: `matching/preseleccion.py`
- Test: `matching/tests/test_preseleccion.py`

**Interfaces:**
- Produces: `Preseleccion`, una dataclass con `relevantes: list[tuple[str, float]]` (id de vacante y similitud, en
  orden descendente), `ocultas_por_modalidad: int` y `tope_alcanzado: bool`.
- Produces: `preseleccionar(perfil: Perfil, tau: float, tope: int = 5000) -> Preseleccion`. La consulta es exacta,
  sin índice, con la distancia coseno de pgvector (`<=>`), y se queda con las vacantes con
  `activa=True AND vector IS NOT NULL AND 1 - distancia >= tau`. Excluye en SQL las de modalidad **opuesta**
  (Remoto ↔ Presencial) cuando el perfil declaró `exp_modalidad` y la vacante **no** tiene `modalidad_inferida`, y las
  cuenta en `ocultas_por_modalidad`. Si llega al tope, hace `log.warning` con el id del perfil.

- [ ] **Step 1: Write the failing tests**: `test_solo_entran_las_que_superan_tau`;
  `test_ordenadas_por_similitud_descendente`; `test_excluye_modalidad_opuesta_y_las_cuenta`;
  `test_no_excluye_si_la_modalidad_de_la_vacante_es_inferida`; `test_sin_modalidad_declarada_no_excluye_nada`;
  `test_ignora_vacantes_sin_vector_o_inactivas`; `test_tope_tecnico_se_marca_y_se_registra` (con `tope=2` y `caplog`).
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_preseleccion.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar con el ORM (`CosineDistance` de `pgvector.django`) más `annotate` y `filter`, y
  verificar con `EXPLAIN` que no hay índice involucrado.
- [ ] **Step 4:** Run the test file. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): preselección exacta por umbral en Postgres`

### Task 4: Cobertura requisito por requisito

**Files:**
- Create: `matching/cobertura.py`
- Test: `matching/tests/test_cobertura.py`

**Interfaces:**
- Produces: `RequisitoEvaluado`, una dataclass congelada con `texto`, `tipo`, `origen`,
  `estado: "cubierto" | "parcial" | "faltante" | "formacion"`, `similitud: float` y `evidencia: str | None`.
- Produces: `Cobertura`, una dataclass con `requisitos: list[RequisitoEvaluado]` y las propiedades
  `obligatorios_cubiertos`, `obligatorios_total`, `faltantes_obligatorios: list[RequisitoEvaluado]`,
  `parciales_con_evidencia` y `porcentaje: int` (redondeo de `(cubiertos + 0,5 × parciales) / obligatorios × 100`,
  contando **solo los obligatorios no de formación**; 0 si no hay ninguno).
- Produces: `cubrir(requisitos: list[Requisito], matriz_req: np.ndarray, evidencias: list[str],
  matriz_evid: np.ndarray, tau_alto: float, tau_bajo: float) -> Cobertura`. La similitud es
  `(matriz_req @ matriz_evid.T).max(axis=1)` y la evidencia es la del `argmax`. Los requisitos de **formación** reciben el
  estado `formacion` y no se miden por similitud. Un requisito es de formación si su texto normalizado empieza con
  "tecnico", "tecnologo", "profesional", "bachiller", "estudiante", "titulo", "formacion", "carrera" o "ingeniero"
  (constante `INICIOS_FORMACION` en `matching/cobertura.py`).

- [ ] **Step 1: Write the failing tests**:
  - `test_umbrales_cubierto_parcial_faltante`: con matrices armadas a mano, una similitud de 0,55 da `cubierto`, 0,45
    da `parcial` y 0,30 da `faltante`;
  - `test_la_evidencia_es_la_mas_parecida`;
  - `test_porcentaje_cuenta_parciales_como_medio` (2 cubiertos + 1 parcial + 1 faltante = 63%);
  - `test_deseables_no_cuentan_en_el_porcentaje`;
  - `test_la_formacion_no_se_mide_por_similitud`;
  - `test_sin_evidencia_todo_es_faltante`, con una matriz de evidencia vacía.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_cobertura.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar, vectorizado con numpy.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): cobertura semántica requisito por requisito`

### Task 5: Restricciones duras (Strategy)

**Files:**
- Create: `matching/restricciones.py`
- Test: `matching/tests/test_restricciones.py`

**Interfaces:**
- Produces: `ResultadoRestriccion`, una dataclass congelada con `criterio: "experiencia" | "salario" | "modalidad" |
  "ubicacion"`, `estado: "cumple" | "parcial" | "no_cumple" | "sin_datos"`, `motivo: str` (en español, para mostrar) y
  `valor_pct: int` (100, 50, 0 o 0 para la barra del detalle).
- Produces: `class Restriccion(Protocol): criterio: str; def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion`,
  con las implementaciones `RestriccionModalidad`, `RestriccionSalario`, `RestriccionUbicacion` y
  `RestriccionExperiencia`, y la lista `RESTRICCIONES` en ese orden.
- Reglas:
  - **Modalidad:** la tabla de afinidad de v2 (100, 50 o 0). 0 es `no_cumple` y 50 es `parcial`. Perfil sin modalidad
    o `modalidad_inferida` da `sin_datos`.
  - **Salario:** si `salario_max` es menor que `exp_salario_min`, `no_cumple`; si falta alguno de los dos, `sin_datos`.
  - **Ubicación:** si la vacante es Remoto, `cumple`; si el perfil no declaró ubicación, `sin_datos`; si alguna ciudad
    del perfil (separadas por comas, sin acentos) aparece en `vacante.ubicacion`, `cumple`; si no, `no_cumple`.
  - **Experiencia (D3):** si la vacante no pide años, `cumple`; si el perfil no declaró los suyos, `sin_datos`; si
    tiene los pedidos o más, `cumple`; si la vacante pide 1 o menos, `parcial`; si tiene menos del
    `politica.factor_experiencia` (0,5) de lo pedido, `no_cumple`; en el resto de casos, `parcial`.

- [ ] **Step 1: Write the failing tests**, uno por fila de cada regla, con los motivos exactos en dos casos:
  `"Ofrece $ 2.000.000 y tu mínimo es $ 3.000.000"` y `"Pide 3 años de experiencia y declaraste 1"`. Más
  `test_candidato_sin_expectativas_nunca_viola_nada` (Review Focus 1): todas sus restricciones dan `sin_datos`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_restricciones.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): restricciones duras como Strategy`

### Task 6: Política (Chain of Responsibility) y solidez

**Files:**
- Create: `matching/politica.py`, `matching/solidez.py`
- Test: `matching/tests/test_politica.py`, `matching/tests/test_solidez.py`

**Interfaces:**
- Consumes: `Cobertura` (Task 4), `ResultadoRestriccion` (Task 5), `vacantes.extraccion.requisitos_insuficientes`.
- Produces: `Politica`, una dataclass congelada con `version="2026-11-02"`, `tau_alto=0.50`, `tau_bajo=0.40`,
  `tau_relevancia=0.40`, `max_faltantes_descartar=3`, `cobertura_nota=0.70`, `factor_experiencia=0.5` y
  `max_palabras_herramienta=4`. `POLITICA` es la instancia vigente.
- Produces: `Accion(TextChoices)` con `POSTULAR`, `AJUSTAR_CV`, `CERRAR_BRECHA`, `DESCARTAR` y `SIN_DATOS`, y
  `Veredicto`, una dataclass con `accion`, `con_nota: str | None` y `motivos: list[str]`.
- Produces: `class Regla(Protocol): def aplicar(self, contexto: ContextoDecision) -> Veredicto | None`. Las reglas,
  **en este orden**, son `DescartarPorRestriccion`, `SinDatos`, `DescartarPorFaltantes`, `Postular`, `AjustarCV` y
  `CerrarBrecha`, y `decidir(contexto) -> Veredicto` aplica la primera que responde. `ContextoDecision` es una
  dataclass con `cobertura`, `restricciones`, `requisitos` (los extraídos, para SIN_DATOS) y `politica`.
  - `Postular` responde si no falta ningún obligatorio, o si la cobertura es ≥ 0,70 y falta exactamente uno, de
    `max_palabras_herramienta` palabras o menos. En ese caso `con_nota` es
    `"Menciona que puedes aprender {texto} rápido"`.
  - `AjustarCV` responde si hay parciales con evidencia, y cada motivo dice
    `"Haz explícito «{requisito}» (tu evidencia: «{evidencia}»)"`.
- Produces: `calcular_solidez(contexto, veredicto) -> tuple[str, str]`, que devuelve `("alta" | "media" | "baja",
  motivo)`. Parte de 3 puntos y resta:
  - 1 por cada restricción `sin_datos`, hasta 2;
  - 1 si algún requisito decisivo está a menos de 0,03 de un umbral;
  - 2 si hay 2 o 3 requisitos de texto.

  3 puntos o más es `alta`, 2 es `media` y menos es `baja`. El motivo nombra la mayor penalización (por ejemplo
  "la vacante no dice el salario"). SIN_DATOS siempre es `baja`.

- [ ] **Step 1: Write the failing tests**: un test por regla con su caso mínimo; `test_orden_de_la_cadena`
  (restricción violada y además pocos requisitos: gana DESCARTAR); `test_etiqueta_faltante_no_bloquea`;
  `test_postular_con_nota_solo_si_cobertura_alta_y_un_faltante_corto`;
  `test_ajustar_cv_lleva_el_texto_y_la_evidencia`; `test_formacion_faltante_no_genera_ajustar_cv`. En solidez:
  `test_solidez_es_monotona_en_datos_faltantes` (agregar un `sin_datos` nunca la sube),
  `test_solidez_baja_cerca_del_umbral` y `test_sin_datos_siempre_baja`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_politica.py matching/tests/test_solidez.py -q`.
  Expected: FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): política como Chain of Responsibility y solidez`

### Task 7: `Decision`, fachada `decidir_para_perfil` y batch

**Files:**
- Modify: `matching/models.py`, `cuentas/views.py` (encola tras el CV y las expectativas)
- Create: `matching/services.py`, `matching/orden.py`, `matching/management/commands/decidir.py`
- Test: `matching/tests/test_decidir.py`

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces, como modelos:
  - `Decision`: `perfil`, `vacante`, `accion`, `accion_anterior`, `con_nota`, `solidez`, `motivo_solidez`, `motivos`
    (json), `similitud`, `cobertura_pct`, `relevancia` (null), `orden` (float), `cobertura` (json: lista de
    `{texto, tipo, origen, estado, similitud, evidencia}`), `restricciones` (json), `fecha_decision` y
    `version_politica`. Es única por `(perfil, vacante)`.
  - `FotoDiaria`: `perfil`, `fecha`, `conteos` (json `{accion: n}`) y `top` (json `{accion: [{vacante_id,
    cobertura_pct, orden}]}`, hasta 10 por acción). Es única por `(perfil, fecha)`.
  - `SolicitudDecision`: `perfil` (único), `creada_en`.
- Produces:
  - `decidir_para_perfil(perfil, embedder, reordenador=None, politica=POLITICA, hoy=None) -> ResumenDecision`. Primero
    `embeber_perfil`, después `preseleccionar`, y por cada relevante, cobertura → restricciones → `decidir` →
    `calcular_solidez`. En **una transacción**:
    - hace upsert de `Decision` y guarda `accion_anterior` cuando la acción cambió;
    - **borra las `Decision` del perfil cuyas vacantes ya no son relevantes** (Review Focus 3);
    - hace upsert de la `FotoDiaria` de `hoy`;
    - borra la `SolicitudDecision`.
  - `ResumenDecision` es una dataclass con `relevantes`, `por_accion`, `ocultas_por_modalidad` y `segundos`.
- Produces: en `matching/orden.py`, `class Ordenador(Protocol): def ordenar(self, perfil, decisiones) -> None`, que
  escribe `orden` y `relevancia`. Implementaciones:
  - `OrdenSimilitudCobertura`, con `orden = similitud × cobertura_pct / 100`;
  - `OrdenConReranker(reordenador)`, que reordena con el reranker las primeras 20 de POSTULAR y AJUSTAR_CV
    (consulta = resumen del perfil: las primeras 10 unidades de evidencia; documento = título + los primeros 8
    requisitos) y deja el resto como el anterior (D5).
- Produces: `manage.py decidir [--todos | --pendientes | --escuchar]`:
  - siempre corre primero `embeber_vacantes`;
  - `--todos` decide para cada perfil con CV;
  - `--pendientes` atiende las `SolicitudDecision`;
  - `--escuchar` repite `--pendientes` cada 5 s hasta Ctrl+C.

  Carga los modelos **una sola vez** por corrida.
- Produces: `cuentas/views.py` llama a `matching.services.solicitar_decision(perfil)` después de guardar el CV o las
  expectativas. Ese servicio crea la `SolicitudDecision` sin cargar modelos.

- [ ] **Step 1: Write the failing tests** (con `EmbedderFalso` y vacantes y CVs armados para dar cada acción):
  `test_decide_las_cinco_acciones` (un perfil, cinco vacantes, una acción por vacante);
  `test_redecidir_actualiza_y_guarda_accion_anterior`;
  `test_las_vacantes_que_dejan_de_ser_relevantes_se_borran`; `test_la_foto_diaria_es_una_por_dia`;
  `test_cargar_cv_encola_sin_cargar_modelos` (falla si se importa `matching.ia.fastembed`);
  `test_comando_pendientes_atiende_la_cola`; `test_vacante_sin_vector_se_embebe_antes_de_decidir` (Review Focus 4);
  `test_orden_por_similitud_y_cobertura`; `test_reranker_solo_reordena_la_primera_pagina` (con `ReordenadorFalso`).
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_decidir.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar, con las migraciones.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): fachada decidir_para_perfil, Decision y batch con cola`

### Task 8: Lecturas para las pantallas (selectors)

**Files:**
- Modify: `matching/selectors.py`
- Test: `matching/tests/test_selectors.py`

**Interfaces:**
- Produces:
  - `plan_de_hoy(perfil, n=5, ahora=None) -> list[ItemPlan]`: solo POSTULAR y AJUSTAR_CV, como máximo una por
    empresa (con `normalizar` de `vacantes.extraccion`, quitando "s.a.s", "sas", "s.a" y "ltda"), ordenadas por
    `orden × frescura`, donde la frescura es 1,0 hasta 72 h, 0,8 hasta 7 días y 0,6 después. `ItemPlan` tiene
    `decision`, `postular_hoy: bool` (menos de 72 h) y los campos del template de v2: `vacante`, `score_pct`
    (= `cobertura_pct`), `coincidencias` (los textos cubiertos) y `razon_principal` (el primer motivo).
  - `decisiones_por_accion(perfil) -> dict[str, list[Decision]]`, en el orden de las acciones de la cadena inversa
    (POSTULAR, AJUSTAR_CV, CERRAR_BRECHA, SIN_DATOS, DESCARTAR), cada lista ordenada por `orden`.
  - `plan_de_aprendizaje(perfil, n=5) -> list[tuple[str, int]]`: los faltantes obligatorios de CERRAR_BRECHA,
    agregados sin distinguir mayúsculas ni acentos, por frecuencia descendente.
  - `detalle(perfil, vacante) -> dict | None`: el contexto de v2 (`match`, `criterios` y `modificador=None`) armado a
    partir de la `Decision`. `match.score` = cobertura, `coincidencias` = cubiertos, `faltantes` = faltantes
    obligatorios. Las 5 barras: Habilidades = cobertura, y las demás, `valor_pct` de cada restricción, con su motivo
    en `explicacion`.
  - `historial(perfil, fecha=None) -> dict`: el contexto de v2 armado desde `FotoDiaria`.
  - `pendiente_de_decision(perfil) -> bool`.

- [ ] **Step 1: Write the failing tests**: `test_plan_de_hoy_una_por_empresa_normalizada` (Review Focus 5:
  "ACME S.A.S." y "Acme SAS"); `test_plan_de_hoy_marca_postular_hoy_antes_de_72h`;
  `test_plan_de_hoy_excluye_descartar_y_sin_datos`; `test_plan_de_aprendizaje_cuenta_frecuencias`;
  `test_detalle_arma_las_cinco_barras`; `test_historial_compara_con_la_foto_anterior`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_selectors.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): selectors del Plan de hoy, acciones, aprendizaje, detalle e historial`

### Task 9: Las pantallas del decisor

**Files:**
- Modify: `matching/views.py`, `matching/templates/matching/dashboard.html`, `matching/templates/matching/detalle.html`
  y `static/css/scoutly.css` (solo clases `decision-*` al final). En los templates, **solo se agregan bloques**; el
  `diff` contra v2 debe mostrar únicamente líneas agregadas, salvo la palabra "Matches de hoy" → "Tu plan de hoy".
- Test: `matching/tests/test_paginas.py` (se amplía)

**Interfaces:**
- Consumes: Task 8.
- Bloques nuevos:
  - **Tarjeta del Plan de hoy:** se agregan, bajo el anillo existente, la insignia `{{ m.decision.get_accion_display }} ·
    solidez {{ m.decision.solidez }}`, `cubres X/Y obligatorios` y la marca "Postular hoy".
  - **Bajo el Plan de hoy:** una sección "Tus vacantes por acción", con pestañas por acción, contadores y la lista
    compacta de cada una; una tarjeta "Plan de aprendizaje" (`"Docker aparece en 9 de tus vacantes relevantes"`); y el
    aviso "N vacantes presenciales ocultas" cuando `ocultas_por_modalidad > 0`.
  - **Detalle:** el anillo y las barras existentes (con su contexto), más la insignia con el motivo de la solidez y un
    bloque "Requisitos" con tres listas (cubiertos, parciales y faltantes), cada requisito con "tu evidencia:
    «...»". "Postularme" queda habilitado si hay `Decision`.
- Estados:
  - si `pendiente_de_decision`, el aviso "Estamos analizando tu hoja de vida. Vuelve en un minuto.";
  - si no hay decisiones ni solicitud pendiente, "No encontramos vacantes relevantes para tu perfil todavía: revisa
    que tu hoja de vida tenga tu experiencia y habilidades" (Review Focus 2).

- [ ] **Step 1: Write the failing tests**: `test_dashboard_muestra_plan_de_hoy_con_insignia_y_solidez`;
  `test_dashboard_muestra_plan_de_aprendizaje`; `test_dashboard_pendiente_muestra_aviso_de_analisis`;
  `test_dashboard_sin_relevantes_explica_por_que`; `test_detalle_muestra_requisitos_con_evidencia`;
  `test_detalle_habilita_postularme_con_decision`; `test_historial_muestra_el_ranking_de_la_foto`;
  `test_los_templates_solo_agregan_lineas_a_v2` (un `difflib` contra `git show pre-sprint3-rebuild:...`, sin líneas
  borradas salvo el título acordado).
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_paginas.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar con impeccable/design: vocabulario CSS existente, la insignia con `--brand`, `--navy`
  o `--magneto-purple` según la acción y la solidez en texto.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS. Después, capturas con
  `scripts/capturas.py` de dashboard, detalle e historial en v3 con decisiones, junto a las de v2 en
  `docs/fase2/capturas/`, con una nota de lo agregado.
- [ ] **Step 5: Commit** `feat(matching): dashboard, detalle e historial del decisor`

### Task 10: Set de evaluación (mitad de ajuste), línea base y calibración

**Files:**
- Create: `matching/evaluacion/cvs.yaml` (10–12 CVs ficticios descritos en datos), `matching/evaluacion/vacantes.json`
  (unas 30 vacantes reales con su texto completo, tomadas de una corrida de `ingerir_vacantes --fuente magneto` y
  minimizadas), `matching/evaluacion/pares.yaml`, `matching/evaluacion/evaluar.py` y
  `matching/management/commands/evaluar_decisor.py`, `docs/fase2/EVALUACION.md`
- Test: `matching/tests/test_evaluacion.py`

**Interfaces:**
- Produces:
  - `cvs.yaml`: 10–12 perfiles (§10) de distintos niveles y áreas, más tres casos difíciles (la habilidad nombrada
    distinto, la experiencia implícita y los datos incompletos). Se convierten en PDF con `cuentas/tests/cvs.py` y
    **pasan por el parser real**.
  - `pares.yaml`: 40–50 pares `{cv, vacante, accion_esperada, justificacion, mitad: ajuste|prueba}`, con unos 20–24
    de ajuste, que cubren las 5 acciones. **El equipo revisa las etiquetas** (§10) y queda anotado en el ledger como
    pendiente.
  - `evaluar(pares, politica, mitad="ajuste") -> Informe`. `Informe` lleva la exactitud, la distribución por acción,
    la matriz de confusión y la exactitud de la **línea base**, que es "similitud pura": POSTULAR si la similitud es
    ≥ τ_relevancia + 0,10, CERRAR_BRECHA si es ≥ τ_relevancia y DESCARTAR en otro caso.
  - `manage.py evaluar_decisor [--mitad ajuste|prueba] [--barrido]`. Con `--barrido` prueba τ_alto en {0,45, 0,50,
    0,55}, τ_bajo en {0,35, 0,40} y τ_relevancia en {0,35, 0,40, 0,45} **solo sobre la mitad de ajuste**, e imprime
    la mejor combinación.
  - La mitad de prueba se reserva para la Fase 4: en esta fase **no se corre**, y `evaluar_decisor` la rechaza salvo
    con `--confirmo-prueba`.

- [ ] **Step 1: Write the failing tests**: `test_el_set_cubre_las_cinco_acciones_en_ajuste`;
  `test_la_mitad_de_prueba_no_se_usa_sin_confirmar`; `test_evaluar_calcula_exactitud_y_linea_base` (con 3 pares de
  juguete y `EmbedderFalso`); `test_ningun_cv_del_set_tiene_datos_de_personas_reales` (los correos son de
  `@correo-ficticio.co` y no hay números de documento).
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_evaluacion.py -q`. Expected: FAIL.
- [ ] **Step 3:** Armar los datos y el código.
- [ ] **Step 4:** Run `manage.py evaluar_decisor --mitad ajuste --barrido` con el **embedder real**
  (`SCOUTLY_EMBEDDER=fastembed`). Si la mejor combinación cambia los umbrales, actualizar `Politica` (con nueva
  `version`). Escribir `docs/fase2/EVALUACION.md` con la exactitud, la distribución, la línea base y si se cumplen los
  anti-objetivos: ≥ 70% de exactitud, ninguna acción por encima del 80% y mejor que la línea base. Si no se cumplen,
  **se dice así**, no se maquilla.
- [ ] **Step 5: Commit** `feat(matching): set de evaluación (mitad de ajuste), línea base y calibración`

### Task 11: De punta a punta con modelos reales

**Files:**
- Test: `matching/tests/test_punta_a_punta.py` (marcado `lento`)
- Modify: `README.md` (cómo levantar el decisor: `ingerir_vacantes`, `decidir --escuchar` y `runserver --insecure`)

- [ ] **Step 1: Write the test (lento)**: `test_cv_real_hasta_dashboard`. Ingiere el fixture, carga un CV del set,
  corre `decidir --pendientes` con MiniLM real, abre el dashboard y comprueba que hay un Plan de hoy con al menos una
  insignia. También mide el tiempo de `decidir_para_perfil` y verifica que sea **≤ 5 s en CPU** (§6).
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_punta_a_punta.py -q -m lento`. Expected: PASS.
  Anotar el tiempo en el ledger.
- [ ] **Step 3:** Actualizar el README y hacer commit `docs: cómo correr el decisor de punta a punta`.

## Fuera de esta fase

- **Fase 3:**
  - Taller de CV (C, texto);
  - B1 (`job_detail`);
  - API para n8n (`/api/decidir` 202), notificaciones por correo con preferencias;
  - Groq (D1);
  - `ResultadoDecision` desde el tablero;
  - verificación de correo.
- **Fase 4:**
  - mitad de prueba del set;
  - `benchmark_escala`;
  - evaluación ciega con reclutadores;
  - un set nuevo de extracción.
