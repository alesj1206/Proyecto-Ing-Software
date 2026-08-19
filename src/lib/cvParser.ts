import { HABILIDADES_CONOCIDAS } from "@/lib/skills";
import type { CampoPerfil } from "@/types/perfil";

// Sprint 1 (HU-01): no se implementa OCR/lectura real del PDF, tal como se
// pidió para este alcance. En su lugar simulamos la extracción a partir de
// metadatos del archivo (nombre y tamaño) para poder ejercitar el flujo
// completo -incluyendo el caso de campos que "no se logran extraer" y
// quedan marcados como pendientes- sin romper la carga. El texto generado
// (experiencia/educación) se redacta a partir de plantillas inspiradas en
// perfiles reales de Magneto, para que el resultado se vea como el de un
// CV real y no como una lista cruda de palabras del nombre del archivo.
// En un sprint futuro esta función se reemplaza por un extractor real.

const EDUCACION_MIN_BYTES = 15_000;

const PALABRAS_IGNORADAS_EN_NOMBRE = new Set([
  "cv",
  "resume",
  "curriculum",
  "hoja",
  "vida",
  "hv",
]);

const HABILIDADES_SET = new Set<string>(HABILIDADES_CONOCIDAS);

// Plantillas de experiencia por área, con redacción similar a la de un
// resumen de perfil de Magneto. Se eligen según las habilidades detectadas,
// en vez de mostrar el nombre del archivo tal cual.
const EXPERIENCIA_POR_AREA: Array<{ habilidades: string[]; texto: string }> = [
  {
    habilidades: ["react", "javascript", "typescript", "html", "css"],
    texto:
      "Desarrollo de interfaces web con React y TypeScript, trabajando junto al equipo de diseño en la construcción de componentes reutilizables.",
  },
  {
    habilidades: ["node.js", "next.js", "sql"],
    texto:
      "Construcción de servicios backend con Node.js e integración con bases de datos SQL, participando en despliegues frecuentes de una plataforma full stack.",
  },
  {
    habilidades: ["python"],
    texto:
      "Diseño y mantenimiento de pipelines de datos en Python, con procesamiento y análisis de volúmenes medianos de información.",
  },
  {
    habilidades: ["aws", "docker", "kubernetes"],
    texto:
      "Automatización de despliegues y gestión de infraestructura en la nube, con contenedores orquestados en Kubernetes.",
  },
  {
    habilidades: ["figma"],
    texto:
      "Diseño de experiencias digitales centradas en el usuario, desde el prototipado en Figma hasta la validación con el equipo de desarrollo.",
  },
  {
    habilidades: ["agile", "scrum", "liderazgo"],
    texto:
      "Facilitación de ceremonias ágiles y coordinación de equipos multidisciplinarios entre áreas técnicas y de negocio.",
  },
];

const EXPERIENCIA_GENERAL =
  "Experiencia profesional en roles afines al área de interés indicada en el perfil.";

const EDUCACION_MOCK = [
  "Ingeniería de Sistemas / Informática — formación universitaria.",
  "Cursos y certificaciones complementarias en tecnología.",
];

function tokenizarNombreArchivo(fileName: string): string[] {
  const sinExtension = fileName.replace(/\.[^/.]+$/, "");
  return sinExtension
    .replace(/[_\-]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter((p) => p.length > 0);
}

// Separa el nombre del archivo en el nombre de la persona (tokens antes de
// la primera habilidad reconocida) y las habilidades mencionadas, en vez de
// tratar todas las palabras del archivo como parte del nombre.
function extraerNombreYHabilidades(fileName: string): {
  nombre: string | null;
  habilidades: string[];
} {
  const tokens = tokenizarNombreArchivo(fileName);

  const nombreTokens: string[] = [];
  const habilidades: string[] = [];
  let enZonaDeHabilidades = false;

  for (const token of tokens) {
    const tokenLower = token.toLowerCase();
    if (HABILIDADES_SET.has(tokenLower)) {
      enZonaDeHabilidades = true;
      if (!habilidades.includes(tokenLower)) habilidades.push(tokenLower);
      continue;
    }
    if (
      !enZonaDeHabilidades &&
      !PALABRAS_IGNORADAS_EN_NOMBRE.has(tokenLower) &&
      /[a-zA-ZÀ-ÿ]/.test(token)
    ) {
      nombreTokens.push(token);
    }
  }

  const nombre =
    nombreTokens.length > 0
      ? nombreTokens
          .map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
          .join(" ")
      : null;

  return {
    nombre,
    habilidades:
      habilidades.length > 0 ? habilidades : ["comunicación", "trabajo en equipo"],
  };
}

function generarContactoDesdeNombre(nombre: string): string {
  const slug = nombre
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .join(".");
  return `${slug}@correo-simulado.com`;
}

function generarExperiencia(habilidades: string[]): string[] {
  const set = new Set(habilidades);
  const encontradas = EXPERIENCIA_POR_AREA.filter((area) =>
    area.habilidades.some((h) => set.has(h))
  ).map((area) => area.texto);

  return encontradas.length > 0 ? encontradas.slice(0, 2) : [EXPERIENCIA_GENERAL];
}

export interface DatosExtraidosCV {
  nombre: string | null;
  contacto: string | null;
  experiencia: string[] | null;
  educacion: string[] | null;
  habilidades: string[];
  camposPendientes: CampoPerfil[];
}

export function mockExtraerDatosCV(
  fileName: string,
  fileSizeBytes: number
): DatosExtraidosCV {
  const camposPendientes: CampoPerfil[] = [];

  const { nombre, habilidades } = extraerNombreYHabilidades(fileName);
  if (!nombre) camposPendientes.push("nombre");

  const contacto = nombre ? generarContactoDesdeNombre(nombre) : null;
  if (!contacto) camposPendientes.push("contacto");

  const experiencia = generarExperiencia(habilidades);

  const educacion = fileSizeBytes >= EDUCACION_MIN_BYTES ? EDUCACION_MOCK : null;
  if (!educacion) camposPendientes.push("educacion");

  return {
    nombre,
    contacto,
    experiencia,
    educacion,
    habilidades,
    camposPendientes,
  };
}
