# Exploración: las dos mejoras principales del decisor (noche del 2026-11-02)

Rama `exploracion/mejoras-decisor`, que sale de `sprint-3` en `013a80b`. No se unió a `sprint-3`: esa decisión es del
equipo. Los scripts están en `docs/exploracion/mejoras/`.

## Qué se buscaba

La Fase 4 dejó dos problemas abiertos:
1. **El decisor no distingue bien** entre Postular, Ajustar CV y Cerrar brecha: 46% en la prueba limpia, lejos del 70%.
2. **El Taller de CV propone emparejamientos absurdos** entre la evidencia del CV y el requisito.

## Cómo se midió, sin hacerse trampa

- **Simulador** (`simular.py`): vuelca cada par etiquetado (requisitos, evidencias, similitudes y restricciones) y
  re-decide sin modelos. Antes de usarlo se comprobó que reproduce las cifras reales de la política .3: ajuste 69%,
  prueba 1 73% y prueba limpia 46%.
- **Desarrollo:** se hizo solo con los 76 pares ya vistos (ajuste, prueba 1 y la prueba de la Fase 4).
- **`prueba_2`:** 25 pares sobre 19 vacantes nuevas de magneto365.com, sin clones por texto contra ninguna mitad
  anterior. Las etiquetas se commitearon (`05f1f69`) **antes** de medir. Se midió **una sola vez**, y solo con las
  tres variantes definidas de antemano.

## Resultado en `prueba_2` (nunca vista)

| Variante | Exactitud | DESCARTAR: recall / precisión |
|---|---|---|
| Actual (política .3, coseno MiniLM) | **36%** (9/25) | 4/7 · 4/5 |
| **A. Fusionar Postular + Ajustar CV** | **48%** (12/25) | 4/7 · 4/5 |
| Cobertura con cross-encoder bge-reranker-v2-m3 | 28% (7/25) | 5/7 · 5/11 |
| Línea base: similitud pura | 16% | — |
| Línea base: clase mayoritaria | 28% | — |

En `prueba_2` la política actual queda **más baja que en la Fase 4 (36% frente a 46%)**. Con dos pruebas nuevas de
unos 25 pares cada una, la exactitud real del decisor de 5 acciones parece estar entre 35% y 50%.

## La fusión es la única mejora que se sostiene

| Set | Actual | Con fusión |
|---|---|---|
| Ajuste (visto) | 69% | 81% |
| Prueba 1 (vista) | 73% | 81% |
| Prueba Fase 4 limpia (vista) | 46% | 67% |
| **`prueba_2` (nueva)** | **36%** | **48%** |

- **Por qué mejora:** la diferencia entre "lo tienes" y "lo tienes a medias" depende de centésimas de similitud y no
  generaliza. Al unir esas dos acciones, el decisor deja de equivocarse en esa frontera.
- **Producto:** "Postular" pasa a decir "Resalta en tu hoja de vida: …" cuando hay algo que hacer explícito, y ofrece
  el Taller.
- **Umbrales:** se re-barrieron con la fusión, solo sobre lo visto, y los actuales siguen siendo los mejores. No hubo
  que recalibrar nada.
- **Prototipo en esta rama:** `Politica.fusionar_ajustar` (apagado por defecto), la regla `AjustarCV` y el detalle, que
  ofrece el Taller para un Postular con algo que resaltar. Lo cubre `matching/tests/test_fusion.py`.

Aun con la fusión, 48% en vacantes nuevas sigue lejos del 70%.

## Lo que no sirvió

- **Cross-encoder (bge-reranker-v2-m3) para medir la cobertura:** sobre lo visto bajó de 63% a 58%, y en `prueba_2`
  dio 28%. Además es caro: en CPU puntúa ~24 pares por segundo, lo que daría horas por candidato con 3.000 vacantes.
  La GPU no arrancó porque al entorno de la Fase 0 le faltan cuDNN 9 y CUDA 13. No se recomienda.
- **Compuerta léxica** (`lexico.py`): si un requisito nombra herramientas (SQL, Python, Siigo, RETHUS) y el CV no
  nombra ninguna, el requisito no puede quedar cubierto. Se diseñó **después** de ver los errores de `prueba_2`, así
  que solo se probó sobre lo visto: sin fusión gana 4 puntos, con fusión no cambia nada. No compensa gastar otra prueba
  nueva en ella.

## ¿Le gana un clasificador aprendido a las reglas?

`mejoras/exp_aprendido.py` entrena una regresión logística multinomial (numpy) sobre las mismas señales que usa el
decisor: cobertura, similitud, restricciones y legibilidad. Se hizo validación cruzada por set: entrena con tres sets y
evalúa en el que no vio. Son 101 pares.

| | Reglas (5 acciones) | Aprendido (5) | Reglas con fusión | Aprendido con fusión |
|---|---|---|---|---|
| Total (101 pares) | 56% | 54% | 69% | 67% |
| `prueba_2` | 36% | 40% | 48% | 48% |

**Empatan.** El cuello de botella no es la lógica de decisión (reglas o modelo), sino la señal de cobertura que da
MiniLM. Aprender umbrales o pesos de estos datos no la mejora. Por eso la recomendación 4 se matiza más abajo.

## Por qué falla, en el fondo (de los errores de `prueba_2`)

1. **MiniLM mide parecido de tema, no si la persona sabe hacer algo.**
   - "Monitoreo pediátrico" queda cubierto con experiencia en hospitalización de adultos.
   - "Python, SQL y Macros" queda cubierto con un CV que solo dice SQL.
   - "Cálculo de comisiones" queda cubierto con "análisis de datos".

   Es el error más frecuente: CERRAR_BRECHA predicho como POSTULAR.
2. **Todavía entra ruido en la extracción:**
   - hashtags ("#BeKPMG");
   - frases de cultura ("Estamos interesados en crear una cultura…");
   - "Modalidad de trabajo: híbrida";
   - "No se requiere experiencia previa";
   - "Contar con documentación al día".
3. **Lo que la persona etiquetó no se puede medir con el texto:** carrera distinta (Contaduría frente a
   Administración), un aviso que es "banco de talentos", o requisitos de cursos.

## El Taller de CV

De las 29 sugerencias que el Taller generaría en los pares vistos, se etiquetaron a mano, **sin mirar ningún
puntaje**, cuáles son sensatas (la evidencia de verdad respalda el requisito). El archivo es
`mejoras/sugerencias_taller_etiquetadas.json`.

- **Solo 4 de 29 son sensatas (14%).** Las demás emparejan cosas como "RPG/ILE" con "Git", "Python" con "consultas
  SQL" o "Manejo de Office" con "Me encargaba de la papelería".
- **Ningún puntaje las separa:** ni el coseno, ni el cross-encoder, ni la similitud del par. Para conservar las 4
  sensatas hay que dejar pasar 15–20 sugerencias, con una precisión de 20–27%.
- **Un filtro estructural** (evidencia solo de la sección de experiencia, requisitos cortos, sin blandas ni cursos)
  sube la precisión a 30–40% y pierde la mitad de las sensatas.

**Conclusión:** con estos modelos, que el Taller proponga texto reescrito no es confiable, y es justo el riesgo que
la spec prohíbe (inflar el CV). La recomendación es cambiar el diseño: el Taller **pregunta** en vez de redactar.

> «Esta vacante pide **Power BI**. ¿Lo has usado? Si sí, escríbelo con tus palabras (por ejemplo, en qué proyecto).»

La evidencia más parecida se muestra solo como pista. No se propone texto y no se copia nada que la persona no haya
escrito. Así el Taller conserva su valor (recordar qué hacer explícito) sin el riesgo de inventar.

### Prototipo del Taller guiado (commit `c56f393`, en esta rama)

- Cada tarjeta dice "Esta vacante pide: X" y "Pista: en tu hoja de vida dice «…»", y pregunta "¿Has trabajado con
  «X»? Si es así, cuéntalo con tus palabras".
- Hay un cuadro de texto y dos botones: **Agregar a mi postulación** y **No lo he hecho**.
- Aceptar sin escribir no cuenta y muestra un aviso. Lo que se copia en "Texto para tu postulación" son solo las
  respuestas del candidato (`SugerenciaCV.respuesta`, migración `0006`). Ya no hay resumen generado.
- **Capturas** en `mejoras/capturas/`:
  - `taller_guiado.png`: la pregunta;
  - `taller_guiado_sin_texto.png`: el aviso al aceptar sin escribir;
  - `taller_guiado_respondido.png`: la respuesta propia como texto para copiar.
- **Lo que no resuelve:** la pregunta sigue saliendo de la decisión. En la captura, a una analista de datos se le
  pregunta por experiencia en tiendas de ropa, porque el decisor marcó esa vacante como Ajustar CV. La diferencia es
  que ahora la respuesta honesta ("No lo he hecho") está a un clic y no se le propone ningún texto. Para que las
  preguntas también tengan sentido hay que mejorar el decisor (recomendaciones 1 y 4).
- **Efecto en la evaluación ciega:** su pregunta 2 (CV original contra CV con sugerencias) dependía del texto
  automático y en esta rama se omite. Habrá que retomarla cuando existan respuestas reales de candidatos.

## Recomendaciones, en orden

1. **Fusionar Postular y Ajustar CV:** +8 a +21 puntos en todos los sets, sin recalibrar nada. Es un cambio de
   producto (§13.2), pero el prototipo ya está. Hay que actualizar §13.2 de la spec, el informe y las capturas.
2. **Taller como preguntas guiadas, sin texto propuesto:** elimina el riesgo de inventar. El prototipo ya está en
   esta rama (`c56f393`), con pruebas y capturas.
3. **Contar el decisor tal como es:**
   - un pre-filtro gratuito y explicable que descarta con buena precisión;
   - un orden de prioridad;
   - una orientación ("te falta X"), pero no una clasificación fina confiable.

   Ningún ajuste de reglas o umbrales probado esta noche cambia eso.
4. **Mejorar la señal antes que la lógica:** un clasificador aprendido sobre las señales actuales empata con las
   reglas, así que calibrar con resultados reales (`ResultadoDecision`) solo ayudará si cambia la señal.
   - **Modelos:** lo más prometedor es un modelo de embeddings más fuerte para pares requisito/evidencia (por ejemplo,
     multilingual-e5 o bge-m3 con la GPU funcionando).
   - **Reconocimiento de herramientas:** detectar las herramientas y títulos que pide la vacante y comprobar si
     aparecen en el CV.
   - **Dónde sí sirven los datos reales:** para saber qué acciones llevan de verdad a entrevistas, no para afinar
     umbrales.
5. **Filtros de ruido** (hashtags, frases de cultura, "no se requiere"): mejoras pequeñas. Conviene hacerlas junto con
   el punto 4, para medirlas con datos reales.

## Pendiente del equipo

- Revisar las etiquetas de `prueba_2` (25 pares en `pares.yaml`).
- Decidir si se adopta la fusión: el prototipo se enciende con `fusionar_ajustar=True` en `matching/politica.py`.
- Decidir si se adopta el Taller guiado. Para unirlo a `sprint-3` hay que aplicar la migración
  `matching/0006_sugerencia_respuesta`; en la base de desarrollo se aplicó para la captura y luego se revirtió.
