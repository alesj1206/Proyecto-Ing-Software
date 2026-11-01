# Scoutly v3 — Reescritura con decisor de acciones (Sprint 3)

Fecha: 2026-11-01 · Rama: `sprint-3` · Punto de retorno: tag `pre-sprint3-rebuild`

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
- **Conjunto decidido.** La búsqueda aproximada trae el **top-100** por candidato. A las 100 se les calcula
  cobertura, reranker y decisión, y cada una queda guardada como `Decision`. La brecha agregada ("Docker
  aparece en 9 de tus mejores vacantes") se cuenta sobre ese mismo top-100.
- **Escritura diaria.** El batch diario escribe las decisiones de **todos** los candidatos con CV. Lo
  incremental aplica a los **embeddings** (vacantes nuevas o modificadas, perfiles cambiados), no a las
  decisiones: re-decidir 100 vacantes es barato una vez que los vectores existen. Así `/historial`
  conserva su semántica de "foto por día".
- **Notificación.** Se notifica cada vacante que hoy es POSTULAR y ayer no lo era (o no estaba en el
  top-100), con un tope de 3 por día y candidato para no saturar. `ResultadoDecision` se asocia a la
  decisión más reciente del par (perfil, vacante) en el momento de la transición del tablero.

## 6. Escala: por qué es viable con 120.000 vacantes

La clave es que **el trabajo pesado depende de cada vacante y no de cada par (candidato, vacante)**:

| Etapa | Frecuencia | Costo estimado (se valida en la Fase 0) |
|---|---|---|
| Extraer requisitos y embeber una vacante | 1 vez por vacante nueva o modificada | 120k × ~9 unidades ≈ 1,1M embeddings para la carga inicial. Con un modelo pequeño en ONNX son decenas de minutos en CPU y bastante menos en GPU. El delta diario (unos miles de vacantes) toma minutos. |
| Almacenamiento | — | Cerca de 1,1M vectores de 384 dimensiones. Con `halfvec` son menos de 1 GB en Postgres. |
| Preselección por candidato | Diaria, o cuando cambia el perfil | Primero el prefiltro SQL mínimo (sección 5.7), luego búsqueda aproximada (índice HNSW de pgvector) sobre los vectores de documento → top-100. Toma milisegundos. |
| Cobertura | Por candidato, sobre el top-100 | 100 × ~9 requisitos × ~30 evidencias son unos 27k productos punto en numpy. Despreciable. |
| Reranker | Por candidato, sobre el top-100 | 100 pares de cross-encoder. Segundos en CPU y se paraleliza entre candidatos. |
| Decisión | Por candidato | Reglas en Python. Despreciable. |
| Groq | Solo cuando el candidato abre un detalle | Igual que hoy. |

**Lo incremental son los vectores**: solo se embeben las vacantes nuevas o modificadas y los perfiles que
cambiaron. Las decisiones se recalculan todos los días (sección 5.7).

**Umbrales de viabilidad (es la puerta de la Fase 0, decisión de diseño)**: en esta máquina, con CPU,
proyectado a 120k vacantes:
- Carga inicial de 120k vacantes: ≤ 8 h en CPU y ≤ 2 h con GPU. Es un proceso que se corre una sola vez.
- Delta diario de 3.000 vacantes nuevas: ≤ 15 min.
- Decisión por candidato (top-100 completo): ≤ 5 s en CPU.

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
- `Decision` (reemplaza a `MatchDiario`): perfil, vacante, fecha, acción, confianza, relevancia,
  cobertura (json: requisito → estado + evidencia), restricciones (json), `version_politica`. Es única por
  (perfil, vacante, fecha) y alimenta el dashboard y `/historial`.
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
