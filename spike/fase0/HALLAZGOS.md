# Fase 0: hallazgos y propuestas de cambio al diseño (pendientes de aprobación)

Los números salen de `REPORTE.md` (generado con `python -m spike.fase0.reporte`) y de `resultados/*.json`.
**El diseño aprobado** (`docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md`) **no se modificó.**
Revisaron este trabajo: un revisor final independiente y 4 revisores de los plugins oh-my-claudecode y octo
(arquitectura, producto, código y seguridad). Sus informes están en `docs/exploracion/revisiones/`.

## Veredicto (contra el spec aprobado)

**El §6 no se cumple en CPU.** Lo único que falla es `pagina_s`: el reranker en CPU tarda 2,0–2,5 s en ordenar una
página de 20 vacantes, y el límite es 1,5 s. Como el §3 dice "todo debe funcionar en CPU" y el §9 dice que, si la
Fase 0 no cumple, se vuelve al diseño, **el resultado formal de la puerta es VOLVER AL DISEÑO.**

Pasa a ser viable si se aprueba **una** de estas dos opciones:
- **P1-a:** el reranker corre en GPU (en esta máquina, una página de 20 tarda 0,11–0,32 s).
- **P1-b:** el reranker deja de ser obligatorio (lo propone la revisión de arquitectura). El propio diseño dice
  que "solo ordena, no decide", así que sin reranker las vacantes se ordenan por similitud × cobertura y todo
  cumple en CPU. Se puede activar cuando haya GPU.

Todo lo demás cumple en CPU con mucho margen:

| Etapa (esta máquina) | Medido | Límite |
|---|---|---|
| Embeber las 120k vacantes, CPU (potion / MiniLM) | 0,01 h / 0,85 h | ≤ 8 h |
| Delta diario de 3.000 vacantes, CPU | < 1 s / 1,3 min | ≤ 15 min |
| Búsqueda exacta en Postgres, 120k vectores, p95 | **17 ms** (384d) / 24 ms (768d), **recall 100%** | — |
| Lectura de requisitos de 3.000 vacantes (bytea), p95 | 72 ms | — |
| Decisión por candidato (reranker en GPU) | 0,32–0,74 s | ≤ 5 s |

## Qué modelos quedan, y qué tan seguros estamos

La elección es **provisional**: el set de calidad es demasiado chico para separar los modelos.
- **Embeddings.** Hay 40 casos, y cada caso vale 2,5 puntos (intervalo de confianza del 95% de unos ±10 puntos).
  MiniLM (36/40) y potion (35/40) están a un solo caso, así que no se distinguen **en orden entre pares**. El
  reporte automático se queda con potion por velocidad, pero **esa elección queda anulada**: el prototipo sobre
  vacantes reales mostró que la cobertura usa un **umbral absoluto**, y ahí potion separa mucho peor. Con τ = 0,40,
  MiniLM deja sobre el umbral al 85% de los positivos y al 10% de los negativos; potion, al 55% y al 8%. **Se
  recomienda `paraphrase-multilingual-MiniLM-L12-v2`** (Apache-2.0, 0,85 h de carga en CPU), con umbrales
  calibrados τ_alto = 0,50 y τ_bajo = 0,40. Ver `docs/exploracion/prototipo-decisor-lecciones.md`.
- **Reranker.** En la tarea real (perfil resumido frente a resumen de vacante), **los tres sacaron 20/20**, así que
  este set no sirve para elegir. En pares cortos, bge sacó 0,95 y jina 0,90. El reporte elige
  **`jina-reranker-v2-base-multilingual`** por velocidad (178 pares/s en GPU), pero su licencia es **CC-BY-NC**:
  sirve para el curso, no para un producto comercial. La alternativa con licencia Apache es `bge-reranker-v2-m3`
  (62 pares/s en GPU, que también cumple).
- **Pendiente para la Fase 4:** un set de ranking más difícil, con trampas del mismo cargo pero distinto nivel
  de senioridad y requisitos casi iguales.

## Propuestas de cambio al diseño (requieren aprobación)

**P1. El reranker en GPU, o hacerlo opcional.** Las opciones a y b están en el veredicto. Recomiendo **b para
la arquitectura** (que la app no dependa de una GPU) **y a para la demo** (en esta máquina sí hay GPU).

**P2. Búsqueda exacta dentro de Postgres, sin índice HNSW** (cambia §6 y §7.3).
- 17 ms con recall 100%, frente a 48 ms con recall de 93% de HNSW, que dejaría por fuera ~7% de las vacantes
  relevantes y contradice la decisión de no limitar al candidato.
- Antes propuse una matriz numpy en memoria (11 ms). **La retiro**: la revisión de arquitectura mostró que se
  desincroniza entre workers y con cada delta diario. Con Postgres hay una sola fuente de verdad.
- HNSW solo vuelve a hacer falta con más de ~1–2M vacantes.

**P3. Requisitos como una matriz `bytea` (float16) por vacante.**
- **Corrección:** la primera comparación (2.147 ms frente a 68 ms) mezclaba protocolo de texto con protocolo
  binario. Con binario en ambos casos, la mejora real es de **204 ms a 72 ms (~3×)**.
- Se mantiene porque ahorra ~130 ms por candidato, pero ya no es crítica.
- Condición (revisión de arquitectura): escribir el bytea y las filas de `Requisito` en una sola transacción,
  con una columna `posicion`. `Decision.cobertura` guarda el texto del requisito, no su id.

**P4. El vector de la vacante es el promedio de sus requisitos más el título** (cambia §5.2).
- MiniLM trunca a ~128 *tokens*, y los 76 documentos/s que dio se midieron sobre texto ya truncado. Con el
  promedio, ningún requisito del final de la vacante se pierde, y el paso más caro de la carga desaparece.
- El vector del perfil se arma igual: el promedio de sus unidades de evidencia.

**P5. Cambios en lo que entrega el decisor (los motiva la crítica de producto y la investigación):**
- **Corrijo mi propio diseño.** "Los ATS filtran por palabras clave" no tiene evidencia sólida (solo 2 de 25
  reclutadores lo hacen). El argumento correcto para AJUSTAR_CV es el volumen (95–244 postulaciones por vacante),
  la lectura de ~7 s y el dato de que un CV adaptado se asocia con 5,71% de entrevistas frente a 3,09%.
- **AJUSTAR_CV entrega texto concreto**, anclado en una evidencia del CV, priorizando el cargo y el resumen, y el
  candidato confirma cada cambio. Si no hay evidencia, la acción pasa a CERRAR_BRECHA.
- **"Plan de hoy":** 3–5 vacantes, como máximo una por empresa, ordenadas por ajuste × frescura. Las de menos de
  72 h llevan la marca "Postular hoy". El catálogo completo sigue visible. Frescura y diversificación son
  **orden y presentación**, no reglas de la cadena de decisión.
- **CERRAR_BRECHA pasa a un plan de aprendizaje** agregado, con las brechas ordenadas por frecuencia.
- **"Confianza" se renombra a "solidez"** (alta/media/baja), siempre con su motivo y sin números, porque no es una
  probabilidad.
- **Métrica de éxito:** el decisor tiene que **superar a una línea base** (orden por similitud pura). La métrica
  norte es **entrevistas ÷ postulaciones**, y se reporta como piloto con intervalos de confianza. La exactitud
  contra etiquetas del equipo se mantiene solo como métrica secundaria.

**P6 (nueva). Integrar el MCP oficial de Magneto para candidatos** (`api.magneto365.com/mcp/candidates`, OAuth 2.1):
- `job_detail` trae el texto completo y el **cuestionario de prefiltro**. Reemplaza a Playwright y resuelve el
  problema de los requisitos vacíos.
- `job_applications` trae el **estado real** de cada postulación, así que el ciclo de retroalimentación queda
  automático.
- `job_apply` permite una **postulación real**, pero solo con confirmación explícita del candidato **en cada
  postulación** (nunca en lote ni desde n8n), con tokens cifrados y registro de auditoría.
- **Límite:** el OAuth es por candidato, así que **no sirve para traer el catálogo de 120k**. Sirve para la
  búsqueda y las sugerencias de cada candidato, y la escala se sigue demostrando con el benchmark sintético.
- Antes de postular de verdad hay que revisar los términos de uso de Magneto.

**P7 (nueva). Arquitectura más simple** (revisión de arquitectura): 5 apps en vez de 8:
- `ia` pasa a `matching/puertos.py`;
- `perfiles` se une a `cuentas`;
- `api` queda como módulo.

Se mantienen Strategy, Chain of Responsibility, Adapter y Facade, y se quita el "Pipeline con interfaz común",
que es solo ceremonia. Solo el batch carga los modelos; la web lee las `Decision` ya calculadas. `decidir` responde
202 y encola el trabajo, para que n8n no se quede esperando.

**P8 (nueva). Privacidad y seguridad como sección del spec** (revisión de seguridad):
- autorización de la Ley 1581 al registrarse;
- quitar los datos personales antes de embeber;
- botón "eliminar mi cuenta";
- evaluación de impacto según la Circular SIC 002/2024.

También son urgentes estos problemas de la v2, que **no toqué**: `SECRET_KEY` versionada en el repo,
`DEBUG=True` expuesto por el túnel, pypdf con 26 CVE y subida de PDF sin límites.

## Limitaciones

- Los vectores del benchmark de búsqueda son **sintéticos** (agrupados). Los tiempos son representativos, pero el
  recall de HNSW con texto real puede ser distinto. Con búsqueda exacta este riesgo desaparece.
- Los sets de calidad los escribí yo. El equipo debe revisarlos y ampliarlos; el set que cuenta es el de la Fase 4.
- Hallazgos menores de la revisión que quedan diferidos (no cambian el veredicto):
  - un calentamiento repetido en `bench_pgvector`;
  - el calentamiento del reranker en GPU con un lote distinto al medido;
  - los casos de acentos que quitan las tildes a las dos opciones a la vez.
