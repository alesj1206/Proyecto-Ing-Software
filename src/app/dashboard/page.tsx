import Link from "next/link";
import { requireSesion } from "@/lib/session";
import { getPerfil } from "@/lib/perfilStore";
import { getVacantes } from "@/lib/vacantes";
import { computeMatchesDeHoy } from "@/lib/matching";
import { VacanteCard } from "@/components/VacanteCard";
import { MatchesList } from "@/components/MatchesList";

export const metadata = { title: "Panel principal · Gestor de Perfil" };
// El perfil (y por lo tanto el ranking) cambia con cada carga de CV, así
// que esta página no debe quedar cacheada como estática.
export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const sesion = await requireSesion();
  const perfil = getPerfil(sesion.uid);
  const vacantes = getVacantes();
  const matches = perfil ? computeMatchesDeHoy(perfil, vacantes) : [];

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Matches de hoy
          </h1>
          {perfil && (
            <Link href="/perfil" className="text-sm text-primary hover:underline">
              Actualizar mi CV
            </Link>
          )}
        </div>

        {!perfil ? (
          <div className="rounded-lg border border-card-border bg-primary/5 p-5">
            <p className="text-sm text-foreground/80">
              Carga tu CV para ver tus primeros matches.
            </p>
            <Link
              href="/onboarding"
              className="mt-3 inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              Cargar CV
            </Link>
          </div>
        ) : (
          <MatchesList matches={matches} />
        )}
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          Vacantes disponibles hoy
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {vacantes.map((v) => (
            <VacanteCard key={v.id} vacante={v} />
          ))}
        </div>
      </section>
    </div>
  );
}
