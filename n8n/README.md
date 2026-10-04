# HU-06 — workflow de n8n: ranking diario de "Matches de hoy"

Este workflow reemplaza el cálculo del ranking "en vivo" por uno que corre
automáticamente una vez al día (criterio de aceptación de HU-06) y queda
persistido en `MatchDiario` (`vacantes/models.py`). El dashboard lee de ahí;
si nadie ha corrido el workflow hoy todavía, `dashboard_view` lo calcula y
lo guarda al vuelo para esa persona, así que el ranking nunca se ve vacío
— pero la fuente de verdad pasa a ser el batch, no cada request.

## Qué hace el workflow

```
Cada día a las 6am  →  POST /api/recalcular-matches
(Schedule Trigger)      (HTTP Request, header X-Scoutly-Token)
```

El endpoint recorre todos los perfiles con CV cargado, recalcula su score
contra todas las vacantes (`vacantes/scoring.py::recalcular_matches_todos`)
y reemplaza las filas de `MatchDiario` del día. Devuelve un resumen JSON
(`perfiles_procesados`, `matches_guardados`).

## Cómo importarlo (pasos manuales — esto sí hay que hacerlo en la UI)

La cuenta owner de esta instancia de n8n ya se creó hace semanas desde el
navegador (ver `~/n8n-vacantes/README.md`) — no tengo esas credenciales ni
puedo crear/usar una sesión por fuera del navegador, así que estos tres
pasos los tienes que hacer tú:

1. Con los contenedores corriendo (`podman start postgres n8n` desde
   `~/n8n-vacantes`, si no están arriba), abre http://localhost:5678 e
   inicia sesión.
2. Menú (⋮) → **Import from File** → selecciona este archivo
   (`workflow-matches-diarios.json`).
3. Abre el nodo **Recalcular matches (Scoutly)** y confirma el valor del
   header `X-Scoutly-Token` — por defecto trae `dev-local-token-change-me`,
   que coincide con el valor por defecto de `N8N_SCORING_TOKEN` en
   `scoutly/settings.py`. Si cambias esa variable de entorno en Django,
   cámbiala aquí también.
4. **Activa** el workflow (toggle arriba a la derecha).

## Para que el POST llegue a Django

n8n corre en un contenedor Podman; Django corre en el host. Ya verifiqué
la conectividad real (`host.containers.internal` resuelve al host desde
dentro del contenedor `n8n` en esta máquina) — para que el request llegue,
Django tiene que escuchar en todas las interfaces, no solo loopback:

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

(Con `127.0.0.1:8000` el contenedor no puede alcanzarlo — probado.)

## Probar sin esperar al Schedule Trigger

Dentro de n8n, con el workflow abierto: botón **Test workflow** (ejecuta el
nodo HTTP Request una vez, de inmediato). O desde la terminal, sin n8n:

```bash
curl -X POST -H "X-Scoutly-Token: dev-local-token-change-me" \
  http://localhost:8000/api/recalcular-matches

# o, sin levantar n8n ni el servidor, directo en Django:
.venv/bin/python manage.py recalcular_matches
```

## Evidencia para el informe

Captura de: el workflow activo en n8n, una ejecución exitosa en el panel
de ejecuciones (ícono ✓ verde), y el dashboard de Scoutly mostrando
"Matches de hoy" con los porcentajes que vienen de esa ejecución.
