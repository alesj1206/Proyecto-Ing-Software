# Qué consigue entrevistas: evidencia para el "decisor" de Scoutly

Fecha: 2026-11-02 · Alcance: investigación web (fuentes al final). Convención: **[E]** = evidencia con fuente; **[I]** = inferencia nuestra.

## Resumen ejecutivo

- El cuello de botella no es un "robot ATS que rechaza el 75 %": es el **volumen** (decenas a cientos de postulaciones por vacante) más **filtros eliminatorios explícitos** (preguntas de prefiltro) y una lectura humana de segundos.
- Lo que más se asocia a entrevistas: **postular temprano**, **CV adaptado a la vacante**, **pocas postulaciones bien elegidas** (no repetir en la misma empresa) y **referidos**.
- Magneto ya cubre recomendación (Mimir), búsqueda con IA, prefiltros y seguimiento de postulaciones. Scoutly aporta valor si es el **decisor explicable del lado del candidato**: le dice qué hacer con cada vacante y por qué, y mide los resultados.

## 1. Cómo funciona hoy el filtrado

- [E] En un estudio de Enhancv con 25 reclutadores de EE. UU. (sept.–oct. 2025), todos usaban preguntas eliminatorias (*knock-out*): autorización de trabajo, licencias, ubicación. Solo 2 de 25 (8 %) tenían configurado un rechazo automático por contenido del CV (umbral de match o habilidad faltante). La muestra es pequeña.
- [E] La cifra de que "el 75 % de los CV los rechaza el ATS" no tiene fuente primaria verificable, y varias revisiones la tratan como mito.
- [E] Volumen: según Greenhouse, las postulaciones por vacante subieron un 134 % desde la salida de ChatGPT. Resúmenes secundarios de sus datos hablan de 95 a 244 postulaciones por vacante en 2025 (cifras no verificadas en la fuente primaria).
- [E] Tiempo de lectura: el estudio de Ladders (2018) midió una primera mirada promedio de 7,4 s, centrada en cargos y títulos de sección. Su metodología está poco documentada. En Colombia, un reclutador citado por Portafolio dice recibir unas 500 hojas de vida por convocatoria y dedicarles de 7 a 8 s a cada una (testimonio, no estudio).
- [E] En Magneto, cada vacante puede tener un **cuestionario de prefiltro** que se responde al postular (`candidate.job_detail` / `candidate.job_apply`, documentación MCP de candidatos).
- [E] No encontramos estadísticas públicas de Computrabajo ni de elempleo sobre postulantes por vacante o tasas de rechazo automático.
- [I] Para Scoutly, la regla de DESCARTAR (modalidad, salario, ubicación, experiencia) imita bien los *knock-outs* reales. El riesgo principal no es el ATS: es perderse entre cientos de CV en una lectura de pocos segundos.

## 2. Qué aumenta la tasa de entrevista

| Palanca | Evidencia | Solidez |
|---|---|---|
| **CV adaptado** | Huntr, 2.º trimestre de 2026 (103.000 postulaciones, 32.000 CV adaptados): 5,71 % de entrevistas con CV adaptado frente a 3,09 % sin adaptar. El mismo patrón aparece en el 1.er trimestre y en 2025. | Media: es asociación, no causalidad, en usuarios de Huntr. |
| **Cartas adaptadas** | ResumeGo, experimento de campo con 7.287 postulaciones: 16,4 % de respuesta con carta adaptada, 12,5 % con carta genérica y 10,7 % sin carta. | Media: experimento hecho por un proveedor. |
| **Postular temprano** | TalentWorks (~1.600 a 4.000 postulaciones): postular en las primeras ~96 h multiplica las probabilidades hasta 8 veces, y cada día de espera posterior las reduce ~28 %. | Baja-media: el análisis original no está disponible y los resúmenes se contradicen sobre la ventana exacta. |
| **Menos postulaciones, mejor elegidas** | Huntr: con una sola postulación a una empresa, 6,14 % de entrevistas; con 8 o más a la misma empresa, 1,85 %. | Media: asociación. |
| **Referidos** | Fed de Nueva York (Brown, Setren y Topa), una sola firma: los referidos eran el 6 % de los postulantes, pero el 21 % de los entrevistados y el 29 % de las contrataciones. Burks et al. (IZA, 9 firmas): los referidos tienen más probabilidad de ser contratados y ~10–30 % menos rotación. | Alta para el efecto; Scoutly no puede producir referidos. |
| **Logros cuantificados** | Huntr: resúmenes con cifras en dinero, 7,24 % de entrevistas frente a 4,13 % sin cifras. | Media-baja. |
| **% de match de palabras clave** | Jobscan recomienda un 75–80 % de coincidencia. | Baja: es una recomendación de proveedor, no un estudio. |
| **Perfil completo** | elempleo recomienda un perfil completo por encima del 90 % para ganar visibilidad. La API de Magneto expone un "nivel de completitud". | Baja: es un consejo, sin cifras de efecto. |

[E] Tasa base: varias fuentes sitúan la tasa de entrevista por postulación en ~2–6 % (TalentWorks ~2 %; Huntr entre 3 y 6 %).
[I] Con tasas base tan bajas, pasar de 3 % a 6 % duplica las entrevistas. Esa es la magnitud que el decisor debería buscar y medir.

## 3. Qué hace Magneto365 (para no duplicarlo)

- [E] Para candidatos: perfil y hoja de vida (subir Word/PDF o crearla en la plataforma, video de presentación), búsqueda de vacantes por texto, **búsqueda con IA en lenguaje natural** (rol, ubicación, modalidad, salario), **vacantes sugeridas por el recomendador "Mimir"** (match de perfil + interacciones del candidato), postulación con prefiltro y lista de "Mis postulaciones" con estado. La descripción general menciona "scoring y `fit_analysis`", pero no aparece como herramienta documentada.
- [E] Para empresas: publicación de vacantes, IA para encontrar talento, pruebas de talento, filtrado de CV con IA, integración con SAP (análisis de CV y evaluación de candidatos). Afirma más de 8 millones de usuarios y más de 5.000 empresas.
- [I] Huecos que Scoutly puede llenar sin duplicar:
  1. Una **acción explicada** por vacante (POSTULAR / AJUSTAR_CV / CERRAR_BRECHA / DESCARTAR), no solo una lista ordenada.
  2. **Brechas agregadas** de habilidades a lo largo del mercado ("Docker aparece en N de tus vacantes relevantes").
  3. **Sugerencias concretas de redacción del CV** por vacante.
  4. **Gestión del momento de postular** (frescura de la vacante, cupo diario).
  5. **Medición del resultado** (tasa de entrevistas) para recalibrar la política.
  - Mimir recomienda vacantes; Scoutly decide y aconseja qué hacer con ellas. El campo `suggestedByMatcher` de Magneto muestra que ellos ya miden la conversión de sus recomendaciones; Scoutly debería medir la suya.

## 4. Riesgos

- **Manipulación de palabras clave.**
  - [E] El 8 % de los reclutadores que sí filtran por contenido usa umbrales de match (Enhancv).
  - [I] Si AJUSTAR_CV sugiere agregar habilidades que el candidato no tiene, Scoutly fomenta CV inflados que fallan en la entrevista y dañan la confianza en la plataforma.
  - Mitigación: solo sugerir palabras clave que tengan **evidencia en el perfil** (sinónimos, proyectos, experiencia previa), y pedir al candidato que confirme cada una. Si no hay evidencia, la acción es CERRAR_BRECHA, no AJUSTAR_CV.
- **Sesgo y equidad.**
  - [E] Wilson y Caliskan (Universidad de Washington, AIES 2024): con embeddings de recuperación sobre más de 550 CV reales, los nombres asociados a personas blancas fueron preferidos en el 85,1 % de los casos y los asociados a mujeres en solo el 11,1 %. Los hombres negros nunca fueron preferidos frente a los hombres blancos. La longitud del documento también influyó.
  - [I] Nuestros embeddings y el modelo reranker pueden heredar sesgos parecidos. Mitigación:
    - eliminar nombre, foto, edad, estado civil y cédula antes de calcular embeddings;
    - normalizar la longitud del texto;
    - auditar con pares de CV contrafactuales;
    - mantener las reglas de DESCARTAR limitadas a restricciones que el propio candidato declaró.
- **Ley 1581 de 2012 y Circular SIC 002 de 2024.**
  - [E] La ley exige autorización previa, expresa e informada (art. 9) y garantiza los derechos de conocer, actualizar, rectificar y suprimir los datos (art. 8). La SIC es la autoridad y puede multar hasta 2.000 SMMLV (cifra de fuentes secundarias).
  - [E] La Circular SIC 002 de 2024 aplica la ley a sistemas de IA: minimización de datos; idoneidad, necesidad, razonabilidad y proporcionalidad; análisis de riesgo y evaluaciones de impacto cuando haya riesgo para derechos fundamentales. La Sentencia T-323 de 2024 de la Corte Constitucional exige que la IA cumpla el régimen de datos.
  - [I] No encontramos en la Ley 1581 un derecho explícito frente a decisiones automatizadas como el art. 22 del RGPD europeo, pero la Circular 002 y los principios de transparencia empujan en esa dirección.
  - [I] Para el MVP:
    - consentimiento explícito para analizar el CV;
    - procesamiento local, que ya es una ventaja;
    - no enviar el CV a APIs externas;
    - política de retención y opción de borrado;
    - toda acción explicable y reversible por el candidato;
    - tratar los datos sensibles (salud, origen étnico, foto/biometría) como excluidos del modelo.

## 5. Recomendaciones de producto (priorizadas) [I salvo que se indique]

**P0: señales que deben entrar al decisor**
1. **Frescura de la vacante.** Calcular el tiempo desde la publicación y aplicar una penalización exponencial (por ejemplo, ×0,72 por día después de 4 días, siguiendo el ~28 % diario de TalentWorks como **hipótesis a calibrar**). Si la vacante tiene buen ajuste y menos de 72 h, marcarla "POSTULAR HOY".
2. **Prefiltro como restricción dura.** Leer el cuestionario de prefiltro de Magneto y anticipar las respuestas. Si el candidato fallaría una pregunta eliminatoria, la acción es DESCARTAR, con la explicación.
3. **AJUSTAR_CV con evidencia.** Para cada requisito obligatorio sin coincidencia literal, buscar evidencia semántica en el perfil. Proponer un texto concreto ("Agrega 'Docker' en Proyecto X, donde usaste contenedores"). Priorizar el cargo y el resumen, que es lo que el reclutador mira en sus ~7 s.
4. **Cupo diario y diversificación.** Limitar las sugerencias a POSTULAR (por ejemplo, 3–5 por día) y evitar repetir la misma empresa (dato de Huntr: 8 o más postulaciones a una empresa → 1,85 %).

**P1**
5. **Competencia por vacante.** Usar el número de postulantes si Magneto lo expone; si no, aproximarlo con la antigüedad de la vacante y el tipo de cargo. Combinarlo con el ajuste para estimar la probabilidad de entrevista.
6. **Urgencia.** Detectar en el texto de la vacante palabras como "inmediato" o "urgente", o una fecha de cierre cercana.
7. **Logros cuantificados.** Sugerir cifras en el resumen del CV (asociación de Huntr: 7,24 % frente a 4,13 %).
8. **Completitud del perfil.** Usar el nivel de completitud de Magneto y recomendar los campos que faltan.

**P2**
9. **Brechas agregadas como plan de aprendizaje.** Ordenar las brechas por frecuencia × valor ("Docker: 37 vacantes relevantes; curso de ~10 h").
10. Indicar si la empresa tiene historial de respuesta con el candidato (requiere datos propios acumulados).

## 6. Cómo medir el éxito con el Kanban existente

- **Métrica norte:** tasa de entrevistas por postulación = postulaciones que llegan a `entrevista` ÷ postulaciones en `postulado`, en una ventana de 30 días. [E] Referencia externa: ~3–6 %.
- **Métricas secundarias:**
  - tiempo de `postulado` a `en_revision` y de ahí a `entrevista`;
  - % de postulaciones que se quedan sin respuesta;
  - tasa de entrevistas por acción (POSTULAR frente a "AJUSTAR_CV aplicado y luego postulado");
  - tasa de entrevistas por franja de frescura (menos de 24 h, 1–4 días, más de 4 días);
  - tasa de aceptación de sugerencias de CV.
- **Instrumentación:**
  - registrar en cada tarjeta del Kanban la acción, la confianza, la versión de la política, la frescura al momento de postular y si el CV fue ajustado;
  - pedir al candidato el desenlace con un clic (marcar `descartado` con motivo).
- **Calibración:** comprobar que entre las vacantes con confianza ~0,8 en POSTULAR haya más entrevistas que entre las de 0,5 (curva de calibración). Recalibrar pesos y umbrales cada mes.
- **Experimento:** prueba A/B entre candidatos (o alternando semanas): decisor con frescura y ajuste de CV frente a solo ordenamiento por similitud. Con una tasa base de ~4 %, detectar un aumento a 6 % requiere ~1.900 postulaciones por grupo (α = 0,05; potencia de 80 %). Para un curso universitario, conviene reportarlo como estudio piloto con intervalos de confianza, no como prueba concluyente.

## Fuentes

- Enhancv, ¿el ATS rechaza CV?: https://enhancv.com/blog/does-ats-reject-resumes/
- Betanews sobre el estudio de Enhancv: https://betanews.com/2025/11/10/study-debunks-viral-claim-that-ai-filters-out-most-job-applicants/
- ClearanceJobs, el volumen y no el ATS: https://news.clearancejobs.com/2026/07/29/recruiters-reveal-ats-doesnt-kill-your-resume-its-overwhelming-volume/
- Greenhouse, nuevos productos de IA (aumento de 134 %): https://www.greenhouse.com/newsroom/greenhouse-unveils-new-ai-driven-products-at-unleash-to-streamline-hiring-in-saturated-job-market
- Noon.ai, postulantes por vacante (secundaria): https://www.noon.ai/blog/articles/353-how-many-applicants-per-job
- HR Dive, estudio de Ladders: https://www.hrdive.com/news/eye-tracking-study-shows-recruiters-look-at-resumes-for-7-seconds/541582/
- PDF del estudio de Ladders: https://csuglobal.edu/sites/default/files/blog-files/theladders-eyetracking-studyc2.pdf
- ERE, crítica al estudio de Ladders: https://www.ere.net/articles/is-the-6-second-resume-scan-a-myth
- Portafolio, reclutador colombiano: https://www.portafolio.co/economia/empleo/este-es-el-secreto-de-una-buena-hoja-de-vida-627721
- Huntr, tendencias del 2.º trimestre de 2026: https://huntr.co/research/job-search-trends-q2-2026
- Huntr, tendencias del 1.er trimestre de 2026: https://huntr.co/research/job-search-trends-q1-2026
- ResumeGo, experimento con cartas de presentación: https://resumego.net/research/cover-letters
- Resumen de TalentWorks (Paul van der Laken): https://paulvanderlaken.com/2017/10/24/talent-works-data-science-to-improve-job-application-chances/
- Burks et al., IZA DP: https://repec.iza.org/dp8175.pdf
- Resumen IZA sobre referidos: https://newsroom.iza.org/en/archive/research/firms-can-rely-on-workers-referred-by-current-employees
- Noon.ai, estadísticas de referidos (cita a la Fed de Nueva York): https://www.noon.ai/blog/articles/360-employee-referral-statistics-2026
- Magneto, documentación MCP de candidatos: https://www.magneto365.com/co/docs/mcp/candidatos
- Magneto Global: https://www.magneto365.com/co/magneto-global
- Magneto, hoja de vida digital: https://www.magneto365.com/co/blog/como-hacer-una-hoja-de-vida-digital
- Betterteam, Magneto Negocios: https://www.betterteam.com/co/magneto-negocios
- SAP, socio Magneto: https://www.sap.com/sk/products/hcm/partners/magneto-global-s-a-s-magneto-aipowered-recruitment.html
- La República, Magneto (contenido patrocinado): https://www.larepublica.co/empresas/magneto-es-la-plataforma-que-busca-mejorar-la-conexion-entre-empresas-y-talento-4470963
- Universidad de Washington, sesgo en filtrado de CV con IA: https://www.washington.edu/news/2024/10/31/ai-bias-resume-screening-race-gender/
- Artículo AIES 2024: https://ojs.aaai.org/index.php/AIES/article/view/31748
- SIC, Circular Externa 002 de 2024: https://sedeelectronica.sic.gov.co/sites/default/files/normativa/Circular%20Externa%20No.%20002%20del%2021%20de%20agosto%20de%202024.pdf
- Cuatrecasas, guía de IA y datos personales: https://www.cuatrecasas.com/es/latam/tecnologia-medios-digitales/art/guia-uso-responsable-ia-datos-personales-colombia
- Brigard Urrutia, SIC sobre IA: https://www.bu.com.co/es/insights/noticias/sic-instruye-sobre-el-uso-de-datos-personales-en-sistemas-de-ia
- Modelo de solicitud de empleo (Ley 1581, arts. 8–9): https://forms-legal.com/es/colombia/employment/hr-forms/solicitud-empleo-colombia
- El Tiempo / elempleo, completitud del perfil: https://www.eltiempo.com/economia/finanzas-personales/ofertas-de-trabajo-disponibles-para-profesionales-de-todos-los-sectores-asi-puedes-postularte-3466407
