# Fase 0 — Reporte de viabilidad (generado por `python -m spike.fase0.reporte`)

**Veredicto global: NO CUMPLE §6 EN CPU → VOLVER AL DISEÑO; viable con GPU para el reranker si se aprueba P1**

Elegido: `minishlab/potion-multilingual-128M` + `jinaai/jina-reranker-v2-base-multilingual` · arquitectura **exacta_pg** (búsqueda exacta dentro de Postgres (sin índice) + requisitos en bytea por vacante) · reranker en **cuda**

Límites (spec §6): carga_inicial_cpu_h ≤ 8, carga_inicial_gpu_h ≤ 2, delta_diario_min ≤ 15, decision_candidato_s ≤ 5, pagina_s ≤ 1.5, calidad ≥ 0.85.

Arquitecturas: **hnsw** = pgvector HNSW + requisitos fila por fila; **exacta** = búsqueda exacta numpy f32 en memoria + requisitos en bytea por vacante; **exacta_pg** = búsqueda exacta dentro de Postgres (sin índice) + requisitos en bytea por vacante.

Solo se listan las combinaciones que cumplen todos los umbrales; el resto queda en el JSON de resultados.

Calidad: 1 caso del set de embeddings = 2.5 puntos; diferencias de un caso no se distinguen (intervalo de 95% ≈ ±10 puntos), así que la elección de modelo es **provisional** hasta el set de evaluación de la Fase 4. `cal. rer` = tarea real (perfil resumido vs. resumen de vacante); `cal. rer unid.` = pares cortos requisito/evidencia.

| Combinación | dim | cal. emb | cal. rer | cal. rer unid. | recall | pares/s | carga_inicial_cpu_h | carga_inicial_gpu_h | delta_diario_min | decision_candidato_s | pagina_s | calidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] | 384 | 0.90 | 1.00 | 0.90 | 0.93 | 178.6 | 0.85 | 0.04 | 1.27 | 0.41 | 0.11 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + jina-reranker-v2-base-multilingual [exacta, reranker cuda] | 384 | 0.90 | 1.00 | 0.90 | 1.00 | 178.6 | 0.85 | 0.04 | 1.27 | 0.31 | 0.11 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + jina-reranker-v2-base-multilingual [exacta_pg, reranker cuda] | 384 | 0.90 | 1.00 | 0.90 | 1.00 | 178.6 | 0.85 | 0.04 | 1.27 | 0.32 | 0.11 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + bge-reranker-v2-m3 [hnsw, reranker cuda] | 384 | 0.90 | 1.00 | 0.95 | 0.93 | 61.7 | 0.85 | 0.04 | 1.27 | 0.83 | 0.32 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + bge-reranker-v2-m3 [exacta, reranker cuda] | 384 | 0.90 | 1.00 | 0.95 | 1.00 | 61.7 | 0.85 | 0.04 | 1.27 | 0.74 | 0.32 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + bge-reranker-v2-m3 [exacta_pg, reranker cuda] | 384 | 0.90 | 1.00 | 0.95 | 1.00 | 61.7 | 0.85 | 0.04 | 1.27 | 0.74 | 0.32 | 0.90 |
| potion-multilingual-128M + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] | 256 | 0.88 | 1.00 | 0.90 | 0.93 | 178.6 | 0.01 | 0.01 | 0.01 | 0.41 | 0.11 | 0.88 |
| potion-multilingual-128M + jina-reranker-v2-base-multilingual [exacta, reranker cuda] | 256 | 0.88 | 1.00 | 0.90 | 1.00 | 178.6 | 0.01 | 0.01 | 0.01 | 0.31 | 0.11 | 0.88 |
| potion-multilingual-128M + jina-reranker-v2-base-multilingual [exacta_pg, reranker cuda] | 256 | 0.88 | 1.00 | 0.90 | 1.00 | 178.6 | 0.01 | 0.01 | 0.01 | 0.32 | 0.11 | 0.88 |
| potion-multilingual-128M + bge-reranker-v2-m3 [hnsw, reranker cuda] | 256 | 0.88 | 1.00 | 0.95 | 0.93 | 61.7 | 0.01 | 0.01 | 0.01 | 0.83 | 0.32 | 0.88 |
| potion-multilingual-128M + bge-reranker-v2-m3 [exacta, reranker cuda] | 256 | 0.88 | 1.00 | 0.95 | 1.00 | 61.7 | 0.01 | 0.01 | 0.01 | 0.74 | 0.32 | 0.88 |
| potion-multilingual-128M + bge-reranker-v2-m3 [exacta_pg, reranker cuda] | 256 | 0.88 | 1.00 | 0.95 | 1.00 | 61.7 | 0.01 | 0.01 | 0.01 | 0.74 | 0.32 | 0.88 |
| multilingual-e5-small + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] | 384 | 0.85 | 1.00 | 0.90 | 0.93 | 178.6 | 0.83 | 0.09 | 1.24 | 0.41 | 0.11 | 0.85 |
| multilingual-e5-small + jina-reranker-v2-base-multilingual [exacta, reranker cuda] | 384 | 0.85 | 1.00 | 0.90 | 1.00 | 178.6 | 0.83 | 0.09 | 1.24 | 0.31 | 0.11 | 0.85 |
| multilingual-e5-small + jina-reranker-v2-base-multilingual [exacta_pg, reranker cuda] | 384 | 0.85 | 1.00 | 0.90 | 1.00 | 178.6 | 0.83 | 0.09 | 1.24 | 0.32 | 0.11 | 0.85 |
| multilingual-e5-small + bge-reranker-v2-m3 [hnsw, reranker cuda] | 384 | 0.85 | 1.00 | 0.95 | 0.93 | 61.7 | 0.83 | 0.09 | 1.24 | 0.83 | 0.32 | 0.85 |
| multilingual-e5-small + bge-reranker-v2-m3 [exacta, reranker cuda] | 384 | 0.85 | 1.00 | 0.95 | 1.00 | 61.7 | 0.83 | 0.09 | 1.24 | 0.74 | 0.32 | 0.85 |
| multilingual-e5-small + bge-reranker-v2-m3 [exacta_pg, reranker cuda] | 384 | 0.85 | 1.00 | 0.95 | 1.00 | 61.7 | 0.83 | 0.09 | 1.24 | 0.74 | 0.32 | 0.85 |

## Por qué falla cada combinación descartada (primer umbral incumplido)

- **decision_candidato_s** (17): multilingual-e5-base + bge-reranker-v2-m3-int8 [exacta, reranker cpu] (5.16 > 5); multilingual-e5-base + bge-reranker-v2-m3-int8 [exacta_pg, reranker cpu] (5.17 > 5); multilingual-e5-base + bge-reranker-v2-m3-int8 [hnsw, reranker cpu] (5.35 > 5); multilingual-e5-base + bge-reranker-v2-m3-int8 [hnsw, reranker cuda] (5.01 > 5); multilingual-e5-small + bge-reranker-v2-m3-int8 [exacta, reranker cpu] (5.10 > 5); multilingual-e5-small + bge-reranker-v2-m3-int8 [exacta_pg, reranker cpu] (5.11 > 5) …
- **pagina_s** (28): multilingual-e5-base + bge-reranker-v2-m3-int8 [exacta, reranker cuda] (2.34 > 1.5); multilingual-e5-base + bge-reranker-v2-m3-int8 [exacta_pg, reranker cuda] (2.34 > 1.5); multilingual-e5-base + jina-reranker-v2-base-multilingual [exacta, reranker cpu] (2.00 > 1.5); multilingual-e5-base + jina-reranker-v2-base-multilingual [exacta_pg, reranker cpu] (2.00 > 1.5); multilingual-e5-base + jina-reranker-v2-base-multilingual [hnsw, reranker cpu] (2.00 > 1.5); multilingual-e5-small + bge-reranker-v2-m3-int8 [exacta, reranker cuda] (2.34 > 1.5) …
- **calidad** (6): multilingual-e5-base + bge-reranker-v2-m3 [exacta, reranker cuda] (0.82); multilingual-e5-base + bge-reranker-v2-m3 [exacta_pg, reranker cuda] (0.82); multilingual-e5-base + bge-reranker-v2-m3 [hnsw, reranker cuda] (0.82); multilingual-e5-base + jina-reranker-v2-base-multilingual [exacta, reranker cuda] (0.82); multilingual-e5-base + jina-reranker-v2-base-multilingual [exacta_pg, reranker cuda] (0.82); multilingual-e5-base + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] (0.82)
- **carga_inicial_gpu_h** (6): paraphrase-multilingual-mpnet-base-v2 + bge-reranker-v2-m3 [exacta, reranker cuda] (nan > 2); paraphrase-multilingual-mpnet-base-v2 + bge-reranker-v2-m3 [exacta_pg, reranker cuda] (nan > 2); paraphrase-multilingual-mpnet-base-v2 + bge-reranker-v2-m3 [hnsw, reranker cuda] (nan > 2); paraphrase-multilingual-mpnet-base-v2 + jina-reranker-v2-base-multilingual [exacta, reranker cuda] (nan > 2); paraphrase-multilingual-mpnet-base-v2 + jina-reranker-v2-base-multilingual [exacta_pg, reranker cuda] (nan > 2); paraphrase-multilingual-mpnet-base-v2 + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] (nan > 2)
