import { NextResponse } from "next/server";
import { crearUsuario, EmailEnUsoError } from "@/lib/users";
import { crearSesion } from "@/lib/session";

function emailValido(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export async function POST(request: Request) {
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Solicitud inválida." }, { status: 400 });
  }

  const email = (body.email ?? "").trim();
  const password = body.password ?? "";

  if (!emailValido(email)) {
    return NextResponse.json(
      { error: "Ingresa un correo electrónico válido." },
      { status: 400 }
    );
  }
  if (password.length < 6) {
    return NextResponse.json(
      { error: "La contraseña debe tener al menos 6 caracteres." },
      { status: 400 }
    );
  }

  let usuario;
  try {
    usuario = crearUsuario(email, password);
  } catch (err) {
    if (err instanceof EmailEnUsoError) {
      return NextResponse.json({ error: err.message }, { status: 409 });
    }
    throw err;
  }

  await crearSesion({ uid: usuario.id, email: usuario.email });

  return NextResponse.json({ email: usuario.email }, { status: 201 });
}
