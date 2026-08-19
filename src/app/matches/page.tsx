import { redirect } from "next/navigation";

// "Matches de hoy" (HU-06) ahora vive dentro de /dashboard, junto al
// listado general de vacantes (HU-04), en la misma vista.
export default function MatchesPage() {
  redirect("/dashboard");
}
