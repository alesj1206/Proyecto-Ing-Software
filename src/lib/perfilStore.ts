import "server-only";
import fs from "node:fs";
import path from "node:path";
import type { Perfil } from "@/types/perfil";

// Sprint 1: sin base de datos todavía. El perfil de cada candidato se
// persiste en un archivo local por usuario dentro de `.data/perfiles/`,
// ignorado por git. En un sprint futuro esto se reemplaza por
// almacenamiento real (DB) sin cambiar la forma en que el resto de la app
// consume `getPerfil()` / `guardarPerfil()`.
const STORE_DIR = path.join(process.cwd(), ".data", "perfiles");

function rutaPerfil(userId: string): string {
  return path.join(STORE_DIR, `${userId}.json`);
}

export function getPerfil(userId: string): Perfil | null {
  try {
    const raw = fs.readFileSync(rutaPerfil(userId), "utf-8");
    return JSON.parse(raw) as Perfil;
  } catch {
    return null;
  }
}

export function guardarPerfil(userId: string, perfil: Perfil): void {
  fs.mkdirSync(STORE_DIR, { recursive: true });
  fs.writeFileSync(rutaPerfil(userId), JSON.stringify(perfil, null, 2), "utf-8");
}
