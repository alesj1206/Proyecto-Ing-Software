# Scoutly

Plataforma de vacantes y matching para candidatos, con la identidad visual
de Magneto. Construida en **Python + Django**.

> La entrega congelada del Sprint 1 vive en [`entregas/sprint-1/`](entregas/sprint-1/)
> y en el tag de git `sprint-1`. Este README documenta el estado actual
> (Sprint 2 en curso); no lo sobrescribe, lo continúa.

## Sprint 2 (en curso)

Punto de partida: todo lo del Sprint 1, sin remover alcance.

| HU | Historia | Prioridad | Estado |
|----|----------|-----------|--------|
| HU-02 | Completar mis expectativas laborales | Should-have | ✅ Hecho — `/expectativas`, pondera hasta 15% del score de match |
| HU-06 | Ranking diario vía workflow n8n automático | Must-have | ✅ Hecho — ver [`n8n/README.md`](n8n/README.md) |
| HU-07 | Entender por qué me recomendaron una vacante | Should-have | ✅ Hecho — sección "¿Por qué te la recomendamos?" en el detalle |
| HU-08 | Postularme (simulado) a una vacante | Should-have | ✅ Hecho — botón "Postularme" en el detalle |
| HU-10 | Tablero de estado de cada proceso | Should-have | ✅ Hecho — `/postulaciones`, Kanban de 4 columnas |

**HU-06 — cómo quedó armado.** El scoring ya no se calcula en cada
request: `vacantes/scoring.py::recalcular_matches_todos()` recorre todos
los perfiles con CV cargado y persiste el ranking del día en el modelo
`MatchDiario`. Lo dispara `POST /api/recalcular-matches` (protegido por el
header `X-Scoutly-Token`, ver `N8N_SCORING_TOKEN` en `settings.py`), que es
exactamente lo que llama el workflow de n8n (`Schedule Trigger` diario →
`HTTP Request`) descrito en [`n8n/README.md`](n8n/README.md) — **ya
instalado, activo y probado con una ejecución real** (ver ese README para
el detalle de cómo se armó todo por API, sin tocar el navegador). El
dashboard lee de `MatchDiario`; si el workflow todavía no
corrió hoy para alguien, se calcula y persiste al vuelo en ese momento
(para que nunca se vea vacío), pero la fuente de verdad es el batch diario.
El ranking también se recalcula de inmediato cuando el candidato actualiza
su CV o sus expectativas (HU-02), sin esperar al siguiente ciclo del
workflow — así cumple el tercer criterio de aceptación de la historia.

*Nota de alcance:* existe una infraestructura de n8n+Postgres más antigua
en `~/n8n-vacantes/` (fuera de este repo), de cuando el equipo evaluó
scrapear Magneto directamente con un pipeline HTTP→HTML→Postgres antes de
pivotar a Django. Se reutilizan sus contenedores de n8n (ya tenían cuenta
creada), pero el workflow de HU-06 apunta al Django actual, no a ese
esquema de Postgres viejo — ver la nota en ese README.

**HU-07 — cómo quedó armado.** `vacantes/matching.py::explicar_match()`
genera las razones con los mismos helpers que usa `compute_match()` para
calcular el score (`_modalidad_coincide`, `_salario_coincide`,
`_ubicacion_coincide`, coincidencia de habilidades) — nunca puede mostrar
una razón que el número no respalde, porque no hay una segunda copia de la
lógica. Si solo hay una razón calculable, se agrega un resumen del % de
match para cumplir el mínimo de 2 que pide la historia.

**HU-08 / HU-10 — cómo quedaron armadas.** Un único modelo,
`vacantes/models.py::Postulacion`, es a la vez la "evidencia con
timestamp" de HU-08 (`fecha_aplicacion`, `auto_now_add`) y la tarjeta del
tablero Kanban de HU-10 (campo `estado`, una de las 4 columnas mínimas).
Postularse es idempotente (`get_or_create`): si ya habías aplicado, el
botón se reemplaza por un badge con la fecha y el estado actual en vez de
duplicar la fila. El estado lo mueve el propio candidato desde
`/postulaciones` — "simulado" significa que no hay bandeja del lado de la
empresa todavía, eso queda fuera de este sprint.

**Identidad visual recalibrada contra Magneto real** (ver sección de abajo)
— esta fue la corrección explícita de la profesora sobre el Sprint 1: la
paleta y el chrome no se sentían como una extensión de Magneto. Se ajustó
`templates/base.html` (barra utilitaria + franja de marca) y
`static/css/scoutly.css` (tokens de color) en todas las pantallas
existentes, sin tocar el flujo ni las rutas del Sprint 1.

## Matching: 5 criterios + explicación por IA (rediseño Sprint 2)

El score de compatibilidad ya no es solo habilidades: son 5 criterios
independientes, cada uno con su propio peso, calculados en
`vacantes/matching.py::evaluar_criterios()`:

| Criterio | Peso | Cómo se mide |
|---|---|---|
| Habilidades | 40% | % de los requisitos de la vacante presentes en el CV |
| Experiencia | 20% | años declarados ÷ años mínimos que pide la vacante |
| Salario | 15% | qué tan cerca está el salario ofrecido del mínimo esperado |
| Modalidad | 15% | afinidad por categoría — exacta 100%, cualquier combinación con Híbrido 50% (es un punto medio real), solo Remoto↔Presencial (únicos opuestos) 0% |
| Ubicación | 10% | coincidencia de ciudad |

Un criterio sin datos suficientes (el candidato no declaró esa
expectativa, o la vacante no exige una antigüedad mínima) se excluye y su
peso se reparte proporcionalmente entre los demás — Habilidades nunca se
excluye.

Cada criterio que aplica trae una **explicación específica generada por
IA** (Groq, modelo gratuito `qwen/qwen3.8-27b`, `GROQ_API_KEY` en
`settings.py`), cacheada en `ExplicacionCriterio` — nunca se llama la API
en cada vista de página, solo cuando el score de ese criterio cambió
desde la última vez. Sin `GROQ_API_KEY` configurada, cae a un texto de
respaldo derivado de los mismos datos reales (nunca genérico). Visible en
el detalle de cada vacante, bajo "Desglose de compatibilidad".

## Vacantes reales de Magneto

Las 9 vacantes mock del Sprint 1 (`vacantes/fixtures/vacantes_raw.json`)
siguen ahí, pero el dataset se amplió con **16 vacantes reales**
importadas en vivo de magneto365.com
(`vacantes/fixtures/vacantes_magneto.json`, ids `mag-001`…`mag-016`) —
título, empresa, ubicación, modalidad, salario, experiencia mínima,
descripción y requisitos son datos reales, no inventados.

Cómo se obtuvieron: `vacantes/management/commands/scrape_magneto.py` usa
Playwright + Chrome (la búsqueda de Magneto es una SPA — el HTML que
responde el servidor no trae las vacantes, se cargan por JavaScript, así
que un scraper con `requests` no sirve). El comando busca por término
("desarrollador", "devops", "QA software", ...), abre el detalle de cada
resultado y lee el panel renderizado — de ahí salen `Requisitos para
aplicar a la vacante` (experiencia/educación), `Salario`, `Ubicación`, la
descripción completa, y la sección `Habilidades` de cada oferta real.
Esas habilidades reales se cruzan contra `vacantes/skills.py`
(`HABILIDADES_CONOCIDAS`, ampliado con términos reales encontrados en el
import: java, spring boot, azure, power bi, machine learning, ci/cd, n8n,
sap, canva, photoshop, illustrator) para construir `requisitos` — un
requisito que no esté en ese vocabulario no podría hacer match con
ningún CV sin importar qué tan real sea el dato.

El `robots.txt` de Magneto permite expresamente crawling (nombra bots de
IA en su lista de user-agents permitidos) y no bloquea las rutas de
`/trabajos/`; solo bloquea URLs con query string, que este comando nunca
usa (toda la navegación es por interacción con la SPA). Aun así es una
importación puntual y acotada (`--por-termino`), no un scraper continuo.

```bash
python manage.py scrape_magneto                                    # usa los términos por defecto
python manage.py scrape_magneto --terminos "desarrollador,devops" --por-termino 5
python manage.py seed_vacantes                                     # carga el resultado a la base de datos
```

## Sprint 1

Cubre las siguientes historias de usuario (deben tener, prioridad alta):

| HU | Historia | Prioridad | Talla | Dificultad | Qué se hizo |
|----|----------|-----------|-------|------------|-------------|
| HU-13 | Registro e inicio de sesión, con rutas protegidas | Alta | M | Media | Modelo `Usuario` custom (login por email), sesión de 30 días, rutas protegidas con `@login_required`. |
| HU-01 | Carga de CV (PDF) para crear el perfil del candidato | Alta | XL | Alta | Parser heurístico (`cv_parser.py`) con `pypdf`: nombre, correo, habilidades, experiencia y educación; lo no detectado queda "Pendiente". |
| HU-04 | Listado de vacantes disponibles | Alta | S | Baja | Listado en el dashboard desde `Vacante`, sembrado con `seed_vacantes` (dedup y validación de datos rotos). |
| HU-06 | Ranking diario de vacantes recomendadas, "Matches de hoy" | Alta | L | Alta | Scoring por coincidencia de palabras clave (`matching.py`) entre habilidades del perfil y requisitos; top 3 en dashboard. |
| HU-05 | Detalle de una vacante (`/vacantes/<id>`) | Alta | M | Media | Vista pública con anillo de compatibilidad y checklist de requisitos cumplidos/faltantes cuando hay sesión. |

### Flujo de la aplicación

1. Primera visita → `/login` (registro o inicio de sesión, en la misma página).
2. Registro exitoso → `/onboarding`, "Carga tu CV para empezar" (HU-01),
   y de ahí a `/perfil` para ver lo que se extrajo del documento.
3. Inicio de sesión de un usuario existente → directo a `/dashboard`.
4. `/dashboard` (protegido) → una sola vista con "Matches de hoy" (HU-06)
   y el listado general de vacantes (HU-04). Si todavía no hay CV cargado,
   se muestra un banner para cargarlo, en vez de quedar vacío.
5. El clic en cualquier vacante, desde matches o desde el listado, lleva
   siempre al mismo componente de detalle: `/vacantes/<id>` (HU-05). Es una
   página pública: si hay sesión y perfil, además muestra el anillo de
   compatibilidad y el checklist de requisitos cumplidos/faltantes.
6. `/perfil` (protegido) muestra el nombre, contacto, experiencia,
   educación y habilidades extraídos del CV, con badges "Pendiente" para lo
   que no se pudo detectar, y permite volver a cargar el PDF en cualquier
   momento.

Las rutas `/dashboard`, `/onboarding` y `/perfil` están protegidas con
`@login_required`: sin sesión activa, Django redirige a `/login`.

### Alcance y mocks de este sprint

- **Vacantes**: dataset mock en `vacantes/fixtures/vacantes_raw.json`,
  simulando lo que hoy entregaría el workflow de n8n (aún no conectado). El
  dataset incluye a propósito un registro duplicado y uno con datos rotos.
  El comando `seed_vacantes` los descarta al sembrar la base de datos
  (validación y deduplicación una sola vez, no en cada consulta).
- **CV**: `vacantes/cv_parser.py` lee el texto real del PDF (con `pypdf`) y
  aplica heurísticas simples: el nombre es la primera línea del documento,
  el correo se detecta con una expresión regular, las habilidades se buscan
  en el texto completo contra el vocabulario de `skills.py`, y experiencia
  /educación se extraen ubicando encabezados en mayúsculas ("EXPERIENCIA",
  "EDUCACIÓN", etc.) y tomando las líneas que siguen. No es OCR: un PDF
  escaneado sin capa de texto no tiene nada que leer, y en ese caso se cae
  al respaldo del nombre del archivo (heurística de la primera versión de
  este sprint). Los campos que no se pueden extraer quedan marcados como
  pendientes en `/perfil`, sin romper el flujo de carga.
- **Matches de hoy**: scoring simple por coincidencia de palabras clave
  entre las habilidades del perfil y los requisitos de cada vacante
  (`vacantes/matching.py`). Se reemplaza por el motor real del workflow de
  n8n en el Sprint 2 (no implementado en este sprint).
- **Cuentas y sesión**: registro con email y contraseña, usando el sistema
  de autenticación nativo de Django (`accounts.Usuario`, `USERNAME_FIELD =
  "email"`). Sesión persistente 30 días. Sin recuperación de contraseña ni
  login social en este sprint.
- **Persistencia**: SQLite (`db.sqlite3`, ignorado por git). En un sprint
  futuro se reemplaza por un motor de producción si hace falta.

### Identidad visual

**Recalibrada en Sprint 2.** La retroalimentación del Sprint 1 fue que la
app no se sentía como una extensión real de Magneto, solo usaba su verde y
azul sobre fondo blanco plano. Se tomaron capturas de magneto365.com y se
extrajeron sus colores reales por pixel-sampling; el resultado difiere del
plan original en tres puntos: Magneto usa una franja de acento **morado**
muy reconocible (no solo verde+azul), el fondo de página es gris-lavanda
claro (no blanco puro, las tarjetas sí son blancas), y hay una barra
utilitaria oscura por encima de la navegación. Tokens actualizados en
`static/css/scoutly.css`:

- Verde `#0CBB4E` — acción primaria (botones, CTA) y señal positiva
  (indicador de compatibilidad de match). Es, de hecho, el color real del
  botón "Crear cuenta" de Magneto.
- Morado `#9140FE` — acento de marca Magneto: franja utilitaria, estados
  activos (pestaña/pill de filtro seleccionado), foco de campos. Con
  moderación, nunca como fondo dominante ni en botones de acción.
- Azul marino `#1A324C` — autoridad: texto, headers, footer, botones de
  acción secundaria ("Aplicar" en Magneto usa este mismo tono).
- Gris-lavanda `#F5F5F9` — fondo de página (antes blanco plano).
  Blanco `#FFFFFF` — tarjetas, listados, navegación.
- Carbón `#2D3033` — barra utilitaria superior.

## Desarrollo local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_vacantes
.venv/bin/python manage.py runserver 3000
```

Abre [http://localhost:3000](http://localhost:3000).

No hay despliegue configurado todavía; eso queda para una etapa posterior.
