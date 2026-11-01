# Revisión de seguridad y privacidad (oh-my-claudecode:security-reviewer)

**Riesgo global: ALTO.** La v2 se expone por túnel con DEBUG activo y recibe hojas de vida reales.

## Código v2 (pendiente de decisión del equipo, no se tocó)
1. **CRÍTICO.** `scoutly/settings.py:34-41` tiene la `SECRET_KEY` fija y versionada en el repo, `DEBUG=True` y
   `ALLOWED_HOSTS='*'`. Cualquier error, a través del túnel, le muestra a internet tracebacks con datos del CV, y
   con esa clave se pueden falsificar datos firmados (por ejemplo, los tokens de restablecimiento de contraseña).
   **Arreglo:** leer la clave y DEBUG de variables de entorno, rotar la clave, poner hosts explícitos y activar
   `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` y `SECURE_PROXY_SSL_HEADER`.
2. **ALTO.** pypdf 6.16.1 tiene 26 CVE (corregidas en 6.21.4 o superior) y Django 6.1 tiene PYSEC-2026-3717
   (corregido en 6.1.1). `requirements.txt` no fija versiones.
3. **ALTO.** La subida de PDF no tiene límite de tamaño ni de páginas (`forms.py:11`, `cv_parser.py:128-130`, con
   un `except Exception` que oculta los errores), así que un PDF malicioso puede tumbar el servidor.
   **Arreglo:** máximo 5 MB, verificar que empiece por `%PDF-` y leer solo las primeras 10 páginas.
4. **MEDIO.** El token de n8n de desarrollo es conocido y sigue siendo válido con DEBUG activo, y permite lanzar
   Chrome a voluntad (DoS).
5. **MEDIO.** Las contraseñas pueden tener 6 caracteres y solo hay un validador.
6. **MEDIO.** `/.env` es legible por todos los usuarios (0644).

**Lo que está bien:** el historial de git no tiene secretos reales, el token se compara con
`hmac.compare_digest`, las vistas filtran por perfil y a Groq no se le envían el nombre ni el correo.

## Lo que la spec v3 debe agregar (Ley 1581 y Circular SIC 002/2024)
- **Autorización previa, expresa e informada** al registrarse, guardando la versión del texto, la fecha y la
  finalidad. Debe mencionar el uso de IA y la transferencia de datos a Groq, en EE. UU.
- **Minimización antes de embeber:** quitar nombre, foto, edad, cédula, teléfono, dirección, género y estado
  civil. A Groq solo se le envían los campos de criterio, nunca el CV.
- **Supresión:** un botón "eliminar mi cuenta" que borre en cascada, más un plazo de retención para perfiles
  inactivos.
- **Evaluación de impacto:** documentar que la decisión es automatizada y ofrecer revisión humana.
- **Postulaciones reales con el MCP de Magneto:**
  - tokens OAuth cifrados, con la clave en una variable de entorno, alcance mínimo y revocables;
  - confirmación por cada postulación (POST con CSRF y resumen de lo que se envía; nada en lote ni desde n8n);
  - registro de auditoría;
  - el decisor solo puede **sugerir** POSTULAR, nunca ejecutarlo.

## Infra de la Fase 0 (corregido)
- Postgres escuchaba en `*:5433`, expuesto a la red local. Ahora solo escucha en `127.0.0.1`.
- `infra/postgres/.env` era 0644. Ahora es 0600.
