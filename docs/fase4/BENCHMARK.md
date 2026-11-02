# Benchmark de escala (spec §6)

- **fecha:** 2026-11-02 04:35
- **vacantes en la base:** 120000
- **CPU:** 12th Gen Intel Core i7-12700H (laptop), solo CPU; la GPU no se usó
- **embeddings:** fastembed
- **política:** 2026-11-04.2 (τ_relevancia 0.25)
- **reranker:** apagado (el umbral de 1,5 s por página no aplica, §13.1)

| etapa | n | valor | umbral §6 | tipo | nota | cumple |
|---|---:|---:|---:|---|---|---|
| delta_diario_min | 3000 | 1.50 | 15 | medido | muestra de 3000 | sí |
| carga_inicial_cpu_h | 120000 | 1.00 | 8 | proyectado | lineal desde la muestra de 3000 | sí |
| carga_masiva_min | 117000 | 13.08 | — | medido | embeddings reutilizados: mide extracción y escritura | — |
| decision_candidato_p50_s | 11 | 2.92 | 5 | medido | relevantes por candidato: mediana 3000, máx 3000; tope técnico (3000) alcanzado por 11 | sí |
| decision_candidato_s | 11 | 4.79 | 5 | medido | el peor candidato | sí |

## Cómo leerlo

- **Medido** es tiempo real en esta máquina. **Proyectado** es una extrapolación lineal, y dice desde qué muestra.
- **Delta diario (1,5 min para 3.000 vacantes, medido):** 3.000 vacantes sintéticas de verdad, extracción de
  requisitos y embeddings con MiniLM en CPU, sin reutilizar nada. Es el trabajo de un día normal y queda 10 veces por
  debajo del límite.
- **Carga inicial (1 h para 120.000, proyectada):** la misma muestra extrapolada a 120.000. Es un proceso que se corre
  una sola vez, y el límite es de 8 h.
- **Carga masiva (13 min para 117.000, medida):** llena la base hasta 120.000. Reutiliza los embeddings de los textos
  repetidos, así que mide la extracción y la escritura en Postgres, no el modelo (ese costo ya lo mide la muestra).
- **Decisión por candidato (mediana 2,9 s, peor 4,8 s, medidas)** con 120.000 vacantes en la base, para los 11 CVs
  ficticios. Incluye embeber el perfil, la preselección exacta en Postgres sobre las 120.000, la cobertura requisito
  por requisito de las 3.000 más parecidas, la política y el guardado.

## Lo que hay que saber

- **Los 11 candidatos llegaron al tope de 3.000.** Con MiniLM casi todo el catálogo supera el umbral de relevancia
  (también con vacantes reales: ~93% a 0,25). A esta escala, el que recorta es el tope: cada candidato recibe decisión
  sobre sus 3.000 vacantes más parecidas, que es lo que asume §6.
- **El peor caso (4,8 s, `disenadora_junior`) está cerca del límite de 5 s.** Los otros 10 quedan entre 2,4 y 3,2 s;
  la causa de la diferencia no se investigó. Si hiciera falta margen, se puede bajar el tope o decidir varios perfiles
  en paralelo (el batch decide uno a la vez).
- **Las vacantes son sintéticas:** cada una toma los requisitos de una misma vacante real (y a veces uno de otra
  área), con variaciones de redacción. Así se parece a un catálogo agrupado por áreas, no a una mezcla al azar.
- **El reranker está apagado** (§13.1), y el umbral de 1,5 s por página no aplica. Con el reranker encendido en GPU,
  las mediciones son las de la Fase 0 (`spike/fase0/REPORTE.md`).
- Se reproduce con `DJANGO_DB_NAME=scoutly_bench SCOUTLY_EMBEDDER=fastembed manage.py benchmark_escala --salida …`,
  sobre una base aparte que termina en `_bench`. El comando se niega a correr sobre cualquier otra.

## Con mpnet (política 2026-11-05.1, 2026-11-02)

Se repitió el benchmark después de adoptar mpnet para la cobertura (spec §13.6), con la memoria de `normalizar` y la
deduplicación por lote (`docs/exploracion/2026-11-02-eficiencia.md`). Es la misma máquina y el mismo comando.

| etapa | MiniLM (Fase 4) | MiniLM + mpnet | umbral §6 | cumple |
|---|---:|---:|---:|---|
| Delta diario (min, 3.000 vacantes, medido) | 1,50 | 4,32 | 15 | sí |
| Carga inicial de 120.000 (h, proyectada) | 1,00 | 2,88 | 8 | sí |
| Carga masiva de 117.000 (min, embeddings reutilizados) | 13,08 | 18,62 | — | — |
| Decisión por candidato, mediana (s, 11 CVs) | 2,92 | 2,29 | 5 | sí |
| Decisión por candidato, peor caso (s) | 4,79 | 3,51 | 5 | sí |

- **Embeber cuesta ~2,9 veces más**, porque cada vacante pasa por dos modelos. La deduplicación compensa una parte;
  sin ella se esperaba ~4 veces más.
- **Decidir es más rápido que antes**, aunque mpnet usa matrices de 768 dimensiones: la memoria de `normalizar` pesa
  más que el costo extra de la multiplicación.
- El catálogo sintético repite textos más que uno real. La deduplicación podría rendir menos con vacantes reales.
