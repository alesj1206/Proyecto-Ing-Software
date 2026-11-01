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
| Umbrales | τ_alto = 0,50, τ_bajo = 0,40, τ_relevancia = 0,40 | Calibrados con el set de 40 y probados sobre vacantes reales |

**Dos lecciones que mandan sobre todo lo demás:**
1. **Sin el texto completo de la vacante, el decisor no decide**: 5 de 14 vacantes salieron SIN_DATOS en el
   prototipo.
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

### Propuesta C: "Taller de CV por vacante" ⭐ la palanca con mejor evidencia
**Qué es:** convertir AJUSTAR_CV en el centro del producto. Para cada vacante del plan, Scoutly propone **cambios
concretos al CV**, como reescribir el cargo, el resumen o una viñeta, siempre **anclados a una evidencia que el
candidato ya tiene**. El candidato acepta o rechaza cada cambio y descarga un CV adaptado para esa postulación.

Funcionamiento:
- La cobertura local (MiniLM) detecta qué requisito está *parcialmente* cubierto y por cuál evidencia.
- Groq solo redacta el texto propuesto, recibiendo **la evidencia y el requisito, sin datos personales**
  (minimización según la Ley 1581).
- Si no hay evidencia, no se sugiere nada: eso va al plan de aprendizaje. Así no se infla el CV.

Detalles:
- **Eslabones que cubre:** el 4 a fondo. Huntr reporta casi el doble de tasa de entrevistas con CV adaptado
  (5,71% contra 3,09%; es asociación, no causalidad).
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
| Entrevistas a corto plazo | Medio | **Alto** | **Alto** | Bajo |
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

## 6. Plan de ejecución (ajusta las fases del diseño a esta recomendación)

| Fase | Entregable | Cómo se verifica | Plugins |
|---|---|---|---|
| **1. Cimientos** | 5 apps (P7), Postgres+pgvector, cuentas/perfiles con **consentimiento Ley 1581** (P8), ingesta con **texto completo** (scraping del detalle o `job_detail`), los 8 templates renderizando igual que en v2 | Capturas antes/después; **set de ~30 vacantes reales con requisitos esperados y un test de extracción** (riesgo n.º 1 del arquitecto) | superpowers (TDD, subagentes), chrome-devtools (capturas), oh-my-claudecode:architect |
| **2. Decisor** | Cobertura, restricciones (Strategy), política (Chain of Responsibility) con **POSTULAR con nota** y **SIN_DATOS**, solidez, Plan de hoy, frescura | Mitad de ajuste del set de evaluación **adelantada a esta fase**; el decisor debe superar a la **línea base de similitud pura** | octo python-pro, karpathy-guidelines |
| **3. Copiloto y Taller** | B1 (MCP en solo lectura + sincronizar postulaciones), C (sugerencias de CV con evidencia + PDF), notificaciones y Plan de hoy por correo | Prueba de punta a punta con las cuentas del equipo; revisión de seguridad de tokens y minimización | oh-my-claudecode:security-reviewer, impeccable/design (UI del taller) |
| **4. Evidencia** | Set de evaluación (mitad de prueba), benchmark de escala, **piloto**: el equipo y algunos voluntarios usan Scoutly 2–3 semanas y se mide entrevistas ÷ postulaciones con decisor frente a sin decisor, reportado con intervalos de confianza | Reporte del piloto; `REPORTE.md` de escala | oh-my-claudecode:critic, octo code-reviewer (pasada final de clean code) |

**Reparto sugerido** (ajústenlo ustedes):
- **Santiago:** el decisor y la parte de IA (fases 0 y 2).
- **Alejandro (Scrum Master):** cimientos, n8n y el MCP (fases 1 y 3, parte B).
- **Miguel:** templates, Taller de CV, UI y evidencia visual (fases 1 y 3, parte C).

**Guion de la demo (lo que hace decir "esto sirve"):**
1. La candidata abre su "Plan de hoy": 3 vacantes frescas, cada una de una empresa distinta.
2. En una aparece "AJUSTAR_CV". Abre el Taller, acepta 2 cambios que muestran su evidencia y descarga el CV
   adaptado.
3. Ve el prefiltro con las respuestas sugeridas.
4. Confirma la postulación (real con B2, o simulada si no se aprueba).
5. Días después, la tarjeta pasa sola a "Entrevista", porque `job_applications` la sincronizó.
6. Cierre con el número: "con el decisor, X% de entrevistas contra Y% de la línea base en el piloto".

## 7. Decisiones que necesitamos de ustedes
1. **¿Aprueban P1-b (reranker opcional) y P2 (búsqueda exacta en Postgres)?** Con eso la Fase 0 queda aprobada
   formalmente.
2. **¿Recomendación A + C + B por etapas, o prefieren otra combinación?**
3. **MCP de Magneto:** ¿alguien del equipo puede revisar los términos de uso y probar el OAuth con su cuenta?
   Sin eso, B no arranca.
4. **¿Postulaciones reales (B2) en la demo?** Mi recomendación es que solo sea con la cuenta y la decisión de cada
   uno, y nunca automáticas.
5. **Seguridad de v2:** ¿se corrige ya (SECRET_KEY, DEBUG, pypdf) o se deja para la reescritura? Mientras la demo
   pública siga por el túnel, conviene corregirlo ya.
6. **Piloto:** ¿consiguen 5–10 voluntarios para 2–3 semanas? Sin piloto, la métrica de entrevistas queda solo
   como diseño.
