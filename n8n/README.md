# HU-06 + HU-11 — workflow de n8n: ranking diario + notificación de matches nuevos

El documento del reto (Magneto, "Idea 4: Workflow con n8n") pide que n8n
orqueste **ingesta, normalización, scoring y notificación** como pasos
explícitos — no un solo paso que hace todo por dentro. Este workflow tiene
dos nodos HTTP Request reales y separados para eso, cada uno verificable
por su cuenta en el panel de ejecuciones de n8n:

```
Cada día a las 6am  →  1. Recalcular matches  →  2. Generar notificaciones
(Schedule Trigger)        (scoring, HU-06)          (HU-11)
```

**Paso 1 — scoring** (`POST /api/recalcular-matches`): recorre todos los
perfiles con CV cargado, recalcula su score contra todas las vacantes
(`vacantes/scoring.py::recalcular_matches_todos`) y reemplaza las filas de
`MatchDiario` del día. El dashboard lee de ahí; si nadie ha corrido el
workflow hoy todavía, `dashboard_view` lo calcula y lo guarda al vuelo para
esa persona, así que el ranking nunca se ve vacío — pero la fuente de
verdad pasa a ser el batch, no cada request.

**Paso 2 — notificación** (`POST /api/generar-notificaciones`): corre
*después* del paso 1 porque necesita comparar el top-3 de hoy (que el paso
1 acaba de calcular) contra el de ayer. Por cada vacante que entró de
nueva al top del candidato, crea una `Notificacion` (siempre visible en la
campana de la app) y trata de enviarla por el canal que el candidato eligió
en `/expectativas` — correo (`vacantes/notificaciones.py::enviar_email`,
backend de consola de Django por defecto — se ve en la terminal donde
corre `runserver`, sin configurar nada) o WhatsApp
(`enviar_whatsapp`, vía Twilio; sin `TWILIO_*` configurado, se queda solo
en la app). Ver `vacantes/notificaciones.py` para el detalle.

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
6. (2026-10-05) Se agregó el segundo nodo (HU-11) con el mismo método —
   `PATCH /rest/workflows/{id}` por API, sin tocar el navegador — y se
   volvió a disparar una ejecución real: el log de Django mostró los dos
   POST en cadena (`/api/recalcular-matches` seguido de
   `/api/generar-notificaciones`), confirmando que n8n corre los dos pasos
   en el orden correcto.

Si quieres verlo en la interfaz (para capturas del informe, por ejemplo):
abre http://localhost:5678 e inicia sesión con las credenciales de
`~/n8n-vacantes/.env`. El workflow se llama **"Scoutly - Matches diarios
(HU-06 + HU-11)"**, debe aparecer **Active**, y al abrirlo se ven los 3
nodos en cadena (trigger → scoring → notificaciones).

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

Dentro de n8n, con el workflow abierto: botón **Test workflow** (ejecuta los
dos nodos HTTP Request en cadena, de inmediato). O desde la terminal, sin
n8n (en orden — el segundo necesita que el primero ya haya corrido hoy):

```bash
curl -X POST -H "X-Scoutly-Token: dev-local-token-change-me" \
  http://localhost:8000/api/recalcular-matches

curl -X POST -H "X-Scoutly-Token: dev-local-token-change-me" \
  http://localhost:8000/api/generar-notificaciones

# o, sin levantar n8n ni el servidor, directo en Django:
.venv/bin/python manage.py recalcular_matches
.venv/bin/python manage.py shell -c "from vacantes.notificaciones import generar_notificaciones_nuevos_matches; print(generar_notificaciones_nuevos_matches())"
```

## Evidencia para el informe

Captura de: el workflow activo en n8n, una ejecución exitosa en el panel
de ejecuciones (ícono ✓ verde), y el dashboard de Scoutly mostrando
"Matches de hoy" con los porcentajes que vienen de esa ejecución.
