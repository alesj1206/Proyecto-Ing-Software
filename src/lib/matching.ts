import type { Perfil } from "@/types/perfil";
import type { Vacante } from "@/types/vacante";

export interface MatchVacante {
  vacante: Vacante;
  score: number; // 0..1, porcentaje de requisitos de la vacante cubiertos por el perfil
  coincidencias: string[];
}

// Sprint 1 (HU-06): scoring simple por coincidencia de palabras clave entre
// las habilidades del perfil (extraídas del CV) y los requisitos de cada
// vacante. Se recalcula en cada solicitud a partir del perfil almacenado,
// por lo que actualizar el perfil (recargar el CV) cambia el ranking en la
// siguiente vista, simulando la ejecución diaria del workflow de n8n.
//
// TODO (Sprint 2): reemplazar este cálculo por el motor de matching real
// ejecutado por el workflow de n8n (scoring semántico, expectativas del
// candidato, etc.). Candidato a implementarse como un agente sobre la API
// de Claude: una llamada por par perfil-vacante con salida estructurada
// (output_config.format / JSON schema) que devuelva score + razonamiento +
// criterios cubiertos, en vez del conteo de palabras clave actual.
export function computeMatchesDeHoy(
  perfil: Perfil,
  vacantes: Vacante[]
): MatchVacante[] {
  const habilidades = new Set(
    perfil.habilidades.map((h) => h.toLowerCase())
  );

  return vacantes
    .map((vacante) => {
      const coincidencias = vacante.requisitos.filter((req) =>
        habilidades.has(req.toLowerCase())
      );
      const score =
        vacante.requisitos.length > 0
          ? coincidencias.length / vacante.requisitos.length
          : 0;
      return { vacante, score, coincidencias };
    })
    .filter((m) => m.score > 0)
    .sort((a, b) => b.score - a.score);
}
