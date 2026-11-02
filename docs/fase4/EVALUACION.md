# Fase 4: evaluación del decisor

Salida cruda de las corridas (política congelada en el commit 825aed6; etiquetas de prueba commiteadas en 7e093c7, antes de correr).

## Resultado

| | Ajuste (26 pares, con la que se calibró) | **Prueba (26 pares, nunca vista)** |
|---|---|---|
| Exactitud del decisor | 81% | **46%** |
| Línea base: similitud pura | 19% | 23% |
| Línea base: clase mayoritaria | 42% | 31% |
| Acción más frecuente en lo predicho | DESCARTAR 46% | DESCARTAR 46% |

**Anti-objetivos de §2 sobre la prueba:**
- exactitud ≥ 70%: **no se cumple (46%)**;
- ninguna acción > 80%: se cumple;
- superar las líneas base: se cumple, por el doble de la similitud pura.

La diferencia entre 81% y 46% es sobreajuste: las reglas de las Fases 2 y 4 se escribieron mirando los errores de la
mitad de ajuste. Los números de la prueba son los que valen, y **no se tocó nada del decisor después de verlos**.

DESCARTAR acierta el 100% (8 de 8). Los errores están en distinguir POSTULAR, AJUSTAR_CV y CERRAR_BRECHA entre sí, y
en SIN_DATOS (0 de 3).

## Después de las correcciones: prueba nueva

Se corrigieron las causas generales del diagnóstico de abajo, se validó solo con lo ya visto y se midió **una vez**
con una prueba nueva de 26 pares (política `2026-11-04.2`).

**Corrección de la revisión final:** dos de esos 26 pares resultaron ser clones casi idénticos de avisos del ajuste.
Magneto republica el mismo aviso por ciudad con otro id; mag-1117923 es copia de mag-1121576 y mag-1116047 lo es de
mag-1116167. Se excluyeron, y la cifra limpia es la de 24 pares. La prueba 1 también tenía 3 clones del ajuste, así
que su 46% está algo contaminado. Ahora un test compara el texto, no solo el id, para que no vuelva a pasar.

| | Prueba 1 (política .1, antes de corregir) | Prueba nueva, 26 pares (.2) | **Prueba nueva limpia, 24 pares (.2)** |
|---|---|---|---|
| Exactitud del decisor | 46% | 50% | **46%** (11 de 24) |
| Línea base: similitud pura | 23% | 23% | — |
| Línea base: clase mayoritaria | 31% | 27% | — |
| DESCARTAR: recall (los que debían descartarse) | 8 de 8 | 6 de 6 | **5 de 5** |
| DESCARTAR: precisión (los descartados que debían serlo) | 8 de 12 (67%) | 6 de 6 | **5 de 5** |

**El anti-objetivo de 70% no se cumple.** Las correcciones subieron la prueba 1 de 46% a 73% cuando se volvió a correr
como validación (ya vista), mientras el ajuste bajó de 81% a 69%. En vacantes nuevas, la cifra limpia no se movió
(46%): la mejora sobre lo visto venía de ajustar mirando esos errores.

**Lo que funciona en vacantes nunca vistas, con la política .2:** como filtro "vale la pena / no vale la pena", en la
prueba nueva limpia acertó las 5 DESCARTAR y no descartó ninguna vacante que valiera la pena. En la prueba 1, con la
política .1, la precisión fue menor: 4 de los 12 descartes no correspondían (3 de ellas sí valían la pena). Son pocos
casos (5), así que es una señal, no una garantía.

**Lo que no funciona:** distinguir entre POSTULAR, AJUSTAR_CV y CERRAR_BRECHA (6 de 16 en la prueba limpia), y
SIN_DATOS (0 de 6 entre las dos pruebas). Con MiniLM, "parcial" contra "cubierto" contra "faltante" depende de
diferencias de similitud de pocas centésimas, y eso no generaliza.

Para referencia (no es una cifra para reportar como logro): si POSTULAR y AJUSTAR_CV fueran una sola acción
("postúlate, y aquí tienes qué resaltar"), la prueba limpia daría 67% (16 de 24).

### Política .3 (revisión final)

La revisión final corrigió falsos descartes en la regla de prácticas y varios casos de la extracción. Sobre lo ya visto
da lo mismo que la .2 (ajuste 69%, prueba 1 73%; corridas al final). **No tiene una medición en vacantes nunca vistas:**
la prueba nueva ya se usó.

## Por qué falla (diagnóstico de los 14 errores, sin cambiar nada)

1. **Pies de página de Magneto tomados como obligatorios (3 errores).** Bloques como "Otras habilidades / Habilidades
   técnicas / interpersonales" repiten los requisitos como palabras sueltas ("Excel", "Power BI", "Proaktividad") y
   cuentan como obligatorios. Si una falta, cuenta doble (habilidad_nombrada_distinto × mag-1117407 acumula 4 faltantes
   y se descarta). La spec dice que las etiquetas son señales, no obligatorios (§13.2).
2. **Requisitos de experiencia con área ("2 años en análisis de datos…") medidos por similitud (2).** Quedan
   "parciales" y mandan a AJUSTAR_CV a candidatos que cumplen todo. La Fase 2 solo excluyó los que piden años sin área.
3. **Municipios del área metropolitana (2).** La restricción de ubicación compara la ciudad literal: Envigado y La
   Estrella quedan "fuera de Medellín". La etiqueta humana los acepta.
4. **Frases de presentación tomadas como requisitos (2 de los 3 SIN_DATOS).** En una vacante escueta, "Serás
   responsable de garantizar un manejo oportuno…" cuenta como requisito, así que nunca llega a SIN_DATOS. El tercero
   tiene similitud 0,29, bajo τ_relevancia, y se oculta como no relevante.
5. **Habilidad nombrada distinto (3).** MiniLM no relaciona "hojas de cálculo" con "Excel avanzado" ni "tableros de
   control" con "Power BI". Es el caso difícil a propósito del set, y sigue sin resolverse.
6. **Listas dentro de un requisito (2).** "Power BI avanzado, Excel avanzado" y "(RPG/ILE, Java, DB2, MySQL, Git y
   UrbanCode)" quedan como un solo requisito, y lo cubre cualquiera de sus partes (con Java basta).
7. **Experiencia específica cubierta por una general (1).** "6 meses en autorizaciones de salud y referencia" se da por
   cubierta con la experiencia general de auxiliar de enfermería.

Las causas 1, 2, 4 y 6 son de extracción y son generales: no dependen de estas vacantes. La 3 es una tabla de áreas
metropolitanas. La 5 y la 7 son límites del modelo de embeddings.

## Corridas

### Mitad de prueba — política 2026-11-04.1

- pares: 26
- exactitud del decisor: 46%
- línea base (similitud pura): 23%
- clase mayoritaria: 31%
- distribución predicha: POSTULAR 4, AJUSTAR_CV 7, CERRAR_BRECHA 3, DESCARTAR 12

| acción esperada | acierto |
|---|---:|
| POSTULAR | 33% |
| AJUSTAR_CV | 25% |
| CERRAR_BRECHA | 20% |
| DESCARTAR | 100% |
| SIN_DATOS | 0% |

| esperada \ predicha | POSTULAR | AJUSTAR_CV | CERRAR_BRECHA | DESCARTAR |
|---|---:|---:|---:|---:|
| POSTULAR | 2 | 3 | 0 | 1 |
| AJUSTAR_CV | 1 | 1 | 1 | 1 |
| CERRAR_BRECHA | 1 | 2 | 1 | 1 |
| DESCARTAR | 0 | 0 | 0 | 8 |
| SIN_DATOS | 0 | 1 | 1 | 1 |

Errores:
- sin_experiencia_practicante × mag-1120768: esperada CERRAR_BRECHA, predicha DESCARTAR (similitud 0.70)
- datos_junior × mag-1073362: esperada POSTULAR, predicha AJUSTAR_CV (similitud 0.79)
- auxiliar_contable × mag-1119027: esperada POSTULAR, predicha AJUSTAR_CV (similitud 0.76)
- sin_experiencia_practicante × mag-1093888: esperada POSTULAR, predicha DESCARTAR (similitud 0.64)
- operario_produccion × mag-1121278: esperada POSTULAR, predicha AJUSTAR_CV (similitud 0.87)
- datos_junior × mag-1086437: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.79)
- habilidad_nombrada_distinto × mag-1117407: esperada AJUSTAR_CV, predicha DESCARTAR (similitud 0.77)
- habilidad_nombrada_distinto × mag-1086437: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.75)
- desarrollador_backend × mag-1009047: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.62)
- auxiliar_enfermeria × mag-1121637: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.72)
- habilidad_nombrada_distinto × mag-1073362: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.70)
- asesora_comercial × mag-1119927: esperada SIN_DATOS, predicha DESCARTAR (similitud 0.29)
- sin_experiencia_practicante × mag-1106225: esperada SIN_DATOS, predicha CERRAR_BRECHA (similitud 0.47)
- experiencia_implicita_y_datos_incompletos × mag-1106225: esperada SIN_DATOS, predicha AJUSTAR_CV (similitud 0.48)

### Mitad de ajuste — política 2026-11-04.1

- pares: 26
- exactitud del decisor: 81%
- línea base (similitud pura): 19%
- clase mayoritaria: 42%
- distribución predicha: POSTULAR 6, AJUSTAR_CV 2, CERRAR_BRECHA 4, DESCARTAR 12, SIN_DATOS 2

| acción esperada | acierto |
|---|---:|
| POSTULAR | 100% |
| AJUSTAR_CV | 33% |
| CERRAR_BRECHA | 100% |
| DESCARTAR | 100% |
| SIN_DATOS | 67% |

| esperada \ predicha | POSTULAR | AJUSTAR_CV | CERRAR_BRECHA | DESCARTAR | SIN_DATOS |
|---|---:|---:|---:|---:|---:|
| POSTULAR | 4 | 0 | 0 | 0 | 0 |
| AJUSTAR_CV | 2 | 2 | 2 | 0 | 0 |
| CERRAR_BRECHA | 0 | 0 | 2 | 0 | 0 |
| DESCARTAR | 0 | 0 | 0 | 11 | 0 |
| SIN_DATOS | 0 | 0 | 0 | 1 | 2 |

Errores:
- datos_junior × mag-1082501: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.78)
- auxiliar_contable × mag-1121313: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.78)
- habilidad_nombrada_distinto × mag-1115173: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.79)
- experiencia_implicita_y_datos_incompletos × mag-1108121: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.67)
- sin_experiencia_practicante × mag-1120958: esperada SIN_DATOS, predicha DESCARTAR (similitud 0.25)


## Después de las correcciones (política 2026-11-04.2, congelada en ca8ba60; etiquetas de la prueba nueva en 67db712)

### Mitad de prueba — política 2026-11-04.2

- pares: 26
- exactitud del decisor: 50%
- línea base (similitud pura): 23%
- clase mayoritaria: 27%
- distribución predicha: POSTULAR 7, AJUSTAR_CV 8, CERRAR_BRECHA 5, DESCARTAR 6

| acción esperada | acierto |
|---|---:|
| POSTULAR | 33% |
| AJUSTAR_CV | 50% |
| CERRAR_BRECHA | 43% |
| DESCARTAR | 100% |
| SIN_DATOS | 0% |

| esperada \ predicha | POSTULAR | AJUSTAR_CV | CERRAR_BRECHA | DESCARTAR |
|---|---:|---:|---:|---:|
| POSTULAR | 2 | 3 | 1 | 0 |
| AJUSTAR_CV | 2 | 2 | 0 | 0 |
| CERRAR_BRECHA | 3 | 1 | 3 | 0 |
| DESCARTAR | 0 | 0 | 0 | 6 |
| SIN_DATOS | 0 | 2 | 1 | 0 |

Errores:
- asesora_comercial × mag-1121530: esperada POSTULAR, predicha CERRAR_BRECHA (similitud 0.60)
- auxiliar_enfermeria × mag-1118625: esperada POSTULAR, predicha AJUSTAR_CV (similitud 0.76)
- auxiliar_enfermeria × mag-1101647: esperada POSTULAR, predicha AJUSTAR_CV (similitud 0.76)
- operario_produccion × mag-1119278: esperada POSTULAR, predicha AJUSTAR_CV (similitud 0.65)
- datos_junior × mag-1105803: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.75)
- habilidad_nombrada_distinto × mag-929661: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.82)
- sin_experiencia_practicante × mag-1121305: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.52)
- operario_produccion × mag-1121512: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.75)
- auxiliar_enfermeria × mag-1120506: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.53)
- datos_junior × mag-1120022: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.71)
- sin_experiencia_practicante × mag-1008663: esperada SIN_DATOS, predicha AJUSTAR_CV (similitud 0.44)
- experiencia_implicita_y_datos_incompletos × mag-1072923: esperada SIN_DATOS, predicha CERRAR_BRECHA (similitud 0.46)
- disenadora_junior × mag-1051473: esperada SIN_DATOS, predicha AJUSTAR_CV (similitud 0.57)


## Corridas de validación sobre lo ya visto (políticas .2 y .3)

### Política 2026-11-04.2

### Mitad de ajuste — política 2026-11-04.2

- pares: 26
- exactitud del decisor: 69%
- línea base (similitud pura): 15%
- clase mayoritaria: 42%
- distribución predicha: POSTULAR 8, AJUSTAR_CV 2, CERRAR_BRECHA 2, DESCARTAR 12, SIN_DATOS 2

| acción esperada | acierto |
|---|---:|
| POSTULAR | 100% |
| AJUSTAR_CV | 17% |
| CERRAR_BRECHA | 0% |
| DESCARTAR | 100% |
| SIN_DATOS | 67% |

| esperada \ predicha | POSTULAR | AJUSTAR_CV | CERRAR_BRECHA | DESCARTAR | SIN_DATOS |
|---|---:|---:|---:|---:|---:|
| POSTULAR | 4 | 0 | 0 | 0 | 0 |
| AJUSTAR_CV | 3 | 1 | 2 | 0 | 0 |
| CERRAR_BRECHA | 1 | 1 | 0 | 0 | 0 |
| DESCARTAR | 0 | 0 | 0 | 11 | 0 |
| SIN_DATOS | 0 | 0 | 0 | 1 | 2 |

Errores:
- datos_junior × mag-1082501: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.78)
- datos_junior × mag-1090491: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.78)
- desarrollador_backend × mag-1094241: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.67)
- auxiliar_contable × mag-1121313: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.72)
- auxiliar_enfermeria × mag-1120341: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.79)
- habilidad_nombrada_distinto × mag-1115173: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.79)
- experiencia_implicita_y_datos_incompletos × mag-1108121: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.67)
- sin_experiencia_practicante × mag-1120958: esperada SIN_DATOS, predicha DESCARTAR (similitud 0.25)

### Mitad de prueba_1 — política 2026-11-04.2

- pares: 26
- exactitud del decisor: 73%
- línea base (similitud pura): 23%
- clase mayoritaria: 31%
- distribución predicha: POSTULAR 10, AJUSTAR_CV 3, CERRAR_BRECHA 2, DESCARTAR 8, SIN_DATOS 3

| acción esperada | acierto |
|---|---:|
| POSTULAR | 100% |
| AJUSTAR_CV | 25% |
| CERRAR_BRECHA | 20% |
| DESCARTAR | 100% |
| SIN_DATOS | 100% |

| esperada \ predicha | POSTULAR | AJUSTAR_CV | CERRAR_BRECHA | DESCARTAR | SIN_DATOS |
|---|---:|---:|---:|---:|---:|
| POSTULAR | 6 | 0 | 0 | 0 | 0 |
| AJUSTAR_CV | 2 | 1 | 1 | 0 | 0 |
| CERRAR_BRECHA | 2 | 2 | 1 | 0 | 0 |
| DESCARTAR | 0 | 0 | 0 | 8 | 0 |
| SIN_DATOS | 0 | 0 | 0 | 0 | 3 |

Errores:
- sin_experiencia_practicante × mag-1120768: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.70)
- habilidad_nombrada_distinto × mag-1117407: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.77)
- habilidad_nombrada_distinto × mag-1086437: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.77)
- operario_produccion × mag-1120888: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.85)
- desarrollador_backend × mag-1009047: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.78)
- auxiliar_enfermeria × mag-1121637: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.72)
- habilidad_nombrada_distinto × mag-1073362: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.71)


### Política 2026-11-04.3

### Mitad de ajuste — política 2026-11-04.3

- pares: 26
- exactitud del decisor: 69%
- línea base (similitud pura): 15%
- clase mayoritaria: 42%
- distribución predicha: POSTULAR 8, AJUSTAR_CV 2, CERRAR_BRECHA 2, DESCARTAR 12, SIN_DATOS 2

| acción esperada | acierto |
|---|---:|
| POSTULAR | 100% |
| AJUSTAR_CV | 17% |
| CERRAR_BRECHA | 0% |
| DESCARTAR | 100% |
| SIN_DATOS | 67% |

| esperada \ predicha | POSTULAR | AJUSTAR_CV | CERRAR_BRECHA | DESCARTAR | SIN_DATOS |
|---|---:|---:|---:|---:|---:|
| POSTULAR | 4 | 0 | 0 | 0 | 0 |
| AJUSTAR_CV | 3 | 1 | 2 | 0 | 0 |
| CERRAR_BRECHA | 1 | 1 | 0 | 0 | 0 |
| DESCARTAR | 0 | 0 | 0 | 11 | 0 |
| SIN_DATOS | 0 | 0 | 0 | 1 | 2 |

Errores:
- datos_junior × mag-1082501: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.78)
- datos_junior × mag-1090491: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.78)
- desarrollador_backend × mag-1094241: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.67)
- auxiliar_contable × mag-1121313: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.72)
- auxiliar_enfermeria × mag-1120341: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.79)
- habilidad_nombrada_distinto × mag-1115173: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.79)
- experiencia_implicita_y_datos_incompletos × mag-1108121: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.67)
- sin_experiencia_practicante × mag-1120958: esperada SIN_DATOS, predicha DESCARTAR (similitud 0.25)

### Mitad de prueba_1 — política 2026-11-04.3

- pares: 26
- exactitud del decisor: 73%
- línea base (similitud pura): 23%
- clase mayoritaria: 31%
- distribución predicha: POSTULAR 10, AJUSTAR_CV 3, CERRAR_BRECHA 2, DESCARTAR 8, SIN_DATOS 3

| acción esperada | acierto |
|---|---:|
| POSTULAR | 100% |
| AJUSTAR_CV | 25% |
| CERRAR_BRECHA | 20% |
| DESCARTAR | 100% |
| SIN_DATOS | 100% |

| esperada \ predicha | POSTULAR | AJUSTAR_CV | CERRAR_BRECHA | DESCARTAR | SIN_DATOS |
|---|---:|---:|---:|---:|---:|
| POSTULAR | 6 | 0 | 0 | 0 | 0 |
| AJUSTAR_CV | 2 | 1 | 1 | 0 | 0 |
| CERRAR_BRECHA | 2 | 2 | 1 | 0 | 0 |
| DESCARTAR | 0 | 0 | 0 | 8 | 0 |
| SIN_DATOS | 0 | 0 | 0 | 0 | 3 |

Errores:
- sin_experiencia_practicante × mag-1120768: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.70)
- habilidad_nombrada_distinto × mag-1117407: esperada AJUSTAR_CV, predicha CERRAR_BRECHA (similitud 0.77)
- habilidad_nombrada_distinto × mag-1086437: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.77)
- operario_produccion × mag-1120888: esperada AJUSTAR_CV, predicha POSTULAR (similitud 0.85)
- desarrollador_backend × mag-1009047: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.78)
- auxiliar_enfermeria × mag-1121637: esperada CERRAR_BRECHA, predicha POSTULAR (similitud 0.72)
- habilidad_nombrada_distinto × mag-1073362: esperada CERRAR_BRECHA, predicha AJUSTAR_CV (similitud 0.71)

