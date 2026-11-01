# Fase 1: verificación visual antes/después

**Cómo se hizo.**
- **v2:** se levantó el tag `pre-sprint3-rebuild` en un worktree aparte (SQLite y `seed_vacantes`).
- **v3:** se levantó la rama `sprint-3` (Postgres e `ingerir_vacantes --fuente fixture`).
- **Mismo recorrido en las dos:** el mismo usuario, el mismo CV ficticio (`cuentas/tests/cvs.py`) y la misma
  vacante de detalle.
- **Capturas:** las tomó `scripts/capturas.py` a 1440×900, en página completa. Están en `capturas/antes/` (v2) y
  `capturas/despues/` (v3).
- **Comparación:** `python scripts/capturas.py --comparar docs/fase1/capturas/antes docs/fase1/capturas/despues`.

| Página | % de píxeles distintos | Lectura |
|---|---|---|
| onboarding | 0,00 % | Idéntica |
| expectativas | 0,00 % | Idéntica |
| postulaciones (tablero vacío) | 0,00 % | Idéntica |
| notificaciones (vacía) | 0,00 % | Idéntica |
| perfil | 23,14 % | **Mismo estilo; cambia el contenido.** v3 lee las habilidades con vocabulario abierto ("Excel avanzado", "Power BI" en vez de "excel", "power bi"), quita los guiones que v2 dejaba en las viñetas y agrega el bloque "Eliminar mi cuenta" (§13.5). |
| historial | 46,06 % | v3 muestra el estado vacío del template, porque todavía no hay decisiones (Fase 2). v2 calculaba su ranking al vuelo. |
| dashboard | 28,14 % | Mismo estilo. v3 no tiene "matches de hoy" (Fase 2), y su catálogo son las 18 vacantes reales; v2 sumaba las 9 de prueba del Sprint 1. |
| detalle | 32,27 % | Mismo estilo. v3 no muestra el anillo ni las barras hasta tener la decisión (Fase 2), y por eso "Postularme" sale deshabilitado. |
| login | 65,48 % | **Rediseño pedido por el usuario:** estructura del login de Magneto con la identidad de Scoutly. |
| registro | 74,55 % | **Rediseño pedido por el usuario:** registro en 2 pasos con la autorización de la Ley 1581. |

**Conclusión.** Los templates de v2 se usan sin cambios: el `diff` contra el tag es vacío en 7 de 8, y `perfil.html`
solo agrega un bloque al final. Las páginas con el mismo estado se ven idénticas píxel a píxel. Las diferencias
que quedan son de contenido o vienen de rediseños pedidos. **Pendiente para la Fase 2:** comparar el dashboard, el
detalle y el historial ya con decisiones.
