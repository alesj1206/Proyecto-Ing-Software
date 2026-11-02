# Fase 4: verificación de punta a punta y visual

Fecha: 2026-11-01. Política `2026-11-04.2`, en esta máquina, con Postgres en Podman y n8n en Podman.

## 1. El flujo diario con n8n real

Se usó el workflow `n8n/workflow-matches-diarios.json` de v3, cargado en la instancia local de n8n, y se lanzó una
ejecución manual (la ejecución 6). Django corría con `runserver --insecure 0.0.0.0:8000` y el batch con
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
