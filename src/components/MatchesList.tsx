import Link from "next/link";
import type { MatchVacante } from "@/lib/matching";

export function MatchesList({ matches }: { matches: MatchVacante[] }) {
  if (matches.length === 0) {
    return (
      <p className="text-sm text-foreground/60">
        Todavía no hay coincidencias con tu perfil actual.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {matches.map(({ vacante, score, coincidencias }, i) => (
        <li key={vacante.id}>
          <Link
            href={`/vacantes/${vacante.id}`}
            className="flex items-center justify-between gap-4 rounded-lg border border-card-border bg-background p-4 transition-colors hover:border-primary"
          >
            <div>
              <p className="text-xs text-foreground/50">#{i + 1}</p>
              <h3 className="font-medium text-foreground">{vacante.titulo}</h3>
              <p className="text-sm text-foreground/70">
                {vacante.empresa} · {vacante.ubicacion}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {coincidencias.map((c) => (
                  <span
                    key={c}
                    className="rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground"
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
            <span className="shrink-0 text-lg font-semibold text-foreground">
              {Math.round(score * 100)}%
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
