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

