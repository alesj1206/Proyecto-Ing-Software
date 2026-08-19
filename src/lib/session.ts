import "server-only";
import { cookies } from "next/headers";
import { cache } from "react";
import { redirect } from "next/navigation";
import {
  COOKIE_SESION,
  DURACION_SEGUNDOS,
  firmarSesion,
  verificarSesion,
} from "@/lib/sessionToken";
import type { SesionPayload } from "@/types/user";

export async function crearSesion(payload: SesionPayload): Promise<void> {
  const token = await firmarSesion(payload);
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_SESION, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: DURACION_SEGUNDOS,
  });
}

export async function cerrarSesion(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_SESION);
}

// cache(): evita volver a verificar el JWT varias veces durante el mismo
// render si varios componentes piden la sesión.
export const getSesion = cache(async (): Promise<SesionPayload | null> => {
  const cookieStore = await cookies();
  return verificarSesion(cookieStore.get(COOKIE_SESION)?.value);
});

export async function requireSesion(): Promise<SesionPayload> {
  const sesion = await getSesion();
  if (!sesion) redirect("/login");
  return sesion;
}
