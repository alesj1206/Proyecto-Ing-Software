import "server-only";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import type { Usuario } from "@/types/user";

// Sprint 1: sin base de datos todavía. Los usuarios (single-tenant, modo
// demo) se persisten en un archivo local dentro de `.data/`, ignorado por
// git. En un sprint futuro esto se reemplaza por una base de datos real.
const STORE_DIR = path.join(process.cwd(), ".data");
const STORE_PATH = path.join(STORE_DIR, "usuarios.json");

function leerUsuarios(): Usuario[] {
  try {
    return JSON.parse(fs.readFileSync(STORE_PATH, "utf-8")) as Usuario[];
  } catch {
    return [];
  }
}

function guardarUsuarios(usuarios: Usuario[]): void {
  fs.mkdirSync(STORE_DIR, { recursive: true });
  fs.writeFileSync(STORE_PATH, JSON.stringify(usuarios, null, 2), "utf-8");
}

function hashPassword(password: string, salt: string): string {
  return crypto.scryptSync(password, salt, 64).toString("hex");
}

export function buscarUsuarioPorEmail(email: string): Usuario | undefined {
  const emailNormalizado = email.trim().toLowerCase();
  return leerUsuarios().find((u) => u.email === emailNormalizado);
}

export class EmailEnUsoError extends Error {}

export function crearUsuario(email: string, password: string): Usuario {
  const emailNormalizado = email.trim().toLowerCase();
  const usuarios = leerUsuarios();

  if (usuarios.some((u) => u.email === emailNormalizado)) {
    throw new EmailEnUsoError("Ya existe una cuenta con ese correo electrónico.");
  }

  const salt = crypto.randomBytes(16).toString("hex");
  const usuario: Usuario = {
    id: crypto.randomUUID(),
    email: emailNormalizado,
    passwordHash: hashPassword(password, salt),
    salt,
    creadoEn: new Date().toISOString(),
  };

  usuarios.push(usuario);
  guardarUsuarios(usuarios);
  return usuario;
}

export function verificarPassword(usuario: Usuario, password: string): boolean {
  const intento = Buffer.from(hashPassword(password, usuario.salt));
  const real = Buffer.from(usuario.passwordHash);
  return intento.length === real.length && crypto.timingSafeEqual(intento, real);
}
