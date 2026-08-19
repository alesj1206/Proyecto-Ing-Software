export type CampoPerfil = "nombre" | "contacto" | "experiencia" | "educacion";

export interface Perfil {
  nombre: string | null;
  contacto: string | null;
  experiencia: string[] | null;
  educacion: string[] | null;
  habilidades: string[];
  camposPendientes: CampoPerfil[];
  cvNombreArchivo: string;
  actualizadoEn: string;
}
