# Scoutly

Scoutly es un copiloto de búsqueda de empleo sobre las vacantes reales de [magneto365.com](https://www.magneto365.com),
construido con **Python + Django** y la identidad visual de Magneto.

Al equipo le correspondió la **Idea 4** del reto de Magneto ("Profile Manager — Reto de Ingeniería"): *"Workflow con
n8n (vacantes → ranking diario → notificación)"*. n8n orquesta la ingesta, la decisión y la notificación como pasos
separados.

El candidato sube su hoja de vida y, cada día, un decisor local y gratuito le dice qué hacer con cada vacante relevante,
siempre con sus razones:

| Acción | Qué significa |
|---|---|
| **Postular** | Cubres los requisitos obligatorios (a veces "con nota": te falta una sola herramienta). |
| **Cerrar brecha** | Te faltan 1 o 2 obligatorios: van a tu plan de aprendizaje. |
| **Descartar** | Viola una restricción tuya (salario, ciudad, modalidad, experiencia o prácticas) o te faltan 3 o más. Siempre dice el motivo. |
| **Revísala tú** | La vacante no dice lo suficiente para decidir. |

En las vacantes de Postular o Cerrar brecha que piden algo obligatorio que tu hoja de vida no dice, el Taller de CV te
pregunta si lo has hecho y te deja contarlo con tus palabras; nunca redacta por ti.

Ningún modelo de pago decide nada. Los embeddings corren en la máquina con fastembed (ONNX, sin torch): MiniLM para
encontrar las vacantes relevantes y mpnet para comparar cada requisito con tu experiencia (spec §13.6). Groq solo
redacta, si el candidato la pide, una explicación en prosa, y nunca recibe el texto del CV.

**Estado (Sprint 3, v3):**
- La rama `sprint-3` es una reescritura completa.
- La evidencia de la Fase 4 está en [`docs/fase4/`](docs/fase4/): la evaluación, el benchmark de 120.000 vacantes, la
  evaluación ciega y la verificación de punta a punta.
- El informe del sprint es [`docs/fase4/INFORME.md`](docs/fase4/INFORME.md).

## Cómo funciona

```
n8n (6 a. m.) ──► /api/importar-vacantes ──► ingesta: texto completo de cada vacante, requisitos y restricciones
             ──► /api/decidir ────────────► cola ──► manage.py decidir --escuchar (batch con los modelos)
             ──► /api/generar-notificaciones          │  embebe lo nuevo, preselecciona en Postgres (las 3.000
                                                      │  más parecidas), mide cobertura, aplica la política,
                                                      ▼  guarda la Decision y notifica
Web (Django): Plan de hoy, acciones, detalle con razones, Taller de CV, tablero de postulaciones, historial
```

- **Apps:**
  - `cuentas`: usuario, perfil, CV, expectativas, consentimiento (Ley 1581) e inicio de sesión;
  - `vacantes`: catálogo, extracción y fuentes;
  - `matching`: el decisor;
  - `postulaciones`: tablero y resultados;
  - `notificaciones`.
- **Módulo `api`:** los endpoints para n8n.
- **La web nunca carga modelos:** solo el batch.
- **Datos:** Postgres 17 + pgvector, en Podman. Cada vacante guarda su vector y la matriz de sus requisitos.

## Levantarlo

Requisitos: Python 3.14, Podman y Chrome (para la ingesta de Magneto).

```bash
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env              # y llena DJANGO_SECRET_KEY y la base (ver los comentarios del archivo)
infra/postgres/levantar.sh        # Postgres 17 + pgvector en 127.0.0.1:5433
.venv/bin/python manage.py migrate
.venv/bin/python manage.py ingerir_vacantes --fuente magneto     # o --fuente fixture, sin red
.venv/bin/python manage.py runserver --insecure                   # http://localhost:8000
.venv/bin/python manage.py decidir --escuchar --procesos 3        # otra terminal: el batch (3 en paralelo)
infra/systemd/instalar.sh   # o, en vez de lo anterior: Postgres y el batch como servicios que arrancan solos
```

Opcional, en el `.env`:
- SMTP (`DJANGO_EMAIL_BACKEND` y `EMAIL_*`) para que los correos de verificación y los avisos lleguen de verdad. Sin
  SMTP salen por la consola. Los avisos van al correo verificado de la cuenta, no al que aparece en el CV.
- `N8N_SCORING_TOKEN` para n8n: ver [`n8n/README.md`](n8n/README.md).
- `GROQ_API_KEY` para "Explícamelo". Sin ella se muestra un texto de respaldo.
- `SOCIAL_*` para entrar con Google, Microsoft, LinkedIn o Facebook: ver
  [`docs/cuentas-sociales.md`](docs/cuentas-sociales.md).
- `SCOUTLY_CONTACTO_DATOS`: el correo del responsable de los datos personales.

**B1 (el MCP oficial de candidatos de Magneto) está construido pero apagado** (`SCOUTLY_MAGNETO_MCP`). Se enciende
solo después de que el equipo revise los términos de uso de Magneto.

## Comandos

| Comando | Para qué |
|---|---|
| `manage.py ingerir_vacantes --fuente magneto\|fixture` | Trae vacantes. Solo reprocesa las que cambiaron. |
| `manage.py decidir --todos\|--pendientes\|--escuchar [--procesos N]` | Corre el decisor (el batch). Con `--procesos N`, N procesos se reparten la cola. Máximo 6. Cada uno ocupa ~2 GB de RAM; en este PC, 3 rinden lo mismo que 6. |
| `manage.py evaluar_decisor --mitad ajuste\|prueba_1\|prueba` | Exactitud contra el set etiquetado. |
| `manage.py benchmark_escala --salida …` | Benchmark de 120.000 vacantes (solo en una base `*_bench`). |
| `manage.py evaluacion_ciega preparar\|tabular` | Materiales y resultados de la evaluación con reclutadores. |

## Pruebas

```bash
.venv/bin/python -m pytest -q -m "not lento"   # 465 pruebas; los fakes reemplazan modelos, Groq y Magneto
.venv/bin/python -m pytest -q -m lento         # las que cargan modelos reales o abren magneto365.com
```

## Lo que hay que saber antes de usarlo

Los detalles están en [`docs/fase4/EVALUACION.md`](docs/fase4/EVALUACION.md).

- **Como filtro da una buena señal:** en la prueba final limpia, con vacantes nunca vistas, acertó las 5 DESCARTAR y no
  descartó ninguna vacante que valiera la pena. Son pocos casos.
- **Las acciones finas eran poco confiables:** en la Fase 4 la exactitud global en vacantes nuevas fue 46%, por
  debajo de la meta de 70%.
- **Después de la exploración** (mpnet para la cobertura y fusión de Postular con Ajustar CV) dio **69%** en una prueba
  nueva y preregistrada de 26 pares, contra 54% de la política anterior. Sigue apenas por debajo de la meta, y son
  pocos pares ([`docs/exploracion/2026-11-02-mejoras-decisor.md`](docs/exploracion/2026-11-02-mejoras-decisor.md)).
- **El Taller de CV ya no propone texto:** de 29 reescrituras automáticas, solo 4 tenían sentido. Ahora pregunta, y
  lo único que se copia es lo que escribe el candidato.
- **Las etiquetas del set de evaluación las propuso el equipo de desarrollo** y están pendientes de revisión.

## Historia

- **Sprint 1:** la entrega congelada vive en [`entregas/sprint-1/`](entregas/sprint-1/), en el tag `sprint-1` y en
  [`ENTREGA_SPRINT1.md`](ENTREGA_SPRINT1.md).
- **Sprint 2 (v2):** ranking por 5 criterios y una llamada a Groq por vacante. El tag `pre-sprint3-rebuild` marca su
  final; el README de entonces está en el historial de git.
- **Sprint 3 (v3):** esta reescritura.
  - Diseño: [`docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md`](docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md).
  - Planes por fase: [`docs/superpowers/plans/`](docs/superpowers/plans/).
