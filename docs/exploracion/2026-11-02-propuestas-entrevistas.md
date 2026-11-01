# Propuestas: cómo Scoutly consigue entrevistas para el candidato (Sprint 3)

Fecha: 2026-11-02 · Estado: **para discutir y aprobar en equipo**. No modifica el diseño aprobado ni el código.
Se apoya en lo siguiente:
- Fase 0: `spike/fase0/HALLAZGOS.md` y `REPORTE.md`.
- La investigación: `docs/exploracion/2026-11-02-que-consigue-entrevistas.md`.
- El prototipo sobre vacantes reales: `docs/exploracion/prototipo-decisor-lecciones.md`.
- Cuatro revisiones: `docs/exploracion/revisiones/`.

## 1. De dónde partimos (la decisión de viabilidad)

La Fase 0 mostró que el decisor local y gratuito **es viable a escala de Magneto (120k vacantes)** con estas
decisiones, que todas las propuestas comparten:

| Pieza | Decisión | Evidencia |
|---|---|---|
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0) | Calidad 0,90; con umbral absoluto separa mucho mejor que potion; carga de 120k en 0,85 h en CPU |
| Búsqueda | **Exacta dentro de Postgres** (sin índice) | 17 ms con recall 100%: no deja ninguna vacante relevante por fuera |
| Requisitos | Matriz bytea por vacante | 72 ms para 3.000 vacantes |
| Reranker | **Opcional** (P1-b): con GPU, bge o jina; sin GPU, orden por similitud × cobertura | En CPU no cumple 1,5 s por página; en GPU tarda 0,1–0,3 s |
| Umbrales | τ_alto = 0,50, τ_bajo = 0,40, τ_relevancia = 0,40 | **Provisionales**: calibrados con el set de 40 casos (escrito por el mismo autor) y revisados a mano sobre 18 vacantes recortadas a 500 caracteres y 3 perfiles ficticios. El set de evaluación de la Fase 2 los confirma o los ajusta |

**Dos lecciones que mandan sobre todo lo demás:**
1. **Sin el texto completo de la vacante, el decisor no decide.** En el prototipo, para el perfil de QA, 5 de sus 14
   vacantes relevantes salieron SIN_DATOS. La causa fue el recorte del fixture: todavía no sabemos cómo se comporta
   con el texto completo.
2. **Una política demasiado estricta pierde entrevistas**: el prototipo le dijo "te falta Canva" a la candidata
   ideal para una práctica de UX.

## 2. Cómo se consigue una entrevista (y dónde entra Scoutly)

Según la evidencia, una entrevista sale de una cadena. Si se rompe cualquier eslabón, se pierde:

| # | Eslabón | Qué dice la evidencia | Qué pieza de Scoutly lo cubre |
|---|---|---|---|
| 1 | Encontrar la vacante **correcta** | 95–244 postulantes por vacante; postular a todo baja la tasa | Búsqueda exacta + umbral de relevancia + DESCARTAR con motivo |
| 2 | Llegar **a tiempo** | Postular en las primeras ~96 h multiplica las posibilidades (evidencia débil, hipótesis a calibrar) | Frescura en el orden y la marca "Postular hoy" |
| 3 | Pasar el **filtro eliminatorio** | 25 de 25 reclutadores usan preguntas de prefiltro | Prefiltro de `job_detail` como restricción dura, con respuestas sugeridas |
| 4 | Que el CV muestre el ajuste en **~7 segundos** | CV adaptado: 5,71% de entrevistas contra 3,09% | AJUSTAR_CV con texto concreto, anclado en evidencia real del CV |
| 5 | **No saturar** a la misma empresa | 1 postulación por empresa: 6,14%; 8 o más: 1,85% | "Plan de hoy" con como máximo una vacante por empresa |
| 6 | **Medir y aprender** | Tasa base de 2–6% | `job_applications` (estado real) o el Kanban → calibrar la política |

Cada propuesta de abajo cubre una parte distinta de esta cadena.

## 3. Las propuestas

### Propuesta A: "Decisor explicable" (el núcleo, sin integraciones externas)
**Qué es:** el diseño aprobado, con las correcciones de la revisión y del prototipo:
- acciones POSTULAR (con o sin nota), AJUSTAR_CV, SIN_DATOS y DESCARTAR, con "solidez" y su motivo;
- un "Plan de hoy" de 3–5 vacantes, como máximo una por empresa;
- un plan de aprendizaje agregado (lo que antes era CERRAR_BRECHA).

Los datos se obtienen haciendo scraping de la **página de detalle** de cada vacante. Los resultados se registran
moviendo tarjetas en el Kanban.

- **Eslabones que cubre:** 1, 2, 5 y parte del 4 (dice *qué* ajustar, pero no redacta el texto).
- **A favor:** no depende de terceros, corre en CPU y es lo más fácil de defender en patrones de diseño.
- **En contra:** la postulación sigue simulada y el resultado depende de que el candidato mueva tarjetas. **No
  produce entrevistas medibles.** Además, el scraping es frágil.
- **Esfuerzo:** medio. Es la base de B y de C.

### Propuesta B: "Copiloto de postulación con el MCP oficial de Magneto" ⭐ mayor impacto en entrevistas
**Qué es:** A, conectado al MCP oficial de candidatos de Magneto (OAuth 2.1, por candidato):
- `candidate.job_search` / `ai_search_jobs` y las **sugerencias de Mimir** (`job_suggestions`) alimentan las
  vacantes de cada candidato. Así Scoutly complementa a Mimir en vez de competir con él.
- `candidate.job_detail` trae el **texto completo** (resuelve SIN_DATOS) y el **cuestionario de prefiltro**
  (eslabón 3).
- `candidate.job_apply` hace una **postulación real**, pero **solo** cuando el candidato la confirma en una
  pantalla de resumen. Nunca en lote ni desde n8n.
- `candidate.job_applications` sincroniza el **estado real** de cada postulación con un nodo nuevo de n8n
  (`sincronizar-postulaciones`). Así la métrica de entrevistas por postulación se mide sola.

Detalles:
- **Eslabones que cubre:** del 1 al 6, en particular el 3 y el 6, que A no cubre.
- **A favor:** convierte a Scoutly en algo que **consigue y mide** entrevistas reales. Usa un canal oficial en
  vez de scraping, y responde el "¿y cómo saben que funciona?" de la sustentación.
- **En contra y riesgos:**
  - el OAuth es por candidato, así que no sirve para traer el catálogo de 120k (la escala se sigue demostrando
    con el benchmark sintético);
  - los límites de uso no están documentados (hay que manejar el error 429 con backoff);
  - hay que **revisar los términos de uso** antes de postular de verdad;
  - los tokens deben guardarse cifrados;
  - hace falta consentimiento según la Ley 1581.
  - Para la demo: **solo cuentas del equipo** y postulaciones reales únicamente a vacantes que cada uno de verdad
    quiera.
- **Esfuerzo:** alto. El orden recomendado es primero **solo lectura** (`job_detail`, `job_search`,
  `job_applications`) y al final `job_apply`, detrás de la confirmación.

### Propuesta C: "Taller de CV por vacante" ⭐ la palanca más respaldada de las disponibles (evidencia media)
**Qué es:** convertir AJUSTAR_CV en el centro del producto. Para cada vacante del plan, Scoutly propone **cambios
concretos al CV**, como reescribir el cargo, el resumen o una viñeta, siempre **anclados a una evidencia que el
candidato ya tiene**. El candidato acepta o rechaza cada cambio y descarga un CV adaptado para esa postulación.

Funcionamiento:
- La cobertura local (MiniLM) detecta qué requisito está *parcialmente* cubierto y por cuál evidencia.
- **Por defecto, las sugerencias se generan localmente con plantillas**, sin ningún servicio externo. Por
  ejemplo: *agrega «Docker» en tu viñeta «Desplegué la app en contenedores…»*. **No se envían viñetas del CV a
  Groq**: aunque no lleven nombre, traen empleadores, proyectos y fechas que identifican a la persona, y además
  sería una transferencia de datos a EE. UU. (revisión de seguridad e investigación §4).
  - Redactar con un LLM queda como opción **solo con autorización expresa** y quitando antes empleadores y fechas.
- Si no hay evidencia, no se sugiere nada: eso va al plan de aprendizaje. Así no se infla el CV.
- **Responsabilidad:** el candidato acepta cada cambio uno por uno, y la pantalla avisa que el CV es suyo y debe
  ser verdadero. Scoutly no envía nada que el candidato no haya leído.

Detalles:
- **Eslabones que cubre:** el 4 a fondo.
  - Huntr reporta casi el doble de tasa de entrevistas con CV adaptado (5,71% contra 3,09%). Es una **asociación
    entre sus propios usuarios**, con evidencia de solidez media.
  - El único experimento de campo de la investigación es sobre **cartas** adaptadas, no sobre CV: 16,4% contra
    12,5% (ResumeGo). Apunta en la misma dirección, pero no prueba el efecto del CV.
- **A favor:** es el diferenciador más claro frente a Magneto/Mimir, que recomiendan vacantes pero no adaptan el
  CV. Se ve muy bien en una demo.
- **En contra:** hay que generar el PDF y controlar que las sugerencias no inventen nada (por eso cada cambio
  muestra "tu evidencia: …").
- **Esfuerzo:** medio. Encaja sobre A sin depender de B.

### Propuesta D: "Mapa del mercado y plan de carrera"
**Qué es:** aprovechar la escala (120k vacantes) para responder "¿qué me abre más puertas?":
- brechas agregadas, por ejemplo "Docker aparece en 37 de tus vacantes relevantes";
- su tendencia en el tiempo;
- vacantes que se abrirían si cierra una brecha.

Detalles:
- **Eslabones que cubre:** ninguno a corto plazo. Aumenta las entrevistas a mediano plazo.
- **A favor:** aquí luce el argumento de escala, y el cálculo es barato y gratis.
- **En contra:** no consigue entrevistas esta semana, así que como propuesta principal no responde al objetivo.
- **Esfuerzo:** bajo si se hace sobre A. Sirve mejor como **sección complementaria** del dashboard.

## 4. Comparación

| | A. Decisor | B. Copiloto MCP | C. Taller de CV | D. Mapa de mercado |
|---|---|---|---|---|
| Entrevistas a corto plazo (esperado, **sin datos propios**) | Medio | Alto | Alto | Bajo |
| Entrevistas medibles | No (Kanban manual) | **Sí** (`job_applications`) | Parcial | No |
| Diferencia frente a Magneto/Mimir | Media | Alta (lo complementa) | **Muy alta** | Media |
| Riesgo técnico o legal | Bajo | **Alto** (OAuth, términos, Ley 1581) | Medio (no inventar) | Bajo |
| Esfuerzo en el sprint | Medio | Alto | Medio | Bajo |
| Funciona sin GPU | Sí | Sí | Sí | Sí |

## 5. Recomendación: A como base, C como diferenciador y B por etapas

1. **A completo** (es requisito de todo lo demás y es lo que más pesa en patrones y clean code).
2. **C**: el Taller de CV. Es la palanca con mejor evidencia y la que más diferencia a Scoutly.
3. **B en dos etapas**:
   - **B1, en este sprint:** solo lectura (`job_detail` para el texto completo y el prefiltro, más
     `job_applications` para medir).
   - **B2, al final y solo si los términos de uso lo permiten:** `job_apply` con confirmación por cada postulación.
4. **D** como una tarjeta del dashboard ("tu mercado"), sin tiempo dedicado aparte.

## 6. Plan de ejecución (alcance realista para 3 personas en un sprint)

La revisión de arquitectura ya advirtió que el diseño base está sobredimensionado para un sprint. Por eso el plan
**garantiza A completo, C en versión texto y B1 solo con `job_detail`**. Todo lo demás queda en un **orden de corte
explícito**.

**Requisito previo, no negociable:** antes de que entre cualquier dato de terceros (voluntarios, evaluadores o
tokens OAuth), se corrigen los hallazgos críticos de seguridad de v2: `SECRET_KEY` fuera del repo y rotada, `DEBUG`
apagado en el túnel, pypdf actualizado y límites a la subida de PDF. También se agrega el consentimiento de la Ley
1581.

| Fase | Entregable | Cómo se verifica | Plugins |
|---|---|---|---|
| **1. Cimientos** | 5 apps (P7), Postgres+pgvector, seguridad y consentimiento (P8), ingesta con **texto completo** (scraping del detalle; o `job_detail` si el MCP ya funciona), los 8 templates renderizando igual que en v2 | Capturas antes/después; **set de ~30 vacantes reales con requisitos esperados y un test de extracción** (riesgo n.º 1 del arquitecto) | superpowers (TDD, subagentes), chrome-devtools, oh-my-claudecode:architect |
| **2. Decisor** | Cobertura, restricciones (Strategy), política (Chain of Responsibility) con **POSTULAR con nota** y **SIN_DATOS**, solidez, Plan de hoy, frescura | Mitad de ajuste del set de evaluación adelantada a esta fase; superar la **línea base de similitud pura** | octo python-pro, karpathy-guidelines |
| **3. Taller y MCP** | C en versión **texto** (sugerencias locales con evidencia, sin PDF); B1 = `job_detail` (texto completo + prefiltro) con las cuentas del equipo | Prueba de punta a punta; revisión de seguridad (tokens, minimización) | oh-my-claudecode:security-reviewer, impeccable/design |
| **4. Evidencia** | Set de evaluación (mitad de prueba), benchmark de escala y **evaluación ciega con 2–3 reclutadores reales** (ver abajo) | Reporte de la evaluación; `REPORTE.md` de escala | oh-my-claudecode:critic, octo code-reviewer |

**Orden de corte si falta tiempo** (se corta primero lo de arriba):
1. B2 (`job_apply`, postulación real);
2. notificaciones y "Plan de hoy" por correo;
3. D (la tarjeta "tu mercado");
4. el PDF del Taller (se entrega el texto para copiar);
5. `job_applications` y la sincronización con n8n;
6. B1 completo (se vuelve al scraping del detalle).

**No se corta:** A (con POSTULAR con nota y SIN_DATOS), la línea base y el set de evaluación.

**La evidencia: evaluación ciega con reclutadores, no piloto de entrevistas.** Para demostrar una diferencia en la
tasa de entrevistas harían falta ~1.900 postulaciones por grupo (investigación §6); con 5–10 voluntarios saldrían
unas 3–9 entrevistas en total, y eso no prueba nada. Dentro del sprint sí es posible esto:
- **2–3 reclutadores reales** (contactos de EAFIT, prácticas o familiares en recursos humanos) comparan **a ciegas**:
  - CV original contra CV adaptado por el Taller, para la misma vacante → valida C;
  - el "Plan de hoy" del decisor contra el top por similitud pura, para el mismo perfil → valida A.
- Se usan los CV ficticios del set de evaluación, **sin datos personales reales**.
- Se reporta como estudio piloto, con el tamaño de la muestra dicho de forma explícita.
- El piloto de entrevistas reales queda como **trabajo futuro**, con la instrumentación ya lista.

**Reparto sugerido** (ajústenlo ustedes):
- **Santiago:** decisor e IA (fases 0 y 2) y la evaluación con reclutadores.
- **Alejandro (Scrum Master):** cimientos, seguridad, n8n y MCP (fases 1 y 3, parte B1).
- **Miguel:** templates, Taller de CV, UI y evidencia visual (fases 1 y 3, parte C).

**Guion de la demo (honesto, sin depender de que una empresa llame):**
1. La candidata abre su "Plan de hoy": 3 vacantes frescas, cada una de una empresa distinta, con su solidez y su
   motivo.
2. En una aparece AJUSTAR_CV. Abre el Taller y acepta 2 cambios, cada uno mostrando "tu evidencia: …".
3. En otra aparece SIN_DATOS: "revísala tú". Así el decisor muestra que no inventa.
4. Si B1 está listo, se ve el prefiltro de la vacante, traído de `job_detail`.
5. Se muestra el plan de aprendizaje agregado.
6. Cierre con evidencia real:
   - "en la evaluación ciega, los reclutadores prefirieron el CV adaptado en N de M casos";
   - "el decisor supera a la línea base en el set de evaluación";
   - "y escala a 120k vacantes: benchmark de 17 ms por búsqueda".

## 7. Decisiones que necesitamos de ustedes
1. **¿Aprueban P1-b (reranker opcional) y P2 (búsqueda exacta en Postgres)?** Con eso la Fase 0 queda aprobada
   formalmente.
2. **¿Alcance A + C (texto) + B1 (`job_detail`), con el orden de corte de arriba?**
3. **Términos de uso de Magneto:** hay que revisarlos tanto para el scraping (A) como para el MCP (B), no solo para
   postular. ¿Quién lo hace y para cuándo? Sin eso, B1 no arranca y se usa el scraping del detalle.
4. **Seguridad de v2:** se propone corregirla **ya**, como requisito previo (ver arriba), no dejarla para la
   reescritura.
5. **Evaluación con reclutadores:** ¿consiguen 2–3 personas de recursos humanos que dediquen ~1 hora?
6. **Postulaciones reales (B2):** fuera del sprint, salvo que los términos lo permitan y el equipo quiera probarlo
   con sus propias cuentas, una postulación a la vez y con confirmación.
