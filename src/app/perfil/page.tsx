import { requireSesion } from "@/lib/session";
import { getPerfil } from "@/lib/perfilStore";
import { CVUploadForm } from "@/components/CVUploadForm";
import type { CampoPerfil } from "@/types/perfil";

export const metadata = { title: "Mi perfil · Gestor de Perfil" };
// El perfil se lee de un archivo local que cambia con cada carga de CV,
// así que esta página no debe quedar cacheada como estática.
export const dynamic = "force-dynamic";

const ETIQUETAS_CAMPO: Record<CampoPerfil, string> = {
  nombre: "Nombre",
  contacto: "Contacto",
  experiencia: "Experiencia",
  educacion: "Educación",
};

function CampoPendiente() {
  return (
    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-700">
      Pendiente
    </span>
  );
}

export default async function PerfilPage() {
  const sesion = await requireSesion();
  const perfil = getPerfil(sesion.uid);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Mi perfil
        </h1>
        <p className="mt-1 text-sm text-foreground/70">
          Sube tu CV en PDF para crear o actualizar tu perfil. Los datos se
          extraen automáticamente; si algún campo no se logra extraer, queda
          marcado como pendiente sin interrumpir el proceso.
        </p>
      </div>

      <CVUploadForm />

      {!perfil ? (
        <p className="text-sm text-foreground/60">
          Todavía no has cargado un CV.
        </p>
      ) : (
        <div className="rounded-lg border border-card-border p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-foreground">Datos extraídos</h2>
            <span className="text-xs text-foreground/50">
              {perfil.cvNombreArchivo}
            </span>
          </div>

          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="flex items-center gap-2 text-xs uppercase tracking-wide text-foreground/50">
                {ETIQUETAS_CAMPO.nombre}
                {perfil.camposPendientes.includes("nombre") && (
                  <CampoPendiente />
                )}
              </dt>
              <dd className="mt-1 text-foreground">{perfil.nombre ?? "—"}</dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 text-xs uppercase tracking-wide text-foreground/50">
                {ETIQUETAS_CAMPO.contacto}
                {perfil.camposPendientes.includes("contacto") && (
                  <CampoPendiente />
                )}
              </dt>
              <dd className="mt-1 text-foreground">{perfil.contacto ?? "—"}</dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 text-xs uppercase tracking-wide text-foreground/50">
                {ETIQUETAS_CAMPO.experiencia}
                {perfil.camposPendientes.includes("experiencia") && (
                  <CampoPendiente />
                )}
              </dt>
              <dd className="mt-1 text-foreground">
                {perfil.experiencia ? (
                  <ul className="list-inside list-disc space-y-1">
                    {perfil.experiencia.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 text-xs uppercase tracking-wide text-foreground/50">
                {ETIQUETAS_CAMPO.educacion}
                {perfil.camposPendientes.includes("educacion") && (
                  <CampoPendiente />
                )}
              </dt>
              <dd className="mt-1 text-foreground">
                {perfil.educacion ? (
                  <ul className="list-inside list-disc space-y-1">
                    {perfil.educacion.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </dd>
            </div>
          </dl>

          <div className="mt-4">
            <h3 className="text-xs uppercase tracking-wide text-foreground/50">
              Habilidades detectadas
            </h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {perfil.habilidades.map((h) => (
                <span
                  key={h}
                  className="rounded-full bg-foreground/5 px-2 py-1 text-xs text-foreground"
                >
                  {h}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
