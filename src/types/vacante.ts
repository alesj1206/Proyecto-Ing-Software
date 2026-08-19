export type Modalidad = "Remoto" | "Presencial" | "Híbrido";

export interface Salario {
  min: number;
  max: number;
  moneda: string;
  periodo: "mensual" | "anual";
}

export interface Vacante {
  id: string;
  titulo: string;
  empresa: string;
  ubicacion: string;
  modalidad: Modalidad;
  salario: Salario | null;
  requisitos: string[];
  descripcion: string;
  fechaPublicacion: string;
}
