# Fase 1 (cimientos) de Scoutly v3: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dejar el proyecto v3 sobre Postgres + pgvector con sus 5 apps. Incluye las cuentas (login y registro al
estilo Magneto, con inicio de sesión social real y la autorización de la Ley 1581), el perfil con vocabulario
abierto, la ingesta de vacantes con texto completo, y los 9 templates de v2 renderizando igual, salvo el login.

**Architecture:** se retiran las apps `accounts` y `vacantes` de v2, que quedan en el tag `pre-sprint3-rebuild`, y
se crean `cuentas`, `vacantes`, `matching`, `postulaciones` y `notificaciones`, más el módulo `api`. Cada app tiene
`models.py`, `services.py` (escrituras), `selectors.py` (lecturas), vistas delgadas y `tests/`. Las fuentes de vacantes
son una Strategy detrás de un puerto. La decisión (embeddings, cobertura y política) es de la Fase 2: aquí solo se
deja lo que ella va a consumir.

**Tech Stack:** Python 3.14, Django ≥ 6.1.1, Postgres 17 + pgvector (Podman, `infra/postgres/levantar.sh`),
psycopg 3, django-allauth 65.x, pytest + pytest-django, Playwright (scraping y capturas) y fpdf2 (CVs ficticios
de test).

**Spec:** `docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md`. La §13 manda sobre las secciones
anteriores.

## Global Constraints

- **Visual idéntico salvo el login:** `templates/base.html`, `static/css/scoutly.css` (solo se le **agregan** clases
  `auth-*` al final, sin modificar las existentes) y los templates onboarding, perfil, expectativas, dashboard,
  detalle, historial, tablero y notificaciones se copian **sin cambios** desde v2. Se rediseñan login y registro.
  La única otra excepción es el bloque "Eliminar mi cuenta" que se agrega al final de `perfil.html` (§13.5).
- **URLs y nombres de ruta iguales a v2:** `raiz`, `login`, `registro`, `logout`, `onboarding`, `perfil`,
  `expectativas`, `dashboard`, `historial`, `vacante_detalle` (`vacantes/<str:vacante_id>`), `postularme`,
  `tablero` (`postulaciones`), `cambiar_estado_postulacion` y `notificaciones`.
- **Identidad Scoutly:** el login copia la **estructura** de Magneto (tarjeta centrada, botones sociales, campo de
  correo), pero con el logo, el nombre y los colores de Scoutly. Nunca se usan el logo ni la marca de Magneto.
- **Vocabulario abierto:** ninguna lista cerrada de habilidades. Tampoco se inventan habilidades por defecto (v2
  ponía "comunicación, trabajo en equipo").
- **Privacidad (§13.5):** no se crea ningún usuario sin una autorización guardada. Los datos personales se quitan
  antes de guardar las unidades de evidencia. Ningún texto del CV sale a un servicio externo.
- **Seguridad (commit `bcc2550`):** se mantienen los secretos desde el entorno, la subida de PDF con máximo 5 MB,
  firma `%PDF-` y 10 páginas, y los validadores de contraseña.
- **Nombres en español**, como el resto del proyecto. TDD con pytest-django contra Postgres real. Los tests no
  descargan modelos ni salen a internet, salvo los marcados `lento`.
- Las fechas y horas son las de `America/Bogota`.

## Review Focus

1. **Login social con un correo que ya tiene cuenta con contraseña.** Solo se enlaza si el proveedor marca el correo
   como verificado; si no, se muestra un error claro y nadie toma la cuenta (Task 6).
2. **Llegar al paso 2 del registro sin pasar por el paso 1** (sesión vencida o URL escrita a mano). Debe volver al
   paso 1 y no crear ningún usuario sin autorización (Task 5).
3. **Un CV escaneado o con solo los datos de contacto.** El perfil se crea con `campos_pendientes`, sin evidencia
   inventada y sin errores (Task 3).
4. **Una vacante sin sección de requisitos o con solo texto de marketing.** Quedan 0 o 1 requisitos, marcados como
   insuficientes, y la ingesta no falla (Task 8).
5. **Re-ingerir una vacante cuyo texto cambió.** Los requisitos se reemplazan en una sola transacción, sin
   duplicados y con `posicion` contigua; si el hash no cambió, no se toca nada (Task 9).

---

### Task 1: Esqueleto v3 sobre Postgres + pgvector

**Files:**
- Delete: `accounts/` y `vacantes/` de v2. La referencia es el tag `pre-sprint3-rebuild`, y los templates se
  recuperan de ahí con `git show pre-sprint3-rebuild:<ruta>`
- Create: `cuentas/`, `vacantes/`, `matching/`, `postulaciones/`, `notificaciones/` (`apps.py`, `models.py` vacío,
  `urls.py`, `tests/__init__.py`), `api/__init__.py`, `conftest.py`, `requirements-dev.txt`
- Modify: `scoutly/settings.py`, `scoutly/urls.py`, `pytest.ini`, `requirements.txt`, `infra/postgres/levantar.sh`,
  `.env.example`
- Test: `scoutly/tests.py` (los 8 existentes), `vacantes/tests/test_base_datos.py`

**Interfaces:**
- Produces: `DATABASES['default']` en Postgres, a partir de `DJANGO_DB_NAME` (por defecto `scoutly_v3`),
  `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST` (por defecto `127.0.0.1`) y `DJANGO_DB_PORT` (por
  defecto `5433`). La extensión `vector` se crea en la migración `vacantes/migrations/0001_initial.py` con
  `pgvector.django.VectorExtension()`.
- Produces: `scoutly/urls.py` incluye las urls de las 5 apps y **todos** los nombres de ruta de Global
  Constraints existen desde esta tarea. `base.html` los usa con `{% url %}`, así que si faltara alguno cualquier
  página con sesión fallaría. La ruta de una vista que todavía no existe apunta a `scoutly.views.pendiente`, que
  responde 501 con "En construcción". Cada tarea dueña reemplaza su ruta, y la Task 10 borra `pendiente`.

- [ ] **Step 1: Write the failing test** `vacantes/tests/test_base_datos.py`

```python
import pytest
from django.db import connection

@pytest.mark.django_db
def test_postgres_con_pgvector():
    assert connection.vendor == "postgresql"
    with connection.cursor() as c:
        c.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        assert c.fetchone() is not None
```

Y en `scoutly/tests.py`:

```python
RUTAS_V2 = ["raiz", "login", "registro", "logout", "onboarding", "perfil", "expectativas", "dashboard",
            "historial", "tablero", "notificaciones"]

def test_todas_las_rutas_de_v2_existen():
    for nombre in RUTAS_V2:
        reverse(nombre)
    reverse("vacante_detalle", args=["x"]); reverse("postularme", args=["x"])
    reverse("cambiar_estado_postulacion", args=[1])
```

- [ ] **Step 2:** Run `.venv/bin/python -m pytest vacantes/tests/test_base_datos.py scoutly/tests.py -v`. Expected:
  ERROR (no hay pytest-django ni Postgres configurado, y no existen las rutas).
- [ ] **Step 3:** Agregar a `requirements.txt` `psycopg[binary]>=3.3,<4`, `pgvector>=0.5,<0.6` y
  `django-allauth>=65.21,<66`; a `requirements-dev.txt` (`-r requirements.txt`) `pytest>=9`, `pytest-django>=4.11`
  y `fpdf2>=2.8`. En `pytest.ini`, `DJANGO_SETTINGS_MODULE = scoutly.settings` (se conserva el marcador `lento`).
  `levantar.sh` crea la base `scoutly_v3` si no existe (idempotente, con `psql` dentro del contenedor). Borrar
  `accounts/` y `vacantes/`, crear las apps nuevas, ajustar `INSTALLED_APPS` y `AUTH_USER_MODEL = "cuentas.Usuario"`
  (el modelo se declara aquí con lo mínimo y se completa en la Task 2) y mover el context processor de
  notificaciones a la Task 10, quitándolo de `TEMPLATES` hasta entonces.
- [ ] **Step 4:** Run `infra/postgres/levantar.sh && .venv/bin/python -m pip install -r requirements-dev.txt &&
  .venv/bin/python -m pytest -q`. Expected: PASS en `test_postgres_con_pgvector` y en los 8 tests de
  `scoutly/tests.py`. Los tests de `spike/` siguen pasando.
- [ ] **Step 5: Commit** `feat(v3): esqueleto de 5 apps sobre Postgres + pgvector`

### Task 2: Cuentas, autorización de datos y páginas legales

**Files:**
- Create: `cuentas/models.py`, `cuentas/legal.py`, `cuentas/services.py`, `cuentas/views_legal.py`,
  `cuentas/templates/cuentas/privacidad.html`, `cuentas/templates/cuentas/terminos.html`
- Test: `cuentas/tests/test_autorizacion.py`

**Interfaces:**
- Produces: `Usuario(AbstractUser)` con `username = None`, `email` único (`USERNAME_FIELD = "email"`) y un manager
  que normaliza el correo con `strip().lower()`.
- Produces: `Autorizacion(usuario FK CASCADE, version_politica: str, version_terminos: str, aceptada_en: datetime,
  finalidad: str)`.
- Produces: en `cuentas/legal.py`, `VERSION_POLITICA = "2026-11-01"`, `VERSION_TERMINOS = "2026-11-01"` y
  `FINALIDAD`, el texto corto de la finalidad. La política dice que los datos se usan para recomendar vacantes con
  IA local, que **a Groq (EE. UU.) solo van campos de criterio, nunca el CV**, y que existen los derechos de
  consulta, corrección y supresión, con el botón "eliminar mi cuenta".
- Produces: `crear_usuario_con_autorizacion(email: str, password: str | None) -> Usuario`, en `services.py`, que
  crea el usuario y su `Autorizacion` en **una transacción**. `password=None` deja la contraseña inutilizable (para
  el login social).
- Produces: las rutas `privacidad` (`/privacidad`) y `terminos` (`/terminos`), públicas.

- [ ] **Step 1: Write the failing tests**

```python
def test_crear_usuario_guarda_la_autorizacion_vigente(db):
    u = crear_usuario_con_autorizacion(" Ana@Ejemplo.com ", "Lienzo-Tardio-73")
    a = u.autorizacion_set.get()
    assert u.email == "ana@ejemplo.com"
    assert (a.version_politica, a.version_terminos) == (VERSION_POLITICA, VERSION_TERMINOS)

def test_si_falla_la_autorizacion_no_queda_usuario(db, monkeypatch):
    monkeypatch.setattr(Autorizacion.objects, "create", mock.Mock(side_effect=IntegrityError))
    with pytest.raises(IntegrityError):
        crear_usuario_con_autorizacion("b@ejemplo.com", "Lienzo-Tardio-73")
    assert not Usuario.objects.filter(email="b@ejemplo.com").exists()

def test_usuario_social_sin_contrasena_usable(db):
    assert not crear_usuario_con_autorizacion("c@ejemplo.com", None).has_usable_password()

def test_paginas_legales_publicas(client):
    for ruta in ("privacidad", "terminos"):
        r = client.get(reverse(ruta))
        assert r.status_code == 200 and VERSION_POLITICA in r.content.decode()
```

- [ ] **Step 2:** Run `.venv/bin/python -m pytest cuentas/tests/test_autorizacion.py -v`. Expected: FAIL (no
  existen los nombres importados).
- [ ] **Step 3:** Implementar los modelos, `legal.py`, el servicio y las dos vistas. Los templates extienden
  `base.html` y usan las clases CSS existentes (`card`, `label-eyebrow`). Generar la migración inicial de `cuentas`.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest cuentas -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(cuentas): usuario por correo, autorización Ley 1581 y páginas legales`

### Task 3: Perfil desde el CV con vocabulario abierto

**Files:**
- Create: `cuentas/cv/__init__.py`, `cuentas/cv/lector.py`, `cuentas/cv/secciones.py`,
  `cuentas/cv/minimizacion.py`, `cuentas/tests/cvs.py` (genera los PDFs ficticios con fpdf2)
- Modify: `cuentas/models.py` (`Perfil`, `EvidenciaPerfil`), `cuentas/forms.py` (`CVUploadForm`, traído de v2 con sus
  límites), `cuentas/services.py`, `cuentas/views.py`, `cuentas/urls.py`
- Copy without changes from `pre-sprint3-rebuild`: `vacantes/templates/vacantes/onboarding.html` y `perfil.html`, a
  `cuentas/templates/cuentas/`
- Test: `cuentas/tests/test_cv.py`

**Interfaces:**
- Produces: `Perfil`, con los mismos campos que en v2 (`nombre`, `contacto`, `experiencia`, `educacion`,
  `habilidades`, `campos_pendientes`, `cv_nombre_archivo`, `actualizado_en`, `exp_*` y `anios_experiencia`) y sus
  métodos `tiene_cv`, `tiene_expectativas` y `puede_notificar`, porque los templates los usan.
- Produces: `EvidenciaPerfil(perfil FK CASCADE, texto: str, seccion: "experiencia" | "habilidades" | "educacion",
  posicion: int)`. El vector lo agrega la Fase 2.
- Produces: `extraer_texto(archivo) -> str` (en `lector.py`: 10 páginas como máximo; un PDF dañado devuelve `""`,
  como en v2) y `analizar_cv(texto: str) -> CVAnalizado`. `CVAnalizado` es una dataclass con `nombre`, `contacto`,
  `experiencia: list[str]`, `educacion: list[str]`, `habilidades: list[str]`, `unidades: list[UnidadEvidencia]` y
  `campos_pendientes: list[str]`. Las habilidades salen de la sección de habilidades, separando por comas, viñetas o
  saltos de línea. **No hay lista cerrada ni habilidades por defecto.** Se reutilizan las heurísticas de encabezados
  de v2 (`ENCABEZADOS_EXPERIENCIA` y `ENCABEZADOS_EDUCACION`, más los de habilidades).
- Produces: `minimizar(texto: str) -> str`, que reemplaza correos, teléfonos (de 7 o más dígitos, con o sin
  espacios, guiones o `+57`), números de documento (con las palabras guía "CC", "cédula" o "documento") y
  direcciones ("Calle", "Cra", "Carrera", "Av" seguidas de un número) por `[dato personal]`. Se aplica a cada unidad
  antes de guardarla.
- Produces: `guardar_perfil_desde_cv(usuario, archivo) -> Perfil`, que reemplaza las `EvidenciaPerfil` del perfil
  en una transacción. Rutas: `onboarding` y `perfil`, con el mismo contexto que en v2 (`form` y `perfil`).

- [ ] **Step 1: Write the failing tests** (los PDFs se generan en el test, con datos ficticios)

```python
def test_habilidades_abiertas_fuera_de_cualquier_lista():
    cv = analizar_cv(texto_cv(habilidades="Kubernetes, Power BI, Figma, Contabilidad NIIF"))
    assert {"Kubernetes", "Power BI", "Figma", "Contabilidad NIIF"} <= set(cv.habilidades)

def test_sin_habilidades_no_se_inventan():
    assert analizar_cv(texto_cv(habilidades=None)).habilidades == []

def test_unidades_de_experiencia_por_vineta():
    cv = analizar_cv(texto_cv(experiencia=["Lideré la migración a la nube.", "Automaticé reportes en SQL."]))
    assert [u.texto for u in cv.unidades if u.seccion == "experiencia"] == [
        "Lideré la migración a la nube.", "Automaticé reportes en SQL."]

def test_minimizar_quita_datos_personales():
    t = minimizar("Ana Pérez, ana@x.com, +57 300 123 4567, CC 1.020.304.050, Calle 10 # 43-12")
    for dato in ("ana@x.com", "300 123 4567", "1.020.304.050", "Calle 10"):
        assert dato not in t

def test_la_evidencia_guardada_esta_minimizada(db, usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv(experiencia=["Soporte a clientes, escribir a ana@x.com"]))
    assert "ana@x.com" not in " ".join(perfil.evidencias.values_list("texto", flat=True))

def test_cv_escaneado_sin_texto(db, usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_sin_texto("ana_perez_cv.pdf"))
    assert "contacto" in perfil.campos_pendientes and perfil.evidencias.count() == 0

def test_cargar_cv_otra_vez_reemplaza_la_evidencia(db, usuario):
    guardar_perfil_desde_cv(usuario, pdf_cv(experiencia=["A.", "B."]))
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv(experiencia=["C."]))
    assert list(perfil.evidencias.filter(seccion="experiencia").values_list("texto", flat=True)) == ["C."]
```

Más los 6 tests de subida y lectura de `vacantes/tests.py` de v2, movidos aquí sin cambiar sus aserciones.

- [ ] **Step 2:** Run `.venv/bin/python -m pytest cuentas/tests/test_cv.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar, reemplazando las rutas `pendiente` de `onboarding` y `perfil`.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest cuentas -v`. Expected: PASS. Además, `GET /onboarding` y
  `GET /perfil` con sesión dan 200.
- [ ] **Step 5: Commit** `feat(cuentas): perfil desde el CV con vocabulario abierto y datos minimizados`

### Task 4: Expectativas

**Files:**
- Modify: `cuentas/forms.py` (`ExpectativasForm`, copiado de v2), `cuentas/views.py`, `cuentas/urls.py`
- Copy without changes: `expectativas.html`, a `cuentas/templates/cuentas/`
- Test: `cuentas/tests/test_expectativas.py`

**Interfaces:**
- Produces: la ruta `expectativas`, con el mismo comportamiento y contexto que v2 (`get_or_create` del perfil y
  redirección al guardar igual que `expectativas_view` en el tag).

- [ ] **Step 1: Write the failing tests**: `test_guarda_expectativas` (un POST con `exp_modalidad="Remoto"` y
  `exp_salario_min=3000000` queda guardado en el perfil) y `test_expectativas_sin_cv_crea_perfil_vacio`
  (`tiene_cv()` es False).
- [ ] **Step 2:** Run `.venv/bin/python -m pytest cuentas/tests/test_expectativas.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest cuentas -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(cuentas): expectativas`

### Task 5: Login y registro al estilo Magneto (correo)

Referencias visuales: la captura del login de Magneto (tarjeta blanca centrada sobre gris claro; título "Inicia
sesión en tu cuenta"; subtítulo; "Redes sociales" con botones en fila; campo de correo con icono; botón "Continuar"
de ancho completo) y la del registro que envió el usuario ("¿Cómo deseas crear tu cuenta?"; "Con tus redes
sociales:"; correo y su confirmación; un recuadro gris con un aviso y dos casillas; botón "Siguiente" en azul
marino; "¿Ya tienes una cuenta? Iniciar sesión").

**Files:**
- Create: `cuentas/forms.py`, `cuentas/views.py`, `cuentas/urls.py`,
  `cuentas/templates/cuentas/login.html`, `cuentas/templates/cuentas/registro.html`,
  `cuentas/templates/cuentas/_botones_sociales.html`
- Modify: `static/css/scoutly.css` (solo se **agregan** clases `auth-*` al final)
- Test: `cuentas/tests/test_login_registro.py`

**Interfaces:**
- Consumes: `crear_usuario_con_autorizacion` (Task 2).
- Produces: el login en 2 pasos, en la ruta `login`. En el paso 1 se escribe el correo y se pulsa "Continuar". El
  paso 2 pide la contraseña, muestra el correo con un enlace "Cambiar" y **siempre se llega a él**, exista o no el
  correo, para no revelar qué cuentas existen. El error es genérico: "Correo electrónico o contraseña incorrectos".
  Si el usuario no tiene contraseña usable (cuenta social), el paso 2 dice "Ingresa con el botón de tu red social".
- Produces: el registro en 2 pasos, en la ruta `registro`.
  - **Paso 1:** correo, confirmación del correo y las casillas `autoriza_datos` (con un enlace a `privacidad`) y
    `acepta_terminos` (con un enlace a `terminos`). Las dos son obligatorias. El correo y las versiones aceptadas
    se guardan en la sesión, en la clave `registro_paso1`.
  - **Paso 2:** contraseña y su confirmación, con `AUTH_PASSWORD_VALIDATORS`. Llama a
    `crear_usuario_con_autorizacion`, inicia sesión y redirige a `onboarding`.
- Produces: `_botones_sociales.html`, que recibe `proveedores` (una lista de `ProveedorSocial`, Task 6) y no dibuja
  nada si está vacía. En esta tarea la lista llega vacía.
- Produces: `logout`, por POST (como en v2), redirige a `login`. Si hay sesión, `raiz` redirige a `dashboard`; si no,
  a `login`.

- [ ] **Step 1: Write the failing tests**

```python
def test_login_paso1_siempre_pide_contrasena(client, db):
    r = client.post(reverse("login"), {"paso": "correo", "email": "nadie@ejemplo.com"})
    assert 'name="password"' in r.content.decode()

def test_login_correcto_con_mayusculas_y_espacios(client, usuario):  # fixture: ana@ejemplo.com / Lienzo-Tardio-73
    client.post(reverse("login"), {"paso": "correo", "email": " Ana@Ejemplo.com "})
    r = client.post(reverse("login"), {"paso": "clave", "password": "Lienzo-Tardio-73"})
    assert r.status_code == 302 and "_auth_user_id" in client.session

def test_login_incorrecto_mensaje_generico(client, usuario):
    client.post(reverse("login"), {"paso": "correo", "email": "ana@ejemplo.com"})
    r = client.post(reverse("login"), {"paso": "clave", "password": "otra"})
    assert "Correo electrónico o contraseña incorrectos" in r.content.decode()

def test_registro_exige_las_dos_casillas(client, db):
    r = client.post(reverse("registro"), {"paso": "datos", "email": "n@e.com", "email_confirmacion": "n@e.com",
                                          "autoriza_datos": "on"})
    assert "registro_paso1" not in client.session and r.status_code == 200

def test_registro_correos_distintos(client, db):
    r = client.post(reverse("registro"), {"paso": "datos", "email": "n@e.com", "email_confirmacion": "m@e.com",
                                          "autoriza_datos": "on", "acepta_terminos": "on"})
    assert "Los correos no coinciden" in r.content.decode()

def test_registro_paso2_sin_paso1_vuelve_al_inicio(client, db):
    r = client.post(reverse("registro"), {"paso": "clave", "password1": "Lienzo-Tardio-73",
                                          "password2": "Lienzo-Tardio-73"})
    assert r.status_code == 302 and r.url == reverse("registro")
    assert not Usuario.objects.exists()

def test_registro_completo_crea_usuario_autorizado_y_va_a_onboarding(client, db):
    client.post(reverse("registro"), {"paso": "datos", "email": "n@e.com", "email_confirmacion": "n@e.com",
                                      "autoriza_datos": "on", "acepta_terminos": "on"})
    r = client.post(reverse("registro"), {"paso": "clave", "password1": "Lienzo-Tardio-73",
                                          "password2": "Lienzo-Tardio-73"})
    assert r.url == reverse("onboarding")
    assert Usuario.objects.get(email="n@e.com").autorizacion_set.exists()

def test_registro_con_correo_existente(client, usuario):
    r = client.post(reverse("registro"), {"paso": "datos", "email": "ana@ejemplo.com",
                                          "email_confirmacion": "ana@ejemplo.com",
                                          "autoriza_datos": "on", "acepta_terminos": "on"})
    assert "Ya existe una cuenta con ese correo" in r.content.decode()

def test_login_no_muestra_estadisticas_inventadas(client, db):
    assert "Precisión del match" not in client.get(reverse("login")).content.decode()
```

- [ ] **Step 2:** Run `.venv/bin/python -m pytest cuentas/tests/test_login_registro.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar los formularios, las vistas y los templates. Las vistas son delgadas: el formulario
  valida y el servicio crea. El campo oculto `paso` elige el formulario. El CSS nuevo sigue la paleta existente:
  `--navy` para el botón principal, el fondo `#F5F5F9` y las tarjetas blancas. Los textos son de Scoutly: "Inicia
  sesión en Scoutly", "Aquí empieza tu próxima entrevista" y "¿Cómo deseas crear tu cuenta?". Después del login, se
  redirige según la regla de v2: sin CV, a `onboarding`; con CV, a `dashboard`. `onboarding` ya existe desde la
  Task 3.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest cuentas -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(cuentas): login y registro en dos pasos con autorización de datos`

### Task 6: Inicio de sesión social real (Google, Microsoft, LinkedIn y Facebook)

**Files:**
- Create: `cuentas/sociales.py`, `cuentas/adaptadores.py`,
  `cuentas/templates/socialaccount/signup.html`, `docs/cuentas-sociales.md`
- Modify: `scoutly/settings.py`, `scoutly/urls.py`, `cuentas/forms.py`, `cuentas/views.py`, `.env.example`
- Test: `cuentas/tests/test_sociales.py`

**Interfaces:**
- Produces: en `cuentas/sociales.py`, `ProveedorSocial(id: str, nombre: str, icono: str)` (dataclass congelada) y
  `proveedores_activos() -> list[ProveedorSocial]`. Esta función devuelve, **en el orden de Magneto**
  (LinkedIn, Facebook, Google, Microsoft), solo los proveedores con `client_id` y `secret` en el entorno:
  `SOCIAL_LINKEDIN_ID/SECRET`, `SOCIAL_FACEBOOK_ID/SECRET`, `SOCIAL_GOOGLE_ID/SECRET` y `SOCIAL_MICROSOFT_ID/SECRET`.
- Produces: `settings.SOCIALACCOUNT_PROVIDERS`, armado con la misma lectura del entorno. LinkedIn va por el
  proveedor `openid_connect`, con `provider_id="linkedin"` y `server_url="https://www.linkedin.com/oauth"`. Los
  demás usan sus proveedores nativos de allauth.
- Produces: la configuración de allauth:
  - `ACCOUNT_LOGIN_METHODS = {"email"}`, `ACCOUNT_USER_MODEL_USERNAME_FIELD = None` y
    `ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]`;
  - `SOCIALACCOUNT_AUTO_SIGNUP = False`, para que todo alta social pase por el formulario con las casillas;
  - `SOCIALACCOUNT_FORMS = {"signup": "cuentas.forms.RegistroSocialForm"}`;
  - `SOCIALACCOUNT_EMAIL_AUTHENTICATION = True` y `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True`. allauth
    solo los aplica a correos que el proveedor marca como verificados;
  - `SOCIALACCOUNT_ADAPTER = "cuentas.adaptadores.AdaptadorSocial"`.
- Produces: `RegistroSocialForm`, con las mismas dos casillas obligatorias. Su `save` crea la `Autorizacion` en la
  misma transacción que el usuario.
- Produces: las urls de allauth bajo `cuentas/`. Antes del include, `cuentas/login/` y `cuentas/signup/` redirigen
  a `login` y a `registro`, para que no queden pantallas de allauth sin estilo.
- Produces: login y registro pasan `proveedores=proveedores_activos()`. Cada botón es un `<form method="post">` con
  CSRF hacia `{% provider_login_url p.id %}`, porque allauth 65 no inicia el login por GET.

- [ ] **Step 1: Write the failing tests**

```python
def test_sin_credenciales_no_hay_botones(client, db, monkeypatch):
    for v in ("LINKEDIN", "FACEBOOK", "GOOGLE", "MICROSOFT"):
        monkeypatch.delenv(f"SOCIAL_{v}_ID", raising=False)
    assert proveedores_activos() == []
    assert "auth-social" not in client.get(reverse("login")).content.decode()

def test_solo_aparecen_los_configurados_en_orden_magneto(monkeypatch):
    monkeypatch.setenv("SOCIAL_GOOGLE_ID", "g"); monkeypatch.setenv("SOCIAL_GOOGLE_SECRET", "s")
    monkeypatch.setenv("SOCIAL_LINKEDIN_ID", "l"); monkeypatch.setenv("SOCIAL_LINKEDIN_SECRET", "s")
    assert [p.id for p in proveedores_activos()] == ["linkedin", "google"]

def test_un_proveedor_sin_secret_no_cuenta(monkeypatch):
    monkeypatch.setenv("SOCIAL_FACEBOOK_ID", "f"); monkeypatch.delenv("SOCIAL_FACEBOOK_SECRET", raising=False)
    assert "facebook" not in [p.id for p in proveedores_activos()]

def test_registro_social_exige_las_casillas():
    form = RegistroSocialForm(sociallogin=sociallogin_falso("x@e.com"), data={"email": "x@e.com"})
    assert not form.is_valid()

def test_correo_no_verificado_no_toma_una_cuenta_existente(db, usuario):
    # El proveedor dice que ana@ejemplo.com NO está verificado: no se conecta a la cuenta de Ana.
    sl = sociallogin_falso("ana@ejemplo.com", verificado=False)
    AdaptadorSocial().pre_social_login(request_falso(), sl)
    assert not sl.is_existing
```

`sociallogin_falso` y `request_falso` van en `cuentas/tests/conftest.py`. Arman un `SocialLogin` de allauth con
`EmailAddress(verified=...)`, sin llamar a ningún proveedor.

- [ ] **Step 2:** Run `.venv/bin/python -m pytest cuentas/tests/test_sociales.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar lo anterior. Si el último test pasa sin adaptador propio, porque allauth ya lo
  garantiza, el adaptador se queda solo con lo que el test necesite y el test se conserva como prueba de
  regresión. El template `socialaccount/signup.html` reusa el recuadro de autorización de `registro.html` (se
  extrae a `_autorizacion.html`). En `docs/cuentas-sociales.md` va, por proveedor, cómo crear la app OAuth, la URL
  de retorno (`http://localhost:8000/cuentas/<proveedor>/login/callback/`) y la limitación del túnel: la URL de
  trycloudflare cambia en cada arranque y OAuth exige registrarla, así que en la demo se usa localhost o un dominio
  fijo.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest cuentas -v`. Expected: PASS.
- [ ] **Step 5 (verificación manual, la hace el usuario con sus credenciales):** con `SOCIAL_GOOGLE_ID/SECRET` en
  `.env`, el botón Google lleva a la pantalla de consentimiento de Google, vuelve a "¿Cómo deseas crear tu cuenta?"
  con las casillas y, al aceptarlas, entra a `onboarding`. Se anota en el ledger si se probó o quedó pendiente.
- [ ] **Step 6: Commit** `feat(cuentas): inicio de sesión social con allauth (solo proveedores configurados)`

### Task 7: Eliminar mi cuenta

**Files:**
- Modify: `cuentas/services.py`, `cuentas/views.py`, `cuentas/urls.py`; agregar el bloque "Eliminar mi cuenta" en
  `perfil.html`, que **solo agrega** un bloque al final (la otra excepción al visual idéntico, la pide §13.5)
- Test: `cuentas/tests/test_eliminar.py`

**Interfaces:**
- Produces: `eliminar_cuenta(usuario: Usuario) -> None` borra en cascada (perfil, evidencia, postulaciones,
  notificaciones, autorizaciones y cuentas sociales). Se expone en la ruta `eliminar_cuenta` (`/cuenta/eliminar`),
  que en GET muestra la confirmación y en POST, con la casilla `confirmo` marcada, borra, cierra sesión y redirige a
  `login` con un mensaje.

- [ ] **Step 1: Write the failing tests**: `test_eliminar_borra_todo_en_cascada` (después de crear un usuario con
  perfil y autorización, `Usuario`, `Perfil` y `Autorizacion` quedan en 0), `test_eliminar_exige_confirmacion` (un
  POST sin `confirmo` no borra nada) y `test_eliminar_requiere_sesion` (redirige a `login`).
- [ ] **Step 2:** Run `.venv/bin/python -m pytest cuentas/tests/test_eliminar.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar. Hay un solo `delete()` sobre el usuario, y las FK declaran `CASCADE`.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest cuentas -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(cuentas): eliminar mi cuenta`

### Task 8: Vacantes y extracción de requisitos con texto completo

**Files:**
- Create: `vacantes/models.py`, `vacantes/extraccion.py`, `vacantes/tests/datos/extraccion.yaml`,
  `vacantes/tests/test_extraccion.py`

**Interfaces:**
- Produces: `Vacante`, con los campos de v2 (`id` str de 20 como pk, `titulo`, `empresa`, `ubicacion`, `modalidad`,
  `salario_min/max/moneda/periodo`, `descripcion`, `fecha_publicacion`, `experiencia_minima` y `urgente`) más
  `texto_completo: TextField`, `url: URLField`, `fuente: str`, `hash_contenido: str(64)`, `activa: bool`,
  `etiquetas: JSONField(list)` (las habilidades que trae Magneto), `prefiltro: JSONField(list)` (las preguntas, que
  llena B1 en la Fase 3) e `ingerida_en`. **Sin vectores**: los agrega la Fase 2.
- Produces: `Requisito(vacante FK CASCADE, texto, tipo: "obligatorio" | "deseable", origen: "texto" | "etiqueta",
  posicion: int)`, único por `(vacante, posicion)`.
- Produces: `extraer_requisitos(texto: str, etiquetas: list[str]) -> list[RequisitoExtraido]`, donde
  `RequisitoExtraido` es una dataclass con `texto`, `tipo` y `origen`. Sus reglas:
  - si hay sección de requisitos (encabezados "requisitos", "perfil", "qué buscamos", "requerimientos" y "lo que
    necesitas"), una unidad por viñeta u oración de esa sección;
  - si no la hay, las oraciones de la descripción con palabras de requisito ("experiencia", "conocimiento",
    "manejo", "título", "formación", "dominio" o "certificación");
  - las palabras guía "deseable", "plus", "valorable", "ideal" o "preferible" marcan `deseable`;
  - el **filtro de ruido** descarta salarios, montos, "importante empresa", "te apasiona", "únete", beneficios y la
    presentación de la empresa;
  - **las etiquetas de Magneto se agregan como `deseable` con `origen="etiqueta"`** (§13.2: son señales, no
    obligatorios);
  - los duplicados se quitan sin distinguir mayúsculas ni acentos.
- Produces: `extraer_restricciones(texto: str) -> Restricciones`, una dataclass con `anios_minimos: int | None`,
  `salario_min/max: int | None`, `modalidad: str | None` y `ubicacion: str | None`, extraídas con regex. Se
  reutilizan las de `scrape_magneto.py` de v2.
- Produces: `requisitos_insuficientes(requisitos) -> bool`, verdadera cuando hay menos de 2 requisitos de
  `origen="texto"`. Es la base de SIN_DATOS (§13.2).

- [ ] **Step 1: Build the labeled set.** Con `spike/exploracion/inspeccionar_detalle.py`, scrapear unas 30 páginas
  de detalle de Magneto de áreas variadas: tecnología, datos, administración, comercial, salud, diseño y operativo.
  Para cada una, guardar en `extraccion.yaml` **solo** la sección de requisitos y la descripción (sin datos de
  contacto), el título, las etiquetas y los `esperados` (los requisitos que una persona extraería, con su tipo).
  Incluir al menos 3 vacantes sin sección de requisitos y 2 con solo marketing. **El equipo revisa las etiquetas**
  (§10); se anota en el ledger que están pendientes de revisión.
- [ ] **Step 2: Write the failing tests**

```python
CASOS = cargar_casos()  # extraccion.yaml

def test_cobertura_de_lo_esperado_en_el_set():
    aciertos = total = 0
    for caso in CASOS:
        hallados = {normalizar(r.texto) for r in extraer_requisitos(caso.texto, caso.etiquetas)}
        for esperado in caso.esperados:
            total += 1
            aciertos += any(normalizar(esperado.texto) in h or h in normalizar(esperado.texto) for h in hallados)
    assert aciertos / total >= 0.80

def test_el_ruido_no_entra_como_requisito():
    for caso in CASOS:
        for r in extraer_requisitos(caso.texto, caso.etiquetas):
            assert not RUIDO_DE_PRUEBA.search(r.texto), (caso.id, r.texto)  # $, "importante empresa", "te apasiona"

def test_deseable_por_palabra_guia():
    [r] = extraer_requisitos("Requisitos:\n- Deseable inglés intermedio", [])
    assert r.tipo == "deseable"

def test_etiquetas_son_deseables():
    reqs = extraer_requisitos("Requisitos:\n- Experiencia en ventas de 2 años", ["Canva"])
    assert ("Canva", "deseable", "etiqueta") in {(r.texto, r.tipo, r.origen) for r in reqs}

def test_vacante_solo_marketing_es_insuficiente():
    reqs = extraer_requisitos("Importante empresa del sector te invita a unirte. ¡Te apasiona crecer!", [])
    assert requisitos_insuficientes(reqs)

def test_anios_minimos():
    assert extraer_restricciones("Experiencia mínima de 3 años en cargos similares").anios_minimos == 3
```

- [ ] **Step 3:** Run `.venv/bin/python -m pytest vacantes/tests/test_extraccion.py -v`. Expected: FAIL.
- [ ] **Step 4:** Implementar los modelos (con la migración, que ya trae la extensión de la Task 1) y la extracción.
  Si el 0,80 no se alcanza, se mejora la extracción, **no** el umbral ni el set.
- [ ] **Step 5:** Run `.venv/bin/python -m pytest vacantes -v`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(vacantes): modelo y extracción de requisitos con vocabulario abierto`

### Task 9: Fuentes de vacantes (Strategy) e ingesta incremental

**Files:**
- Create: `vacantes/fuentes/__init__.py` (el puerto), `vacantes/fuentes/fixture.py`,
  `vacantes/fuentes/magneto_detalle.py`, `vacantes/services.py`,
  `vacantes/management/commands/ingerir_vacantes.py`
- Copy: `vacantes/fixtures/vacantes_magneto.json`, desde el tag
- Test: `vacantes/tests/test_ingesta.py`

**Interfaces:**
- Consumes: `extraer_requisitos`, `extraer_restricciones` (Task 8).
- Produces: `VacanteCruda`, una dataclass congelada con `id`, `titulo`, `empresa`, `ubicacion`, `modalidad`,
  `texto_completo`, `etiquetas`, `url`, `fecha_publicacion`, `salario_texto` y `urgente`.
- Produces: `class FuenteVacantes(Protocol): nombre: str; def obtener(self) -> Iterable[VacanteCruda]`.
- Produces: `FuenteFixture(ruta: Path)` y `FuenteMagnetoDetalle(terminos: list[str], por_termino: int)`. Esta
  última usa Playwright: busca, abre **la página de detalle** de cada vacante y toma el texto completo **sin
  truncar**. Se apoya en la lógica de `scrape_magneto.py` (tag) y en `spike/exploracion/inspeccionar_detalle.py`.
- Produces: `ingerir(fuente: FuenteVacantes) -> ResumenIngesta`, donde `ResumenIngesta(creadas, actualizadas,
  sin_cambios, insuficientes)`. `hash_contenido` es el sha256 de `titulo + texto_completo + etiquetas`. Una vacante
  nueva o con un hash distinto se guarda junto con sus requisitos (borrar y recrear) en **una transacción por
  vacante**; con el mismo hash no se toca. El comando es
  `manage.py ingerir_vacantes --fuente fixture|magneto [--terminos ...] [--por-termino N]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_ingesta_crea_vacantes_y_requisitos(db):
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL avanzado\n- Excel")]))
    assert (r.creadas, Requisito.objects.filter(vacante_id="v1").count()) == (1, 2)

def test_misma_vacante_sin_cambios_no_se_toca(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL")]))
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL")]))
    assert r.sin_cambios == 1

def test_vacante_modificada_reemplaza_requisitos_sin_duplicar(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel\n- Python")]))
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- Power BI")]))
    assert list(Requisito.objects.filter(vacante_id="v1").values_list("posicion", "texto")) == [(0, "Power BI")]

def test_una_vacante_que_falla_no_tumba_la_ingesta(db, monkeypatch):
    original = servicios.extraer_requisitos
    def explota_en_v2(texto, etiquetas):
        if "ROMPER" in texto:
            raise ValueError("texto ilegible")
        return original(texto, etiquetas)
    monkeypatch.setattr(servicios, "extraer_requisitos", explota_en_v2)
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL"), cruda("v2", "ROMPER"),
                                 cruda("v3", "Requisitos:\n- Excel")]))
    assert (r.creadas, r.errores) == (2, 1)
    assert set(Vacante.objects.values_list("id", flat=True)) == {"v1", "v3"}

def test_fuente_fixture_lee_las_18_vacantes_de_v2(db):
    assert ingerir(FuenteFixture(RUTA_FIXTURE)).creadas == 18

@pytest.mark.lento
def test_magneto_detalle_trae_texto_sin_truncar():
    [v] = list(FuenteMagnetoDetalle(["analista de datos"], 1).obtener())
    assert len(v.texto_completo) > 500
```

`FuenteEnMemoria` es un fake de test que implementa el puerto. `ResumenIngesta` agrega el campo `errores: int` que
pide el cuarto test.

- [ ] **Step 2:** Run `.venv/bin/python -m pytest vacantes/tests/test_ingesta.py -v -m "not lento"`. Expected: FAIL.
- [ ] **Step 3:** Implementar. El log registra el id de cada vacante fallida y el motivo.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest vacantes -v -m "not lento"`. Expected: PASS. Después correr una
  vez `-m lento` y `manage.py ingerir_vacantes --fuente magneto --terminos "analista de datos" --por-termino 3`, y
  anotar el resumen en el ledger.
- [ ] **Step 5: Commit** `feat(vacantes): fuentes como Strategy e ingesta incremental por hash`

### Task 10: Las demás páginas renderizan con el visual de v2

**Files:**
- Copy without changes from the tag: `dashboard.html`, `detalle.html` e `historial.html` a
  `matching/templates/matching/`; `tablero.html` a `postulaciones/templates/postulaciones/`; `notificaciones.html` a
  `notificaciones/templates/notificaciones/`
- Create: `matching/views.py`, `matching/selectors.py`, `postulaciones/models.py`, `postulaciones/views.py`,
  `notificaciones/models.py`, `notificaciones/views.py`, `notificaciones/context_processors.py` y las `urls.py`
- Test: `matching/tests/test_paginas.py`

**Interfaces:**
- Produces: las rutas `dashboard`, `vacante_detalle`, `historial`, `tablero`, `postularme`,
  `cambiar_estado_postulacion` y `notificaciones`. Cada vista entrega **las mismas claves de contexto** que su
  equivalente en `vacantes/views.py` del tag. En esta fase las colecciones que dependen de decisiones llegan
  vacías, así que los templates muestran el estado vacío que ya tienen. El detalle muestra los datos de la vacante
  y sus requisitos, con las 5 barras en estado "sin datos".
- Produces: `Postulacion` y `Notificacion`, con los campos de v2 y FK a `cuentas.Perfil`. La lógica de postular y
  de mover tarjetas se trae igual que en v2 (HU-08 y HU-10); el registro de resultados es de la Fase 3.
- Produces: el context processor `notificaciones_sin_leer`, de vuelta en `TEMPLATES`.
- **Prohibido** cambiar un template para que acepte el contexto nuevo: si un template exige una clave, la vista la
  entrega.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("ruta,args", [("dashboard", []), ("historial", []), ("tablero", []),
                                        ("notificaciones", []), ("vacante_detalle", ["v1"])])
def test_cada_pagina_renderiza_con_sesion_y_cv(client_con_cv, vacante_v1, ruta, args):
    r = client_con_cv.get(reverse(ruta, args=args))
    assert r.status_code == 200

def test_postular_crea_postulacion_y_aparece_en_tablero(client_con_cv, vacante_v1):
    client_con_cv.post(reverse("postularme", args=["v1"]))
    assert Postulacion.objects.count() == 1
    assert vacante_v1.titulo in client_con_cv.get(reverse("tablero")).content.decode()

def test_ya_no_quedan_rutas_pendientes(client_con_cv):
    assert not hasattr(importlib.import_module("scoutly.views"), "pendiente")
```

- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_paginas.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implementar. Los templates se copian con `git show pre-sprint3-rebuild:<ruta> > <destino>` y se
  verifica con `git diff --no-index` que son idénticos al original, salvo la ruta de `{% extends %}` si cambia.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: toda la suite en verde.
- [ ] **Step 5: Commit** `feat(v3): todas las páginas renderizan con los templates de v2`

### Task 11: Verificación visual antes/después

**Files:**
- Create: `scripts/capturas.py`, `docs/fase1/capturas/` (PNG) y `docs/fase1/VERIFICACION_VISUAL.md`

**Interfaces:**
- Produces: `python scripts/capturas.py --base URL --salida DIR --usuario EMAIL --clave CLAVE`. Inicia sesión con
  Playwright y captura a 1440×900 las páginas login, registro, onboarding, perfil, expectativas, dashboard
  (vacío), historial (vacío), tablero (vacío y con una postulación), notificaciones (vacío) y detalle de una
  vacante.

- [ ] **Step 1:** Levantar v2 desde el tag en un worktree (`git worktree add ../scoutly-v2 pre-sprint3-rebuild`,
  con SQLite, `migrate` y `seed_vacantes`), crear un usuario con el mismo CV ficticio y capturar en `antes/`.
- [ ] **Step 2:** Levantar v3 (`ingerir_vacantes --fuente fixture`), con el mismo usuario y el mismo CV, y capturar
  en `despues/`.
- [ ] **Step 3:** Comparar con Pillow (`ImageChops.difference`) las páginas cuyo estado es equivalente
  (onboarding, perfil, expectativas, tablero, notificaciones e historial vacíos). Se espera menos de 1% de píxeles
  distintos; si hay más, se corrige la vista, nunca el template. El dashboard poblado y el detalle con decisiones
  se comparan en la Fase 2. Login y registro se revisan junto a las capturas de Magneto: misma estructura, marca
  Scoutly.
- [ ] **Step 4:** Escribir `VERIFICACION_VISUAL.md` con la tabla de páginas y su % de diferencia, y borrar el
  worktree.
- [ ] **Step 5: Commit** `docs(fase1): verificación visual antes/después`

## Fuera de esta fase

Lo siguiente queda para fases posteriores (§9 y §13):
- Fase 2: embeddings, la matriz `bytea`, la cobertura, las restricciones, la política, `Decision`, la solidez, el
  Plan de hoy y el dashboard poblado.
- Fase 3: B1 (`job_detail`), el Taller de CV, las notificaciones por correo y la API para n8n.
- Fase 4: el set de evaluación y el benchmark.

Tampoco entra la recuperación de contraseña, que v2 tampoco tenía. Queda anotada como pendiente.
