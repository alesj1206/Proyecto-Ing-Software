# Proyecto-Ing-Software · Gestor de Perfil

Plataforma de vacantes y matching para candidatos. Construida con
[Next.js](https://nextjs.org) (App Router) + TypeScript, con la identidad
visual de Magneto, y pensada para desplegarse en Vercel más adelante.

## Sprint 1

Cubre las siguientes historias de usuario (deben tener, prioridad alta):

- **HU-04** — Listado de vacantes disponibles.
- **HU-05** — Detalle de una vacante (`/vacantes/[id]`).
- **HU-01** — Carga de CV (PDF) para crear el perfil del candidato.
- **HU-06** — Ranking diario de vacantes recomendadas, "Matches de hoy".
- **HU-13** — Registro e inicio de sesión, con rutas protegidas.

### Flujo de la aplicación

1. Primera visita → `/login` (registro o inicio de sesión).
2. Registro exitoso → `/onboarding`, "Carga tu CV para empezar" (HU-01).
3. Inicio de sesión de un usuario existente → directo a `/dashboard`.
4. `/dashboard` (protegido) → una sola vista con "Matches de hoy" (HU-06)
   y el listado general de vacantes (HU-04). Si todavía no hay CV cargado,
   "Matches de hoy" muestra un mensaje para cargarlo, en vez de quedar
   vacío o roto.
5. El clic en cualquier vacante, desde matches o desde el listado, lleva
   siempre al mismo componente de detalle: `/vacantes/[id]` (HU-05).

Las rutas `/dashboard`, `/onboarding` y `/perfil` están protegidas por
`src/proxy.ts` (el equivalente a `middleware.ts` en Next.js 16): sin
sesión activa, se redirige a `/login`.

### Alcance y mocks de este sprint

- **Vacantes**: dataset mock en `src/data/vacantes.json`, simulando lo que
  hoy entregaría el workflow de n8n (aún no conectado). El dataset incluye
  a propósito un registro duplicado y uno con datos rotos para ejercitar
  el filtrado defensivo en `src/lib/vacantes.ts`.
- **CV**: la extracción de datos del PDF está simulada (mock) en
  `src/lib/cvParser.ts` — no hay OCR real en este sprint. Los campos que
  no se pueden extraer quedan marcados como pendientes sin romper el
  flujo de carga.
- **Matches de hoy**: scoring simple por coincidencia de palabras clave
  entre las habilidades del perfil y los requisitos de cada vacante
  (`src/lib/matching.ts`). Se reemplaza por el motor real del workflow de
  n8n en el Sprint 2 — evaluando además un agente sobre la API de Claude
  que compare perfil y vacante para generar el puntaje de compatibilidad
  junto con el razonamiento detrás (no implementado en este sprint).
- **Cuentas y sesión**: registro con email y contraseña (hash `scrypt`),
  sesión con cookie firmada (30 días, se mantiene activa hasta cerrar
  sesión). Sin recuperación de contraseña ni login social en este sprint.
- **Persistencia**: usuarios y perfiles (uno por usuario) se guardan en
  archivos locales dentro de `.data/`, ignorado por git. En un sprint
  futuro se reemplaza por una base de datos real.

### Identidad visual

Paleta fija de Magneto, definida en `src/app/globals.css`:

- Verde `#0CBB4E` — acciones, botones, acentos.
- Azul oscuro `#1A324C` — texto, headers, fondo de navegación.
- Blanco `#FFFFFF` — fondo base y tarjetas.

## Desarrollo local

```bash
npm install
npm run dev
```

Abre [http://localhost:3000](http://localhost:3000).

No hay despliegue ni configuración de Vercel todavía; eso queda para una
etapa posterior.
