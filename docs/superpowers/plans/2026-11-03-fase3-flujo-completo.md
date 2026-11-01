# Fase 3 (flujo completo) de Scoutly v3: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** completar el ciclo "vacantes → decisión → acción del candidato → resultado". El candidato recibe un Taller
de CV en versión texto para las vacantes de AJUSTAR_CV y una explicación en prosa a pedido (Groq, sin datos del CV).
Hay notificaciones según su preferencia y registro del resultado de cada postulación. n8n orquesta la ingesta, la
decisión y las notificaciones por API, y el registro por correo pasa a ser verificado. B1 (`job_detail` del MCP de
Magneto) queda listo detrás de su puerto, pero **apagado hasta que el equipo revise los términos de uso**.

**Architecture:** se extiende lo existente sin rehacerlo:
- `matching` gana el taller (`matching/taller.py`) y las explicaciones (`matching/explicaciones.py`, Adapter de
  Groq con caché);
- `postulaciones` gana `ResultadoDecision`;
- `notificaciones` gana el servicio que genera notificaciones a partir de `Decision.accion_anterior`/`cambio_en`;
- `api/` (módulo, §13.4) expone los 3 endpoints para n8n con token;
- `vacantes/fuentes/magneto_mcp.py` implementa el puerto de fuentes para B1.

**Tech Stack:** lo de las Fases 1 y 2, más `requests` para Groq (ya está en `requirements.txt`) y el envío de correo
de Django (backend de consola por defecto, SMTP con `.env`).

**Spec:** `docs/superpowers/specs/2026-11-01-scoutly-v3-decisor-design.md`. Aplican §5.5, §5.6, §5.7 (notificación),
§7.4, §13.3 (C texto y B1, orden de corte), §13.4 y §13.5. La §13 manda.

## Global Constraints

- **Ningún texto del CV sale de la máquina (§13.3, §13.5).** A Groq solo van campos de criterio: la acción, los
  conteos, los estados de las restricciones con sus motivos (que no citan el CV), los textos de los requisitos de la
  vacante (que son públicos) y su estado. **Nunca la evidencia** ni el nombre o el correo.
- **El Taller nunca inventa (§13.3).** Cada sugerencia sale de un requisito *parcial* que **tiene** evidencia, y la
  muestra ("tu evidencia: «…»"). El candidato acepta o rechaza cada una. Sin evidencia no hay sugerencia. No hay
  PDF: se entrega texto para copiar.
- **Notificaciones (§5.7):** se notifica una vacante POSTULAR *nueva*, es decir, la que hoy es POSTULAR y antes no lo
  era o no estaba entre las relevantes (`accion_anterior != "POSTULAR"`, incluido `"NUEVA"`) **y cambió hoy**
  (`cambio_en` de hoy). La campana muestra todas. Por correo se respeta la preferencia: `resumen` (por defecto, un
  solo correo), `individual` (como máximo N al día, por defecto 3) o `desactivado`.
- **API para n8n (§7.4, §13.4):** `POST /api/importar-vacantes`, `POST /api/decidir` y
  `POST /api/generar-notificaciones`, con el header `X-Scoutly-Token` comparado con `hmac.compare_digest`. Sin
  DEBUG, el token de desarrollo se rechaza (como en v2). `decidir` responde **202** y solo encola. La web nunca
  carga modelos.
- **B1 (§13.3):** apagado por defecto (`SCOUTLY_MAGNETO_MCP` vacío). Es de solo lectura (`job_detail`): no hay
  `job_apply` ni `job_applications`. Los tokens OAuth se guardan **cifrados** (Fernet, con la clave en el entorno).
- **Visual:** a los templates de v2 solo se les agregan bloques. Los nuevos (taller, verificación) usan el vocabulario
  CSS existente y las clases `decision-*`/`auth-*`.
- TDD con pytest-django y el embedder falso. Groq y Magneto se reemplazan en los tests por fakes, sin red.

## Decisiones del builder (reversibles; van al ledger como Ruling)

- **D1. Las sugerencias del Taller no modifican el CV guardado.** Son texto para *esa* postulación; si el candidato
  quiere que cambie su perfil, vuelve a cargar el CV. Así nada que el candidato no subió entra a la evidencia.
- **D2. La explicación de Groq se carga aparte** (`GET /vacantes/<id>/explicacion`, un fragmento HTML) cuando el
  candidato pulsa "Explícamelo". Así el detalle nunca espera a Groq, y la explicación queda en caché por
  `(decision, version_politica, hash de los insumos)`.
- **D3. La ingesta pedida por n8n corre en un hilo** con un candado de base de datos (`pg_try_advisory_lock`):
  devuelve 202, o 409 si ya hay una en curso. No hace falta un broker de colas en el sprint.
- **D4. Verificación de correo:** las cuentas creadas con correo quedan inactivas hasta abrir un enlace firmado
  (`django.core.signing`, válido 3 días). Las cuentas sociales ya entran verificadas por su proveedor. Esto cierra el
  pendiente de la revisión de la Fase 1 (registrar un correo ajeno).
- **D5. "Tu mercado" (D, §13.3) es una tarjeta del dashboard** calculada en el batch y guardada en `FotoDiaria`:
  cuántas vacantes son relevantes, el rango de salarios y las empresas que más publican.

## Review Focus

1. **Un candidato que pide `individual` con N = 3 y tiene 10 vacantes POSTULAR nuevas el mismo día.** Le llegan 3
   correos y las 10 quedan en la campana. Volver a correr `generar-notificaciones` ese día no duplica nada (Task 4).
2. **Volver a decidir dos veces el mismo día.** Una vacante que ya se notificó como POSTULAR en la mañana no se
   vuelve a notificar en la tarde (Task 4).
3. **Una vacante AJUSTAR_CV cuyo requisito parcial tiene una evidencia vieja** (el CV cambió después de decidir).
   El Taller no muestra sugerencias con una evidencia que el CV actual ya no tiene (Task 2).
4. **Groq caído, lento o sin clave.** La explicación cae a un texto de respaldo armado con los motivos, sin error
   500 y en 8 s o menos (Task 3).
5. **Un enlace de verificación vencido, alterado o usado dos veces.** Muestra un mensaje claro y permite pedir uno
   nuevo, sin activar una cuenta ajena (Task 6).

---

### Task 1: Registro del resultado de cada decisión (§5.5)

**Files:**
- Modify: `postulaciones/models.py`, `postulaciones/services.py`
- Test: `postulaciones/tests/test_resultados.py`

**Interfaces:**
- Produces: `ResultadoDecision`, con `postulacion` (FK, CASCADE), `resultado` (`"entrevista"` o `"descartado"`),
  `accion`, `solidez`, `cobertura_pct`, `version_politica`, `insumos` (json: copia de `cobertura` y `restricciones`
  de la `Decision` en ese momento) y `registrado_en`.
- Produces: `cambiar_estado(postulacion, estado)` crea un `ResultadoDecision` cuando el estado nuevo es
  `entrevista` o `descartado` y existe una `Decision` para ese par. Si el par no tiene decisión, el resultado se guarda
  con `accion=""`.

- [ ] **Step 1: Write the failing tests**:
  - `test_pasar_a_entrevista_registra_el_resultado_con_los_insumos`: `accion`, `cobertura_pct` y `version_politica`
    salen de la `Decision`, e `insumos["cobertura"]` es igual al de la decisión;
  - `test_en_revision_no_registra_resultado`;
  - `test_sin_decision_registra_igual_sin_accion`;
  - `test_volver_a_entrevista_no_duplica`, que mira el último resultado por postulación y estado.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest postulaciones -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar, con su migración.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `feat(postulaciones): registro del resultado de cada decisión`

### Task 2: Taller de CV en versión texto (C, §13.3)

**Files:**
- Create: `matching/taller.py`, `matching/templates/matching/taller.html`
- Modify: `matching/models.py` (`SugerenciaCV`), `matching/views.py`, `matching/urls.py`,
  `matching/templates/matching/detalle.html` (agregar el botón "Abrir el taller de CV" si la acción es AJUSTAR_CV)
- Test: `matching/tests/test_taller.py`

**Interfaces:**
- Produces: `SugerenciaCV`, con `perfil`, `vacante`, `tipo` (`"requisito"` o `"resumen"`), `requisito`,
  `evidencia`, `propuesta`, `estado` (`"pendiente"`, `"aceptada"` o `"rechazada"`) y `creada_en`. Es única por
  `(perfil, vacante, tipo, requisito)`.
- Produces: `generar_sugerencias(decision, evidencias_actuales: list[str]) -> list[SugerenciaCV]`. No guarda nada y
  sigue estas reglas:
  - **Por cada requisito parcial** cuya evidencia esté entre las actuales (Review Focus 3), la propuesta es
    `"{evidencia sin punto final} ({requisito})."`, con el aviso **"solo si es verdad"**.
  - **Una sugerencia de resumen** cuando hay 2 o más requisitos cubiertos:
    `"Resumen sugerido: experiencia en {cubierto 1}, {cubierto 2} y {cubierto 3}."`, armada solo con los textos de
    los requisitos cubiertos (máximo 3).
- Produces: `taller(perfil, vacante) -> list[SugerenciaCV]`, que sincroniza sin borrar las aceptadas o rechazadas;
  `responder(sugerencia, acepta: bool)`; y `texto_adaptado(perfil, vacante) -> str`, que junta las aceptadas para
  copiar.
- Rutas:
  - `vacantes/<id>/taller` (GET): solo con sesión y solo si hay una `Decision` del candidato;
  - `vacantes/<id>/taller/<sugerencia_id>` (POST, con `acepta` en `1` o `0`): solo sobre sugerencias del propio
    candidato.

- [ ] **Step 1: Write the failing tests**:
  - `test_sugerencia_por_requisito_parcial_con_su_evidencia`;
  - `test_sin_evidencia_no_hay_sugerencia` (el faltante va al plan de aprendizaje);
  - `test_evidencia_que_ya_no_esta_en_el_cv_no_se_sugiere`;
  - `test_resumen_solo_con_requisitos_cubiertos`;
  - `test_aceptar_y_rechazar_y_texto_para_copiar`;
  - `test_no_se_puede_responder_la_sugerencia_de_otro` (404);
  - `test_la_pagina_avisa_que_el_cv_debe_ser_verdadero` (contiene "Solo acepta lo que sea verdad");
  - `test_el_detalle_ofrece_el_taller_solo_en_ajustar_cv`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_taller.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar, con la migración y el template (extiende `base.html`; clases `card`, `requirement-item`
  y `decision-*`).
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS, con el test de "solo agrega
  líneas" todavía en verde.
- [ ] **Step 5: Commit** `feat(matching): taller de CV en versión texto`

### Task 3: Explicación en prosa a pedido con Groq (§5.6)

**Files:**
- Create: `matching/explicaciones.py`, `matching/templates/matching/_explicacion.html`
- Modify: `matching/puertos.py` (`Redactor`), `matching/ia/__init__.py` (`obtener_redactor()`),
  `matching/ia/groq.py`, `matching/ia/fakes.py` (`RedactorFalso`), `matching/models.py` (`ExplicacionDecision`),
  `matching/views.py`, `matching/urls.py`, `detalle.html` (agrega el botón "Explícamelo" y un contenedor que lo
  carga con `fetch`)
- Test: `matching/tests/test_explicaciones.py`

**Interfaces:**
- Produces: `class Redactor(Protocol): def redactar(self, insumos: dict) -> str | None` (`None` si falla).
  `RedactorGroq(api_key, modelo=settings.SCOUTLY_GROQ_MODELO, timeout=8)` usa
  `https://api.groq.com/openai/v1/chat/completions`, con el modelo por defecto `"qwen/qwen3.8-27b"`, el que funcionaba
  en v2.
- Produces: `insumos_publicos(decision) -> dict`, con `accion`, `solidez`, `cobertura_pct`,
  `requisitos: [{texto, estado}]` (de `decision.cobertura`, **sin `evidencia`**) y
  `restricciones: [{criterio, estado, motivo}]`.
- Produces: `explicar(decision, redactor) -> str`. Cachea en `ExplicacionDecision(decision, firma, texto)`, con
  `firma = sha256(insumos_publicos)`. Si `redactor` es `None` o devuelve `None`, arma un respaldo con los motivos de
  la decisión.
- Ruta `vacantes/<id>/explicacion` (GET, con sesión): devuelve el fragmento `_explicacion.html`.

- [ ] **Step 1: Write the failing tests**:
  - `test_a_groq_nunca_va_la_evidencia_ni_el_nombre`: un `RedactorFalso` captura los insumos, y en su
    `json.dumps` no aparecen la evidencia del CV, el nombre ni el correo;
  - `test_se_cachea_y_no_se_repite_la_llamada`;
  - `test_si_cambian_los_insumos_se_regenera`;
  - `test_groq_caido_usa_el_respaldo` (`RedactorFalso(falla=True)`);
  - `test_groq_lento_respeta_el_timeout`: se usa `requests` con un mock que lanza `Timeout`, y debe devolver el
    respaldo;
  - `test_la_explicacion_requiere_sesion_y_decision_propia`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest matching/tests/test_explicaciones.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar. La privacidad (`/privacidad`) ya dice que a Groq solo van campos de criterio; se
  actualiza "en una fase posterior" → "cuando pides una explicación", lo que sube `VERSION_POLITICA`.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(matching): explicación a pedido con Groq (sin datos del CV)`

### Task 4: Notificaciones con preferencia del candidato (§5.7)

**Files:**
- Modify: `cuentas/models.py` (`Perfil.notif_modo` con choices `resumen` (por defecto), `individual` y
  `desactivado`, y `Perfil.notif_max` (por defecto 3)), `cuentas/forms.py` (`ExpectativasForm` gana los dos campos),
  `cuentas/templates/cuentas/expectativas.html` (solo se agregan los dos campos), `notificaciones/services.py`,
  `notificaciones/models.py`
- Test: `notificaciones/tests/test_generar.py`

**Interfaces:**
- Produces: `generar_notificaciones(hoy: date | None = None) -> ResumenNotificaciones`, con
  `ResumenNotificaciones(creadas, correos)`. Por cada perfil:
  - crea una `Notificacion` (es idempotente gracias a la restricción única `perfil, vacante, fecha`) por cada
    `Decision` con `accion="POSTULAR"`, `accion_anterior != "POSTULAR"` y `cambio_en` de hoy;
  - envía correo según `notif_modo`: `resumen` = 1 correo con todas; `individual` = como máximo `notif_max` correos;
    `desactivado` = ninguno;
  - marca `enviada=True` solo en las enviadas.

  `score_pct` = `cobertura_pct`, y el mensaje es `"Nueva vacante para postular: {titulo} en {empresa}"`.
- Produces: `enviar_correo(perfil, asunto, cuerpo) -> bool`, con `send_mail` y el remitente `DEFAULT_FROM_EMAIL`. Si
  el perfil no tiene correo, devuelve `False` (`puede_notificar`).

- [ ] **Step 1: Write the failing tests** (con `mail.outbox`):
  - `test_solo_notifica_postular_nuevo_de_hoy`, con 4 decisiones: POSTULAR/NUEVA de hoy, POSTULAR/POSTULAR (sin
    cambio), POSTULAR/AJUSTAR_CV de ayer y AJUSTAR_CV/NUEVA. Solo cuenta la primera;
  - `test_resumen_envia_un_solo_correo_con_todas`;
  - `test_individual_respeta_el_maximo_y_la_campana_las_tiene_todas` (Review Focus 1);
  - `test_desactivado_no_envia_correo_pero_si_campana`;
  - `test_correr_dos_veces_no_duplica` (Review Focus 1 y 2);
  - `test_redecidir_el_mismo_dia_no_renotifica` (Review Focus 2: la segunda corrida deja `accion_anterior="POSTULAR"`);
  - `test_la_preferencia_se_guarda_desde_expectativas`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest notificaciones -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar, con las migraciones.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(notificaciones): nuevas vacantes para postular según la preferencia del candidato`

### Task 5: API para n8n y workflow (§7.4, §13.4)

**Files:**
- Create: `api/autenticacion.py`, `api/views.py`, `api/urls.py`
- Modify: `scoutly/urls.py`, `n8n/workflow-matches-diarios.json` (nodos `importar-vacantes` → `decidir` →
  `generar-notificaciones`), `n8n/README.md`
- Test: `api/tests/test_api.py`

**Interfaces:**
- Produces: `token_valido(request) -> JsonResponse | None`, la lógica de v2: 401 si el token no coincide; 503 si no
  hay DEBUG y el token es el de desarrollo. Las vistas son `csrf_exempt` y solo aceptan POST:
  - `importar_vacantes` responde 202 y lanza `ingerir(FuenteMagnetoDetalle(...))` en un hilo protegido con
    `pg_try_advisory_lock`. Si el candado está tomado, responde 409. El cuerpo JSON puede traer `terminos` y
    `por_termino`;
  - `decidir` encola una `SolicitudDecision` por cada perfil con CV y responde **202**
    `{"encolados": n}`. No carga modelos;
  - `generar_notificaciones` llama a `notificaciones.services.generar_notificaciones()` y responde 200 con el resumen.
- n8n: los 3 nodos HTTP en ese orden, con un timeout de 10 min para la ingesta (como en v2). El README explica que
  `decidir --escuchar` debe estar corriendo.

- [ ] **Step 1: Write the failing tests**:
  - `test_sin_token_401`;
  - `test_token_de_desarrollo_rechazado_sin_debug` (503);
  - `test_decidir_encola_y_responde_202_sin_cargar_modelos`;
  - `test_importar_responde_202_y_409_si_ya_corre`, con la fuente reemplazada por una `FuenteEnMemoria` lenta y el
    hilo esperado con `join` en el test;
  - `test_generar_notificaciones_devuelve_el_resumen`;
  - `test_solo_post` (405);
  - `test_el_workflow_llama_los_tres_endpoints_en_orden`, que lee el JSON y comprueba las URLs y el orden de las
    conexiones.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest api -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(api): endpoints para n8n (ingesta, decidir 202, notificaciones) y workflow`

### Task 6: Verificación del correo al registrarse (D4)

**Files:**
- Modify: `cuentas/views_auth.py`, `cuentas/services.py`, `cuentas/urls.py`,
  `cuentas/templates/cuentas/registro.html` (estado "Revisa tu correo")
- Create: `cuentas/templates/cuentas/verificacion.html`
- Test: `cuentas/tests/test_verificacion.py`

**Interfaces:**
- Produces: `enviar_verificacion(usuario, request) -> None`, que manda el enlace firmado
  (`signing.dumps({"u": pk, "e": email}, salt="verificacion")`). `verificar(token) -> Usuario`, con
  `max_age = 3 días`. Lanza `EnlaceInvalido` o `EnlaceVencido`, y activa la cuenta (`is_active=True`).
- El registro por correo crea el usuario con `is_active=False` y muestra "Te enviamos un enlace a {email}". El login
  de una cuenta sin verificar dice "Confirma tu correo para entrar" con "Reenviar enlace" (la misma respuesta para un
  correo inexistente, sin revelar nada). Las cuentas sociales quedan activas.
- Rutas: `cuentas/verificar/<token>` (GET) y `cuentas/verificar/reenviar` (POST).

- [ ] **Step 1: Write the failing tests**:
  - `test_registro_deja_la_cuenta_inactiva_y_envia_el_enlace`;
  - `test_el_enlace_activa_y_permite_entrar`;
  - `test_enlace_alterado_vencido_o_reusado` (Review Focus 5);
  - `test_reenviar_no_revela_si_el_correo_existe`;
  - `test_el_enlace_de_otro_usuario_no_activa_la_mia`;
  - `test_cuentas_sociales_no_necesitan_verificacion`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest cuentas/tests/test_verificacion.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implementar. En `/privacidad` se agrega "te enviamos un correo para confirmar tu cuenta", lo que
  sube la versión.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q -m "not lento"`. Expected: PASS (los tests de login y registro
  existentes se ajustan para verificar antes de entrar, con una línea en el ledger).
- [ ] **Step 5: Commit** `feat(cuentas): verificación del correo al registrarse`

### Task 7: Tarjeta "Tu mercado" (D5)

**Files:**
- Modify: `matching/models.py` (`FotoDiaria.mercado` json), `matching/services.py` (calcula el mercado en
  `_guardar`), `matching/selectors.py`, `matching/views.py`, `dashboard.html` (solo agrega la tarjeta)
- Test: `matching/tests/test_mercado.py`

**Interfaces:**
- Produces: en `FotoDiaria.mercado`: `{"relevantes": n, "salario_min": int|None, "salario_max": int|None,
  "empresas": [[nombre, n], ...hasta 3]}`, calculado sobre las vacantes relevantes que **no** son DESCARTAR.
  `selectors.mercado(perfil) -> dict | None`.
- La tarjeta dice "{n} vacantes relevantes para ti · salarios de $ X a $ Y · más publican: A, B, C".

- [ ] **Step 1: Write the failing tests**: `test_mercado_excluye_descartar`; `test_mercado_sin_salarios`;
  `test_la_tarjeta_aparece_en_el_dashboard`.
- [ ] **Step 2–4:** fallan, se implementa y pasan (`.venv/bin/python -m pytest matching -q -m "not lento"`).
- [ ] **Step 5: Commit** `feat(matching): tarjeta "Tu mercado"`

### Task 8: B1, `job_detail` del MCP de Magneto, apagado por defecto (§13.3)

**Bloqueo:** el equipo no ha revisado los términos de uso de Magneto. Esta tarea deja el adaptador probado con fakes
y el flujo OAuth del candidato, pero **no se activa** (`SCOUTLY_MAGNETO_MCP` vacío) hasta que el equipo lo apruebe.

**Files:**
- Create: `vacantes/fuentes/magneto_mcp.py`, `cuentas/oauth_magneto.py`,
  `cuentas/templates/cuentas/conectar_magneto.html`
- Modify: `cuentas/models.py` (`ConexionMagneto`), `matching/templates/matching/detalle.html` (agrega un bloque
  "Preguntas de la empresa" con las de `vacante.prefiltro`), `requirements.txt` (`cryptography`), `.env.example`
- Test: `vacantes/tests/test_magneto_mcp.py`, `cuentas/tests/test_conexion_magneto.py`

**Interfaces:**
- Produces: `class ClienteMCP(Protocol): def job_detail(self, vacante_id: str) -> dict`. `ClienteMCPHttp(token)`
  llama a `tools/call` con JSON-RPC sobre HTTP en `https://api.magneto365.com/mcp/candidates`, con
  `Authorization: Bearer`; `ClienteMCPFalso(respuestas)` sirve a los tests.
- Produces: `FuenteMagnetoMCP(cliente: ClienteMCP, ids: list[str])`, que implementa `FuenteVacantes`. De cada
  `job_detail` arma una `VacanteCruda` con el texto completo y guarda las preguntas en `Vacante.prefiltro`
  (`ingerir` gana ese campo).
- Produces: `ConexionMagneto(usuario, token_cifrado, expira_en)`, con un token cifrado con Fernet (la clave sale de
  `SCOUTLY_CLAVE_TOKENS`) y que se puede revocar (botón "Desconectar"). El flujo OAuth 2.1 con PKCE vive en
  `cuentas/oauth_magneto.py`, y sus URLs y el `client_id` salen del entorno.
- `manage.py ingerir_vacantes --fuente magneto-mcp` existe en el registro de estrategias, pero **falla con un
  mensaje claro** si `SCOUTLY_MAGNETO_MCP` no está activado.

- [ ] **Step 1: Write the failing tests**:
  - `test_job_detail_se_convierte_en_vacante_cruda_con_prefiltro`;
  - `test_el_token_se_guarda_cifrado` (el valor de la base no contiene el token);
  - `test_desconectar_borra_el_token`;
  - `test_la_fuente_mcp_esta_apagada_por_defecto`;
  - `test_el_detalle_muestra_las_preguntas_de_la_empresa`;
  - `test_un_429_reintenta_con_espera`.
- [ ] **Step 2–4:** fallan, se implementa y pasan.
- [ ] **Step 5: Commit** `feat(vacantes): fuente MCP de Magneto (job_detail) apagada hasta revisar términos`

### Task 9: De punta a punta y documentación

**Files:**
- Test: `api/tests/test_flujo_n8n.py`
- Modify: `README.md`, `docs/fase3/FLUJO.md` (nuevo)

- [ ] **Step 1: Write the test** `test_flujo_diario_como_n8n`. Llama en orden a `POST /api/importar-vacantes` (con
  una fuente en memoria), `POST /api/decidir` y `decidir --pendientes` (el batch, con el embedder falso), y después
  a `POST /api/generar-notificaciones`. Al final, el candidato tiene decisiones, una notificación POSTULAR nueva y un
  correo según su preferencia. Se le pasa un tablero a "entrevista" y queda un `ResultadoDecision`.
- [ ] **Step 2:** Run. Expected: PASS.
- [ ] **Step 3:** En `docs/fase3/FLUJO.md`, un diagrama Mermaid del ciclo diario (n8n → API → batch → web → correo)
  y cómo levantarlo: `levantar.sh`, `runserver --insecure`, `decidir --escuchar` y n8n.
- [ ] **Step 4: Commit** `docs(fase3): flujo diario de punta a punta`

## Fuera de esta fase

- **Fase 4:**
  - rebalancear y correr la mitad de prueba;
  - evaluación ciega con reclutadores;
  - `benchmark_escala`;
  - un set nuevo de extracción.
- **B2 y medición real de entrevistas** (`job_apply` y `job_applications`), solo si los términos de uso lo permiten.
- **El PDF del Taller.**
- **La migración de `EMAIL_*` a `MAILERS`:** solo genera advertencias de deprecación.
