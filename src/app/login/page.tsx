import { AuthForm } from "@/components/AuthForm";

export const metadata = { title: "Ingresar · Gestor de Perfil" };

export default function LoginPage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 py-12">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Gestor de Perfil
        </h1>
        <p className="mt-1 text-sm text-foreground/70">
          Crea tu cuenta o inicia sesión para ver tus vacantes y tus matches.
        </p>
      </div>
      <AuthForm />
    </div>
  );
}
