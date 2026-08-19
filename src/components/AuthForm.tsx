"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Modo = "login" | "registro";

export function AuthForm() {
  const router = useRouter();
  const [modo, setModo] = useState<Modo>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  function cambiarModo(siguiente: Modo) {
    setModo(siguiente);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setCargando(true);

    try {
      const endpoint = modo === "login" ? "/api/auth/login" : "/api/auth/register";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.error ?? "Ocurrió un error. Intenta de nuevo.");
        return;
      }

      // HU-13: justo después del registro va a onboarding (HU-01); al
      // iniciar sesión de nuevo, el dashboard ya maneja con gracia el caso
      // de perfil sin CV.
      router.push(modo === "registro" ? "/onboarding" : "/dashboard");
      router.refresh();
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-col gap-6">
      <div className="flex rounded-md border border-card-border p-1">
        <button
          type="button"
          onClick={() => cambiarModo("login")}
          className={`flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
            modo === "login"
              ? "bg-primary text-primary-foreground"
              : "text-foreground/70"
          }`}
        >
          Iniciar sesión
        </button>
        <button
          type="button"
          onClick={() => cambiarModo("registro")}
          className={`flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
            modo === "registro"
              ? "bg-primary text-primary-foreground"
              : "text-foreground/70"
          }`}
        >
          Crear cuenta
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-foreground">
          Correo electrónico
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-md border border-card-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-foreground">
          Contraseña
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-md border border-card-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={cargando}
          className="mt-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {cargando
            ? "Procesando…"
            : modo === "login"
              ? "Iniciar sesión"
              : "Crear cuenta"}
        </button>
      </form>
    </div>
  );
}
