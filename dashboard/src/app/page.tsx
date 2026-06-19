"use client";

/**
 * Home — dispatcher por variante (HRO / CRM / Rugol).
 *
 * Antes hacía `redirect("/projects")` ciego. Ahora lee `/api/health` y enruta:
 *   - variant "hro"  → renderiza <HroCockpit/> (la "sala de reclutamiento").
 *   - variant "crm"  → /pipeline (tablero de prospectos).
 *   - resto / rugol  → /projects (bienvenido genérico, ahí sí aplica).
 *
 * Como `redirect()` no se puede invocar tras hooks de forma trivial, usamos
 * `router.replace()` dentro de un efecto. Mientras /api/health carga (o si
 * falla) mostramos un spinner centrado y, ante error, caemos a /projects para
 * no dejar al usuario en una pantalla en blanco.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api";
import { HroCockpit } from "@/components/hro/cockpit";

export default function Home() {
  const router = useRouter();
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const variant = health.data?.variant;

  useEffect(() => {
    // Solo redirigimos para CRM / Rugol; HRO se queda renderizando el cockpit.
    if (variant === "crm") {
      router.replace("/pipeline");
    } else if (health.isSuccess && variant !== "hro") {
      // rugol (o variante desconocida) → bienvenido genérico.
      router.replace("/projects");
    } else if (health.isError) {
      // Si /api/health falla, no dejamos la pantalla colgada: vamos a /projects.
      router.replace("/projects");
    }
  }, [variant, health.isSuccess, health.isError, router]);

  if (variant === "hro") {
    return <HroCockpit />;
  }

  // Cargando salud, o a punto de redirigir: spinner centrado.
  return (
    <div className="min-h-screen grid place-items-center">
      <div
        className="w-8 h-8 rounded-full border-2 border-[--color-border-strong] border-t-[--color-accent-strong] animate-spin"
        role="status"
        aria-label="Cargando"
      />
    </div>
  );
}
