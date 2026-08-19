import Link from "next/link";
import type { Vacante } from "@/types/vacante";

export function VacanteCard({ vacante }: { vacante: Vacante }) {
  return (
    <Link
      href={`/vacantes/${vacante.id}`}
      className="flex flex-col gap-2 rounded-lg border border-card-border bg-background p-5 transition-colors hover:border-primary"
    >
      <h3 className="font-medium text-foreground">{vacante.titulo}</h3>
      <p className="text-sm text-foreground/70">{vacante.empresa}</p>
      <div className="mt-1 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-foreground/5 px-2 py-1 text-foreground">
          {vacante.ubicacion}
        </span>
        <span className="rounded-full bg-foreground/5 px-2 py-1 text-foreground">
          {vacante.modalidad}
        </span>
      </div>
    </Link>
  );
}
