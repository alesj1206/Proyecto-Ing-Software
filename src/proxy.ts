import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { COOKIE_SESION, verificarSesion } from "@/lib/sessionToken";

// HU-13: "Matches de hoy" y "cargar CV" viven detrás de estas rutas
// protegidas (dashboard, onboarding y mi-perfil); sin sesión activa se
// redirige al login.
const RUTAS_PROTEGIDAS = ["/dashboard", "/onboarding", "/perfil"];
const RUTAS_SOLO_INVITADO = ["/login"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const sesion = await verificarSesion(
    request.cookies.get(COOKIE_SESION)?.value
  );

  const esProtegida = RUTAS_PROTEGIDAS.some(
    (ruta) => pathname === ruta || pathname.startsWith(`${ruta}/`)
  );
  if (esProtegida && !sesion) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const esSoloInvitado = RUTAS_SOLO_INVITADO.includes(pathname);
  if (esSoloInvitado && sesion) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  if (pathname === "/") {
    return NextResponse.redirect(
      new URL(sesion ? "/dashboard" : "/login", request.url)
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
