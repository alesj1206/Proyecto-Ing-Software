# Fase 4: decisiones tomadas y pendientes menores

Estas son las decisiones que tomó el equipo de desarrollo (Claude) durante la Fase 4, cada una con lo que cuesta si
estuvo mal. Las marcadas **(usuario)** las tomó el usuario. Al final están los pendientes menores que no se
arreglaron.

## Decisiones del usuario

1. **(usuario)** La prueba 1 dio 46%. Se corrigió el decisor y se midió con una prueba nueva de vacantes nunca vistas.
   La prueba 1 pasó a llamarse `prueba_1` y quedó solo como validación.
2. **(usuario)** La prueba nueva dio 50% (46% sin los clones). Se reporta tal cual: el decisor se presenta como un buen
   filtro y las acciones finas como orientativas. No hubo más rondas de ajuste.
3. **(usuario)** Tope de 3.000 vacantes por candidato. Con MiniLM casi todo el catálogo supera el umbral de relevancia,
   y 3.000 es lo que asume la spec en §6.

## Decisiones del equipo de desarrollo

### Código
- **Taller:** `taller()` no se cambió porque `get_or_create` ya tolera dos GET simultáneos. Lo cubre una prueba.
  *Costo:* si la Fase 3 vio otro caso, sigue abierto.
- **Regla de prácticas: cuándo no aplica.** Devuelve "no aplica" (None) en vez de agregar una fila "estudiante" a cada
  decisión. *Costo:* quien itere las restricciones debe filtrar los None.
- **Regla de prácticas: qué la activa.** Solo palabras de rol en el título (practicante, aprendiz, pasante, "práctica
  profesional/académica" al inicio) o "contrato de aprendizaje" en la descripción. "Estudiante de…" no la activa,
  porque suele ser una alternativa. *Costo:* una vacante solo para estudiantes sin esas palabras no se filtra.
- **"Aprendiz" sigue activando la regla:** en Colombia casi siempre es el contrato de aprendizaje SENA. *Costo:* un
  "aprendiz de cocina" que no sea SENA descartaría a quien no estudia.
- **Enumeraciones:** las que usan "o" no se separan, porque son alternativas.
- **Listas entre paréntesis:** cuando son herramientas ("(RPG/ILE, Java, DB2 y Git)"), los ítems reemplazan la línea
  y heredan si eran deseables. Los lugares y las siglas cortas no se separan. *Costo:* se pierde el contexto de la
  frase.
- **Pie de Magneto:** el bloque "Otras habilidades" deja de contar como requisito, aunque quitarlo daba un par más.
  Así lo pide la spec (§13.2: las etiquetas son señales). *Costo:* ~1 par en la evaluación.
- **Umbrales:** τ_alto 0,45, τ_bajo 0,35 y τ_relevancia 0,25 (71% sobre lo visto) en vez del máximo (75%), porque el
  máximo casi nunca recomienda Ajustar CV y dejaría el Taller sin uso. *Costo:* 4 puntos sobre lo visto.
- **Reproceso automático:** la versión de las reglas de extracción va dentro del hash de cada vacante, así que la
  próxima ingesta reprocesa todo cuando cambian. *Costo:* una ingesta completa más lenta, una sola vez.
- **"Tu mercado" y plan de aprendizaje:** solo cuentan vacantes con similitud ≥ 0,40. El Plan de hoy y el Taller
  siguen usando el conjunto amplio.
- **Benchmark:** el aviso de "tope alcanzado" pasó de advertencia a información, porque con catálogos grandes es lo
  normal. Las vacantes sintéticas toman sus requisitos de una misma vacante real, para parecerse a un catálogo
  agrupado por áreas.

### Evaluación
- **Vacantes agregadas:** solo las 14 + 24 que usa algún par.
- **Búsquedas extra:** se hicieron 5 búsquedas de vacantes en total, porque Ajustar CV y Sin datos escasean en
  vacantes reales.
- **Envigado y La Estrella** se etiquetaron como Medellín (área metropolitana). *Costo:* si el equipo no lo acepta,
  cambia una etiqueta.
- **Criterio de Sin datos:** la vacante no permite juzgar el ajuste. Si pide un título específico que la persona tiene,
  es Postular. *Costo:* el borde es discutible; el equipo debe revisar los Sin datos.
- **Clones excluidos:** se quitaron 2 pares que eran copias de avisos del ajuste. Se reportan 46% (limpio) y 50%.
- **La política entregada (.3) no tiene medición en vacantes nuevas:** la prueba nueva ya se usó. Sobre lo visto da lo
  mismo que la .2.

### Evaluación ciega
- **CV con sugerencias:** acepta todas las sugerencias del Taller, incluso las malas. Es el peor caso para Scoutly y
  evita que alguien elija a mano. *Costo:* puede subestimar el Taller.
- **La pregunta 2 no es ciega del todo:** el CV con sugerencias es más largo. Mide preferencia.
- **Sorteo secreto:** usa el azar del sistema, la clave queda fuera del repo con permisos 600 y su SHA-256 está en
  `evaluacion_ciega/CLAVE_SHA256.txt`.

### Verificación y documentos
- **Correo por consola:** el de la verificación salió por consola porque en desarrollo solo hay cuentas ficticias. La
  prueba con un buzón real la hace el usuario registrándose.
- **Capturas:** se tomaron con Playwright, porque el navegador de chrome-devtools estaba ocupado por otra sesión.
- **La sugerencia absurda del Taller** quedó documentada y no se arregló en la fase. Es una de las dos mejoras que se
  exploran aparte.
- **Grafo:** graphify se actualizó solo con el código (sin LLM), y `graphify-out/` sigue sin estar en git.
- **Formato del informe:** es Markdown; si el curso pide docx o pdf, se convierte.

## Después de la Fase 4: adopción de la exploración (2026-11-02)

- **(usuario)** Se adopta la variante V4 (mpnet para la cobertura + fusión) y se une la rama
  `exploracion/mejoras-decisor`. Queda escrito en la spec §13.6.
- **(usuario)** Como no hay banda "parcial", el Taller pregunta por los obligatorios faltantes.
- **Mpnet recibe el texto completo del requisito, sin `nucleo`.** Así se midió en `prueba_3`; `nucleo` fue un
  ajuste para MiniLM. *Costo:* "Experiencia de 2 años en X" se compara entera y no solo por su área.
- **Cada vacante guarda con qué modelos se embebió** (`modelos_embebido`). Antes, un cambio de modelo solo llegaba con
  la siguiente ingesta, y mientras tanto el decisor se saltaba todas las vacantes. Las matrices de dimensión distinta
  también se saltan. *Costo:* la primera corrida después del cambio re-embebe todo el catálogo.
- **Las pruebas de la cadena fijan su propia política** (con banda parcial y sin fusión), porque la vigente nunca
  produce AJUSTAR_CV. *Costo:* ninguno; la política vigente tiene sus propias pruebas.

- **Revisión independiente, hallazgo crítico (arreglado):**
  - Una vacante con vectores desactualizados se saltaba y su decisión se borraba. Pasaba mientras otro proceso
    re-embebía el catálogo, por ejemplo en el primer arranque con mpnet, y después volvía como "nueva" y se notificaba
    otra vez.
  - Ahora la decisión anterior se conserva tal cual.
  - La preselección exige además que la vacante esté embebida con los modelos actuales.
  - *Costo:* mientras dura el re-embebido, el candidato ve la decisión vieja de esas vacantes.
- **Revisión independiente, hallazgos importantes (arreglados):**
  - `ModelosEmbebido(busqueda, cobertura)` es obligatorio; ya no se puede decidir con un solo modelo.
  - `matching/candados.py` centraliza los candados de aviso y no los deja tomados si hay un error.
  - La cola bloquea solo su propia fila, no la del perfil.
  - **El Taller decide la vigencia por requisito.** La migración `matching/0008` borra las sugerencias del Taller
    anterior, que tenían texto escrito por el sistema. *Costo:* quien hubiera aceptado una pierde ese historial. Solo
    había cuentas ficticias.
  - **`--procesos`:** se lanza con la ruta de `manage.py`, maneja SIGTERM, avisa si un hijo muere y tiene un máximo
    de 6.
  - **Con la política vigente, parte de la fusión no se ejecuta** (la nota "Resalta…"). Se documentó y se conserva el
    código para políticas con banda parcial. *Costo:* código que hoy no corre.
- **Incidente (2026-11-02):** una prueba de `--procesos 50`, escrita antes de implementar el tope, lanzó procesos reales
  de ~2 GB y agotó la memoria del PC, que se colgó. No hubo correos ni datos perdidos. Las pruebas de ese módulo ahora
  prohíben lanzar procesos reales.
- **(usuario)** Las decisiones que no cambiaron no se reescriben.
  - Una huella del contenido decide cuáles escribir.
  - `fecha_decision` pasa a significar "última escritura".
  - *Costo:* si se agrega un campo a `Decision`, entra solo en la huella y fuerza una reescritura completa, una vez.

- **`empresa` y `ubicacion` pasan a 500 caracteres** (migración `vacantes/0007`). Dos vacantes reales fallaron por pasar
  de 150. No se recortan, porque recortar una lista de ciudades descartaría a quien vive en las últimas. *Costo:* no se
  supo cuál de los dos campos falló, y esas dos vacantes (`mag-940469`, `mag-1089200`) siguen fuera del catálogo.
- **Carga del catálogo real:** la primera corrida perdió 14 términos y casi todo "auxiliar contable" por una caída de
  internet (20:00–20:13). Se relanzaron esos 15 y se cortó a las 23:35, el límite acordado con el usuario. *Costo:* el
  término en curso al cortar se perdió, porque las vacantes se guardan al terminar cada término, y el catálogo quedó
  con pocas vacantes de ingeniería y recursos humanos.

## Pendientes menores (no se arreglaron)

- **Evaluación ciega:**
  - los paquetes no muestran las expectativas del candidato (ciudad, salario);
  - el paquete 6 tiene listas de una sola vacante.
- **Áreas metropolitanas:** se comparan por subcadena. "Caldas" y "Barbosa" también existen en otros departamentos.
- **Re-ingesta completa:**
  - una decisión tomada en medio de ella puede hacer que vacantes reaparezcan como "nuevas" y se notifiquen de nuevo;
  - el candado de ingesta no se renueva si tarda más de 30 minutos.
- **Benchmark:** el delta diario se midió con la base vacía.
- **Regla de prácticas:** hace una consulta por cada vacante de prácticas y por candidato.
- **Una caída de red no se reintenta:** la carga registra el error, salta el término y sigue, y al final solo cuenta los
  errores de guardado. El resumen `errores: 2` no mostró los 14 términos perdidos; se vieron en el registro.
- **Etiquetas en conflicto:** mag-1118625 (Postular) y mag-1121592 (Ajustar CV) son casi iguales y tienen el mismo CV.
  El equipo debe decidir la etiqueta.
