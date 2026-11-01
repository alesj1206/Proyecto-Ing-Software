# Prototipo del decisor sobre vacantes reales de Magneto

18 vacantes reales (fixture de v2, texto recortado a 500 caracteres) × 3 perfiles ficticios. Embeddings `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, reranker `BAAI/bge-reranker-v2-m3` (GPU). **v2**: τ_alto=0.5, τ_bajo=0.4 (calibrados), τ_relevancia=0.4, sin ruido ni formación en los requisitos, SIN_DATOS en vez de POSTULAR cuando no hay requisitos. "Hoy" = 2026-10-05 (fecha más reciente del fixture).

## Analista de datos junior (Medellín)

Similitud perfil↔vacante (las 18): [0.65, 0.61, 0.53, 0.48, 0.4, 0.4, 0.39, 0.38, 0.38, 0.35, 0.35, 0.33, 0.31, 0.29, 0.28, 0.25, 0.24, 0.16]. Fuera por relevancia (< 0.4): 14.

Distribución de las relevantes: POSTULAR 0, AJUSTAR_CV 0, CERRAR_BRECHA 0, SIN_DATOS 2, DESCARTAR 2

**Plan de hoy** (máx. 3, una por empresa): ninguna

| Acción | Vacante | Empresa | Cobertura | Solidez | Motivo principal |
|---|---|---|---|---|---|
| SIN_DATOS | Analista de Datos (Facilities) | Confidencial | 0% | baja | la vacante no trae requisitos legibles: revísala tú |
| SIN_DATOS | Analista De Datos (facilities) - Bogota | ADECCO SERVICIOS COLOMBIA | 0% | baja | la vacante no trae requisitos legibles: revísala tú |
| DESCARTAR | Analista de datos Bogota | ACTIVOS S.A.S | 75% | alta | está en Bogotá, D.C., fuera de tus ciudades |
| DESCARTAR | Analista BI (Datos) - Medellín | Jose Raul Serna Rendon | 50% | alta | pide 3 años y tienes 1 |

## QA tester semi-senior (Bogotá)

Similitud perfil↔vacante (las 18): [0.62, 0.62, 0.6, 0.54, 0.53, 0.52, 0.49, 0.48, 0.47, 0.46, 0.44, 0.43, 0.41, 0.41, 0.32, 0.29, 0.27, 0.11]. Fuera por relevancia (< 0.4): 4.

Distribución de las relevantes: POSTULAR 0, AJUSTAR_CV 0, CERRAR_BRECHA 1, SIN_DATOS 5, DESCARTAR 8

**Plan de hoy** (máx. 3, una por empresa): ninguna

| Acción | Vacante | Empresa | Cobertura | Solidez | Motivo principal |
|---|---|---|---|---|---|
| CERRAR_BRECHA | Analista QA Tester (Software Testing) | Confidencial | 25% | media | te falta: azure |
| SIN_DATOS | Analista de Datos (Facilities) | Confidencial | 0% | baja | la vacante no trae requisitos legibles: revísala tú |
| SIN_DATOS | Analista QA (Soporte funcional) - Sector Financiero | VALCREDIT SAS | 0% | baja | la vacante no trae requisitos legibles: revísala tú |
| SIN_DATOS | Tester QA Junior (Pruebas de Software) - Bogotá | CROYDON COLOMBIA S.A | 0% | baja | la vacante no trae requisitos legibles: revísala tú |
| SIN_DATOS | Analista De Datos (facilities) - Bogota | ADECCO SERVICIOS COLOMBIA | 0% | baja | la vacante no trae requisitos legibles: revísala tú |
| SIN_DATOS | CEID Analista QA 1626523752-5 | Servicio de Empleo Comfam | 0% | baja | la vacante no trae requisitos legibles: revísala tú |
| DESCARTAR | Ingeniero SRE DevOps | STRATEGIC POINTS S.A.S | 33% | media | está en Medellín, fuera de tus ciudades |
| DESCARTAR | Ingeniero DevOps Junior (SRE) | STRATEGIC POINTS S.A.S | 30% | media | está en Medellín, fuera de tus ciudades |
| DESCARTAR | Analista BI (Datos) - Medellín | Jose Raul Serna Rendon | 33% | alta | está en Sabaneta, fuera de tus ciudades |
| DESCARTAR | Analista de datos Bogota | ACTIVOS S.A.S | 25% | alta | ofrece 1.750.905 y tu mínimo es 3.000.000 |
| DESCARTAR | Diseñador/a UX/UI para personas con o sin discapacidad  | Servicio de Empleo Comfam | 33% | alta | está en Medellín, fuera de tus ciudades |
| DESCARTAR | Ingeniero DevOps / Cloud | ACCENTURE LTDA | 12% | media | está en Medellín, fuera de tus ciudades |
| DESCARTAR | Desarrollador Backend Java- Medellín | ACCENTURE LTDA | 0% | media | está en Medellín, fuera de tus ciudades |
| DESCARTAR | Practicante UX - UI Designer | Crystal | 0% | media | está en Itagui, fuera de tus ciudades |

**Brechas más repetidas (plan de aprendizaje):** azure (1)

## Diseñadora UX/UI junior (Medellín)

Similitud perfil↔vacante (las 18): [0.79, 0.69, 0.45, 0.42, 0.37, 0.36, 0.35, 0.34, 0.33, 0.32, 0.31, 0.3, 0.29, 0.28, 0.25, 0.18, 0.17, 0.16]. Fuera por relevancia (< 0.4): 14.

Distribución de las relevantes: POSTULAR 0, AJUSTAR_CV 0, CERRAR_BRECHA 1, SIN_DATOS 0, DESCARTAR 3

**Plan de hoy** (máx. 3, una por empresa): ninguna

| Acción | Vacante | Empresa | Cobertura | Solidez | Motivo principal |
|---|---|---|---|---|---|
| CERRAR_BRECHA | Practicante UX - UI Designer | Crystal | 70% | media | te falta: canva |
| DESCARTAR | Diseñador/a UX/UI para personas con o sin discapacidad  | Servicio de Empleo Comfam | 67% | alta | pide 2 años y tienes 0 |
| DESCARTAR | Ingeniero SRE DevOps | STRATEGIC POINTS S.A.S | 17% | media | pide 3 años y tienes 0 |
| DESCARTAR | Ingeniero DevOps / Cloud | ACCENTURE LTDA | 12% | media | pide 3 años y tienes 0 |

**Brechas más repetidas (plan de aprendizaje):** canva (1)

## Distribución de similitud máxima requisito→evidencia (para calibrar τ)

n=99, p10=0.20, p25=0.25, p50=0.35, p75=0.43, p90=0.50
