# Revisión de arquitectura (oh-my-claudecode:architect)

El núcleo del diseño es sólido: un decisor por reglas, determinístico y explicable, que cumple la rúbrica de
patrones, y la Fase 0 muestra que es viable. Pero está **sobredimensionado para 3 personas en un sprint**, y P2
tiene un problema de consistencia entre procesos sin resolver.

## Hallazgos por severidad
1. **CRÍTICO — P2 (matriz en memoria) no funciona con varios procesos ni con deltas diarios.**
   - Cada worker de Django, el batch y n8n tendrían su propia copia de 176 MB, y todas quedarían desactualizadas
     después de cada `importar-vacantes`.
   - El motivo real de P2 es el recall, no la latencia (47 ms contra 6,5 ms no importa). Ese recall de 93% se
     midió con vectores sintéticos y con `relaxed_order` / `max_scan_tuples` ajustables.
   - Casi toda la mejora de 2,85 s a 0,73 s viene de P3, no de P2.
   - **Recomendación:** búsqueda **exacta dentro de Postgres**: escaneo secuencial sobre los 120k vectores
     `halfvec`, sin índice. Da recall de 100%, una sola fuente de verdad y nada que invalidar. *(Pendiente de
     medir.)* Si se mantiene numpy, la matriz se carga al inicio de **cada corrida** del batch, no al arrancar el
     proceso.
2. **ALTO — Dónde viven los modelos.**
   - bge fp32 ocupa 2,3 GB y necesita GPU, así que no puede cargarse en cada worker web.
   - Solo el batch carga los modelos; la web lee `Decision` ya calculadas.
   - **El reranker debe ser opcional**: el propio diseño dice que "solo ordena, no decide". Ordenar por
     similitud × cobertura alcanza para la demo. Así P1 deja de depender de la GPU.
3. **ALTO — P3 duplica la fuente de verdad.**
   - Si una re-ingesta cambia el orden de los requisitos, la fila i del bytea deja de corresponder al requisito i.
   - Hay que escribir los dos en la misma transacción, con una columna `posicion`.
   - `Decision.cobertura` debe guardar el texto del requisito, no su id.
4. **MEDIO — Demasiadas apps.** Pasar de 8 a 5:
   - `ia` → `matching/puertos.py`;
   - `perfiles` se une a `cuentas`;
   - `api` queda como el módulo `api.py`.
   - Se mantienen Strategy, Chain of Responsibility, Adapter y Facade.
   - El "Pipeline con interfaz común" es ceremonia; una fachada que llame las etapas en orden basta.
   - Los selectors solo donde la lectura no sea trivial.
5. **MEDIO — P5.**
   - La frescura y no repetir empresa son **orden y presentación**, no reglas de la cadena.
   - El prefiltro necesita las respuestas del candidato, así que en la práctica daría `sin_datos`: queda para la
     Fase 3.
   - P4 se mantiene si el vector del perfil se arma de la misma forma (promedio de sus unidades de evidencia).

## MCP de Magneto
- **No sirve para traer el catálogo completo de 120k vacantes**: el OAuth es por candidato, no hay cuenta de
  servicio y los límites de uso no están documentados.
- Sí sirve para buscar **por candidato**: el decisor trabaja sobre sus búsquedas y las sugerencias de Mimir. Con
  esto, el argumento de escala pasa a depender del benchmark sintético.
- Es mejor que Playwright: es un canal oficial, y `job_detail` trae el texto completo.
- **Recomendaciones:**
  - `FuenteMagnetoMCP` como otra Strategy de fuente de vacantes.
  - Un puerto `Postulador` con dos implementaciones: la simulada (por defecto) y la del MCP.
  - `job_apply` solo con **confirmación explícita por cada postulación**, nunca automática.
  - `job_applications` alimenta automáticamente `ResultadoDecision`, con un nodo n8n `sincronizar-postulaciones`.
- **Riesgos:** guardar los tokens de refresco cifrados, consentimiento según la Ley 1581, manejar el error 429
  con backoff, revisar los términos de uso y, en la demo, usar solo las cuentas del equipo.

## Los 3 riesgos principales (Fases 1-2)
1. **Extracción de requisitos sobre texto real.** Hacer un set de ~30 vacantes reales con requisitos esperados y
   un test de extracción **antes** de la política.
2. **Umbrales calibrados solo con datos sintéticos.** Adelantar a la Fase 2 la mitad de ajuste del set de
   evaluación.
3. **`decidir` para N candidatos supera los timeouts HTTP de n8n.** El endpoint responde 202 y encola el trabajo,
   que ejecuta un comando de gestión.
