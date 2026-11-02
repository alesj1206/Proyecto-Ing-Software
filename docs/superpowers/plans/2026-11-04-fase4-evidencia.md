# Fase 4 (evidencia) de Scoutly v3: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** demostrar con números honestos que el decisor sirve y que escala:
- la exactitud sobre la mitad de **prueba**, que hasta ahora nadie ha corrido, previamente rebalanceada;
- el benchmark de 120.000 vacantes;
- los materiales de la evaluación ciega con reclutadores;
- el flujo de n8n y el visual verificados de punta a punta;
- la documentación con la que el equipo sustenta (README, informe y grafo de graphify).

Antes de eso se cierran las deudas de la Fase 3 que afectan la evidencia o el código que se va a mostrar.

**Architecture:** no hay apps nuevas.
- `matching/evaluacion/` gana el rebalanceo, la matriz de confusión y la evaluación ciega.
- `matching/benchmark/` es un módulo nuevo detrás del comando `benchmark_escala`.
- `docs/fase4/` reúne todo lo que se presenta.

**Tech Stack:** lo de las Fases 1–3. Además:
- `fastembed` real para la evaluación y el benchmark;
- Playwright, el scraper existente, para traer vacantes reales nuevas;
- chrome-devtools-mcp para las capturas;
- n8n en Podman.

**Spec:** `docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md`. Aplican §2 (anti-objetivos), §6, §9.4,
§10 y §13.1–§13.3. La §13 manda. Antecedente: `docs/fase2/EVALUACION.md` (advertencias sobre la mitad de prueba).

## Global Constraints

- **Sin trampa (§10):**
  - los umbrales y las reglas se ajustan solo con la mitad de ajuste;
  - la mitad de prueba se etiqueta **antes** de correrla, y esas etiquetas se commitean en un commit propio, previo a la corrida: el hash prueba el orden;
  - se corre **una sola vez** con la política congelada;
  - después de verla no se toca nada del decisor ni de las etiquetas de prueba.
- **Anti-objetivos (§2) sobre la prueba:**
  - exactitud ≥ 70%;
  - ninguna acción por encima del 80% de las predicciones;
  - superar a la línea base de similitud (§13.2);
  - se reportan también la línea base de clase mayoritaria y la matriz de confusión.
- **Si la prueba no cumple, se reporta tal cual** y se le avisa al usuario. No se recalibra mirando la prueba.
- **Sin datos personales reales:**
  - los CVs del set y de la evaluación ciega son los ficticios de `cvs.yaml`;
  - a las vacantes nuevas se les quitan los datos de contacto (correos y teléfonos), como en `vacantes.json`.
- **Benchmark (§6):** los umbrales son:
  - carga inicial de 120k ≤ 8 h en CPU (proyectada a partir de una muestra medida);
  - delta diario de 3.000 vacantes ≤ 15 min (medido);
  - decisión por candidato ≤ 5 s en CPU (medida con 120k vacantes en la base).

  El reranker queda apagado, así que el umbral de 1,5 s por página no aplica (§13.1). El benchmark **nunca** corre contra `scoutly_v3`: exige una base cuyo nombre termine en `_bench`.
- **Etiquetas propuestas por el builder:** se marcan "PENDIENTE de revisión del equipo" (§10), igual que las de la Fase 2.
- TDD con pytest-django y el embedder falso para todo el código nuevo. Los comandos que cargan modelos reales se marcan `lento`.
- **Visual (§2.6):** las capturas finales deben ser equivalentes a las de v2. Esta fase no agrega elementos visuales.

## Review Focus

1. **Fuga entre mitades:** una vacante de la prueba que también aparece en el ajuste, o un par de prueba que se etiquetó después de ver una predicción. Un test de estructura impide lo primero y el orden de los commits demuestra lo segundo.
2. **Desbalance que infla la exactitud:** si la prueba vuelve a estar dominada por DESCARTAR, la exactitud no dice nada. El test de estructura exige al menos 4 pares por acción (3 para SIN_DATOS) y que DESCARTAR sea ≤ 35%.
3. **El benchmark contra la base real:** correrlo con `DJANGO_DB_NAME=scoutly_v3` borraría o llenaría datos de usuarios. El comando se niega a correr salvo con `_bench`, y hay un test para eso.
4. **La proyección del benchmark disfrazada de medición:** el informe separa "medido" de "proyectado" y dice con qué muestra se proyectó.
5. **La regla de prácticas descarta a quien sí es estudiante:** un CV que dice "cursando 7.º semestre" o "(en curso)" no se descarta. El test lo fija.

---

### Task 1: Deudas de la Fase 3 que tocan la evidencia y el código a mostrar

**Files:**
- Modify:
  - `vacantes/fuentes/magneto_detalle.py`: recibe `TERMINOS_POR_DEFECTO`;
  - `vacantes/management/commands/ingerir_vacantes.py` y `api/views.py`: lo importan de ahí;
  - `matching/restricciones.py` y `matching/selectors.py`: un solo `pesos()` en `matching/formato.py` (nuevo);
  - `postulaciones/services.py`: el snapshot guarda `similitud`, `con_nota` y `motivos`;
  - `matching/taller.py`: `taller()` tolera dos GET simultáneos.
- Test:
  - `postulaciones/tests/test_resultados.py` (agregar);
  - `matching/tests/test_taller.py` (agregar);
  - `matching/tests/test_formato.py` (nuevo).

**Interfaces:**
- Produces:
  - `matching.formato.pesos(valor: int) -> str`, que devuelve lo mismo que los dos `_pesos` actuales;
  - `vacantes.fuentes.magneto_detalle.TERMINOS_POR_DEFECTO: list[str]`.

- [ ] **Step 1: tests que fallan.**
  - `test_pesos_formatea_con_puntos`: `pesos(3500000) == "$ 3.500.000"`. Usa el formato exacto que hoy devuelve `_pesos`; léelo antes de escribir el assert.
  - `test_resultado_guarda_insumos_para_calibrar`: después de `registrar_resultado`, `insumos` tiene las claves `similitud`, `con_nota` y `motivos`, con los valores de la `Decision`.
  - `test_taller_get_concurrente_no_da_500`: crear la sugerencia a mano antes de llamar `taller()` simula la carrera de los dos GET; `taller()` devuelve la lista sin lanzar `IntegrityError`.
- [ ] **Step 2: correrlos.** Esperado: los tres fallan (`ImportError`, `KeyError` e `IntegrityError`).
- [ ] **Step 3: implementar.**
  - En `taller()`, crear las sugerencias con `bulk_create(..., ignore_conflicts=True)` y luego leerlas. La restricción única ya existe.
  - Mover las constantes y `pesos` a su nuevo lugar.
  - Arreglar el orden de imports de `cuentas/views_auth.py` y el E302 de `cuentas/views.py`.
- [ ] **Step 4: correr.** `.venv/bin/python -m pytest -q -m "not lento"`. Esperado: todo en verde.
- [ ] **Step 5: commit.** `refactor(fase4): deudas de la Fase 3 (pesos, términos, insumos para calibrar, taller concurrente)`.

### Task 2: Las dos mejoras pendientes del decisor, validadas solo con la mitad de ajuste

**Files:**
- Modify:
  - `vacantes/extraccion.py`: separar enumeraciones de herramientas;
  - `matching/restricciones.py`: nueva `RestriccionEstudiante`;
  - `matching/politica.py`: nueva versión;
  - `docs/fase2/EVALUACION.md`: no se toca, porque es histórico.
- Test: `vacantes/tests/test_extraccion.py` y `matching/tests/test_restricciones.py` (agregar).

**Interfaces:**
- Consumes: el protocolo `Restriccion.evaluar(perfil, vacante, politica) -> ResultadoRestriccion` y la lista `RESTRICCIONES`.
- Produces:
  - `RestriccionEstudiante`, con `criterio = "estudiante"`, agregada al final de `RESTRICCIONES`;
  - `Politica.version = "2026-11-04.1"`.

- [ ] **Step 1: tests de extracción que fallan.**
  - `test_enumeracion_de_herramientas_se_separa`:
    ```python
    textos = [r.texto for r in extraer_requisitos("Requisitos:\n- Manejo de Power BI, Power Apps y Power Automate", [])]
    assert textos == ["Manejo de Power BI", "Manejo de Power Apps", "Manejo de Power Automate"]
    ```
  - `test_enumeracion_de_frases_no_se_separa`: "Experiencia en atención al cliente, ventas y cobranza" sigue siendo **un** requisito.
    - Solo se separan enumeraciones cuyos ítems empiezan con mayúscula o son siglas y tienen ≤ 3 palabras.
    - El prefijo común ("Manejo de", "Conocimiento en") se repite en cada ítem.
- [ ] **Step 2: tests de la restricción que fallan.**
  - `test_practica_exige_estudiante`: una vacante con "practicante", "práctica profesional", "aprendiz SENA" o "estudiante de últimos semestres" en el título o los requisitos, y un perfil cuya evidencia no muestra estudios en curso, da `estado="viola"` con el motivo `"La vacante es para estudiantes y tu CV no muestra estudios en curso"`.
  - `test_estudiante_en_curso_no_se_descarta`: con una evidencia que dice "cursando 7.º semestre", "(en curso)", "actualmente" o "a la fecha" dentro de la educación, da `estado="cumple"`.
  - `test_vacante_normal_no_aplica`: una vacante sin esas marcas da `estado="no_aplica"`. Usa el nombre de estado que ya usen las otras restricciones; léelo antes.
- [ ] **Step 3: correr.** Esperado: FAIL.
- [ ] **Step 4: implementar.**
  - Las marcas de "vacante para estudiantes" y de "estudios en curso" se comparan sobre texto normalizado, con `normalizar()` de `vacantes/extraccion.py`.
  - Subir `Politica.version` a `"2026-11-04.1"`.
- [ ] **Step 5: correr la suite y luego el ajuste.**
  - Suite: `.venv/bin/python -m pytest -q -m "not lento"` en verde.
  - Ajuste: `SCOUTLY_EMBEDDER=fastembed .venv/bin/python manage.py evaluar_decisor --mitad ajuste`.
  - Esperado: exactitud ≥ 73% (no empeora) y ninguna acción > 80%. Si empeora, revertir la mejora que lo cause y dejar el Ruling.
- [ ] **Step 6: commit.**
  - Mensaje: `feat(decisor): enumeraciones de herramientas y prácticas para estudiantes (ajuste: N%)`.
  - Desde aquí **la política queda congelada** hasta el final de la Task 4.

### Task 3: Rebalancear la mitad de prueba (solo etiquetas, sin correr nada)

**Files:**
- Modify:
  - `matching/evaluacion/vacantes.json`: agregar vacantes reales nuevas;
  - `matching/evaluacion/pares.yaml`: rehacer la mitad de prueba.
- Create: `matching/evaluacion/capturar.py` (exporta vacantes de `FuenteMagnetoDetalle` al formato de `vacantes.json`, sin contactos).
- Test: `matching/tests/test_set_evaluacion.py` (nuevo).

**Interfaces:**
- Consumes: `FuenteMagnetoDetalle(terminos, por_termino)` y su `obtener()`; usa el nombre real del método del puerto `FuenteVacantes`.
- Produces: `capturar.sin_contactos(texto: str) -> str` y `capturar.exportar(fuente, excluir_ids: set[str]) -> list[dict]`.

- [ ] **Step 1: tests que fallan.**
  - `test_sin_contactos_quita_correos_y_telefonos`: `"Envía tu hoja a rh@empresa.co o al 300 123 4567"` queda sin el correo y sin el número.
  - `test_las_mitades_no_comparten_vacantes`: `{p.vacante for prueba} & {p.vacante for ajuste} == set()`.
  - `test_la_prueba_esta_balanceada`: cada acción tiene ≥ 4 pares (SIN_DATOS ≥ 3), DESCARTAR es ≤ 35% y hay entre 22 y 30 pares.
  - `test_todo_par_apunta_a_datos_existentes`: cada `cv` está en `cvs.yaml` y cada `vacante` en `vacantes.json`.
- [ ] **Step 2: correr.** Esperado:
  - `sin_contactos` falla por `ImportError`;
  - los tres tests de estructura fallan con la prueba actual (comparte 11 vacantes y tiene 14 DESCARTAR).
- [ ] **Step 3: implementar `capturar.py`.** Correrlo con el scraper real (`lento`) sobre términos que cubran las áreas de los CVs:
  - datos;
  - desarrollo;
  - contabilidad;
  - comercial;
  - salud;
  - diseño;
  - prácticas.

  Se agregan entre 15 y 25 vacantes **que no estén** en `vacantes.json`.
- [ ] **Step 4: escribir la nueva prueba leyendo el CV y los requisitos, sin correr el decisor.**
  - Se conservan los pares de prueba viejos cuya vacante no está en el ajuste, hasta que DESCARTAR quede ≤ 35%; los demás se quitan.
  - Se completa con pares sobre las vacantes nuevas, cada uno con su justificación de una línea.
  - Se marca el bloque como "PENDIENTE de revisión del equipo".
- [ ] **Step 5: correr.** `.venv/bin/python -m pytest -q matching/tests/test_set_evaluacion.py`. Esperado: PASS.
- [ ] **Step 6: commit (este commit es la prueba de que las etiquetas existen antes de la corrida).**
  - Mensaje: `data(evaluación): mitad de prueba rebalanceada con vacantes nuevas (etiquetas antes de correr)`.

### Task 4: Correr la prueba una vez y reportarla

**Files:**
- Modify:
  - `matching/evaluacion/evaluar.py`: matriz de confusión imprimible y exactitud por acción;
  - `matching/management/commands/evaluar_decisor.py`: `--salida` escribe el informe en Markdown.
- Create: `docs/fase4/EVALUACION.md`.
- Test: `matching/tests/test_evaluar.py` (agregar).

**Interfaces:**
- Produces:
  - `Informe.exactitud_por_accion() -> dict[str, float]`;
  - `Informe.tabla_confusion() -> str` (Markdown, con filas = esperada y columnas = predicha).

- [ ] **Step 1: tests que fallan.**
  - `test_exactitud_por_accion`: con aciertos {POSTULAR: 1 de 2} da `{"POSTULAR": 0.5, …}`.
  - `test_tabla_confusion_markdown`: la tabla tiene una fila por acción esperada, y la celda (DESCARTAR, POSTULAR) muestra el conteo.
- [ ] **Step 2: correr.** Esperado: FAIL. Implementar y correr de nuevo: PASS.
- [ ] **Step 3: commit.** `feat(evaluación): matriz de confusión y exactitud por acción`.
- [ ] **Step 4: la corrida única.**
  - Comando: `SCOUTLY_EMBEDDER=fastembed .venv/bin/python manage.py evaluar_decisor --mitad prueba --confirmo-prueba --salida docs/fase4/EVALUACION.md`.
  - Se conserva la salida tal cual. Se corre también `--mitad ajuste` con la política congelada para la tabla comparativa.
- [ ] **Step 5: completar `docs/fase4/EVALUACION.md`** con:
  - las dos mitades;
  - las tres líneas base;
  - la distribución;
  - la matriz;
  - el cumplimiento de cada anti-objetivo;
  - los errores con su causa;
  - el hash del commit de la Task 3.

  **Si algún anti-objetivo no se cumple:** se escribe así, se para y se le avisa al usuario. Es una de las cuatro paradas.
- [ ] **Step 6: commit.** `docs(fase4): evaluación en la mitad de prueba`.

### Task 5: `benchmark_escala`

**Files:**
- Create:
  - `matching/benchmark/__init__.py` y `matching/benchmark/sintetico.py` (generador);
  - `matching/benchmark/medir.py` (cronometraje);
  - `matching/management/commands/benchmark_escala.py`;
  - `docs/fase4/BENCHMARK.md`.
- Test: `matching/tests/test_benchmark.py`.

**Interfaces:**
- Consumes:
  - `vacantes.services.ingerir(fuente)`;
  - `matching.services.decidir_para_perfil(perfil, embedder, ...)`;
  - `FuenteVacantes`;
  - `matching.evaluacion.evaluar.preparar` (para los perfiles ficticios).
- Produces:
  - `sintetico.FuenteSintetica(plantillas: list[dict], n: int, semilla: int)`, un `FuenteVacantes` que genera n vacantes con ids `syn-<i>`;
  - `medir.Medicion(etapa: str, n: int, segundos: float, tipo: Literal["medido", "proyectado"])`;
  - `medir.informe_markdown(mediciones, umbrales) -> str`.

- [ ] **Step 1: tests que fallan.**
  - `test_se_niega_fuera_de_bench`: con la base de test (cuyo nombre no termina en `_bench`), `call_command("benchmark_escala")` lanza `CommandError` con "_bench".
  - `test_fuente_sintetica_es_determinista_y_variada`: dos instancias con la misma semilla dan las mismas vacantes; con n=200 hay ≥ 150 títulos distintos; ninguna vacante trae correos.
  - `test_informe_separa_medido_de_proyectado`: el Markdown lleva una columna "tipo" y una columna "cumple" contra cada umbral de §6.
- [ ] **Step 2: correr.** Esperado: FAIL.
- [ ] **Step 3: implementar.**
  - **Variedad:** el generador combina títulos, ciudades, modalidades, salarios y subconjuntos de requisitos de las plantillas reales (`vacantes.json`), con variaciones léxicas, para que el número de textos de requisitos distintos se parezca al real.
  - **Etapas medidas:**
    1. Ingesta real con embeddings de una muestra (`--muestra`, por defecto 3.000 = delta diario). Se mide y además se proyecta linealmente a 120k.
    2. Carga masiva hasta `--vacantes` (por defecto 120.000). Los vectores se reutilizan de la muestra por plantilla, así que se mide la escritura y no el embedding; el informe lo dice.
    3. `decidir_para_perfil` para los N perfiles ficticios (`--candidatos`, por defecto 11): se informan el p50, el p95 y el máximo.
  - **Salida:** `--salida` escribe `docs/fase4/BENCHMARK.md` con CPU y GPU, si está, y la versión de los modelos.
- [ ] **Step 4: correr.** `.venv/bin/python -m pytest -q matching/tests/test_benchmark.py`. Esperado: PASS.
- [ ] **Step 5: corrida real.**
  - Crear la base: `podman exec scoutly-postgres createdb -U scoutly scoutly_bench`, con la extensión `vector` y las migraciones aplicadas.
  - Correr: `DJANGO_DB_NAME=scoutly_bench SCOUTLY_EMBEDDER=fastembed .venv/bin/python manage.py benchmark_escala --salida docs/fase4/BENCHMARK.md` en segundo plano.
  - Esperado: el informe dice si se cumplen los umbrales de §6. Si alguno no se cumple, se reporta así y se le avisa al usuario.
- [ ] **Step 6: commit.** `feat(benchmark): benchmark_escala con 120k vacantes sintéticas y reporte`.

### Task 6: Materiales de la evaluación ciega con reclutadores (§13.3)

**Files:**
- Create:
  - `matching/evaluacion/ciega.py`;
  - `matching/management/commands/evaluacion_ciega.py` (subcomandos `preparar` y `tabular`);
  - `docs/fase4/evaluacion_ciega/INSTRUCCIONES.md`.
- Test: `matching/tests/test_evaluacion_ciega.py`.

**Interfaces:**
- Consumes:
  - `matching.selectors.plan_de_hoy(perfil, n, ahora)`;
  - el orden por similitud pura (`linea_base` de `evaluar.py`);
  - `matching.taller.texto_adaptado(perfil, vacante)` con todas las sugerencias aceptadas.
- Produces:
  - `ciega.preparar(escenario, cvs: list[str], semilla: int) -> tuple[list[Paquete], dict]`: los paquetes llevan "Lista A/B" y "CV 1/2"; la clave dice qué es cada letra;
  - `ciega.tabular(respuestas_csv: Path, clave: dict) -> dict`, que da el % de preferencia por el decisor y por el CV adaptado, por reclutador y en total.

- [ ] **Step 1: tests que fallan.**
  - `test_paquete_no_revela_el_origen`: ningún paquete contiene "decisor", "similitud", "adaptado", "Plan de hoy" ni la acción.
  - `test_la_asignacion_ab_es_aleatoria_pero_reproducible`: con la misma semilla se obtiene la misma clave; y en 6 CVs no todas las A son del decisor.
  - `test_tabular_cuenta_preferencias`: un CSV `reclutador,paquete,pregunta,eleccion` con 3 filas produce los % esperados.
  - `test_csv_mal_formado_da_error_claro`: falta una columna → `CommandError` que nombra la columna.
- [ ] **Step 2: correr.** Esperado: FAIL. Implementar y correr de nuevo: PASS.
- [ ] **Step 3: generar los materiales.**
  - `preparar` escribe los paquetes en `docs/fase4/evaluacion_ciega/paquetes/`, uno por CV ficticio, con 4–6 CVs.
  - La **clave** va fuera del repo, en `~/.scoutly/clave_evaluacion_ciega.json`, para que nadie del equipo la vea antes de tabular. Se ignora en git si se copia.
- [ ] **Step 4: escribir las instrucciones.** `INSTRUCCIONES.md` explica para los reclutadores qué comparar, las dos preguntas ("¿cuál lista le recomendarías a este candidato?" y "¿cuál CV pasaría tu primer filtro?") y el formato del CSV.
- [ ] **Step 5: commit.** `feat(evaluación): materiales y tabulación de la evaluación ciega`.
  - Si el usuario no consigue reclutadores, el informe lo dice y reporta solo el set (§13.3).

### Task 7: Verificación de punta a punta y visual

**Files:**
- Create: `docs/fase4/VERIFICACION.md` y `docs/fase4/capturas/*.png`.
- Modify: `n8n/README.md`, que se reescribe para v3: tres pasos, 202 y `decidir --escuchar`, y se corrigen las observaciones históricas alteradas por el reemplazo mecánico de la Fase 3.

- [ ] **Step 1: correr el flujo real.** Levantar `runserver --insecure 0.0.0.0:8000` y `decidir --escuchar`, y disparar el workflow de n8n (`POST /rest/workflows/{id}/run`). Esperado en el log de Django:
  - `/api/importar-vacantes` responde 202;
  - `/api/decidir` responde 202;
  - `/api/generar-notificaciones` responde 200;
  - y el escuchador decide y notifica con el backend de consola. Se guarda el extracto del log.
- [ ] **Step 2: capturas con chrome-devtools.** Se captura cada página de v2 (login, registro, dashboard, detalle, historial, postulaciones, perfil y notificaciones) más las de las Fases 2 y 3 (taller y verificación), y se comparan con `docs/fase1/capturas` y `docs/fase2/capturas`. Esperado: sin regresiones visuales; cualquier diferencia se anota.
- [ ] **Step 3: escribir y commitear.** Se escriben `VERIFICACION.md` y el README de n8n. Commit: `docs(fase4): verificación de punta a punta, capturas y README de n8n`.

### Task 8: README, informe y grafo

**Files:**
- Modify: `README.md`, reescrito para v3: qué hace, cómo levantarlo (Podman, `.env` y comandos), arquitectura y patrones, privacidad y estado de B1.
- Create: `docs/fase4/INFORME.md`, el informe del sprint para la sustentación, con:
  - el problema y el por qué (Reto 4);
  - el decisor y sus patrones, con `archivo:línea` para cada uno: Strategy, Chain of Responsibility, Adapter/Ports y Facade;
  - la escala (enlaza BENCHMARK);
  - la evaluación (enlaza EVALUACION y la evaluación ciega);
  - la privacidad (Ley 1581);
  - los límites conocidos y el trabajo futuro (calibración con `ResultadoDecision` y B1).
- Update: `graphify-out/` con `graphify --update` sobre el repo.

- [ ] **Step 1: escribir el README y el informe.** Cada número sale de los documentos de la Fase 4; no se escribe ninguno de memoria.
- [ ] **Step 2: comprobar las referencias.** Cada `archivo:línea` citado existe: se verifica con un script que lea las referencias y revise la línea.
- [ ] **Step 3: actualizar el grafo.** Correr graphify `--update` y revisar que `GRAPH_REPORT.md` refleja las apps de v3.
- [ ] **Step 4: commit.** `docs(fase4): README v3, informe del sprint y grafo actualizado`.

## Decisiones del builder (reversibles; van al ledger como Ruling)

- **D1. La regla de prácticas es una restricción y no un estado de cobertura.** Así DESCARTAR muestra su motivo (§13.5). La formación sigue sin medirse por similitud (§13.2).
- **D2. El benchmark reutiliza los vectores por plantilla en la carga masiva.** Embeber 1,1M textos tomaría horas y no cambia lo que se mide en la decisión. La ingesta con embeddings se mide de verdad sobre la muestra y se proyecta. El informe lo dice.
- **D3. La clave de la evaluación ciega vive fuera del repo.** Así el equipo no la ve antes de tabular.
- **D4. Si la prueba no cumple los anti-objetivos, no se recalibra.** Se reporta y se decide con el usuario: un número honesto vale más que uno ajustado a la prueba.

## Enmienda tras la Task 4 (decisión del usuario, 2026-11-01)

La prueba dio 46% (< 70%). El usuario eligió **corregir y medir con una prueba nueva**:

### Task 4b: correcciones generales del decisor + tercera mitad nunca vista

- Se corrigen las causas generales del diagnóstico (`docs/fase4/EVALUACION.md`), con TDD:
  1. el pie "Otras habilidades / Habilidades técnicas…" de Magneto deja de ser requisito;
  2. la experiencia con área se compara por su núcleo (sin "mínimo N años de experiencia en");
  3. las listas dentro de un requisito se separan: entre paréntesis, o con calificador "avanzado/intermedio/básico";
  4. las frases de presentación ("Serás responsable…", "Si tienes…") son ruido;
  5. la ubicación acepta los municipios del área metropolitana.
- Las causas 5 y 7 (límites del modelo) quedan como limitación documentada.
- **Validación:** solo con lo ya visto, es decir, el ajuste más la prueba de 46% (que pasa a llamarse `prueba_1`).
- **Medición final:** se construye una prueba **nueva** con vacantes que ninguna mitad usa, balanceada igual que la Task 3. Sus etiquetas se commitean antes de correrla, se corre una sola vez y se reportan las dos cifras (46% y la nueva).
