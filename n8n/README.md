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

## Estado: ya instalado y probado (2026-10-04)

La instancia de n8n se recreó desde cero (la anterior, de hace 7 semanas,
no tenía credenciales accesibles) y el workflow quedó importado y
**activo** vía la API REST de n8n, sin pasos manuales en el navegador:

1. Se recreó el contenedor `n8n` con un volumen `n8n_data` nuevo y vacío.
2. Con la instancia en blanco, `POST /rest/owner/setup` (endpoint que solo
   responde mientras no exista owner) creó la cuenta — ver credenciales en
   `~/n8n-vacantes/.env` (`N8N_OWNER_EMAIL` / `N8N_OWNER_PASSWORD`; solo
   válidas para `localhost:5678` en esta máquina).
3. `POST /rest/login` con esas credenciales dio una cookie de sesión.
4. `POST /rest/workflows` (con la cookie) creó el workflow de este archivo;
   `POST /rest/workflows/{id}/activate` lo activó.
5. Se disparó una ejecución manual real
   (`POST /rest/workflows/{id}/run`) para confirmarlo de punta a punta: el
   log de Django mostró `POST /api/recalcular-matches HTTP/1.1 200` viniendo
   del contenedor, y `MatchDiario` quedó actualizado.

Si quieres verlo en la interfaz (para capturas del informe, por ejemplo):
abre http://localhost:5678 e inicia sesión con las credenciales de
`~/n8n-vacantes/.env`. El workflow se llama **"Scoutly - Matches diarios
(HU-06)"** y debe aparecer **Active**.

Para volver a importar manualmente desde cero (si recreas la instancia de
nuevo): Menú (⋮) → **Import from File** → este archivo
(`workflow-matches-diarios.json`), confirmar el header `X-Scoutly-Token`
en el nodo HTTP Request (debe coincidir con `N8N_SCORING_TOKEN` en
`scoutly/settings.py`), y activar con el toggle.

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
