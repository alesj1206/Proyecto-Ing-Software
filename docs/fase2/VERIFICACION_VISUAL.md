# Fase 2: el decisor en pantalla

Las capturas se tomaron con `scripts/capturas.py` sobre datos reales:
- 35 vacantes: las 18 del fixture de v2 y 17 ingeridas de magneto365.com con su texto completo;
- un CV ficticio de analista de datos;
- `manage.py decidir --pendientes` con MiniLM real.

Resultado: 25 vacantes relevantes, repartidas así:

| Acción | Vacantes |
|---|---|
| POSTULAR | 1 |
| AJUSTAR_CV | 1 |
| CERRAR_BRECHA | 2 |
| SIN_DATOS | 10 |
| DESCARTAR | 11 |

Las 10 SIN_DATOS son vacantes del fixture de v2, que tienen el texto recortado a 500 caracteres.

**Qué se agregó a los templates de v2** (el test `test_los_templates_solo_agregan_lineas_a_v2` comprueba que no se
borró nada más):

- **Dashboard** (`capturas/dashboard.png`):
  - "Matches de hoy" pasa a "Tu plan de hoy";
  - cada tarjeta lleva la insignia "Acción · solidez", "Cubres X/Y obligatorios" y la marca "Postular hoy";
  - se agregan la sección "Tus vacantes por acción", la tarjeta "Plan de aprendizaje", el aviso "Estamos
    analizando tu hoja de vida" y el aviso de vacantes ocultas por modalidad.
- **Detalle** (`capturas/detalle.png`):
  - el anillo muestra la cobertura, y a su lado van la insignia con el motivo de la solidez y la nota de POSTULAR;
  - las 5 barras ya no muestran "peso X%", porque v3 no pondera criterios;
  - se agrega la tarjeta "Qué hacer con esta vacante": cada requisito aparece cubierto, parcial o faltante, con
    "tu evidencia: «…»";
  - "Postularme" vuelve a estar habilitado.
- **Historial** (`capturas/historial.png`): el ranking sale de `FotoDiaria`.

**Problemas de calidad vistos en las capturas** (se tratan en la Task 10):
- Los requisitos que solo piden años de experiencia generan sugerencias de AJUSTAR_CV y entran al plan de
  aprendizaje, aunque ya los cubre la restricción de experiencia.
- Algunas líneas agrupan varias habilidades ("Power BI, Power Apps… Python y SQL") en un solo requisito.
