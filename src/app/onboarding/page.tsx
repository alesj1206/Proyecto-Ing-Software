import Link from "next/link";
import { requireSesion } from "@/lib/session";
import { CVUploadForm } from "@/components/CVUploadForm";

export const metadata = { title: "Bienvenido · Gestor de Perfil" };

export default async function OnboardingPage() {
  await requireSesion();

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-6 py-8 text-center">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Carga tu CV para empezar
        </h1>
        <p className="mt-2 text-sm text-foreground/70">
          Con tu CV creamos tu perfil y calculamos tus primeros matches.
        </p>
      </div>

      <div className="w-full max-w-sm text-left">
        <CVUploadForm redirectTo="/dashboard" />
      </div>

      <Link
        href="/dashboard"
        className="text-sm text-foreground/60 hover:underline"
      >
        Saltar por ahora
      </Link>
    </div>
  );
}
