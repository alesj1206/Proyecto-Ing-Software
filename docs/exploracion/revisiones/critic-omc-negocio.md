# Crítica de producto (oh-my-claudecode:critic) — ¿el decisor consigue entrevistas?

**Veredicto: REVISAR.** El motor es sólido (local, explicable, escala según la Fase 0). El problema es lo que
entrega. Tal como está diseñado §5, un evaluador lo vería como "un ranking con etiquetas".

## Valor de cada acción
- **DESCARTAR — valor real.** Es el equivalente a los filtros eliminatorios (los usan 25 de 25 reclutadores,
  según Enhancv) y le ahorra volumen al candidato. Le falta el cuestionario de prefiltro de Magneto.
- **AJUSTAR_CV — la palanca con mejor evidencia** (CV adaptado: 5,71% de entrevistas contra 3,09%, según Huntr).
  Pero §5.1 la justifica con el argumento de que el ATS filtra por palabras clave, que ya quedó refutado. Además,
  la salida no es un texto concreto. Y "parcial" se define como una similitud entre τ_bajo y τ_alto, lo que no
  prueba que el candidato tenga la experiencia: hay riesgo de empujarlo a inflar el CV.
- **POSTULAR ordenado por reranker** es un ranking con otra etiqueta: no considera frescura, cupo diario ni
  diversificación por empresa.
- **CERRAR_BRECHA** no consigue entrevistas a corto plazo. Su valor está en la brecha agregada (plan de
  aprendizaje), no en cada vacante.

## Hallazgos críticos
- **La métrica de éxito no mide entrevistas.** "≥ 70% de exactitud contra las etiquetas del equipo" con 20–25
  pares de prueba (±18 puntos) mide si el decisor coincide con lo que piensa el equipo. Además, el anti-objetivo
  "ninguna acción supera el 80%" no se puede incumplir, porque el set se arma para cubrir las 4 acciones.
- **La postulación simulada** y un resultado que depende de que el candidato mueva tarjetas en el Kanban no
  producen entrevistas medibles. El MCP oficial de Magneto ofrece `job_applications` con el estado real.

## Confianza
Hoy mide **qué tan sólida es la decisión, no la probabilidad de entrevista**. Debe mostrarse como "solidez:
alta/media/baja", con el motivo y sin números. Prueba honesta para Sprint 3: la exactitud en los casos de
solidez alta debe ser mayor que en los de solidez baja.

## Cambios priorizados
1. **Línea base.** El decisor debe superar al orden por similitud pura (en el set de evaluación y en un
   piloto). Métrica norte: entrevistas ÷ postulaciones, tomada de `job_applications` y reportada como piloto con
   intervalos de confianza.
2. **Prefiltro de `job_detail` como restricción dura**, con respuestas prellenadas.
3. **AJUSTAR_CV entrega texto concreto** anclado en una evidencia del CV, priorizando cargo y resumen, y el
   candidato confirma cada cambio. Si no hay evidencia, la acción pasa a CERRAR_BRECHA.
4. **Frescura.** POSTULAR se ordena por ajuste × frescura, y las vacantes de menos de 72 h se marcan "Postular hoy".
5. **"Plan de hoy"**: 3–5 vacantes, como máximo una por empresa. El catálogo completo sigue visible.
6. **CERRAR_BRECHA sale del flujo de cada vacante** y pasa a un plan de aprendizaje ordenado por frecuencia.
7. **Instrumentación** de cada postulación (acción, solidez, versión de la política, frescura, CV ajustado).
   `job_apply` real solo con confirmación explícita y consentimiento (Ley 1581).

## Preguntas abiertas
- ¿Con 1 requisito obligatorio faltante conviene postular de todos modos?
- ¿Magneto expone la fecha de publicación y el número de postulantes?
- ¿El texto que se envía a Groq cumple la minimización de datos?
