# Entrega Sprint 1 — Scoutly

Este documento cubre los 5 puntos pedidos para la entrega del sprint 1.

## 1. Problema — Solución — Equipo

**Problema:** un candidato tiene que revisar decenas de vacantes una por una
para saber si aplica o no, sin ninguna guía sobre qué tan compatible es con
cada una. Los portales de empleo actuales muestran listados planos, sin
priorización real para el usuario.

**Solución:** Scoutly — el candidato sube su hoja de vida una sola vez, el
sistema la lee, extrae su perfil (habilidades, experiencia, educación) y
muestra un ranking diario de las vacantes más compatibles ("Matches de
hoy"), en vez de un listado genérico.

**Equipo:** Alejandro, Miguel e Iain (scrum team, ver reparto de aportes en
el punto 5).

## 2. Antecedentes y valor agregado vs. apps encontradas

Se revisaron portales existentes en el mercado colombiano: Magneto,
Computrabajo, ElEmpleo y LinkedIn Jobs. Todos resuelven el listado y la
postulación, pero comparten la misma limitación: el match entre candidato y
vacante lo hace el usuario manualmente, leyendo requisito por requisito.

Valor agregado de Scoutly:

1. **Extracción automática del perfil desde el CV en PDF** — sin
   formularios largos, se sube la hoja de vida y el sistema saca nombre,
   contacto, experiencia, educación y habilidades.
2. **Matching diario por compatibilidad real** — se compara las
   habilidades del perfil contra los requisitos de cada vacante y se
   muestra un score de compatibilidad y qué requisitos faltan, no solo si
   aplica o no.

La identidad visual sigue la línea de las plataformas de reclutamiento
colombianas (verde, azul oscuro, blanco) por ser el lenguaje visual que el
usuario objetivo ya asocia con "portal de empleo confiable".

## 3. Características de la aplicación (RF y RNF / mockup)

### Requisitos funcionales (historias de usuario, prioridad alta)

| HU | Historia | Talla | Dificultad | Qué se hizo |
|----|----------|-------|------------|-------------|
| HU-13 | Registro e inicio de sesión, con rutas protegidas | M | Media | Modelo `Usuario` custom (login por email), sesión de 30 días, rutas protegidas con `@login_required`. |
| HU-01 | Carga de CV (PDF) para crear el perfil del candidato | XL | Alta | Parser heurístico (`cv_parser.py`) con `pypdf`: nombre, correo, habilidades, experiencia y educación; lo no detectado queda "Pendiente". |
| HU-04 | Listado de vacantes disponibles | S | Baja | Listado en el dashboard desde `Vacante`, sembrado con `seed_vacantes` (dedup y validación de datos rotos). |
| HU-06 | Ranking diario de vacantes recomendadas, "Matches de hoy" | L | Alta | Scoring por coincidencia de palabras clave (`matching.py`) entre habilidades del perfil y requisitos; top 3 en dashboard. |
| HU-05 | Detalle de una vacante (`/vacantes/<id>`) | M | Media | Vista pública con anillo de compatibilidad y checklist de requisitos cumplidos/faltantes cuando hay sesión. |

Detalle completo de cada historia (criterios de aceptación, puntos) en los
issues del repo, etiquetados `HU`.

### Requisitos no funcionales

- **Seguridad de sesión:** contraseñas con hash (nunca texto plano); rutas
  de dashboard, onboarding y perfil exigen sesión activa.
- **Persistencia consistente:** validación y deduplicación de vacantes al
  sembrar la base de datos (no en cada consulta).
- **Degradación controlada:** si el CV no se puede leer (p. ej. PDF
  escaneado sin texto), el perfil no se rompe — los campos quedan
  marcados como "pendiente".

### Mockup

El mockup son las pantallas reales de la app corriendo en Django (no hay
maqueta separada): `/login`, `/onboarding`, `/perfil`, `/dashboard`,
`/vacantes/<id>` — ver capturas o correr la app localmente (instrucciones
en el `README.md`).

## 4. Funcionalidad

Flujo completo implementado y probado de punta a punta:

1. `/login` — registro e inicio de sesión en la misma vista.
2. `/onboarding` — carga de CV en PDF tras registrarse.
3. `/perfil` — datos extraídos del CV, con "Pendiente" en lo no detectado;
   se puede volver a cargar el PDF en cualquier momento.
4. `/dashboard` — "Matches de hoy" (top 3 por compatibilidad) + listado
   general de vacantes.
5. `/vacantes/<id>` — detalle de vacante; con sesión y perfil, muestra el
   anillo de compatibilidad y el checklist de requisitos.

Vacantes de este sprint como dataset simulado (`vacantes/fixtures/vacantes_raw.json`),
reemplazado por el workflow real de n8n en el sprint 2.

## 5. Qué hizo cada integrante del equipo scrum

- **Iain**: desarrollo completo de la aplicación en Django — modelos,
  vistas, extracción de CV, lógica de matching y reconstrucción del
  prototipo inicial (de Next.js a Django).
- **Miguel**: antecedentes / investigación de apps de la competencia.
- **Alejandro**: problema-solución-equipo y definición de características
  (RF/RNF).

*(Ajustar Miguel/Alejandro si hicieron algo adicional en código o backlog.)*
