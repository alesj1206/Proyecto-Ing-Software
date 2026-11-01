# Revisión de código (octo:code-reviewer): qué del spike pasa a la app

**Se promueve casi tal cual (funciones puras con tests):**
- `bench_cobertura.cobertura` → núcleo de `matching`.
- `bench_alternativas.busqueda_exacta` → falta tiparla con `NDArray` y renombrar `q` y `tope`.
- `requisitos_como_bytes` / `bytes_como_requisitos` → pasan a un `CodecRequisitos`, con el dtype float16 como
  constante y validación de `dim`.

**Se rediseña:**
- `comun.py` tiene 3 responsabilidades: configuración y conexión a la BD (con un parser `.env` casero y
  `localhost` fijo), catálogo de modelos y adaptador de fastembed con selección de proveedor. Además, el catálogo
  se duplica en `reporte.DIMENSION` y la lógica de los prefijos e5 está repartida entre `calidad.py` y
  `bench_modelos.py`, cuando le corresponde al adaptador.
- `calidad.py` mezcla carga del YAML, instanciación de modelos, cálculo y persistencia, así que no se puede
  probar sin modelos reales. Además, `evaluar_reranker` y `evaluar_reranker_resumen` repiten el mismo algoritmo de
  preferencia por pares.
- `buscar_por_umbral`:
  - el nombre de la tabla se interpola con un f-string (debería usar `psycopg.sql.Identifier`);
  - los `SET` de sesión contaminan la conexión (con conexiones persistentes de Django hay que usar `SET LOCAL`
    dentro de una transacción);
  - los parámetros de HNSW están fijos en el código;
  - devuelve tuplas anónimas.
- `reporte.veredictos` / `elegir` trabajan con dicts y claves mágicas, el parámetro `cumple` es un parche, y
  `segundos_indice_hnsw` se reutiliza para la carga en bytea, lo que confunde. Esto no pasa a la app.
- `textos.py` → se convierte en factory de fixtures de prueba.

**Nombres:** `cargar_*` significa tres cosas distintas (insertar filas, instanciar un modelo y leer YAML). Hay
mezcla de español e inglés (`_providers`, `rend`, `rr`, `ret`, `_md`) y utilidades duplicadas (`_seg` /
`_cronometrar`, `_slug` en 3 lugares).

**Tests:**
- Buenos: `test_reporte`, `test_alternativas`, `test_cobertura` y `test_textos`.
- Débiles: los tests lentos de calidad solo verifican el tamaño y escriben en disco; `test_umbral_definido` prueba
  una constante; el test de serialización tiene poco valor; hacer monkeypatch de `_leer` indica que falta un
  puerto de resultados.
- No hay ningún fake, y los tests de BD no tienen marcador `integracion`.

**Los 5 refactors de mayor valor para la app:**
1. Puertos y adaptadores en `ia`:
   - Protocols `ProveedorEmbeddings` (`embeber_consultas`, `embeber_pasajes`) y `Reranker`
     (`puntuar(consulta, docs) -> list[float]`);
   - un `AdaptadorFastembed` que encapsule los prefijos e5, el registro de modelos personalizados y CPU/CUDA;
   - un dataclass `ModeloEmbedding` (id, dim, prefijos) que reemplace a `E5_PERSONALIZADOS`, `DIMENSION` y
     `usa_prefijo_e5`;
   - fakes determinísticos para los tests.
2. `EvaluadorCalidad` que reciba el puerto y los casos: un solo algoritmo `preferencia_por_pares`, sin escribir
   en disco, y tests con fakes que verifiquen la exactitud, el desglose por tipo y los fallos.
3. Strategy en `matching`: un Protocol `BuscadorVacantes` con dos implementaciones, `BuscadorHnsw` y
   `BuscadorExacto`, que devuelvan `Coincidencia(vacante_id, similitud)`.
4. `RepositorioVectores` sobre pgvector: `sql.Identifier`, `SET LOCAL`, un dataclass `ConfigHnsw` y la conexión
   desde `settings.DATABASES` (se elimina `conectar()`).
5. Dominio tipado con dataclasses (`ResultadoCalidad`, `Veredicto`, `Umbral.evaluar()` como Specification),
   sin utilidades duplicadas y con verbos únicos en español (`insertar_`, `instanciar_`, `leer_`).
