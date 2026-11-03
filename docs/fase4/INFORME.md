# Scoutly v3: informe del Sprint 3

## 1. El problema

El reto de Magneto (Idea 4) pide un flujo diario con n8n: vacantes → ranking → notificación. La v2 calculaba el ranking
sin IA, comparando habilidades por texto exacto ("coincide o no"), así que perdía requisitos dichos con otras palabras.
Groq solo redactaba explicaciones al abrir el detalle de una vacante. Mejorar esa comparación con un LLM por vacante
tampoco sirve a la escala de Magneto (~120.000 vacantes activas): sería lento, caro y difícil de explicar. Además, el objetivo de fondo no es un ranking: es que el candidato **consiga entrevistas**.

La v3 reemplaza el ranking por un **decisor local y gratuito**. Para cada par (candidato, vacante) da una acción
(Postular, Cerrar brecha, Descartar o Revísala tú), su solidez (alta, media o baja) y las razones que la
respaldan, todas calculadas con datos y nunca redactadas por un LLM. Groq solo escribe, a pedido, una explicación en
prosa con los campos de criterio, sin el texto del CV.

## 2. Arquitectura y patrones

Son cinco apps (`cuentas`, `vacantes`, `matching`, `postulaciones` y `notificaciones`) más el módulo `api` para n8n.
La lógica vive en servicios y selectores, y las vistas son delgadas. Solo el batch (`manage.py decidir --escuchar`)
carga modelos; la web lee decisiones ya calculadas.

| Patrón | Dónde | Para qué |
|---|---|---|
| **Ports & Adapters** | `matching/puertos.py:10` (Embedder), `:20` (ModelosEmbebido), `:33` (Redactor), `:39` (Reordenador); adaptadores en `matching/ia/fastembed.py:18`, `matching/ia/groq.py:20`; fakes en `matching/ia/fakes.py:17`; `vacantes/fuentes/magneto_mcp.py:25` (ClienteMCP) | El dominio no conoce fastembed, Groq ni el MCP de Magneto. Los tests usan fakes y no cargan modelos ni salen a la red. |
| **Strategy** (restricciones) | `matching/restricciones.py:33` (protocolo), `:161` (lista) | Modalidad, salario, ubicación (con áreas metropolitanas), experiencia y prácticas. Agregar un criterio es agregar una clase. |
| **Strategy** (fuentes de vacantes) | `vacantes/fuentes/__init__.py:26` (FuenteVacantes); `vacantes/management/commands/ingerir_vacantes.py:38` (registro); implementaciones en `vacantes/fuentes/magneto_detalle.py:91`, `vacantes/fuentes/fixture.py:11`, `vacantes/fuentes/magneto_mcp.py:70`, `matching/benchmark/sintetico.py:21` | Scraping, fixture, MCP de Magneto (B1, apagado) y datos sintéticos del benchmark detrás del mismo puerto. |
| **Strategy** (orden) | `matching/orden.py:14` (Ordenador), `:20` (similitud × cobertura) | El reranker opcional entra sin tocar el decisor. |
| **Chain of Responsibility** | `matching/politica.py:59` (Regla), `:120` (CADENA) | La primera regla que aplica decide: Descartar por restricción → Sin datos → Descartar por faltantes → Postular → Ajustar CV → Cerrar brecha. Los umbrales viven en un objeto versionado (`matching/politica.py:16`). |
| **Facade** | `matching/services.py:148` (`decidir_para_perfil`) | Un punto de entrada para el batch: embebe el perfil, preselecciona, cubre, decide, ordena y guarda. |

Piezas que sostienen la escala:
- **Preselección exacta en Postgres** (`matching/preseleccion.py:27`): una consulta de pgvector sobre todas las
  vacantes, sin índice aproximado (recall 100%), con un tope de las 3.000 más parecidas.
- **Cobertura vectorizada** (`matching/cobertura.py:100`): requisitos contra evidencias del CV en numpy, sobre una
  matriz guardada por vacante.
- **Incrementalidad:** solo se embebe lo nuevo o lo cambiado, y solo se reescriben las decisiones que cambiaron. La
  versión de las reglas de extracción va dentro del hash de contenido.
- **Dos modelos locales:** MiniLM (384 dimensiones) para la preselección y mpnet (768) para comparar cada requisito con
  la evidencia del CV (`matching/puertos.py:20`).
- **Varios procesos en paralelo:** la cola se reparte con `SELECT … FOR UPDATE SKIP LOCKED` y los candados de aviso viven
  en `matching/candados.py`.

## 3. Escala: el benchmark (`BENCHMARK.md`)

Con 120.000 vacantes sintéticas en la base, en un i7-12700H y solo CPU, se cumplen los límites de la spec con los dos
modelos:

| Etapa | Resultado | Límite | |
|---|---|---|---|
| Vacantes nuevas de un día (3.000) | 4,3 min | 15 min | medido |
| Carga inicial de 120.000 | 2,9 h | 8 h | proyectado |
| Decisión por candidato | mediana 2,29 s, peor 3,51 s | 5 s | medido |
| De subir el CV a ver las decisiones (navegador real) | 2,9 s | — | medido una vez |
| Dashboard con 3.000 decisiones | 0,27 s | — | medido |
| Vaciar una cola de 11 candidatos con 3 procesos | 10,7 s (32,0 s con 1) | — | medido |

MiniLM deja pasar casi todo el catálogo por el umbral de relevancia. A esta escala el que recorta es el tope de 3.000
vacantes por candidato, que es lo que asume la spec. Son datos sintéticos: repiten textos más que un catálogo real.

## 4. ¿Funciona? La evaluación (`EVALUACION.md`)

- **Set:** 11 CVs ficticios y 70 vacantes reales de magneto365.com, sin datos de contacto. Son 78 pares etiquetados a
  mano, de los cuales 2 se excluyeron por ser clones.
- **Mitades:** ajuste (para calibrar), prueba 1, y una prueba final con vacantes que ninguna otra mitad usa. Un test
  verifica ahora que no haya clones por texto entre las mitades.
- **Método:** las etiquetas de cada prueba se commitearon antes de su primera corrida. La prueba 1 se reusó después
  como validación y desde entonces ya no cuenta como "nunca vista".

| | Ajuste (política .2) | Prueba 1 (política .1, primera corrida) | **Prueba final limpia, 24 pares (política .2)** |
|---|---|---|---|
| Decisor | 69% | 46% | **46%** |
| Línea base por similitud | 15% | 23% | 23% (sobre los 26 pares) |
| Clase mayoritaria | 42% | 31% | 27% (sobre los 26 pares) |

Con los 26 pares originales la prueba final daba 50%. Dos eran clones de avisos del ajuste (Magneto republica el mismo
aviso por ciudad con otro id), y el número que vale es el limpio.

**Conclusión honesta:**
- **Como filtro da una buena señal:**
  - en la prueba final limpia acertó las 5 DESCARTAR y no descartó ninguna vacante que valiera la pena;
  - en la prueba 1 (política .1) la precisión fue menor: 8 de 12;
  - son pocos casos, así que es una señal, no una garantía;
  - supera por el doble a la línea base de similitud, que es lo que hacía v2 sin Groq.
- **No cumple la meta de 70%** porque no distingue bien entre Postular, Ajustar CV y Cerrar brecha: "lo tienes", "lo
  tienes a medias" y "te falta" dependen de diferencias de similitud de pocas centésimas, y eso no generaliza.
- **La prueba 1 enseñó algo importante:** las reglas escritas mirando errores subían la cifra sobre lo visto, pero no
  sobre vacantes nuevas.
- **La política final (.3)** corrige falsos descartes de la regla de prácticas. Sobre lo visto da lo mismo que la .2,
  y todavía no tiene medición en vacantes nuevas.

### Después de la exploración: la política vigente (2026-11-05.1)

La exploración (`docs/exploracion/2026-11-02-mejoras-decisor.md`) encontró que el límite era la señal de MiniLM y que
Ajustar CV no se distinguía de Postular. Antes de buscar vacantes nuevas se preregistraron cuatro variantes con sus
umbrales, y se midieron una sola vez en `prueba_3`:

| Variante (`prueba_3`, 26 pares nuevos) | Exactitud |
|---|---|
| Política anterior (MiniLM, 5 acciones) | 54% |
| Fusión de Postular y Ajustar CV | 62% |
| mpnet para la cobertura | 62% |
| **mpnet + fusión (adoptada)** | **69%** (18/26) |

Con la política adoptada y el código de producción, en todos los sets:

| Set | Pares | Decisor | Línea base por similitud | Clase mayoritaria | ¿Vacantes nuevas? |
|---|---:|---:|---:|---:|---|
| `prueba_3` | 26 | **69%** | 42% | 42% | **sí, preregistrada** |
| `prueba_2` | 25 | 48% | 32% | 32% | no: se usó para elegir umbrales |
| `prueba` | 24 | 62% | 38% | 38% | no |
| `prueba_1` | 26 | 85% | 38% | 38% | no |
| `ajuste` | 26 | 88% | 38% | 42% | no |

**Cómo leerlo:**
- **El número que vale es 69%, y no alcanza la meta de 70%.** Con solo 26 pares, su intervalo de confianza del 95% va más
  o menos de 50% a 83%. Es señal de mejora, no garantía.
- **Las cifras de 85–88% no prueban nada sobre vacantes nuevas:** esos pares ya se conocían al elegir la política.
- **No es del todo comparable con el 46% de arriba:** fusionar reduce las acciones de 5 a 4, y eso sube también la línea
  base. Por eso la comparación justa es dentro de `prueba_3`.
- **Las etiquetas las propuso el equipo de desarrollo** y siguen pendientes de revisión.

**Evaluación ciega con reclutadores** (`evaluacion_ciega/`): los 6 paquetes, regenerados con la política vigente, las
instrucciones y la tabulación están listos. Comparan el Plan de hoy con el top por similitud; la comparación de CV queda
para cuando haya respuestas reales del Taller. La clave queda fuera del repositorio. Falta conseguir a los reclutadores; si no se consiguen, se reporta solo el
set (§13.3).

## 5. El flujo de punta a punta (`VERIFICACION.md`)

- **n8n real:** importar (202) → decidir (202) → notificaciones (200). El batch decidió y armó el resumen "3 vacantes
  nuevas para postular".
- **Visual:** las capturas de todas las páginas coinciden con las de v2. Solo se agregaron los bloques nuevos: tarjeta
  de mercado, Taller y "Explícamelo".
- **Recorrido con navegador real** (2026-11-02, base de 120.000 vacantes y correo por consola): registro, verificación,
  login, CV, decisiones, detalle, Taller, notificaciones, historial, perfil y expectativas, sin respuestas 4xx/5xx ni
  errores de JavaScript. Encontró dos defectos que las pruebas no veían: el dashboard listaba todo el catálogo (86 MB,
  30 s) y un candidato nuevo recibía miles de avisos. Se corrigieron con catálogo paginado y un máximo de 20 avisos al día.
- **Servicios:** Postgres, el batch y la web corren como servicios de usuario con límites de memoria (`infra/systemd/`).
- **Correo real:** queda pendiente probarlo con una cuenta real. En desarrollo solo hay cuentas ficticias.
- **El flujo de n8n se repitió** el 2026-11-03 con la política vigente y sus tres nodos respondieron 202, 202 y 200 (ver
  `VERIFICACION.md`). Fue en un contenedor temporal, con una copia de la base y correo por consola, pidiendo solo 2
  vacantes. Falta dejarlo fijo: `N8N_SCORING_TOKEN` no está en el `.env`.
- **Catálogo real (2026-11-02):** 2.457 vacantes de Magneto y 17.399 requisitos, todas embebidas con la política vigente.
  - **Cobertura incompleta:** la carga perdió términos por una caída de internet y el relanzamiento se cortó a la hora
    acordada. Títulos como "recursos humanos" (4), "ingeniero industrial" (4), "ingeniero civil" (3) o "ingeniero de
    sistemas" (2) casi no aparecen. Se retoma con `ingerir_vacantes --solo-nuevas`.
  - **Vacantes sin requisitos:** 83 (3,4%).
  - **Tiempo:** ~1,5 s por candidato con 5 CV ficticios (`decidir_para_perfil`). En el recorrido con navegador las
    decisiones se vieron 6,2 s después de subir el CV, con el batch recién arrancado; es una sola medición.
  - **Recorrido sobre una copia de esta base:** sin respuestas 4xx/5xx, errores de JavaScript ni trazas de error. Las
    capturas están en `capturas/catalogo_real/`.
  - **`prueba_3` se repitió sobre esa copia:** 69%, sin ajustes.

## 6. Privacidad (Ley 1581)

- **Consentimiento:** se pide autorización expresa al registrarse y se guarda con su versión y su fecha.
- **Minimización:** antes de embeber se quitan nombre, correo, teléfono, documento y dirección.
- **Groq:** nunca recibe el CV.
- **Borrado:** el botón "eliminar mi cuenta" borra todo en cascada.
- **Correos:** los avisos van al correo verificado de la cuenta, no al que aparece en el CV.
- **Registro:** la cuenta no existe hasta que la persona abre el enlace del correo, así que nadie puede quedarse con el
  correo de otro.

## 7. Límites conocidos y siguientes pasos

1. **Mejorar la señal, no la lógica.** Un clasificador aprendido empata con las reglas. Lo pendiente es reconocer
   herramientas y títulos concretos: mpnet todavía mide más parecido de tema que si la persona sabe hacer algo.
2. **El Taller pregunta por lo que falta, pero la pregunta sale de la decisión.** Si el decisor se equivoca, pregunta algo
   irrelevante; la respuesta honesta ("No lo he hecho") está a un clic y nunca se propone texto.
3. **Calibrar con resultados reales:** cada vez que una postulación pasa a Entrevista o Descartado, se guarda junto con
   los insumos de la decisión (`ResultadoDecision`). Con suficientes casos se puede ajustar la política, o entrenar
   una regresión logística, con datos reales en vez de etiquetas propuestas.
4. **B1 (`job_detail` del MCP de Magneto)** trae el texto completo y las preguntas de la empresa. Está construido y
   apagado hasta revisar los términos de uso.
5. **Revisión de las etiquetas del set** por parte del equipo, y la evaluación ciega con reclutadores.
6. **Falsos positivos a la vista en el catálogo real.** Con 5 CV ficticios, el Plan de hoy es sensato en general, pero
   muestra "Cocinero" a un operario de producción y "Analista Senior" a un perfil junior. Es el mismo límite del punto 1
   (parecido de tema). Es una revisión a ojo, no una medición, y no se ajustaron umbrales mirando estos casos.
7. **Historial y notificaciones siguen mostrando porcentaje.** En el Plan de hoy, las filas y el detalle el anillo ya
   dice "3/3" y no "100%", porque ese porcentaje se leía como "encajas del todo" al lado de "solidez baja". Las otras
   dos páginas guardan solo el porcentaje, así que para cambiarlas hay que agregar datos a sus tablas.
