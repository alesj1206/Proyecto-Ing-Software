# Fase 4: verificación de punta a punta y visual

Fecha: 2026-11-01. Política `2026-11-04.2`, en esta máquina, con Postgres en Podman y n8n en Podman.

## 1. El flujo diario con n8n real

Se usó el workflow `n8n/workflow-matches-diarios.json` de v3, cargado en la instancia local de n8n, y se lanzó una
ejecución manual (la ejecución 6). Django corría con `runserver --insecure 0.0.0.0:8000` (en una red de confianza y sin DEBUG; ver `n8n/README.md`) y el batch con
`manage.py decidir --escuchar`.

Log de Django (los tres nodos en cadena):

```
"POST /api/importar-vacantes HTTP/1.1" 202 30
"POST /api/decidir HTTP/1.1" 202 16
"POST /api/generar-notificaciones HTTP/1.1" 200 28
```

Log del batch (`decidir --escuchar`). Después de que la ingesta en segundo plano terminó, el batch decidió y notificó:

```
perfil 1: 60 relevantes {CERRAR_BRECHA: 18, DESCARTAR: 19, SIN_DATOS: 19, POSTULAR: 2, AJUSTAR_CV: 2} en 0.05 s
perfil 261: 60 relevantes {DESCARTAR: 29, AJUSTAR_CV: 2, CERRAR_BRECHA: 7, SIN_DATOS: 19, POSTULAR: 3} en 0.08 s
Subject: 3 vacantes nuevas para postular
To: demo-fase4@correo-ficticio.co
```

- **Ingesta:** la ingesta real de magneto365.com terminó (EstadoIngesta libre) y encoló una decisión por perfil.
- **Decisión:** el batch decidió para los dos perfiles con CV de la base de desarrollo.
- **Notificaciones:** el resumen salió para cada perfil con POSTULAR nuevas.
- **Token:** antes de configurar n8n, una llamada de prueba sin token a `generar-notificaciones` respondió 401, como
  debe.

**El correo salió por la consola, no por SMTP**, a propósito. Las dos cuentas de la base de desarrollo tienen direcciones
ficticias (`@ejemplo.com` y `@correo-ficticio.co`), y con SMTP real los correos irían a dominios ajenos. La prueba con
un buzón real queda para el usuario: registrarse con su correo (lo que además prueba el correo de verificación),
cargar un CV y disparar el workflow.

El token de n8n de esta verificación se generó solo para esta corrida. Para dejarlo fijo hay que poner
`N8N_SCORING_TOKEN` en el `.env` y el mismo valor en los tres nodos.

## 2. Visual

Las capturas están en `docs/fase4/capturas/`. Se tomaron con Playwright y Chrome a 1366×900, con una cuenta de
demostración que tiene el CV ficticio `datos_junior`. El navegador de chrome-devtools-mcp estaba ocupado por otra
sesión.

| Página | Contra | Resultado |
|---|---|---|
| login, registro | `docs/fase1/capturas/despues` | igual: el login tipo Magneto de la Fase 1 |
| dashboard | `docs/fase2/capturas/dashboard.png` | misma estructura; se agrega la tarjeta "Tu mercado" (Fase 3) |
| detalle (POSTULAR y AJUSTAR_CV) | `docs/fase2/capturas/detalle.png` | igual, con "Explícamelo" y el acceso al Taller (Fase 3) |
| taller | (nuevo en la Fase 3) | usa el vocabulario visual existente |
| historial, postulaciones, perfil, expectativas, notificaciones | Fase 1 | iguales |

No hay regresiones visuales.

## 3. Hallazgo: una sugerencia del Taller sin sentido

En la captura `taller.png`, la cuenta de demostración (analista de datos) recibe AJUSTAR_CV en "Asesor Comercial Retail
- Sin Experiencia". El Taller le sugiere:

> Diseñé tableros en Power BI para el área comercial (Validación de experiencia en tiendas de ropa calzado accesorios
> maletas marroquinería o electrodomésticos).

La evidencia no respalda ese requisito. Es el mismo problema que mide la evaluación (`EVALUACION.md`): "parcial" se
decide con diferencias de similitud de pocas centésimas. Aquí el riesgo es mayor, porque el Taller convierte ese
"parcial" en una frase que el candidato podría copiar. El aviso "Solo acepta lo que sea verdad" y el botón Rechazar
son la salvaguarda actual. Hay un arreglo posible que no se hizo: exigir una similitud mínima más alta entre evidencia y
requisito para sugerir (por ejemplo, la de "cubierto") o mostrar solo sugerencias de requisitos de herramienta.

## 4. Efecto del umbral de relevancia en la interfaz (revisión final)

Con τ_relevancia en 0,25, casi todo el catálogo cuenta como "relevante": en esta verificación, 60 de unas 60 vacantes.
La revisión final encontró tres efectos en la interfaz:
- **"Tu mercado":** inflaba el número y el rango de salarios.
- **El plan de aprendizaje:** se llenaba de brechas de áreas ajenas.
- **El Plan de hoy y el Taller:** pueden trabajar sobre vacantes poco relacionadas. Así se explica el ejemplo de
  "Asesor Comercial Retail" de arriba.

Arreglo parcial (política .3): "Tu mercado" y el plan de aprendizaje solo cuentan vacantes con similitud ≥ 0,40
(`SIMILITUD_CERCANA` en `matching/services.py`). El Plan de hoy y el Taller siguen usando el conjunto amplio. Es una
de las dos mejoras que se exploran aparte.

## Repetición del flujo de n8n con la política vigente (2026-11-03)

Se usó `n8n/workflow-matches-diarios.json` en un contenedor temporal de n8n, sin tocar la instancia local, contra una copia
del catálogo real (2.457 vacantes) con correo por consola y un token de un solo uso.

| Nodo | Respuesta |
|---|---|
| 0. Importar vacantes | 202, `{"estado": "ingesta iniciada"}` |
| 1. Decidir | 202, `{"encolados": 3}` |
| 2. Generar notificaciones | 200, `{"creadas": 0, "correos": 0}` |

- **Sin token:** la API respondió 401.
- **Notificaciones:** el nodo 2 dio 0 porque corre antes de que el batch termine. Después el batch decidió los 3 perfiles,
  embebió la vacante actualizada y creó 60 avisos con 3 correos de "20 vacantes nuevas para postular". Sin trazas de error.
- **Diferencias con el flujo diario:** el disparador de horario se cambió por uno manual (la CLI de n8n no arranca desde
  uno de horario), el nodo 0 pidió 1 término y 2 vacantes en vez de los valores por defecto, y la URL apuntó a la copia.
- **Sin probar:** el disparador de las 6 a. m. y el flujo con la web real de `scoutly-web`, que escucha solo en
  `127.0.0.1:8000` y no se alcanza desde un contenedor en su red normal (ver `n8n/README.md`).

