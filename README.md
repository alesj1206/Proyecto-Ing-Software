# Scoutly · Sprint 1

Plataforma de vacantes y matching para candidatos, con la identidad visual
de Magneto. Construida en **Python + Django**.

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

Paleta fija de Magneto, definida en `static/css/scoutly.css` (CSS plano, sin
Tailwind ni build de Node):

- Verde `#0CBB4E` — acciones, botones, acentos.
- Azul oscuro `#1A324C` — texto, headers, fondo de navegación.
- Blanco `#FFFFFF` — fondo base y tarjetas.

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
