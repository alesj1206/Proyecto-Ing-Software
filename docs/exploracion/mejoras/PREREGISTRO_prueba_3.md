# Preregistro de la medición en `prueba_3`

Escrito y commiteado **antes** de buscar, etiquetar o medir las vacantes de `prueba_3`. Se medirá **una sola vez**,
con estas cuatro variantes y estos valores. Nada de esto se cambia después de ver resultados.

| Variante | Embeddings de cobertura | τ_alto | τ_bajo | Fusión Postular+Ajustar |
|---|---|---|---|---|
| V1. Actual (política 2026-11-04.3) | MiniLM-L12 | 0,45 | 0,35 | no |
| V2. Fusión | MiniLM-L12 | 0,45 | 0,35 | sí |
| V3. mpnet | paraphrase-multilingual-mpnet-base-v2 | 0,475 | 0,425 | no |
| V4. mpnet + fusión | paraphrase-multilingual-mpnet-base-v2 | 0,425 | 0,425 | sí |

- **Común a las cuatro:** la similitud del par (preselección) sigue con MiniLM y τ_relevancia 0,25, y las
  restricciones y la extracción son las de la política .3.
- **Umbrales de mpnet:** se eligieron con los 101 pares ya vistos (ajuste, prueba_1, prueba y prueba_2).
  - Exactitud sobre lo visto: 63% (V3) y 71% (V4).
  - Con validación cruzada por set: 62% y 71%.
- **Criterio de éxito** (anti-objetivo de §2): exactitud ≥ 70% y ninguna acción por encima del 80%.
- **Construcción de `prueba_3`:**
  - unas 25 vacantes nuevas de magneto365.com, sin clones por texto contra ninguna mitad anterior;
  - al menos 4 pares por acción (3 de SIN_DATOS) y DESCARTAR ≤ 35%;
  - etiquetas commiteadas antes de medir.
