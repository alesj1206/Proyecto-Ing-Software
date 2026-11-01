# Fase 0 — Reporte de viabilidad (generado por `python -m spike.fase0.reporte`)

**Veredicto global: VIABLE SOLO CON GPU PARA EL RERANKER**

Elegido: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` + `BAAI/bge-reranker-v2-m3` · arquitectura **exacta** (búsqueda exacta numpy f32 en memoria + requisitos en bytea por vacante) · reranker en **cuda**

Límites (spec §6): carga_inicial_cpu_h ≤ 8, carga_inicial_gpu_h ≤ 2, delta_diario_min ≤ 15, decision_candidato_s ≤ 5, pagina_s ≤ 1.5, calidad ≥ 0.85.

Arquitecturas: **hnsw** = pgvector HNSW + requisitos fila por fila; **exacta** = búsqueda exacta numpy f32 en memoria + requisitos en bytea por vacante.

Solo se listan las combinaciones que cumplen todos los umbrales; el resto queda en el JSON de resultados.

| Combinación | dim | cal. emb | cal. rer | recall | pares/s | carga_inicial_cpu_h | carga_inicial_gpu_h | delta_diario_min | decision_candidato_s | pagina_s | calidad |
|---|---|---|---|---|---|---|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] | 384 | 0.90 | 0.90 | 0.93 | 178.6 | 0.85 | 0.04 | 1.27 | 2.42 | 0.11 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + jina-reranker-v2-base-multilingual [exacta, reranker cuda] | 384 | 0.90 | 0.90 | 1.00 | 178.6 | 0.85 | 0.04 | 1.27 | 0.30 | 0.11 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + bge-reranker-v2-m3 [hnsw, reranker cuda] | 384 | 0.90 | 0.95 | 0.93 | 61.7 | 0.85 | 0.04 | 1.27 | 2.85 | 0.32 | 0.90 |
| paraphrase-multilingual-MiniLM-L12-v2 + bge-reranker-v2-m3 [exacta, reranker cuda] | 384 | 0.90 | 0.95 | 1.00 | 61.7 | 0.85 | 0.04 | 1.27 | 0.73 | 0.32 | 0.90 |
| potion-multilingual-128M + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] | 256 | 0.88 | 0.90 | 0.93 | 178.6 | 0.01 | 0.01 | 0.01 | 2.42 | 0.11 | 0.88 |
| potion-multilingual-128M + jina-reranker-v2-base-multilingual [exacta, reranker cuda] | 256 | 0.88 | 0.90 | 1.00 | 178.6 | 0.01 | 0.01 | 0.01 | 0.30 | 0.11 | 0.88 |
| potion-multilingual-128M + bge-reranker-v2-m3 [hnsw, reranker cuda] | 256 | 0.88 | 0.95 | 0.93 | 61.7 | 0.01 | 0.01 | 0.01 | 2.85 | 0.32 | 0.88 |
| potion-multilingual-128M + bge-reranker-v2-m3 [exacta, reranker cuda] | 256 | 0.88 | 0.95 | 1.00 | 61.7 | 0.01 | 0.01 | 0.01 | 0.73 | 0.32 | 0.88 |
| multilingual-e5-small + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] | 384 | 0.85 | 0.90 | 0.93 | 178.6 | 0.83 | 0.09 | 1.24 | 2.42 | 0.11 | 0.85 |
| multilingual-e5-small + jina-reranker-v2-base-multilingual [exacta, reranker cuda] | 384 | 0.85 | 0.90 | 1.00 | 178.6 | 0.83 | 0.09 | 1.24 | 0.30 | 0.11 | 0.85 |
| paraphrase-multilingual-mpnet-base-v2 + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] | 768 | 0.85 | 0.90 | 0.93 | 178.6 | 2.81 | — | 4.21 | 4.49 | 0.11 | 0.85 |
| paraphrase-multilingual-mpnet-base-v2 + jina-reranker-v2-base-multilingual [exacta, reranker cuda] | 768 | 0.85 | 0.90 | 1.00 | 178.6 | 2.81 | — | 4.21 | 0.35 | 0.11 | 0.85 |
| multilingual-e5-small + bge-reranker-v2-m3 [hnsw, reranker cuda] | 384 | 0.85 | 0.95 | 0.93 | 61.7 | 0.83 | 0.09 | 1.24 | 2.85 | 0.32 | 0.85 |
| multilingual-e5-small + bge-reranker-v2-m3 [exacta, reranker cuda] | 384 | 0.85 | 0.95 | 1.00 | 61.7 | 0.83 | 0.09 | 1.24 | 0.73 | 0.32 | 0.85 |
| paraphrase-multilingual-mpnet-base-v2 + bge-reranker-v2-m3 [hnsw, reranker cuda] | 768 | 0.85 | 0.95 | 0.93 | 61.7 | 2.81 | — | 4.21 | 4.91 | 0.32 | 0.85 |
| paraphrase-multilingual-mpnet-base-v2 + bge-reranker-v2-m3 [exacta, reranker cuda] | 768 | 0.85 | 0.95 | 1.00 | 61.7 | 2.81 | — | 4.21 | 0.78 | 0.32 | 0.85 |

## Por qué falla cada combinación descartada (primer umbral incumplido)

- **decision_candidato_s** (20): multilingual-e5-base + bge-reranker-v2-m3-int8 [exacta, reranker cpu] (5.15 > 5); multilingual-e5-base + bge-reranker-v2-m3-int8 [hnsw, reranker cpu] (9.28 > 5); multilingual-e5-base + bge-reranker-v2-m3-int8 [hnsw, reranker cuda] (8.94 > 5); multilingual-e5-base + jina-reranker-v2-base-multilingual [hnsw, reranker cpu] (8.27 > 5); multilingual-e5-small + bge-reranker-v2-m3-int8 [exacta, reranker cpu] (5.09 > 5); multilingual-e5-small + bge-reranker-v2-m3-int8 [hnsw, reranker cpu] (7.21 > 5) …
- **pagina_s** (10): multilingual-e5-base + bge-reranker-v2-m3-int8 [exacta, reranker cuda] (2.34 > 1.5); multilingual-e5-base + jina-reranker-v2-base-multilingual [exacta, reranker cpu] (2.00 > 1.5); multilingual-e5-small + bge-reranker-v2-m3-int8 [exacta, reranker cuda] (2.34 > 1.5); multilingual-e5-small + jina-reranker-v2-base-multilingual [exacta, reranker cpu] (2.00 > 1.5); paraphrase-multilingual-MiniLM-L12-v2 + bge-reranker-v2-m3-int8 [exacta, reranker cuda] (2.34 > 1.5); paraphrase-multilingual-MiniLM-L12-v2 + jina-reranker-v2-base-multilingual [exacta, reranker cpu] (2.00 > 1.5) …
- **calidad** (4): multilingual-e5-base + bge-reranker-v2-m3 [exacta, reranker cuda] (0.82); multilingual-e5-base + bge-reranker-v2-m3 [hnsw, reranker cuda] (0.82); multilingual-e5-base + jina-reranker-v2-base-multilingual [exacta, reranker cuda] (0.82); multilingual-e5-base + jina-reranker-v2-base-multilingual [hnsw, reranker cuda] (0.82)
