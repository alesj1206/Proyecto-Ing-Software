# Crítica del documento de propuestas (oh-my-claudecode:critic). Ya incorporada.

**Veredicto: REVISAR.** Hubo 3 hallazgos mayores y los tres se incorporaron:
1. **El alcance A + C + B no cabía en un sprint.** Ahora el plan garantiza A, C en versión texto y B1 con
   `job_detail`, y define un orden de corte explícito.
2. **La métrica "X% contra Y%" del piloto era insostenible** (harían falta ~1.900 postulaciones por grupo). Se
   reemplazó por una evaluación ciega con 2–3 reclutadores reales.
3. **Contradicción con Groq:** las viñetas del CV identifican a la persona. Ahora las sugerencias son locales y
   con plantillas; usar un LLM queda solo con autorización expresa.

También se corrigieron estas afirmaciones exageradas:
- "umbrales probados sobre vacantes reales";
- el dato de 5/14 SIN_DATOS, que era de un solo perfil;
- C como "la palanca con mejor evidencia" (es evidencia media);
- "Alto" de impacto sin datos propios.

Y se agregaron:
- la seguridad de v2 como requisito previo no negociable;
- los términos de uso también para el scraping;
- la responsabilidad del candidato sobre cada cambio en su CV.
