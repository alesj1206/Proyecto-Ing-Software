# Fase 0: hallazgos y propuestas de cambio al diseño (pendientes de aprobación)

Los números vienen de `REPORTE.md` (generado) y de `resultados/*.json`. El diseño aprobado
(`docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md`) **no se modificó**. Abajo se proponen los
cambios para que el equipo los apruebe o los rechace.

## Veredicto

**Viable, con una condición: el reranker necesita GPU para cumplir los tiempos interactivos.** Todo lo demás
(carga, delta diario, búsqueda y cobertura) cumple en CPU con amplio margen.

| Etapa | Medido (esta máquina) | Límite |
|---|---|---|
| Embeber las 120k vacantes (MiniLM, CPU) | **0,85 h** | ≤ 8 h |
| Embeber las 120k vacantes (MiniLM, GPU) | **0,04 h** (~2 min) | ≤ 2 h |
| Delta diario de 3.000 vacantes (CPU) | **1,3 min** | ≤ 15 min |
| Decisión por candidato (3.000 relevantes + reranking de 40 pares en GPU) | **0,73 s** | ≤ 5 s |
| Página siguiente bajo demanda (20 pares, GPU) | **0,32 s** | ≤ 1,5 s |
| Calidad en español (40 casos difíciles) | embeddings **0,90**, reranker **0,95** | ≥ 0,85 |

Modelos elegidos (los dos con licencia **Apache-2.0**, que permite uso comercial a diferencia de jina):
- **Embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensiones, 0,22 GB).
- **Reranker:** `BAAI/bge-reranker-v2-m3` (fp32, 2,3 GB, en GPU). Acertó 8 de 8 negativos difíciles: separa "Java"
  de "JavaScript" y "enfermería" de "veterinaria".

## Propuestas de cambio al diseño (requieren aprobación)

**P1. El reranker corre en GPU (hoy el diseño dice que la GPU es opcional).**
En CPU el mejor reranker da 8–10 pares/s, así que una página de 20 tarda 2–2,5 s.
- Alternativa en CPU: página bajo demanda de **10** vacantes con `jina-reranker-v2` (1,0 s). Pero jina tiene
  licencia **no comercial** y un 5% menos de calidad.
- Otra alternativa: reordenar en el batch nocturno muchas más páginas (por ejemplo 200 pares, unos 20 s por
  candidato en CPU), de modo que casi nunca haga falta reordenar bajo demanda.
- Recomendación: GPU para la demo y el benchmark (la máquina la tiene), con jina en CPU y páginas de 10 como
  respaldo documentado.

**P2. La búsqueda es exacta en memoria, no con HNSW (cambia §6 y §7.3).**
- Búsqueda exacta en numpy float32 sobre la matriz de 120k × 384 (176 MB): **6,5 ms con recall 100%**.
- HNSW de pgvector: 47 ms con **recall 93%**. Es decir, dejaría por fuera ~7% de las vacantes relevantes, y eso
  choca con la decisión de no limitar al candidato.
- Postgres sigue siendo la fuente de verdad. El proceso de decisión carga la matriz al arrancar. HNSW solo
  vuelve a ser necesario por encima de ~1–2M vacantes.

**P3. Los requisitos de cada vacante se guardan como un `bytea` (matriz float16), no como una fila por requisito.**
Leer los requisitos de 3.000 vacantes baja de **2.147 ms a 68 ms**. Una tabla `Requisito` con el texto sigue
existiendo para mostrar y auditar; el vector de cada requisito va en el bytea.

**P4. El vector de la vacante es el promedio de los vectores de sus requisitos más el del título (cambia §5.2).**
MiniLM solo lee las primeras ~128 palabras, así que embeber la descripción completa perdería los requisitos
del final. Las unidades cortas ya están dentro de su ventana. Esto además quita el paso más caro de la carga
(los documentos largos se procesaban a 5–76/s).

**P5. Cambios en la lógica del decisor que salen de la investigación** (`docs/exploracion/2026-11-02-que-consigue-entrevistas.md`):
- **Corrección a mi propio diseño.** El argumento de "los ATS filtran por palabras clave" de AJUSTAR_CV **no
  tiene evidencia sólida** (solo 2 de 25 reclutadores rechazan automáticamente por contenido). El argumento
  correcto es otro: hay entre 95 y 244 postulantes por vacante, la primera lectura dura ~7 s, y un CV adaptado se
  asocia con 5,71% de entrevistas frente a 3,09%. AJUSTAR_CV se mantiene, pero **solo sugiere lo que tiene
  evidencia en el perfil** (si no la hay, la acción es CERRAR_BRECHA) y prioriza el cargo y el resumen del CV.
- **Frescura.** Penalizar la antigüedad de la vacante (hipótesis a calibrar: postular en las primeras ~96 h).
  Agregar la marca "Postular hoy" para vacantes con buen ajuste y menos de 72 h.
- **Prefiltro de Magneto como restricción dura.** Cada vacante de Magneto puede traer un cuestionario
  eliminatorio. Si se puede leer al ingerir la vacante, se evalúa igual que la modalidad o el salario.
- **No repetir empresa.** Diversificar las vacantes POSTULAR: 8 o más postulaciones a una misma empresa se asocian
  con 1,85% de entrevistas, frente a 6,14% con una sola.
- **Métrica norte:** entrevistas ÷ postulaciones, medida con el Kanban (con los estados `postulado` y
  `entrevista`). Referencia externa: 3–6%.
- **Equidad y Ley 1581:** quitar nombre, foto, edad, cédula y estado civil **antes** de embeber (hay estudios de
  sesgo en embeddings de CV). El procesamiento local ya es una ventaja: el CV no sale de la máquina, salvo el
  texto que se le pasa a Groq para las explicaciones, y eso hay que revisarlo.

## Limitaciones de esta fase

- Los vectores del benchmark de pgvector y de la búsqueda exacta son **sintéticos** (agrupados, no de texto
  real). Los tiempos son representativos; el recall con textos reales hay que confirmarlo en la Fase 2.
- El set de calidad (40 casos) lo escribí yo. Puede estar sesgado hacia lo que el modelo hace bien, así que el
  equipo debe revisarlo y ampliarlo. El set de evaluación de la Fase 4 es el que cuenta.
- La GPU de producción no está definida. Si la demo corre en un servidor sin GPU, aplica la alternativa de P1.
