import { redirect } from "next/navigation";

// El listado general de vacantes (HU-04) ahora vive dentro de /dashboard,
// junto a "Matches de hoy" (HU-06), en la misma vista.
export default function VacantesPage() {
  redirect("/dashboard");
}
