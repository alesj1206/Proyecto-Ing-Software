# Scoutly v3: informe del Sprint 3

## 1. El problema

El reto de Magneto (Idea 4) pide un flujo diario con n8n: vacantes → ranking → notificación. La v2 analizaba cada
vacante con una llamada a Groq. A la escala de Magneto (~120.000 vacantes activas) eso es lento, caro y no se puede
explicar. Además, el objetivo de fondo no es un ranking: es que el candidato **consiga entrevistas**.

La v3 reemplaza el ranking por un **decisor local y gratuito**. Para cada par (candidato, vacante) da una acción
(Postular, Ajustar CV, Cerrar brecha, Descartar o Revísala tú), su solidez (alta, media o baja) y las razones que la
respaldan, todas calculadas con datos y nunca redactadas por un LLM. Groq solo escribe, a pedido, una explicación en
prosa con los campos de criterio, sin el texto del CV.

## 2. Arquitectura y patrones

Son cinco apps (`cuentas`, `vacantes`, `matching`, `postulaciones` y `notificaciones`) más el módulo `api` para n8n.
La lógica vive en servicios y selectores, y las vistas son delgadas. Solo el batch (`manage.py decidir --escuchar`)
carga modelos; la web lee decisiones ya calculadas.

| Patrón | Dónde | Para qué |
|---|---|---|
| **Ports & Adapters** | `matching/puertos.py:9` (Embedder), `:17` (Redactor), `:23` (Reordenador); adaptadores en `matching/ia/fastembed.py:17`, `matching/ia/groq.py:20`; fakes en `matching/ia/fakes.py:17`; `vacantes/fuentes/magneto_mcp.py:25` (ClienteMCP) | El dominio no conoce fastembed, Groq ni el MCP de Magneto. Los tests usan fakes y no cargan modelos ni salen a la red. |
| **Strategy** (restricciones) | `matching/restricciones.py:31` (protocolo), `:144` (lista) | Modalidad, salario, ubicación (con áreas metropolitanas), experiencia y prácticas. Agregar un criterio es agregar una clase. |
| **Strategy** (fuentes de vacantes) | `vacantes/fuentes/__init__.py:26` (FuenteVacantes); `vacantes/management/commands/ingerir_vacantes.py:31` (registro); implementaciones en `vacantes/fuentes/magneto_detalle.py:89`, `vacantes/fuentes/fixture.py:11`, `vacantes/fuentes/magneto_mcp.py:70`, `matching/benchmark/sintetico.py:21` | Scraping, fixture, MCP de Magneto (B1, apagado) y datos sintéticos del benchmark detrás del mismo puerto. |
| **Strategy** (orden) | `matching/orden.py:14` (Ordenador), `:20` (similitud × cobertura) | El reranker opcional entra sin tocar el decisor. |
| **Chain of Responsibility** | `matching/politica.py:53` (Regla), `:111` (CADENA) | La primera regla que aplica decide: Descartar por restricción → Sin datos → Descartar por faltantes → Postular → Ajustar CV → Cerrar brecha. Los umbrales viven en un objeto versionado (`matching/politica.py:16`). |
| **Facade** | `matching/services.py:103` (`decidir_para_perfil`) | Un punto de entrada para el batch: embebe el perfil, preselecciona, cubre, decide, ordena y guarda. |

Piezas que sostienen la escala:
- **Preselección exacta en Postgres** (`matching/preseleccion.py:27`): una consulta de pgvector sobre todas las
  vacantes, sin índice aproximado (recall 100%), con un tope de las 3.000 más parecidas.
- **Cobertura vectorizada** (`matching/cobertura.py:100`): requisitos contra evidencias del CV en numpy, sobre una
  matriz guardada por vacante.
- **Incrementalidad:** solo se embebe lo nuevo o lo cambiado. La versión de las reglas de extracción va dentro del hash
  de contenido.

## 3. Escala: el benchmark (`BENCHMARK.md`)

Con 120.000 vacantes sintéticas en la base, en un i7-12700H y solo CPU, se cumplen los cuatro límites de la spec:

| Etapa | Resultado | Límite | |
|---|---|---|---|
| Vacantes nuevas de un día (3.000) | 1,5 min | 15 min | medido |
| Carga inicial de 120.000 | 1 h | 8 h | proyectado |
| Decisión por candidato | mediana 2,9 s, peor 4,8 s | 5 s | medido |

Con MiniLM, casi todo el catálogo supera el umbral de relevancia. A esta escala el que recorta es el tope de 3.000
vacantes por candidato, que es lo que asume la spec.

## 4. ¿Funciona? La evaluación (`EVALUACION.md`)

- **Set:** 11 CVs ficticios y 70 vacantes reales de magneto365.com, sin datos de contacto, en 78 pares etiquetados a
  mano.
- **Mitades:** ajuste (para calibrar), prueba 1 y una prueba final con 24 vacantes que ninguna otra mitad usa.
- **Método:** las etiquetas de cada prueba se commitearon antes de correrla, y cada prueba se corrió una sola vez.

| | Ajuste | Prueba 1 (antes de corregir) | **Prueba final (nunca vista)** |
|---|---|---|---|
| Decisor | 69% | 46% | **50%** |
| Línea base por similitud | 15% | 23% | 23% |
| Clase mayoritaria | 42% | 31% | 27% |

**Conclusión honesta:**
- **Como filtro funciona:** acierta los 14 DESCARTAR de las dos pruebas y, en la final, no descarta ninguna vacante que
  valiera la pena. También supera por el doble a la línea base de similitud, que es lo que hacía v2 sin Groq.
- **No cumple la meta de 70%** porque no distingue bien entre Postular, Ajustar CV y Cerrar brecha: "lo tienes", "lo
  tienes a medias" y "te falta" dependen de diferencias de similitud de pocas centésimas, y eso no generaliza.
- **La prueba 1 enseñó algo importante:** las reglas escritas mirando los errores del ajuste subían la cifra sobre lo
  visto, pero no sobre vacantes nuevas. Por eso se construyó la prueba final.

**Evaluación ciega con reclutadores** (`evaluacion_ciega/`): los 6 paquetes, las instrucciones y la tabulación están
listos. La clave queda fuera del repositorio. Falta conseguir a los reclutadores; si no se consiguen, se reporta solo el
set (§13.3).

## 5. El flujo de punta a punta (`VERIFICACION.md`)

- **n8n real:** importar (202) → decidir (202) → notificaciones (200). El batch decidió y armó el resumen "3 vacantes
  nuevas para postular".
- **Visual:** las capturas de todas las páginas coinciden con las de v2. Solo se agregaron los bloques nuevos: tarjeta
  de mercado, Taller y "Explícamelo".
- **Correo real:** queda pendiente probarlo con una cuenta real. En desarrollo solo hay cuentas ficticias.

## 6. Privacidad (Ley 1581)

- **Consentimiento:** se pide autorización expresa al registrarse y se guarda con su versión y su fecha.
- **Minimización:** antes de embeber se quitan nombre, correo, teléfono, documento y dirección.
- **Groq:** nunca recibe el CV.
- **Borrado:** el botón "eliminar mi cuenta" borra todo en cascada.
- **Correos:** los avisos van al correo verificado de la cuenta, no al que aparece en el CV.
- **Registro:** la cuenta no existe hasta que la persona abre el enlace del correo, así que nadie puede quedarse con el
  correo de otro.

## 7. Límites conocidos y siguientes pasos

1. **La distinción fina entre acciones.** Hay dos caminos: fusionar Postular y Ajustar CV en "Postúlate, y resalta
   esto" (sobre la prueba final habría dado 69%, pero es un cambio de producto que hay que medir con otra prueba), o
   usar el reranker (cross-encoder, con GPU) para decidir la cobertura.
2. **El Taller de CV puede emparejar evidencia y requisito sin relación.** Hay que exigir una similitud mínima más alta
   para sugerir.
3. **Calibrar con resultados reales:** cada vez que una postulación pasa a Entrevista o Descartado, se guarda junto con
   los insumos de la decisión (`ResultadoDecision`). Con suficientes casos se puede ajustar la política, o entrenar
   una regresión logística, con datos reales en vez de etiquetas propuestas.
4. **B1 (`job_detail` del MCP de Magneto)** trae el texto completo y las preguntas de la empresa. Está construido y
   apagado hasta revisar los términos de uso.
5. **Revisión de las etiquetas del set** por parte del equipo, y la evaluación ciega con reclutadores.
