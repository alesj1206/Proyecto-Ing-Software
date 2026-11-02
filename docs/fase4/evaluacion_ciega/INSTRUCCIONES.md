# Evaluación ciega con reclutadores (spec §13.3)

Gracias por ayudarnos. Te tomará unos 20 minutos.

## Qué vas a ver

En la carpeta `paquetes/` hay un archivo por candidato (`paquete_1.md`, `paquete_2.md`, …). Los candidatos son
**ficticios**: no corresponden a ninguna persona real. Cada paquete trae:

1. **El CV del candidato** (experiencia, educación y habilidades).
2. **Pregunta 1:** dos listas de 5 vacantes reales de magneto365.com, *Lista A* y *Lista B*. ¿Cuál le recomendarías a
   este candidato para enviar su hoja de vida esta semana?
3. **Pregunta 2** (solo en algunos paquetes): una vacante y dos versiones del CV, *CV 1* y *CV 2*. ¿Cuál pasaría tu
   primer filtro para esa vacante?

No te decimos cómo se armó cada opción, a propósito: queremos tu criterio de reclutador, no el nuestro. Si las dos
opciones te parecen iguales, elige la que preferirías por poco.

## Cómo responder

Llena un archivo `respuestas.csv` con esta cabecera exacta y una fila por pregunta:

```csv
reclutador,paquete,pregunta,eleccion
ana_r,1,lista,A
ana_r,1,cv,2
ana_r,2,lista,B
```

- `reclutador`: un alias tuyo, sin tu nombre real.
- `paquete`: el número del archivo.
- `pregunta`: `lista` para la pregunta 1, `cv` para la pregunta 2.
- `eleccion`: `A` o `B` en la pregunta 1; `1` o `2` en la pregunta 2.

Envíale el CSV al equipo. No guardamos nada más que eso.

## Para el equipo (después de recibir las respuestas)

```bash
.venv/bin/python manage.py evaluacion_ciega tabular --respuestas respuestas.csv
```

La clave que dice qué es cada opción está en `~/.scoutly/clave_evaluacion_ciega.json`, **fuera del repositorio**, y no
se abre antes de tabular. El resultado dice en qué porcentaje de las veces se prefirió la lista del decisor y el CV con
las sugerencias del Taller, en total y por reclutador. Si no se consiguen reclutadores, el informe reporta solo el set
de evaluación (§13.3).

Los paquetes se regeneran con `manage.py evaluacion_ciega preparar`; con la misma semilla salen idénticos.
