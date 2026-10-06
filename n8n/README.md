# HU-06 + HU-11 — workflow de n8n: ingesta real + ranking diario + notificación

El documento del reto (Magneto, "Idea 4: Workflow con n8n") pide que n8n
orqueste **ingesta, normalización, scoring y notificación** como pasos
explícitos — no un solo paso que hace todo por dentro. Este workflow tiene
tres nodos HTTP Request reales y separados para eso, cada uno verificable
por su cuenta en el panel de ejecuciones de n8n:

```
Cada día       0. Importar vacantes   1. Recalcular matches   2. Generar
a las 6am  →   (ingesta real de   →   (scoring, HU-06)    →   notificaciones
(Schedule         Magneto)                                       (HU-11)
 Trigger)
```

**Paso 0 — ingesta** (`POST /api/importar-vacantes`): corre el scraper real
de magneto365.com (`vacantes/management/commands/scrape_magneto.py`, vía
Playwright + Chrome) y siembra el resultado
(`vacantes/management/commands/seed_vacantes.py`) — así el scoring del
paso 1 ya ve vacantes frescas el mismo día. Usa ids estables por contenido
(`mag-<hash(título+empresa)>`, no por posición en la corrida): la misma
publicación real de Magneto siempre mapea al mismo id aunque el orden de
los resultados cambie de un día a otro, para que una `Postulacion` /
`MatchDiario` / `Notificacion` que ya apunta a esa vacante no quede pegada
a una vacante distinta tras la siguiente corrida. **Es el paso lento**: un
navegador real con esperas entre búsquedas, puede tardar varios minutos
(~3-4 min en esta máquina, a veces más si hay otras cosas corriendo) — por
eso su nodo en n8n tiene un timeout de 10 min (`600000`), muy por encima de
los 15s de los otros dos, que solo hacen trabajo de base de datos.

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
campana de la app) y trata de mandarla por correo al que trae el CV
(`vacantes/notificaciones.py::enviar_email`). Por defecto usa el backend
de consola de Django — se ve en la terminal donde corre `runserver`, sin
configurar nada —, pero con SMTP real configurado (`DJANGO_EMAIL_BACKEND`
+ `EMAIL_HOST*` en `settings.py`) llega de verdad a la bandeja de entrada.
(Se evaluó WhatsApp vía Twilio y se descartó: exige que cada candidato
haga un opt-in manual por WhatsApp antes de poder recibir nada — el
correo no le pide ningún paso extra.) Ver `vacantes/notificaciones.py`
para el detalle.

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
7. (2026-10-05) Se agregó el nodo de ingesta (paso 0) con el mismo método.
   Primer intento con timeout de 4 min: el scraping real tardó un poco más
   (~4:20 min esa corrida) y n8n marcó el nodo como fallido por timeout del
   lado del cliente — aunque Django sí había terminado el trabajo del lado
   del servidor (el POST completó con 200 igual, solo que después de que
   n8n ya se había rendido). Se subió el timeout del nodo a 10 min
   (`600000`) y se repitió la ejecución: los 3 nodos corrieron en cadena
   sin error, confirmado en el log de Django (`/api/importar-vacantes` →
   `/api/recalcular-matches` → `/api/generar-notificaciones`, los tres 200,
   mismo segundo).

Si quieres verlo en la interfaz (para capturas del informe, por ejemplo):
abre http://localhost:5678 e inicia sesión con las credenciales de
`~/n8n-vacantes/.env`. El workflow se llama **"Scoutly - Matches diarios
(HU-06 + HU-11, ingesta real)"**, debe aparecer **Active**, y al abrirlo se
ven los 4 nodos en cadena (trigger → ingesta → scoring → notificaciones).

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
tres nodos HTTP Request en cadena, de inmediato — cuenta con que el primero
por sí solo puede tardar varios minutos). O desde la terminal, sin n8n (en
orden — cada uno depende de que el anterior ya haya corrido):

```bash
curl -X POST -H "X-Scoutly-Token: dev-local-token-change-me" \
  http://localhost:8000/api/importar-vacantes   # lento: scraping real

curl -X POST -H "X-Scoutly-Token: dev-local-token-change-me" \
  http://localhost:8000/api/recalcular-matches

curl -X POST -H "X-Scoutly-Token: dev-local-token-change-me" \
  http://localhost:8000/api/generar-notificaciones

# o, sin levantar n8n ni el servidor, directo en Django:
.venv/bin/python manage.py scrape_magneto && .venv/bin/python manage.py seed_vacantes
.venv/bin/python manage.py recalcular_matches
.venv/bin/python manage.py shell -c "from vacantes.notificaciones import generar_notificaciones_nuevos_matches; print(generar_notificaciones_nuevos_matches())"
```

## Evidencia para el informe

Captura de: el workflow activo en n8n, una ejecución exitosa en el panel
de ejecuciones (ícono ✓ verde), y el dashboard de Scoutly mostrando
"Matches de hoy" con los porcentajes que vienen de esa ejecución.
