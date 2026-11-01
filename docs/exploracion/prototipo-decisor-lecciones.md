# Prototipo del decisor sobre vacantes reales: lecciones

Se probó un prototipo **desechable** (`spike/exploracion/decisor_prototipo.py`) con 18 vacantes reales de Magneto
(el fixture de v2, con el texto recortado a 500 caracteres) y 3 perfiles ficticios: analista de datos junior, QA
semi-senior y diseñadora UX junior. Usa MiniLM y bge-reranker-v2-m3 en GPU. Resultados:
`prototipo-decisor-resultados-v1.md` (primera versión) y `prototipo-decisor-resultados.md` (versión 2).

## Qué falló en la v1 y cómo se corrigió en la v2
| Problema en la v1 | Causa | Corrección en la v2 |
|---|---|---|
| Brechas absurdas: "te falta: $ 10.000.000 Medellín Importante empresa…" | La extracción tomaba como requisitos el salario, la presentación de la empresa y frases de marketing | Filtro de ruido (salario, "importante empresa", "te apasiona"…) |
| **Le dijo POSTULAR a un QA para "Analista de Datos" con "cubres 0 de 0"** | Una vacante sin requisitos legibles caía por defecto en POSTULAR | Nueva acción **SIN_DATOS** ("revísala tú"), que nunca entra al plan de hoy |
| Vacantes de DevOps evaluadas para una diseñadora | El prototipo se saltó el umbral de relevancia del spec §5.7 | `τ_relevancia = 0,40`: la diseñadora pasa de 18 vacantes a 4 relevantes, y las 2 de UX quedan arriba (0,79 y 0,69) |
| AJUSTAR_CV le pidió a un tecnólogo "haz explícito que eres profesional en administración" | Comparar la formación por similitud: lo "parcial" no prueba que tenga esa formación (riesgo de inflar el CV, que ya advertía la crítica) | La formación sale de la cobertura semántica y se trata como dato estructurado |
| Casi nada quedaba "cubierto" | τ_alto = 0,62 cuando el p90 real de similitud era 0,54 | Calibración con el set de 40: **τ_alto = 0,50** (65% de positivos, 2% de negativos) y **τ_bajo = 0,40** (85% / 10%) |

## Hallazgo sobre los modelos (corrige la elección de la Fase 0)
El reporte de la Fase 0 eligió `potion` por una métrica de **orden entre pares** (87,5%). Pero la cobertura usa un
**umbral absoluto**, y ahí potion separa mucho peor:

| Modelo | τ = 0,40: positivos sobre el umbral | negativos sobre el umbral |
|---|---|---|
| MiniLM | **85%** | 10% |
| potion | 55% | 8% |

**Para la cobertura se debe usar MiniLM.** La lección de método: la métrica de calidad tiene que imitar la
decisión real (clasificar con un umbral), no solo el orden. Esto entra en el set de evaluación de la Fase 4.

## Lo que la v2 todavía enseña (y que importa para conseguir entrevistas)
1. **El cuello de botella son los datos de entrada, no el modelo.** Para el QA, 5 de sus 14 vacantes relevantes
   salen SIN_DATOS porque el texto viene recortado a 500 caracteres. **Con el texto completo**, ya sea con el
   scraping del detalle o con `candidate.job_detail` del MCP oficial de Magneto, el decisor tiene con qué decidir.
   Esto es la prioridad número 1.
2. **La política es demasiado estricta y pierde entrevistas.** A la diseñadora junior le dice "cerrar brecha: te
   falta Canva" en la práctica de UX donde tiene 70% de cobertura y encaja casi perfecto. Las **etiquetas de
   habilidades de Magneto son señales, no requisitos obligatorios**. Propuesta: con cobertura ≥ 0,7 y **un solo**
   faltante de nivel herramienta, la acción es **POSTULAR con nota** ("menciona que puedes aprender Canva
   rápido"). Es la "pregunta abierta" que dejó la crítica de producto, ahora respondida con un caso real.
3. **Las restricciones duras hacen la mayor parte del trabajo.** Ubicación, experiencia y salario descartan la
   mayoría de las vacantes. Por eso la búsqueda **por candidato** (sus ciudades y su modalidad), con el
   prefiltro en SQL o con `job_search` del MCP, es lo que deja al decisor trabajar sobre vacantes que de verdad
   le sirven.
4. La regla de experiencia (descartar si tiene menos del 50% de los años pedidos) deja por fuera a juniors con 0
   años en vacantes que piden 1. Hay que calibrarla, porque la evidencia sobre juniors no la respalda.
