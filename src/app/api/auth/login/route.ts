import { NextResponse } from "next/server";
import { buscarUsuarioPorEmail, verificarPassword } from "@/lib/users";
import { crearSesion } from "@/lib/session";

export async function POST(request: Request) {
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Solicitud inválida." }, { status: 400 });
  }

  const email = (body.email ?? "").trim();
  const password = body.password ?? "";

  const usuario = buscarUsuarioPorEmail(email);
  if (!usuario || !verificarPassword(usuario, password)) {
    return NextResponse.json(
      { error: "Correo electrónico o contraseña incorrectos." },
      { status: 401 }
    );
  }

  await crearSesion({ uid: usuario.id, email: usuario.email });

  return NextResponse.json({ email: usuario.email }, { status: 200 });
}
