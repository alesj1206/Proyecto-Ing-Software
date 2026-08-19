"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

export function CVUploadForm({ redirectTo }: { redirectTo?: string } = {}) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    const archivo = fileInputRef.current?.files?.[0];
    if (!archivo) {
      setError("Selecciona un archivo PDF.");
      return;
    }
    if (archivo.type !== "application/pdf" && !archivo.name.toLowerCase().endsWith(".pdf")) {
      setError("El archivo debe ser un PDF.");
      return;
    }

    const formData = new FormData();
    formData.append("cv", archivo);

    setCargando(true);
    try {
      const res = await fetch("/api/cv", { method: "POST", body: formData });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.error ?? "No se pudo procesar el CV.");
        return;
      }
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (redirectTo) {
        router.push(redirectTo);
      }
      router.refresh();
    } finally {
      setCargando(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-lg border border-card-border p-5"
    >
      <label htmlFor="cv" className="text-sm font-medium text-foreground">
        Sube tu hoja de vida (PDF)
      </label>
      <input
        ref={fileInputRef}
        id="cv"
        name="cv"
        type="file"
        accept="application/pdf,.pdf"
        className="text-sm text-foreground"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={cargando}
        className="w-fit rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {cargando ? "Procesando…" : "Cargar CV"}
      </button>
    </form>
  );
}
