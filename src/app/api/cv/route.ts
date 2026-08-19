import { NextResponse } from "next/server";
import { mockExtraerDatosCV } from "@/lib/cvParser";
import { guardarPerfil } from "@/lib/perfilStore";
import { getSesion } from "@/lib/session";
import type { Perfil } from "@/types/perfil";

export async function POST(request: Request) {
  // El proxy ya protege /onboarding y /perfil, pero esta ruta también se
  // valida acá (defensa en profundidad para Route Handlers, HU-13 AC3).
  const sesion = await getSesion();
  if (!sesion) {
    return NextResponse.json(
      { error: "Debes iniciar sesión para cargar tu CV." },
      { status: 401 }
    );
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "Debes adjuntar un archivo PDF." },
      { status: 400 }
    );
  }
  const archivo = formData.get("cv");

  if (!(archivo instanceof File) || archivo.size === 0) {
    return NextResponse.json(
      { error: "Debes adjuntar un archivo PDF." },
      { status: 400 }
    );
  }

  const esPdf =
    archivo.type === "application/pdf" ||
    archivo.name.toLowerCase().endsWith(".pdf");

  if (!esPdf) {
    return NextResponse.json(
      { error: "El archivo debe ser un PDF." },
      { status: 400 }
    );
  }

  const datos = mockExtraerDatosCV(archivo.name, archivo.size);

  const perfil: Perfil = {
    nombre: datos.nombre,
    contacto: datos.contacto,
    experiencia: datos.experiencia,
    educacion: datos.educacion,
    habilidades: datos.habilidades,
    camposPendientes: datos.camposPendientes,
    cvNombreArchivo: archivo.name,
    actualizadoEn: new Date().toISOString(),
  };

  guardarPerfil(sesion.uid, perfil);

  return NextResponse.json(perfil, { status: 200 });
}
