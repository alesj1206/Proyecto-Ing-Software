import Link from "next/link";
import { getSesion } from "@/lib/session";
import { LogoutButton } from "@/components/LogoutButton";

export async function NavBar() {
  const sesion = await getSesion();

  return (
    <header className="bg-nav-background text-nav-foreground">
      <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link
          href={sesion ? "/dashboard" : "/login"}
          className="font-semibold tracking-tight"
        >
          Gestor de Perfil
        </Link>
        {sesion && (
          <div className="flex items-center gap-6 text-sm">
            <Link
              href="/dashboard"
              className="text-nav-foreground/80 transition-colors hover:text-nav-foreground"
            >
              Panel principal
            </Link>
            <Link
              href="/perfil"
              className="text-nav-foreground/80 transition-colors hover:text-nav-foreground"
            >
              Mi perfil
            </Link>
            <LogoutButton />
          </div>
        )}
      </nav>
    </header>
  );
}
