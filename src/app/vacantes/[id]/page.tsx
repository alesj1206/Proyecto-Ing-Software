import Link from "next/link";
import { notFound } from "next/navigation";
import { formatSalario, getVacantePorId } from "@/lib/vacantes";

export default async function VacanteDetallePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const vacante = getVacantePorId(id);

  if (!vacante) notFound();

  return (
    <div className="flex flex-col gap-6">
      <Link href="/dashboard" className="text-sm text-foreground/70 hover:underline">
        ← Volver al dashboard
      </Link>

      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          {vacante.titulo}
        </h1>
        <p className="mt-1 text-foreground/70">{vacante.empresa}</p>
      </div>

      <dl className="grid gap-4 rounded-lg border border-card-border p-5 sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-foreground/50">
            Ubicación
          </dt>
          <dd className="mt-1 text-foreground">{vacante.ubicacion}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-foreground/50">
            Modalidad
          </dt>
          <dd className="mt-1 text-foreground">{vacante.modalidad}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-foreground/50">
            Salario
          </dt>
          <dd className="mt-1 text-foreground">{formatSalario(vacante)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-foreground/50">
            Publicada
          </dt>
          <dd className="mt-1 text-foreground">{vacante.fechaPublicacion}</dd>
        </div>
      </dl>

      <div>
        <h2 className="text-sm font-medium text-foreground">Requisitos</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {vacante.requisitos.map((r) => (
            <span
              key={r}
              className="rounded-full bg-foreground/5 px-2 py-1 text-xs text-foreground"
            >
              {r}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-sm font-medium text-foreground">Descripción</h2>
        <p className="mt-2 text-sm text-foreground/80">{vacante.descripcion}</p>
      </div>
    </div>
  );
}
