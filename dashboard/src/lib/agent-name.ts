/**
 * Cómo se llama un agente: una sola fuente de verdad para el dashboard.
 *
 * El backend exige `^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$` (core/api/agents.py).
 * El formulario tenía el mismo criterio como `pattern` del input y NO
 * funcionaba: los navegadores compilan el `pattern` con el flag `v`, y bajo
 * `v` un guion literal suelto dentro de una clase de caracteres es un error de
 * sintaxis. Cuando el pattern no compila, el navegador lo ignora en silencio —
 * `validity.patternMismatch` queda en false para siempre—. Resultado medido:
 * "Analista BI" pasaba la validación del navegador, viajaba al servidor y
 * volvía como 400 en inglés. Trece intentos seguidos en el log.
 *
 * Por eso el guion va escapado, y hay test que compila este pattern con `v`.
 */
export const AGENT_NAME_PATTERN = "[a-z0-9][a-z0-9\\-]+[a-z0-9]";
export const AGENT_NAME_MIN = 3;
export const AGENT_NAME_MAX = 64;

/**
 * Convierte lo que una persona escribe en el nombre que el backend acepta.
 *
 * "Analista BI" → "analista-bi" · "Reporte Philips W14" → "reporte-philips-w14"
 *
 * Nadie debería tener que aprender las reglas de un slug para crear un agente:
 * el formulario muestra el resultado mientras escribís.
 */
export function slugifyAgentName(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // á → a, ñ → n
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, AGENT_NAME_MAX)
    .replace(/-+$/g, ""); // el corte no puede dejar un guion final
}

/** El motivo por el que un nombre no sirve, o null si sirve. */
export function agentNameProblem(slug: string): "short" | "empty" | null {
  if (!slug) return "empty";
  if (slug.length < AGENT_NAME_MIN) return "short";
  return null;
}
