import { SignJWT, jwtVerify } from "jose";
import type { SesionPayload } from "@/types/user";

// Módulo sin dependencias de Node (solo Web Crypto vía `jose`), para poder
// verificar la sesión tanto en Route Handlers/Server Components como en
// `proxy.ts`.
export const COOKIE_SESION = "session";
export const DURACION_SEGUNDOS = 30 * 24 * 60 * 60; // 30 días: la sesión se mantiene activa hasta cerrar sesión.

// Sprint 1: secreto de firma fijo para desarrollo local. En un sprint
// futuro (con despliegue real) debe venir de una variable de entorno.
const secretKey =
  process.env.SESSION_SECRET ?? "dev-only-magneto-profile-manager-secret";
const encodedKey = new TextEncoder().encode(secretKey);

export async function firmarSesion(payload: SesionPayload): Promise<string> {
  return new SignJWT({ ...payload })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${DURACION_SEGUNDOS}s`)
    .sign(encodedKey);
}

export async function verificarSesion(
  token: string | undefined
): Promise<SesionPayload | null> {
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, encodedKey, {
      algorithms: ["HS256"],
    });
    if (typeof payload.uid !== "string" || typeof payload.email !== "string") {
      return null;
    }
    return { uid: payload.uid, email: payload.email };
  } catch {
    return null;
  }
}
