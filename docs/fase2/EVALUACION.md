# Fase 2: evaluación del decisor (mitad de ajuste) — RESULTADO PARCIAL

`SCOUTLY_EMBEDDER=fastembed manage.py evaluar_decisor --mitad ajuste --barrido`, con MiniLM real, 11 CVs ficticios
(que pasan por el parser real), 32 vacantes reales y 26 pares de ajuste. Las etiquetas están pendientes de revisión
por el equipo.

| Métrica | Valor | Objetivo (spec §2) |
|---|---|---|
| Exactitud del decisor (umbrales actuales 0,50 / 0,40 / 0,40) | **54%** | ≥ 70% → **NO SE CUMPLE** |
| Exactitud de la línea base (similitud pura) | 19% | El decisor debe superarla → se cumple |
| Mejor combinación del barrido (τ_alto 0,45) | 58% | — |
| Distribución | CERRAR_BRECHA 9, DESCARTAR 11, POSTULAR 3, SIN_DATOS 2, AJUSTAR_CV 1 | Ninguna > 80% → se cumple |

**Errores dominantes (sin corregir todavía):** sobra CERRAR_BRECHA donde una persona diría POSTULAR o AJUSTAR_CV (7 de 12
errores). Hipótesis por revisar:
- requisitos largos que agrupan varias habilidades y quedan como faltantes;
- τ_bajo demasiado alto para "parcial";
- la ubicación no reconoce las áreas metropolitanas;
- la formación de practicante no se valida.

**Pendiente:** diagnosticar los errores sobre la mitad de ajuste, ajustar y volver a medir. La mitad de prueba no se ha
tocado.
