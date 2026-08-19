"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();
  const [cargando, setCargando] = useState(false);

  async function handleClick() {
    setCargando(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      router.push("/login");
      router.refresh();
    } finally {
      setCargando(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={cargando}
      className="rounded-md border border-nav-foreground/30 px-3 py-1.5 text-sm text-nav-foreground/90 transition-colors hover:border-nav-foreground hover:text-nav-foreground disabled:opacity-50"
    >
      Cerrar sesión
    </button>
  );
}
