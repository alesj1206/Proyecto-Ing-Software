# Scoutly v3 — Reescritura con decisor de acciones (Sprint 3)

Fecha: 2026-11-01 · Rama: `sprint-3` · Punto de retorno: tag `pre-sprint3-rebuild`

> **Enmendado el 2026-11-02 tras la Fase 0 (§13).** Donde §13 contradiga una sección anterior, manda §13.

## 1. Intención y por qué

Scoutly (reto Magneto, Idea 4: *vacantes → ranking diario → notificación*, orquestado por n8n) existe para que
el candidato **consiga entrevistas**. Hoy el sistema no puede cumplir eso a escala real:

- **Vocabulario cerrado.** `vacantes/skills.py` tiene 29 términos. El CV (`cv_parser.py`) y los requisitos de
  cada vacante (`scrape_magneto.py::_mapear_requisitos`) se filtran contra esa lista con regex exacto. Todo
  requisito real que no esté en la lista se descarta en silencio.
- **Match binario.** `matching.py::_score_habilidades` compara por igualdad de strings: "coincide o no".
- **No escala.** Magneto tiene ~120.000 vacantes. Analizar cada una con un LLM (Groq) por candidato es
  inviable en costo y tiempo. La herramienta que les recomendaron (Jev) resuelve esto devolviendo
  *decisiones estructuradas con confianza*, pero es de pago.
- **Código difícil de defender.** El grafo de graphify muestra todo dentro de una sola app (`vacantes`),
  un `views.py` de 561 líneas que mezcla HTTP, reglas y datos, y una comunidad con cohesión 0.06. En
  Sprint 3 se califican patrones de diseño y clean code.

**Qué se construye:** una reescritura desde cero del backend con un **decisor local, gratuito y open source**
que, para cada candidato, recorre el catálogo completo y devuelve por vacante **una acción con confianza y
razones**, como Jev, sin costo por token. **La parte visual se conserva tal cual.**

## 2. Objetivos, no-objetivos y anti-objetivos

**Objetivos**
1. Extracción de **vocabulario abierto**, sin lista cerrada, tanto en el CV como en las vacantes.
2. Comparación **semántica** de requisitos contra evidencia del CV (embeddings), no por igualdad de texto.
3. Un **decisor** que asigna a cada vacante preseleccionada una de 4 acciones, con confianza y razones
   estructuradas (sección 5).
4. **Viabilidad a escala Magneto**: un benchmark reproducible con 120.000 vacantes sintéticas demuestra
   tiempos de ingesta y de decisión por usuario en esta máquina (sección 6).
5. **Arquitectura limpia** con patrones nombrables en la sustentación (sección 7) y tests (TDD) en el núcleo.
6. **Visual idéntico**: los 8 templates, `base.html`, `static/css` y `static/img` se reutilizan, las URLs
   no cambian y solo se agregan los elementos visuales del decisor.
7. Se conserva el flujo de n8n (ingesta → decisión → notificación) en pasos separados, porque el reto lo exige.

**No-objetivos (Sprint 3)**
- Postulación real en Magneto: sigue simulada (HU-08).
- Entrenar un modelo de ML propio. El decisor usa modelos preentrenados y una política explícita. Sí se
  **guardan los datos** para calibrarlo después (sección 5.5).
- Scrapear de verdad las 120k vacantes a diario con Playwright, porque no es viable para el equipo. La escala
  se demuestra con un benchmark sintético y la ingesta real queda detrás de un adaptador (sección 7).
- Cambiar la identidad visual o agregar canales de notificación (WhatsApp sigue descartado).

**Anti-objetivos (cualquiera de estos hace fallar el proyecto aunque "funcione")**
- **Un decisor decorativo.** Si en el set de evaluación más del 80% de las vacantes cae en una sola acción,
  o si la exactitud contra las etiquetas humanas es menor al 70%, el decisor no aporta y hay que
  reajustarlo antes de entregar.
- Llamar a un LLM por cada vacante o por cada par (candidato, vacante).
- Romper la apariencia actual de alguna página.
- Un "decisor" que inventa: toda razón mostrada al usuario sale de datos calculados, nunca de texto libre
  del LLM sin datos que la respalden.

## 3. Restricciones

- **Gratis y open source.** Solo modelos con licencia que permita uso académico, corriendo localmente.
- **Python 3.14 y Django 6.1** (ya en el `.venv`). Verificado que existen wheels para 3.14 de `fastembed`
  0.9.1, `onnxruntime` 1.31.1, `numpy` 2.5, `tokenizers`, `pgvector` 0.5.1 y `psycopg[binary]` 3.3.6.
  **No se usa torch**: fastembed ejecuta los modelos con ONNX, así que el entorno queda liviano.
- Máquina de desarrollo: RTX 3060 Laptop (6 GB). La GPU es opcional y acelera el benchmark; todo debe
  funcionar en CPU.
- Podman 5.8 ya está instalado y n8n ya corre en Podman, así que Postgres también va en Podman.
- Groq se mantiene **solo** para redactar explicaciones bajo demanda, con caché (como hoy).
- Equipo de 3 personas y un sprint de duración, así que el trabajo va por fases (sección 9).

## 4. Enfoques considerados

| Enfoque | Por qué no / por qué sí |
|---|---|
| **Jev (pago)** | Es justo el tipo de decisor buscado, pero tiene costo por token, el servicio es cerrado y está en acceso anticipado. Descartado por costo. |
| **LLM por vacante (Groq u Ollama local con salida JSON)** | Con 120k vacantes × N candidatos es caro en la nube y lento en local (segundos por decisión). Aunque solo se use sobre la preselección, el resultado no es determinístico ni testeable. Descartado. |
| **Ampliar el diccionario + fuzzy matching (rapidfuzz)** | Rápido y barato, pero sigue siendo vocabulario cerrado y similitud de texto, no de significado ("Java" ≈ "JavaScript"). No resuelve el problema de fondo. Descartado. |
| **Elegido: pipeline local "recuperar → cubrir → rerankear → decidir"** | Los embeddings filtran rápido las 120k vacantes. La cobertura semántica requisito por requisito da brechas explicables. Un reranker (cross-encoder) ordena la preselección. Una **política explícita** decide la acción y su confianza. Todo es gratis, determinístico y testeable, y escala porque el trabajo pesado se hace una sola vez por vacante. |

## 5. El decisor

### 5.1 Qué decide y por qué importa

El candidato no necesita "un porcentaje". Necesita saber **qué hacer** con cada vacante para maximizar sus
entrevistas. El decisor responde la pregunta *"¿qué hago con esta vacante?"* con una de 4 acciones:

| Acción | Cuándo | Qué ve el candidato |
|---|---|---|
| **POSTULAR** | Cumple las restricciones duras y cubre todos los requisitos obligatorios con evidencia clara en el CV. | "Postúlate ya", más los requisitos que cubre. |
| **AJUSTAR_CV** | Cumple las restricciones duras y no le falta ningún obligatorio, pero ≥1 obligatorio solo tiene **cobertura parcial**: hay experiencia relacionada, pero el CV no lo dice explícitamente. | "Antes de postularte, menciona X en tu CV". Esto importa porque los filtros de las empresas (ATS) leen palabras clave, así que es lo que más cambia la tasa de entrevistas con menos esfuerzo. |
| **CERRAR_BRECHA** | Cumple las restricciones duras, pero le faltan 1–2 obligatorios. | "Te falta Docker", más la **brecha agregada**: "Docker aparece en 9 de tus 100 mejores vacantes". |
| **DESCARTAR** | Viola una restricción dura o le faltan ≥3 obligatorios. | La vacante aparece colapsada, **con el motivo** ("modalidad opuesta a la que buscas"), para que el candidato confíe en el filtro y no sienta que se le esconden cosas. |

Dentro de cada acción, las vacantes se ordenan por **relevancia** (el puntaje del reranker). El dashboard agrupa
por acción y muestra primero POSTULAR.

### 5.2 Insumos que calcula el pipeline

1. **Requisitos de la vacante (unidades)**, extraídos una sola vez en la ingesta. Cada viñeta u oración de
   la sección de requisitos y cada etiqueta de habilidad que trae Magneto se convierte en un `Requisito`
   con texto libre (sin lista cerrada). Cada uno se clasifica como `obligatorio` o `deseable` con reglas de
   palabras guía ("deseable", "plus", "valorable", "ideal" → deseable). Si la vacante no trae sección de
   requisitos, se usan las oraciones de la descripción que contengan verbos o sustantivos de requisito.
   Además se extraen con regex las restricciones estructuradas: años mínimos, salario, modalidad y
   ubicación (lo que el scraper ya obtiene).
2. **Evidencia del candidato (unidades)**: cada viñeta u oración de las secciones de experiencia,
   habilidades y educación del CV, más las habilidades que el candidato declare. Se vuelve a calcular
   solo cuando cambia el CV.
3. **Embeddings**: un vector por requisito, uno por unidad de evidencia y un vector de documento por
   vacante y por perfil. Modelo multilingüe con fastembed (sección 8).
4. **Cobertura por requisito**: es la similitud máxima del requisito contra todas las unidades de
   evidencia del candidato. Da `cubierto` (≥ τ_alto), `parcial` (entre τ_bajo y τ_alto) o `faltante`
   (< τ_bajo). Guarda **qué evidencia** lo cubrió, para poder mostrarla.
5. **Restricciones duras**: cada una es una Strategy independiente que devuelve `cumple`, `no_cumple` o
   `sin_datos`, con su motivo. Son: modalidad (afinidad, como la tabla actual), salario (lo ofrecido vs. el
   mínimo esperado), ubicación (si la vacante no es remota) y experiencia (se viola si el candidato tiene
   menos del 50% del mínimo). `sin_datos` **no descarta**, pero baja la confianza.
6. **Relevancia**: el puntaje del cross-encoder para (perfil resumido, vacante resumida), solo sobre la
   preselección.

### 5.3 Política de decisión

Es una tabla de reglas **ordenada**: gana la primera que aplica (Chain of Responsibility). Cada regla es una
clase pequeña y testeable. Los umbrales (τ_alto, τ_bajo, cuántos faltantes llevan a descartar, el corte de
experiencia) viven en **un solo objeto de configuración** versionado (`version_politica`), para poder
ajustarlos con el set de evaluación sin tocar el código.

### 5.4 Confianza

Va de 0 a 1 y se muestra como alta, media o baja. Combina tres factores:
- **Margen**: qué tan lejos del umbral que la decidió está la métrica (por ejemplo, una vacante con
  cobertura parcial justo en τ_alto da confianza baja).
- **Completitud de datos**: cada restricción `sin_datos` y cada campo del perfil sin declarar la reduce.
- **Calidad de la extracción**: si la vacante produjo pocos requisitos (0–1), la confianza es baja.

La fórmula exacta queda a cargo del builder, pero tiene que ser monótona en esos tres factores y estar
cubierta por tests. **La confianza es honesta, no probabilística**: no se presenta como una "probabilidad de
entrevista" porque todavía no está calibrada.

### 5.5 Ciclo de retroalimentación (preparado desde el día 1)

Cada decisión se guarda junto con los insumos que la produjeron (features + `version_politica`). Cuando el
candidato mueve una postulación a *Entrevista* o *Descartado* en el tablero (HU-10), esa transición queda
registrada como **resultado** de la decisión. En Sprint 3 no se entrena nada, pero quedan datos reales para
calibrar umbrales o ajustar una regresión logística después. Esto también responde a la pregunta "¿cómo
sabrían que funciona?" en la sustentación.

### 5.6 Explicaciones

Las razones estructuradas (requisitos cubiertos, parciales y faltantes, y las restricciones) se muestran
**siempre** y sin IA. Groq solo redacta la versión en prosa cuando el candidato abre el detalle de una
vacante, con caché y texto de respaldo (como hoy). Groq nunca participa en la decisión.

### 5.7 Qué vacantes llegan al decisor (decisión de diseño)

- **Ingesta del texto completo.** La v2 lee solo el bloque del listado de búsqueda, corta la descripción a
  500 caracteres (`_limpiar_descripcion`) y 8 de las 18 vacantes reales quedan con `requisitos: []`. Así el
  decisor no tendría con qué decidir. En v3 la fuente de Magneto **abre la página de detalle de cada
  vacante** y guarda el texto completo, sin truncar. Esto hace más lento el scraping real (por eso se
  separa como paso propio en n8n y se procesa de forma incremental, solo las vacantes nuevas por
  `hash_contenido`), pero es imprescindible.
- **Prefiltro SQL mínimo.** En SQL solo se excluyen las vacantes vencidas o inactivas y las de modalidad
  **opuesta** (Remoto ↔ Presencial, cuando ambos lados la declararon). Del resto de restricciones duras se
  encarga el decisor, que las muestra como DESCARTAR con su motivo. El dashboard indica cuántas
  vacantes se excluyeron por modalidad ("N vacantes presenciales ocultas"), así que nada desaparece en
  silencio.
- **Conjunto decidido: umbral, no tope (decidido por el usuario).** No hay un número máximo de vacantes por
  candidato, porque un tope fijo esconde vacantes buenas a perfiles amplios. Entra **toda vacante cuya
  similitud de documento con el perfil supere `τ_relevancia`**, sean 30 o 3.000. La búsqueda usa el índice
  HNSW con escaneo iterativo de pgvector (`hnsw.iterative_scan`) para seguir trayendo resultados mientras
  superen el umbral, más un tope técnico de seguridad alto (por ejemplo 5.000) que solo protege contra
  perfiles degenerados y queda registrado en el log si se alcanza. A todas las vacantes que entran se les
  calcula cobertura, restricciones y decisión (las tres operaciones son baratas).
- **El reranker solo ordena, no decide.** Se aplica por páginas dentro de cada acción: al calcular, las
  primeras páginas de POSTULAR y AJUSTAR_CV; el resto se ordena bajo demanda cuando el candidato pagina,
  y queda en caché. Antes de reordenarse, las vacantes se ordenan por similitud de documento.
- **Brecha agregada** ("Docker aparece en 37 de tus vacantes relevantes") se cuenta sobre **todas** las
  vacantes decididas.
- **Persistencia.** `Decision` guarda la **decisión vigente** por par (perfil, vacante): se actualiza en
  lugar de duplicarse cada día y conserva `fecha_decision` y `accion_anterior`. `/historial` lee
  `FotoDiaria`, un resumen por candidato y día (conteos por acción y las ~10 vacantes principales de cada
  acción con su cobertura), así que la base no crece con miles de filas diarias por persona. Lo
  incremental aplica a los **embeddings** (vacantes nuevas o modificadas, perfiles cambiados). Las
  decisiones se recalculan en el batch diario para todos los candidatos con CV.
- **Notificación (preferencia del candidato, decidido por el usuario).** Un cambio a POSTULAR es *nuevo*
  cuando la vacante hoy es POSTULAR y antes no lo era (o no estaba entre las relevantes). Las
  notificaciones nunca limitan lo que se ve: todo sigue en el dashboard. Por correo, el candidato elige en
  `/expectativas` entre: **resumen diario** (un solo correo con todas las novedades, por defecto),
  **individual con máximo N al día** (N configurable, por defecto 3) o **desactivado**. La campana dentro de
  la app muestra todas. `ResultadoDecision` se asocia a la `Decision` vigente del par en el momento de la
  transición del tablero, con una copia de los insumos de ese momento.

## 6. Escala: por qué es viable con 120.000 vacantes

La clave es que **el trabajo pesado depende de cada vacante y no de cada par (candidato, vacante)**:

| Etapa | Frecuencia | Costo estimado (se valida en la Fase 0) |
|---|---|---|
| Extraer requisitos y embeber una vacante | 1 vez por vacante nueva o modificada | 120k × ~9 unidades ≈ 1,1M embeddings para la carga inicial. Con un modelo pequeño en ONNX son decenas de minutos en CPU y bastante menos en GPU. El delta diario (unos miles de vacantes) toma minutos. |
| Almacenamiento | — | Cerca de 1,1M vectores de 384 dimensiones. Con `halfvec` son menos de 1 GB en Postgres. |
| Preselección por candidato | Diaria, o cuando cambia el perfil | Primero el prefiltro SQL mínimo (sección 5.7), luego búsqueda aproximada HNSW con escaneo iterativo hasta `τ_relevancia`. De milisegundos a menos de un segundo. |
| Cobertura | Por candidato, sobre todas las relevantes | Con 3.000 vacantes × ~9 requisitos × ~30 evidencias son unos 810k productos punto, vectorizados en numpy. Menos de un segundo. |
| Reranker | Por candidato, solo las páginas visibles | ~40 pares en el batch (primeras páginas) y luego bajo demanda al paginar. Segundos en CPU. |
| Decisión | Por candidato | Reglas en Python. Despreciable. |
| Groq | Solo cuando el candidato abre un detalle | Igual que hoy. |

**Lo incremental son los vectores**: solo se embeben las vacantes nuevas o modificadas y los perfiles que
cambiaron. Las decisiones se recalculan todos los días (sección 5.7).

**Umbrales de viabilidad (es la puerta de la Fase 0, decisión de diseño)**: en esta máquina, con CPU,
proyectado a 120k vacantes:
- Carga inicial de 120k vacantes: ≤ 8 h en CPU y ≤ 2 h con GPU. Es un proceso que se corre una sola vez.
- Delta diario de 3.000 vacantes nuevas: ≤ 15 min.
- Decisión por candidato (todas las relevantes, con un perfil amplio de unas 3.000, más el reranking de las
  primeras páginas): ≤ 5 s en CPU.
- Página siguiente ordenada bajo demanda: ≤ 1,5 s.

Si un modelo no cumple estos umbrales, se usa la variante más pequeña (e5-small antes que e5-base, y el
reranker más liviano). Si ni la variante más pequeña cumple, se vuelve a este documento.

**Entregable de escala**: el comando `manage.py benchmark_escala` genera 120k vacantes sintéticas a partir
de plantillas de vacantes reales, ejecuta la ingesta y la decisión para N candidatos de prueba, y reporta los
tiempos. Ese número es el que se presenta.

## 7. Arquitectura

### 7.1 Apps (una responsabilidad cada una)

| App | Responsabilidad | Reutiliza de v2 |
|---|---|---|
| `cuentas` | Usuario custom (login por email), login, registro, logout | `accounts/` (incluido el fix de registro por GET) |
| `perfiles` | Perfil, carga y parseo del CV (texto → secciones → unidades de evidencia), expectativas | Las heurísticas de secciones de `cv_parser.py`, **sin** la lista cerrada |
| `vacantes` | Catálogo, `Requisito`, pipeline de ingesta, fuentes de vacantes | La lógica de scraping de `scrape_magneto.py` (detrás de un adaptador) |
| `matching` | El decisor: preselección, cobertura, reranker, política, `Decision`, explicaciones | La tabla de afinidad de modalidad y el adaptador de Groq con caché |
| `postulaciones` | Postulación simulada, tablero Kanban, registro de resultados | HU-08 y HU-10 |
| `notificaciones` | Notificación de decisiones POSTULAR nuevas, correo SMTP, campana | HU-11, `context_processors` |
| `ia` | Puertos (Protocols) de embeddings y reranker, adaptadores de fastembed, fakes para tests | — |
| `api` | Endpoints para n8n con token (`importar-vacantes`, `decidir`, `generar-notificaciones`) | Endpoints actuales |

**Dentro de cada app**: `models.py`, `services.py` (casos de uso que escriben), `selectors.py` (lecturas),
`views.py` delgado (HTTP → servicio → template) y `tests/`.

### 7.2 Patrones (para la sustentación)

- **Pipeline**: tanto la ingesta (fuente → normalizar → extraer requisitos → embeber → guardar) como la
  decisión (preseleccionar → cubrir → rerankear → decidir → guardar) son etapas con una interfaz común.
- **Strategy**: cada restricción dura y cada fuente de vacantes.
- **Chain of Responsibility**: la política de decisión (sección 5.3).
- **Adapter + Ports (Protocols)**: embeddings, reranker, Groq y Magneto. Los tests usan fakes
  determinísticos, sin descargar modelos.
- **Facade**: `matching.services.decidir_para_perfil(perfil)` es la única puerta que usan las vistas y la API.
- **Service layer / selectors**: sacan la lógica de las vistas (el problema principal que muestra el grafo).

### 7.3 Datos (Postgres 17 + pgvector, en Podman)

- `Vacante`: los campos actuales + `vector_doc (halfvec)` + `hash_contenido` para la re-ingesta incremental.
- `Requisito`: vacante, texto, `tipo` (obligatorio/deseable), `vector (halfvec)`.
- `Perfil`: los campos actuales + `vector_doc`. `EvidenciaPerfil`: perfil, texto, sección, `vector`.
- `Decision` (reemplaza a `MatchDiario`): la **decisión vigente**. Tiene perfil, vacante, acción,
  `accion_anterior`, confianza, similitud, relevancia del reranker (puede ser nula hasta que se ordena),
  cobertura (json: requisito → estado + evidencia), restricciones (json), `fecha_decision` y
  `version_politica`. Es única por (perfil, vacante) y alimenta el dashboard y el detalle.
- `FotoDiaria`: perfil, fecha, conteos por acción y las ~10 vacantes principales de cada acción (json).
  Es única por (perfil, fecha) y alimenta `/historial`.
- `Perfil` también guarda la preferencia de notificación (resumen diario / individual con máximo N /
  desactivado) y N.
- `ResultadoDecision`: decisión, resultado (entrevista/descartado) y fecha. Lo escribe postulaciones.
- `Postulacion`, `Notificacion` y `ExplicacionCriterio`: equivalentes a los actuales.
- **No se migran datos de v2**: la base es nueva y las vacantes se vuelven a ingerir. Las cuentas de demo se
  recrean.

### 7.4 n8n

El workflow mantiene sus 3 nodos HTTP en el mismo orden: `importar-vacantes` → `decidir` (reemplaza a
`recalcular-matches`) → `generar-notificaciones`. Se actualizan el JSON del workflow y el `n8n/README.md`.

### 7.5 Visual

- Las URLs y los nombres de rutas (`dashboard`, `vacante_detalle`, `postularme`, `tablero`, etc.) se mantienen.
- Cada template recibe el mismo contexto que en v2, o uno compatible, para que se vea igual.
- **El anillo de % (dashboard, detalle, historial y notificaciones) pasa a mostrar la cobertura**: el % de
  requisitos obligatorios cubiertos (los parciales cuentan como medio). Al lado va la **insignia de acción
  con su confianza** (ej. `POSTULAR · confianza alta`) y debajo el texto "cubres 5/6 obligatorios"
  (decidido por el usuario).
- **Las 5 barras del detalle se mantienen**: *Habilidades* = cobertura. *Experiencia*, *Salario*,
  *Modalidad* y *Ubicación* = estado de cada restricción dura (cumple / parcial / no cumple / sin datos),
  mostrado como barra con su texto. `ExplicacionCriterio` sigue indexada por esos 5 criterios, y su
  `score_pct` pasa a ser el valor de la barra.
- Lo nuevo (insignia de acción, confianza, bloque de requisitos cubiertos/parciales/faltantes, brecha
  agregada y agrupación por acción en el dashboard) se diseña **con el vocabulario CSS existente**.
- Para verificar, se toman capturas antes/después de cada página y se comparan.

## 8. Modelos (los elige el builder en la Fase 0 dentro de estos criterios)

- **Embeddings**: multilingüe con buen rendimiento en español, soportado por fastembed, dimensión ≤ 768 y
  licencia apta para uso académico. Candidatos: `intfloat/multilingual-e5-small` / `-base` y
  `paraphrase-multilingual-MiniLM-L12-v2`.
- **Reranker**: un cross-encoder multilingüe soportado por `fastembed.rerank.cross_encoder`. Candidatos:
  `jinaai/jina-reranker-v2-base-multilingual` (licencia CC-BY-NC: sirve para el curso, **no** para uso
  comercial, y hay que documentarlo) o un `bge-reranker` con licencia más abierta si rinde bien en español.
- La elección se justifica con el set de evaluación (sección 10) y con el benchmark.

## 9. Fases (en orden)

0. **Spike de validación**: Postgres+pgvector en Podman, carga de modelos con fastembed, medición real de
   embeddings/s y pares de reranker/s en CPU y GPU, y elección de modelos. Si los números invalidan la
   sección 6, se vuelve a este documento antes de seguir.
1. **Cimientos**: proyecto nuevo, apps, settings (Postgres, `.env`), `cuentas`, `perfiles` y `vacantes`
   con la ingesta, más **todos los templates renderizando** con el visual intacto.
2. **Decisor**: puertos de `ia`, cobertura, restricciones, política, confianza, `Decision`, dashboard y
   detalle con los elementos nuevos.
3. **Flujo completo**: postulaciones con registro de resultados, notificaciones, API para n8n, workflow
   actualizado y probado de punta a punta.
4. **Evidencia**: set de evaluación, ajuste de umbrales, `benchmark_escala`, README, informe y
   actualización del grafo de graphify.

## 10. Calidad y verificación

- **TDD** en `matching` (cobertura, restricciones, política, confianza), en la extracción de requisitos y
  evidencia, y en los servicios. Se usa pytest + pytest-django, y los tests unitarios no cargan modelos (usan
  fakes).
- **Set de evaluación** (decidido por el usuario: sin datos personales reales):
  - **10–12 CVs ficticios en PDF**, modelados sobre la estructura y redacción de perfiles reales de Magneto y
    LinkedIn, sin copiar a ninguna persona. Cubren distintos niveles (sin experiencia, junior, semi-senior,
    senior), áreas (tecnología, datos, administración/contabilidad, comercial, salud, diseño) y casos
    difíciles: un CV que tiene la habilidad pero la nombra distinto, un CV con la experiencia implícita y
    otro con datos incompletos. Viven en `matching/evaluacion/cvs/` y pasan por el parser real.
  - **40–50 pares (CV, vacante real ingerida)** elegidos para cubrir las 4 acciones, cada uno con la acción
    esperada y una justificación de una línea, en `matching/evaluacion/pares.yaml`.
  - **Independencia**: las etiquetas se proponen y el equipo las **revisa y corrige** antes de usarlas, para
    que el set no sea un reflejo de la misma política que evalúa.
  - **Sin trampa**: los umbrales se ajustan con la mitad de los pares (ajuste) y la exactitud se reporta con
    la otra mitad (prueba), que no se toca durante el ajuste.
  - Se mide la exactitud y la distribución por acción, y se aplican los umbrales de los anti-objetivos (≥ 70%
    de exactitud en prueba, ninguna acción por encima del 80%).
- **Criterios de "listo"**: tests en verde, set de evaluación por encima del umbral, benchmark ejecutado y
  reportado, las 3 etapas de n8n en verde y capturas visuales equivalentes a las de v2.

## 11. Herramientas de construcción (plugins)

- **superpowers**: `writing-plans` (plan), `test-driven-development`, `subagent-driven-development`
  (ejecución), `requesting-code-review` y `verification-before-completion` (cierre de cada fase).
- **oh-my-claudecode**: `architect` (revisa este diseño y el plan), `code-reviewer`, y
  `minimal-code-discipline` / `ai-slop-cleaner` (pasada de clean code por fase).
- **octo**: personas `python-pro`, `database-architect` (esquema pgvector e índices) y `backend-architect`.
- **andrej-karpathy-skills**: guía de cambios quirúrgicos y criterios verificables durante la implementación.
- **impeccable** + **design**: los elementos visuales nuevos, coherentes con el estilo existente.
- **chrome-devtools-mcp**: capturas antes/después para comprobar que el visual se conserva.

## 12. Queda a criterio del builder

La estructura interna de los módulos, los nombres de clases y funciones, la fórmula exacta de la confianza
(dentro de 5.4), los valores iniciales de los umbrales (se ajustan en la Fase 4), cómo se generan los
datos sintéticos del benchmark y el detalle de los fakes de test.

## 13. Enmiendas aprobadas tras la Fase 0 (2026-11-02)

Origen: `spike/fase0/HALLAZGOS.md` (P1–P8), `docs/exploracion/prototipo-decisor-lecciones.md` y
`docs/exploracion/2026-11-02-propuestas-entrevistas.md`. El usuario aprobó: reranker opcional, alcance
**A + C (texto) + B1**, y corregir la seguridad de v2 antes de empezar (hecho en el commit `bcc2550`). Lo marcado
*(criterio del builder)* lo decidió el builder y se puede revertir.

### 13.1 Escala y modelos (reemplaza §5.7 "Conjunto decidido", §6, §7.3 y §8 donde choquen)
- **Embeddings:** `paraphrase-multilingual-MiniLM-L12-v2` (384 d, Apache-2.0). Umbrales iniciales
  τ_alto = 0,50, τ_bajo = 0,40 y τ_relevancia = 0,40, **provisionales** hasta el set de evaluación.
- **Búsqueda exacta dentro de Postgres, sin índice HNSW** *(criterio del builder, P2)*: 17 ms p95 con recall
  100% sobre 120k vectores. Una sola fuente de verdad, sin matrices en memoria. HNSW solo vuelve con más de ~1M.
- **Vector de la vacante = promedio de los vectores de sus requisitos y del título**. El del perfil es el promedio
  de sus unidades de evidencia (P4: MiniLM trunca a ~128 tokens).
- **Requisitos:** además de las filas `Requisito` (texto, tipo y `posicion`), cada vacante guarda su matriz de
  vectores como un `bytea` float16, escrita en la **misma transacción** (P3). `Decision.cobertura` guarda el
  **texto** del requisito, no su id.
- **Reranker opcional (P1-b):** está apagado por defecto. Sin él, el orden dentro de cada acción es
  similitud × cobertura. Si se enciende (`SCOUTLY_RERANKER=bge`, con GPU), usa `bge-reranker-v2-m3`
  (Apache-2.0) *(criterio del builder: se prefiere por licencia sobre jina, que es CC-BY-NC)*. El umbral de
  §6 "página ≤ 1,5 s" aplica solo con el reranker encendido.
- La puerta de viabilidad de la Fase 0 queda **aprobada** con estas decisiones.

### 13.2 El decisor (reemplaza §5.1 y §5.4 donde choquen)
| Acción | Cuándo (en orden de la cadena) |
|---|---|
| **DESCARTAR** | Viola una restricción dura (con su motivo), o le faltan ≥ 3 obligatorios. |
| **SIN_DATOS** | La vacante tiene menos de 2 requisitos legibles. Se muestra como "revísala tú" y **nunca** entra al Plan de hoy. |
| **POSTULAR** | Cubre todos los obligatorios. **POSTULAR con nota** si la cobertura es ≥ 0,7 y falta **uno solo** de nivel herramienta o etiqueta de Magneto (las etiquetas son señales, no obligatorios). |
| **AJUSTAR_CV** | No le falta ningún obligatorio, pero ≥ 1 es parcial y tiene evidencia que lo respalda. |
| **CERRAR_BRECHA** | Le faltan 1 o 2 obligatorios. |

- **"Confianza" pasa a llamarse "solidez"** (alta, media o baja), siempre con su motivo y **sin números**,
  porque no es una probabilidad. Los factores de §5.4 se mantienen.
- **La formación no se mide por similitud.** Es un dato estructurado (nivel y área), porque lo "parcial" no prueba
  un título y AJUSTAR_CV nunca debe sugerir inflar el CV.
- **Filtro de ruido en la extracción:** salario, presentación de la empresa y frases de marketing no son requisitos.
- **El argumento de AJUSTAR_CV** es el volumen de postulantes y la lectura de ~7 s, **no** "los ATS filtran por
  palabra clave" (§5.1 queda corregido en ese punto).
- **Plan de hoy:** 3–5 vacantes POSTULAR/AJUSTAR_CV, como máximo una por empresa, ordenadas por ajuste × frescura.
  Las de menos de 72 h llevan la marca "Postular hoy". Frescura y diversidad son **orden y presentación**, no
  reglas de la cadena. El catálogo completo sigue visible.
- **Plan de aprendizaje:** las brechas de CERRAR_BRECHA, agregadas y ordenadas por frecuencia (es la "brecha
  agregada" de §5.7). Es una tarjeta del dashboard.
- **Métrica:** el decisor debe **superar a la línea base** (orden por similitud pura) en el set de evaluación.
  Los anti-objetivos de §2 se mantienen.
- La regla de experiencia (< 50% de los años pedidos) se marca como **a calibrar**: con 0 años deja fuera a
  juniors en vacantes que piden 1.

### 13.3 Alcance del sprint (reemplaza §2 "No-objetivos" y §9 donde choquen)
- **A, el decisor explicable:** completo. No se recorta.
- **C, el Taller de CV en versión texto:** por cada requisito parcial, una sugerencia concreta de reescritura
  **anclada en una evidencia del CV** ("tu evidencia: …"). Se generan **localmente con plantillas**: no se envían
  viñetas del CV a ningún servicio externo. El candidato acepta o rechaza cada sugerencia, y sin evidencia no se
  sugiere nada (eso va al plan de aprendizaje). El PDF adaptado queda fuera.
- **B1, `candidate.job_detail` del MCP oficial de Magneto:** solo lectura, para traer el texto completo y el
  cuestionario de prefiltro. Va detrás del mismo puerto que el scraping de la página de detalle (Strategy de
  fuentes). **Arranca solo cuando el equipo revise los términos de uso de Magneto**; mientras tanto, la fuente
  por defecto es el scraping del detalle.
- **Fuera del sprint:** `job_apply` (postulación real), `job_applications` y el PDF del Taller.
- **Orden de corte si falta tiempo:** notificaciones por correo → tarjeta "tu mercado" → B1 (se queda el
  scraping). **No se cortan** A, la línea base ni el set de evaluación.
- **Evidencia (Fase 4):** además del set de evaluación, una **evaluación ciega con 2–3 reclutadores**
  (CV original contra el adaptado, y el Plan de hoy contra el top por similitud), usando solo CVs ficticios. Si
  no se consiguen reclutadores, se reporta solo el set de evaluación.

### 13.4 Arquitectura (reemplaza §7.1 y §7.2 donde choquen)
- **5 apps:** `cuentas` (usuario, perfil, CV y expectativas), `vacantes` (catálogo, requisitos, ingesta y
  fuentes), `matching` (decisor, puertos de IA en `matching/puertos.py`, adaptadores y fakes), `postulaciones`
  y `notificaciones`. Los endpoints para n8n viven en un **módulo** `api`, no en una app.
- Patrones: **Strategy** (restricciones y fuentes), **Chain of Responsibility** (política), **Adapter + Ports**
  (embeddings, reranker, Groq, Magneto) y **Facade** (`decidir_para_perfil`). Se quita el "Pipeline con interfaz
  común".
- **Solo el batch carga los modelos**; la web lee las `Decision` ya calculadas. `POST /api/decidir` responde 202 y
  encola el trabajo, para que n8n no espere.

### 13.5 Privacidad y seguridad (sección nueva)
- **Autorización según la Ley 1581** al registrarse: se guardan la versión del texto, la fecha y la finalidad. El
  texto menciona el uso de IA y que Groq (en EE. UU.) solo recibe campos de criterio, nunca el CV.
- **Minimización:** antes de embeber se quitan nombre, correo, teléfono, documento, dirección, edad, género y
  estado civil.
- Un botón **"eliminar mi cuenta"** que borra todo en cascada.
- **Revisión humana:** la decisión es automatizada y se dice así. DESCARTAR siempre muestra el motivo y la
  vacante sigue accesible.
- Se mantienen los arreglos de v2 (secretos y DEBUG desde el entorno, límites a la subida de PDF y validadores de
  contraseña).
