import { redirect } from "next/navigation";
import { getSesion } from "@/lib/session";

// El proxy ya redirige "/" según la sesión; esta página es un respaldo
// server-side por si algún día el matcher del proxy cambia.
export default async function Home() {
  const sesion = await getSesion();
  redirect(sesion ? "/dashboard" : "/login");
}
