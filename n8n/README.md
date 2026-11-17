# Workflow de n8n: ingesta, decisión y notificación (Scoutly v3)

El reto de Magneto ("Idea 4: Workflow con n8n") pide que n8n orqueste **ingesta, scoring y notificación** como pasos
explícitos. El workflow `workflow-matches-diarios.json` tiene tres nodos HTTP Request en cadena, cada uno verificable
por su cuenta en el panel de ejecuciones de n8n. Entre un paso y el siguiente, n8n consulta `GET /api/estado` y espera
a que el anterior termine:

```
Cada día     0. Importar vacantes      espera: ingesta      1. Decidir            espera: cola      2. Generar notificaciones
a las 6am →  POST /api/importar-  →    GET /api/estado  →   POST /api/decidir →   GET /api/estado → POST /api/generar-notificaciones
             vacantes (202 / 409)      cada 30 s            (202: encola)         cada 15 s         (200: resumen)
```

Todos llevan el header `X-Scoutly-Token`, que debe coincidir con `N8N_SCORING_TOKEN` del `.env`. Sin `DEBUG`, el
token de desarrollo se rechaza.

## Cómo espera n8n

`GET /api/estado` responde `{"ingesta_en_curso": true|false, "ultimo_resumen": "...", "cola": N, "corridas": [...]}`.
`corridas` trae las 5 últimas filas de la bitácora (tabla `Corrida`: paso, inicio, fin, ok y resumen), que también se
ve completa en `/admin`. Con esa respuesta:

- después del paso 0, n8n repite la consulta cada 30 s mientras `ingesta_en_curso` sea `true`. Una ingesta con más de
  30 minutos se da por colgada y cuenta como terminada;
- después del paso 1, la repite cada 15 s mientras `cola` (perfiles sin decidir) sea mayor que 0.

La respuesta de cada consulta queda en el panel de ejecuciones, con el resumen de la ingesta (creadas, actualizadas,
errores). Si el batch no está corriendo, la cola nunca se vacía: el workflow se corta solo a la hora
(`executionTimeout`) y la ejecución aparece como fallida.

## Qué hace cada paso

**Paso 0, ingesta** (`POST /api/importar-vacantes`):
- abre la página de detalle de cada vacante de magneto365.com (Playwright) y guarda el texto completo, los
  requisitos y las restricciones;
- responde **202** de inmediato porque corre en un hilo, o **409** si ya hay una ingesta en curso;
- acepta en el cuerpo `{"terminos": [...], "por_termino": N}`: hasta 10 términos de 60 caracteres y entre 1 y 20 por
  término; si la entrada es inválida responde 400;
- al terminar **encola una decisión por cada perfil**, así las vacantes nuevas llegan al batch aunque n8n ya haya
  pasado al siguiente paso.

**Paso 1, decisión** (`POST /api/decidir`):
- solo encola (**202**), porque la web nunca carga modelos;
- el que decide es `manage.py decidir --escuchar`, que **debe estar corriendo** en otra terminal: embebe las vacantes
  nuevas y, por cada perfil, preselecciona sus vacantes relevantes (hasta 3.000), mide la cobertura y aplica la
  política;
- al terminar un lote, el mismo batch **envía las notificaciones pendientes**.

**Paso 2, notificaciones** (`POST /api/generar-notificaciones`):
- crea una `Notificacion` por cada vacante que pasó a POSTULAR en las últimas 36 horas y aún no se avisó;
- manda los correos según la preferencia de cada candidato: un resumen diario (por defecto), uno por vacante (hasta N
  al día, de 1 a 10) o ninguno;
- es idempotente: llamarlo dos veces no duplica avisos ni correos. Sirve de red de seguridad si el batch no notificó.

El correo va a la cuenta verificada del candidato, nunca al que aparece en el CV. Por defecto usa el backend de consola
de Django (se ve en la terminal de `runserver`); con SMTP en el `.env` (`DJANGO_EMAIL_BACKEND` y `EMAIL_*`) llega de
verdad.

## Para que el POST llegue a Django

n8n corre en un contenedor Podman y Django en el host. `host.containers.internal` resuelve al host desde el contenedor,
pero Django tiene que escuchar en todas las interfaces:

```bash
.venv/bin/python manage.py runserver --insecure 0.0.0.0:8000
.venv/bin/python manage.py decidir --escuchar     # en otra terminal
```

Con `127.0.0.1:8000` el contenedor no lo alcanza.

Si usas los servicios de `infra/systemd/`, el batch ya está corriendo y la web escucha solo en `127.0.0.1:8000`. Para n8n,
detén la web (`systemctl --user stop scoutly-web`) y usa el `runserver` de arriba mientras pruebas el flujo. Para dejarla
fija, agrega la puerta de enlace de Podman con `systemctl --user edit scoutly-web`.

> **Cuidado:** `0.0.0.0` expone el servidor de desarrollo a toda la red (Wi-Fi compartida incluida). Úsalo solo en
> una red de confianza, y **nunca con `DJANGO_DEBUG=true`**: una página de error mostraría datos del CV. Es más seguro
> escuchar solo en la puerta de enlace de Podman (`podman network inspect podman` da la IP, por ejemplo
> `runserver --insecure 10.88.0.1:8000`).

## Importar el workflow

En n8n: Menú (⋮) → **Import from File** → `workflow-matches-diarios.json`. Luego se pone el token en el header de los
cinco nodos HTTP y se activa con el interruptor. Los nodos responden en segundos (timeout de 15 s; el de notificaciones, 60 s).

## Probar sin esperar a las 6 a. m.

Dentro de n8n, el botón **Test workflow** corre el flujo completo, con sus esperas. Desde la terminal:

```bash
TOKEN=...   # el de N8N_SCORING_TOKEN
curl -X POST -H "X-Scoutly-Token: $TOKEN" http://localhost:8000/api/importar-vacantes
curl -X POST -H "X-Scoutly-Token: $TOKEN" http://localhost:8000/api/decidir
curl -X POST -H "X-Scoutly-Token: $TOKEN" http://localhost:8000/api/generar-notificaciones
curl -H "X-Scoutly-Token: $TOKEN" http://localhost:8000/api/estado   # ¿terminó la ingesta? ¿cuántos perfiles faltan?

# o sin servidor, directo en Django:
.venv/bin/python manage.py ingerir_vacantes --fuente magneto
.venv/bin/python manage.py decidir --todos
```

El contrato de los cuatro endpoints (OpenAPI 3.1) está en `api/openapi.yaml`.

La verificación de punta a punta de la Fase 4, con el log de una ejecución real, está en `docs/fase4/VERIFICACION.md`.

## Historia

En v2 (Sprint 2) el paso 1 era `POST /api/recalcular-matches` y calculaba un ranking por similitud dentro de la
petición. Las observaciones de esa época (por ejemplo, el ajuste del timeout de la ingesta a 10 minutos el 2026-10-05)
están en el historial de git de este archivo.
