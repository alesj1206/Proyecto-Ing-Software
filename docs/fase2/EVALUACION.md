# Fase 2: evaluación del decisor (mitad de ajuste)

Comando: `SCOUTLY_EMBEDDER=fastembed manage.py evaluar_decisor --mitad ajuste [--barrido]`.

Insumos:
- MiniLM real;
- **11 CVs ficticios** (`matching/evaluacion/cvs.yaml`) que pasan por el parser real;
- **32 vacantes reales** de magneto365.com con su texto completo y sin datos de contacto (`vacantes.json`);
- **26 pares de ajuste** de los 47 de `pares.yaml`. Los otros 21 se reservan para la Fase 4 y **no se han corrido**.

**Las etiquetas las propuso el builder y el equipo debe revisarlas** (spec §10).

## Resultado

| | Antes de calibrar | Después de calibrar |
|---|---|---|
| Exactitud del decisor | 54% | **73%** |
| Exactitud de la línea base (similitud pura) | 19% | 19% |
| Acción más frecuente | DESCARTAR 42% | DESCARTAR 42% |

Distribución final: POSTULAR 7, AJUSTAR_CV 3, CERRAR_BRECHA 3, DESCARTAR 11, SIN_DATOS 2.

**Anti-objetivos de §2 sobre la mitad de ajuste:**
- exactitud ≥ 70%: se cumple;
- ninguna acción por encima del 80%: se cumple;
- superar la línea base: se cumple.

Es la mitad con la que se calibró, así que el número es **optimista**. El número que cuenta lo da la mitad de prueba,
en la Fase 4.

## Qué se cambió, y por qué (todo sale del diagnóstico de los errores de la mitad de ajuste)

1. **Los requisitos que solo piden años de experiencia** ("Experiencia: mínimo 1–2 años") no se miden por similitud.
   Ya los evalúa la restricción de experiencia.
2. **Competencias blandas y condiciones** ("Trabajo en equipo", "Disponibilidad para rotar turnos", "Esquema de
   vacunación") **no cuentan como brecha.** Casi nunca están en un CV y no se cierran estudiando. Eran 5 de los 12
   errores: mandaban a CERRAR_BRECHA a candidatos que debían postular.
3. **Las sub-viñetas "o"** dentro de una línea ("Conocimientos: o Power BI… o Python y SQL") se separan en
   requisitos distintos.
4. **τ_alto pasa de 0,50 a 0,45** (`Politica.version = "2026-11-02.2"`). Es la mejor combinación del barrido
   (τ_alto ∈ {0,45, 0,50, 0,55}, τ_bajo ∈ {0,35, 0,40}, τ_relevancia ∈ {0,35, 0,40, 0,45}). τ_bajo = 0,40 y
   τ_relevancia = 0,40 no cambian, porque τ_relevancia no movió la exactitud dentro de la grilla.
5. **Una etiqueta se corrigió por un error de hecho:** la vacante mag-1094241 también es en Barranquilla. La
   corrección queda escrita en `pares.yaml`.

## Errores que quedan (7 de 26)

| Par | Esperada | Predicha | Causa |
|---|---|---|---|
| datos_junior × mag-1082501 | AJUSTAR_CV | POSTULAR (con nota) | Discutible: le falta "JOIN" y el decisor dice "menciona que puedes aprenderlo" |
| datos_junior × mag-1090491 | CERRAR_BRECHA | POSTULAR | "Power BI, Power Apps y Power Automate" sigue siendo un solo requisito: Power BI lo cubre todo |
| auxiliar_contable × mag-1121313 | AJUSTAR_CV | CERRAR_BRECHA | "Demostrar manejo de software contable" no se parece lo suficiente a "World Office y Siigo" |
| disenadora_junior × mag-1120969 | DESCARTAR | AJUSTAR_CV | No se valida que la práctica exija ser estudiante (la formación no se mide; límite conocido) |
| habilidad_nombrada_distinto × mag-1115173 | AJUSTAR_CV | CERRAR_BRECHA | "Hojas de cálculo" no llega a "Excel avanzado" (el caso difícil a propósito) |
| experiencia_implicita × mag-1108121 | AJUSTAR_CV | POSTULAR | El CV implícito alcanza a cubrir más de lo que una persona daría por cubierto |
| sin_experiencia × mag-1120958 | SIN_DATOS | DESCARTAR | La vacante no es relevante para su perfil (similitud 0,25), así que no se muestra. Probablemente la etiqueta era la equivocada |

**Para la Fase 4:**
- correr la mitad de prueba;
- validar la formación de las prácticas (pedir que el candidato sea estudiante);
- separar las enumeraciones de herramientas ("Power BI, Power Apps y Power Automate").
