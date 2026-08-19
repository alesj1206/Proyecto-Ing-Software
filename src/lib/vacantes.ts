import vacantesRaw from "@/data/vacantes.json";
import type { Vacante } from "@/types/vacante";

// Sprint 1: el dataset viene de un JSON mock local que simula lo que hoy
// entrega el workflow de n8n. En un sprint futuro este import se reemplaza
// por la fuente real (API/webhook de n8n) sin cambiar el resto de la app,
// ya que el resto del código solo depende de `getVacantes()`.
const RAW_VACANTES = vacantesRaw as Vacante[];

function esVacanteValida(v: Partial<Vacante>): v is Vacante {
  return Boolean(
    v.id &&
      v.titulo &&
      v.titulo.trim().length > 0 &&
      v.empresa &&
      v.ubicacion &&
      v.modalidad
  );
}

export function getVacantes(): Vacante[] {
  const vistas = new Set<string>();
  const vacantes: Vacante[] = [];

  for (const v of RAW_VACANTES) {
    if (!esVacanteValida(v)) continue; // descarta datos rotos
    if (vistas.has(v.id)) continue; // descarta duplicados (se queda la primera aparición)
    vistas.add(v.id);
    vacantes.push(v);
  }

  return vacantes.sort(
    (a, b) =>
      new Date(b.fechaPublicacion).getTime() -
      new Date(a.fechaPublicacion).getTime()
  );
}

export function getVacantePorId(id: string): Vacante | undefined {
  return getVacantes().find((v) => v.id === id);
}

export function formatSalario(v: Vacante): string {
  if (!v.salario) return "No especificado";
  const { min, max, moneda, periodo } = v.salario;
  const fmt = (n: number) => n.toLocaleString("es-CO");
  return `${moneda} ${fmt(min)} - ${fmt(max)} / ${periodo}`;
}
