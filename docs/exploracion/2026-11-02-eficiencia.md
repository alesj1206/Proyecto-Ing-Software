# Eficiencia del decisor: qué se midió, qué se cambió y qué queda (2026-11-02)

Se hizo después de adoptar mpnet + fusión (spec §13.6). Todo se midió en este PC (CPU, sin GPU), sobre la base
`scoutly_bench` con 120.000 vacantes sintéticas y 3.000 por candidato.

## Cambios aplicados (con pruebas)

| Cambio | Commit |
|---|---|
| Memoria para `normalizar` en textos cortos (≤ 300 caracteres) | `b72bde2` |
| Filtro barato antes de normalizar la descripción completa en la regla de prácticas | `b72bde2` |
| Cada texto distinto se embebe una vez por lote de 256 vacantes | `285d684` |

- **La decisión por candidato bajó un 27%**, de 2,87 s a 2,10 s de mediana, cronometrada sin perfilador sobre 4
  candidatos (`decidir_para_perfil`).
  - Con el perfilador, `normalizar` era el 40% del tiempo: 76.000 llamadas sobre textos de requisitos que se repiten.
  - La memoria sirve en el proceso por lotes (`decidir --todos` o `--escuchar`), que vive mucho tiempo.
  - Las descripciones largas no se guardan en memoria, para que esta no crezca con el catálogo (máximo 32.768 textos
    cortos).
- **La regla de prácticas solo normaliza la descripción si menciona «aprend…».** Hay pruebas para mayúsculas, tildes y
  espacios raros.
- **La deduplicación por lote** evita volver a embeber los textos repetidos. En la base de desarrollo, 63 vacantes
  tienen 416 requisitos y 334 distintos (20% repetidos). A escala real deberían repetirse más, pero eso no se midió.

## Probado y no adoptado

**mpnet cuantizado a int8** (`Xenova/paraphrase-multilingual-mpnet-base-v2`, `onnx/model_quantized.onnx`).

| | fp32 (adoptado) | int8 |
|---|---|---|
| Textos por segundo (814 textos reales, CPU) | 67 | 155 (2,3×) |
| Diferencia del mejor coseno por requisito | — | media 0,012, p95 0,031 |
| Decisiones iguales a fp32 (127 pares) | — | 121 |
| Exactitud total (127 pares) | 71% | 69% |
| `prueba_3` | 69% | 65% |

No se adopta. Los umbrales están calibrados para fp32 y la ingesta con fp32 ya cumple los límites de §6. Si algún día
la ingesta no alcanza, es la palanca más barata, pero habría que recalibrar los umbrales en un set nuevo. La web
reporta algo parecido: ~2,3× de velocidad con ~4% de pérdida en STS
([Sentence Transformers](https://huggingface.co/shibing624/text2vec-base-chinese/commit/183bb99aa7af74355fb58d16edf8c13ae7c5433e)).
El README de [fast-sentence-transformers](https://pypi.org/project/fast-sentence-transformers/) habla de hasta 5×,
pero es un número indicativo, sin el hardware descrito.

## Propuestas que quedan (no implementadas)

1. *(Implementada, ver abajo.)*
2. **Guardar en la vacante si es de prácticas,** calculado en la ingesta, en vez de revisarlo para cada candidato.
3. **Memoria persistente de embeddings por hash del texto.** Un cambio de reglas de extracción re-embebe todo el
   catálogo, aunque la mayoría de los textos ya se hayan embebido antes.
4. **La GPU.** El PC tiene una NVIDIA, pero al venv le faltan las bibliotecas CUDA/cuDNN que usa onnxruntime-gpu
   (Fase 0). La web reporta ~20× en ONNX con GPU
   ([fast-sentence-transformers](https://pypi.org/project/fast-sentence-transformers/)). Instalarlas pide `sudo`, así
   que le toca al usuario.
5. **No hace falta tocar la búsqueda en Postgres.**
   - La preselección exacta tarda 17 ms (Fase 0) y ya usa `halfvec`.
   - Según una [guía de pgvector](https://smithery.ai/skills/timescale/pgvector-semantic-search), la cuantización
     binaria con reordenamiento solo se justifica desde ~10 M de vectores; `halfvec` ya ahorra la mitad del espacio
     ([Neon](https://neon.com/blog/dont-use-vector-use-halvec-instead-and-save-50-of-your-storage-cost)).
6. **Embeddings estáticos (model2vec, `potion-multilingual-128M`, ya descargado).**
   - Sus autores dicen que es hasta 500× más rápido, pero rinde ~91% de LaBSE en MTEB, según sus propios números
     ([model card](https://huggingface.co/minishlab/potion-multilingual-128m)).
   - Podría ser un pre-filtro antes de MiniLM, pero hoy la preselección no es el cuello de botella: no se recomienda.

## No reescribir las decisiones que no cambiaron (implementada después, a pedido del usuario)

- **Huella del contenido.** Cada `Decision` guarda una (`huella`, sha256, migración `matching/0007`). En la siguiente
  corrida solo se escriben las decisiones cuya huella, `accion_anterior` o `cambio_en` cambiaron.
- **Una decisión que acaba de cambiar se escribe una vez más,** para que `accion_anterior` alcance a la acción. Así
  las notificaciones se comportan igual que antes.
- **`fecha_decision` pasa a ser "la última vez que se escribió".** No lo usa ningún código.
- **Medido en `scoutly_bench`** (3 candidatos, 3.000 vacantes cada uno, con mpnet):

| Corrida | Segundos por candidato |
|---|---|
| Primera, escribe todo | 2,16 / 2,53 / 2,50 |
| Siguiente, sin cambios | 1,54 / 1,77 / 1,77 |

  Son ~0,7 s menos por candidato, cerca de un 30%.

## Benchmark de escala con mpnet

El detalle está en `docs/fase4/BENCHMARK.md` (sección "Con mpnet"). Se corrió con los tres cambios aplicados y todo
cumple §6:

- **Delta diario:** 4,3 min (límite 15).
- **Carga inicial proyectada:** 2,9 h (límite 8).
- **Decisión por candidato:** 2,29 s de mediana y 3,51 s en el peor caso (límite 5).
